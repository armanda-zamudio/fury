import subprocess
import asyncio
import logging
import queue
import random
import threading
import typing
import json
import uuid
import os
import io
from bs4 import BeautifulSoup
from urllib.parse import urlsplit, urlparse
# from pdf2image import convert_from_path
from PIL import Image

import aiolimiter
from playwright.async_api import (
    Browser,
    Page,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    Request
)

from crimsonking.application.workflow.model import (
    DownloadError, 
    WorkflowData, 
    Exception403,
    Exception502,
    WebWarmingError
    )

from crimsonking_downloader.application.workflow.ports import Downloader, DownloaderWarmingFactory
from crimsonking_downloader.domain.model import PDFBytes, ScreenshotBytes


from ih.download.domain.model import HttpResponse
from ih.download.domain.ports import ProxyUrlFactory

type DownloadResult = typing.Tuple[
    HttpResponse, ScreenshotBytes | None, PDFBytes | None
]
type DownloadResponse = DownloadResult | Exception
type DownloadRequest = typing.Tuple[str,str, str, list, queue.Queue] | None


class StopCommand(Exception): ...


class PlaywrightDownloadServer(Downloader):
    def __init__(
        self,
        *,
        max_rate: float = 10.0,
        time_period: float = 1.0,
        max_additional_wait: float = 5.0,
        buffer_wait: float = 5.0,
        browser_kwargs: dict[str, typing.Any] = {},
        browser_context_kwargs: dict[str, typing.Any] = {},
        proxy_url_factory: ProxyUrlFactory | None = None,
        downloader_warming_factory: DownloaderWarmingFactory | None = None,
                
    ):
        self._max_rate = max_rate
        self._time_period = time_period
        self._browser_kwargs = browser_kwargs
        self._browser_context_kwargs = browser_context_kwargs
        self._request_queue = queue.Queue()
        self._thread: threading.Thread = None
        self._log = logging.getLogger().getChild(self.__class__.__qualname__)
        self._log.setLevel(logging.DEBUG)
        self._throttle: aiolimiter.AsyncLimiter = None
        self._next_additional_wait: float = 0
        self._max_additional_wait: float = max_additional_wait
        self._proxy_url_factory = proxy_url_factory
        self._downloader_warming_factory = downloader_warming_factory
        self._downloader_warm:bool = False
        self._buffer_wait:float = buffer_wait

    
    async def _execute_download(self, url: str, uuid:str, url_type:str, years:list, page: Page):
        screenshot_bytes = None
        pdf_bytes = None
        self._log.info("Requesting go-ahead from rate limiter.")
        self._next_additional_wait = random.random() * self._max_additional_wait + self._buffer_wait 
        json_data = []

        # Define the routing handler function for filtering images
        async def block_images(route):
            if route.request.resource_type == "image":
                await route.abort() # Abort the request if it's an image
            else:
                await route.continue_() # Allow other requests to proceed
        await page.route("**/*", block_images)

        async def handle_request_finish(request:Request):
            response = await request.response()
            if response:

                if "text/html" in response.headers.get("content-type", ""):     
                    response_url = response.url                
                    if ("JournalDetail/GetnfAllOutline" in response_url 
                        # or "JournalDetail/GetArticleList" in response_url 
                        or "JournalDetail/GetJournalYearList" in response_url
                        ): 
                        self._log.debug(f"Adding HTML into JSON")   
                        

                        html_element = None
                        try:
                            html_element = await response.text()
                        except Exception:
                             self._log.warning(f"issues with response for request {request.url}")   

                        if not html_element:
                            try:
                                html_element = await response.body()
                            except Exception:
                                self._log.warning(f"issues with response for request {request.url}")                              

                        if html_element:
                            json_element = {
                                "url": request.url,
                                "api_url": response_url,
                                "page_content": html_element
                            }   
                            # self.log_json(json_element)
                            # self._log.info(f"GOTO {json_element}.")

                            json_data.append(json_element)    
                            
                        

                # JournalDetail/GetArticleList
                
                if "application/json" in response.headers.get("content-type", ""):
                    # Adjust condition to match the specific URL or pattern of the JSON data you want
                    response_url = response.url 

                    ############## ARTICLE HANDLER ##############
                    if ("kcms/detail/info" in response_url 
                        or "kcms/detail/coreFileRecommend" in response_url
                        or "kcms/detail/similarLiterature" in response_url
                        or "kcms/cite/references" in response_url) :
                        self._log.debug(f"Adding ARTICLE JSON")                        
                        #    json_element = await asyncio.ensure_future(response.json())
                        json_element = await response.json()
                        # self._log.info(f"GOTO {json_element}.")
                        self.log_json(json_element)
                        if "success" in json_element:
                            if json_element["success"]:
                                 json_data.append(json_element)  
                            else:
                                logging.warning(f"Error with call: {response_url}")     
                        else:
                            json_data.append(json_element)                    
                    
                    ############## AUTHOR HANDLER ##############
                    if "kcms/author" in response_url:
                        self._log.debug(f"Adding AUTHOR JSON")                        
                        #    json_element = await asyncio.ensure_future(response.json())
                        json_element = await response.json()
                        # self._log.info(f"GOTO {json_element}.")
                        self.log_json(json_element)
                        if "success" in json_element:
                            if json_element["success"]:
                                 json_data.append(json_element)  
                            else:
                                logging.warning(f"Error with call: {response_url}")                                      
                        else:
                            json_data.append(json_element)                                  

                    ############## AUTHOR HANDLER ##############
                    if "kcms/org" in response_url:
                        self._log.debug(f"Adding ORGANIZATION JSON")                        
                        #    json_element = await asyncio.ensure_future(response.json())
                        json_element = await response.json()
                        # self._log.info(f"GOTO {json_element}.")
                        self.log_json(json_element)
                        if "success" in json_element:
                            if json_element["success"]:
                                 json_data.append(json_element)  
                            else:
                                logging.warning(f"Error with call: {response_url}")                                      
                        else:
                            json_data.append(json_element)  

                    ############## FUNDING HANDLER ##############
                    if "kcms/fund" in response_url:
                        self._log.debug(f"Adding FUNDING JSON")                        
                        #    json_element = await asyncio.ensure_future(response.json())
                        json_element = await response.json()
                        # self._log.info(f"GOTO {json_element}.")
                        self.log_json(json_element)
                        if "success" in json_element:
                            if json_element["success"]:
                                 json_data.append(json_element)  
                            else:
                                logging.warning(f"Error with call: {response_url}")                                      
                        else:
                            json_data.append(json_element)                         
                        # for item in json_element["getalbum_resp"]["article_list"]:
                        #     try:
                        #         json_data.append(item["url"])
                        #     except:
                        #         self._log.debug(f"could not add url: {item}")
                                
        async with self._throttle:
            
            try:
                self._log.info(f"GOTO {url} --- UUID {uuid}")
                
                try:                    
                    page.on("requestfinished", handle_request_finish)
                    response_status_code = 200
                    response_status_text = "OK"
                    response_url = ""
                    headers = []
                    


                    for i in range(3):

                        try: 

                            if i > 1:
                                await asyncio.sleep(self._next_additional_wait if self._next_additional_wait>0 else 5)                            
                            response = await page.goto(url.replace(";",""), timeout=300 * 1000, wait_until= 'domcontentloaded')                            
                            if json_data:
                                if response:
                                    response_status_code = response.status
                                    response_status_text = response.status_text
                                    response_url         = response.url
                                    headers = await response.headers_array()
                                break
                        except Exception:
                            self._log.warning(f"Error going to {url.replace(";","")}")
                    if json_data is None or not json_data:
                        self._log.info(f"Navigation to {url} failed to return a response (interrupted or similar issue).")
                        raise Exception(f"Navigation to {url} failed to return a response (interrupted or similar issue).")
                                    
                    await asyncio.sleep(self._next_additional_wait)
                    if url_type == "journal":
                        logging.info("getting additional journals")
                        await self._get_articles_by_journal_api(json_data,years,page)
                    await asyncio.sleep(self._next_additional_wait)
                    json_data.append({"uuid":uuid, "url":url})
                    self._log.info(
                        f"{response_status_code} => Received response for {response_url}"
                    )  
                    http_response = HttpResponse(
                        status_code=response_status_code,
                        status_message=response_status_text,
                        content=json.dumps(json_data),
                        headers=headers,
                    )                    

                except PlaywrightTimeoutError as e:
                    self._log.warning(e)
                    if self._next_additional_wait > 0.0:
                        self._log.info(
                            f"Adding additional wait of {self._next_additional_wait}"
                        )
                        await asyncio.sleep(self._next_additional_wait)     
                    if json_data and response:
                        http_response = HttpResponse(
                            status_code=response_status_code,
                            status_message=response_status_text,
                            content=json.dumps(json_data),
                            headers=headers,
                        )      
                    else:                             
                        raise
                return http_response, screenshot_bytes, pdf_bytes
            except PlaywrightTimeoutError:
                self._log.warning(f"Timed out requesting {url}.")
                raise
            except Exception403:
                raise
            except Exception502:
                raise      
            except WebWarmingError:
                raise      
            except Exception as exc:
                self._log.warning(f"Unexpected error navigating to {url}", exc_info=exc)
                return exc
            
    async def _get_articles_by_journal_api(self, json_data:list, years:list, page:Page):
        if not years:
            return
        
        urls = []
        for year in years:        
            for data in json_data:
                if "api_url" in data:
                    if "GetJournalYearList" in data["api_url"]:    
                        soup = BeautifulSoup(data["page_content"], 'html.parser')
                        all_a_tags = soup.find_all('a', attrs={'id': True})
                        issues = []
                        for id_tag in all_a_tags:
                            if year in id_tag["id"]:
                                issues.append(id_tag["id"])
                        
                        parsed_url = urlparse(data["url"])                       

                        for issue in issues:
                            # url = parsed_url.scheme+"://"+parsed_url.netloc+parsed_url.path.replace("GetJournalYearList","GetArticleList")
                            url = parsed_url.scheme+"://"+parsed_url.netloc+parsed_url.path.replace("GetJournalYearList","GetArticleList")
                            url += "?year="+year
                            url += "&issue="+issue.replace(f"yq{year}","")
                            url += f"&{parsed_url.query}"
                            urls.append(url)                        
                        break
        
        
        # self.log_json
        if urls:
            urls.reverse()
            self._log.info(f"invoking additional api calls for the following urls: {urls}")
            for article_list_url in urls:             
                # await asyncio.sleep(random.uniform(5, 10))   
                self._log.info(f"invoking api call {article_list_url}")
                # logging.info(f"invoking additional api calls {urls[0]}")
                
                post_response = await page.request.post(url=article_list_url)

                if post_response:
                    self._log.info(f"received a status {post_response.status} from {article_list_url}")     

                    page_content = await post_response.text()
                    if "<script>window.location.href='//www.cnki.net'</script>" in page_content:
                        raise ValueError(f"Error in page content for posting API. URL: {article_list_url} ")
                    if post_response.status == 200:
                        json_element = {
                                "url": article_list_url,
                                "api_url": post_response.url,
                                "page_content": page_content
                        }
                        self._log.info(f"sucessfully captured {article_list_url}")
                        # self.log_json(json_element)
                        json_data.append(json_element)    
                    else:
                        self._log.info(f"issues capturing {article_list_url}")
                await asyncio.sleep(random.uniform(5, 10))                           

        


    async def _process_request(self, page: Page):
        error: Exception | None = None


        warm_page:Page = page


            

        request: DownloadRequest = typing.cast(
            DownloadRequest, self._request_queue.get()
        )
        

        if request is None:
            self._log.info(
                "Received None in the request queue, which is the shutdown signal."
            )
            raise StopCommand()
        try:
            url, uuid, url_type, years, response_queue = request
        except TypeError:
            self._log.warning("Error unpacking request from queue. Exiting.")
            return
        MAX_RETRIES=2    
        for i in range(MAX_RETRIES):
            try:
                ###################### WARM THE WEBSITE #########################
                if self._downloader_warming_factory:
                    try:
                        # if url_type == "journal":                            
                        #     self._downloader_warm = True
                        #     self._downloader_warming_factory.warm_page = page
                        #     warm_page = page
                        # else:   
                        if self._downloader_warm:
                            self._log.info("Downloader is warm")
                            if self._downloader_warming_factory.warm_page:
                                warm_page = self._downloader_warming_factory.warm_page
                            else:
                                warm_page = await self._downloader_warming_factory(page)                    
                        else:
                            warm_page = await self._downloader_warming_factory(page)      
                            self._downloader_warming_factory.warm_page = warm_page         
                            self._downloader_warm = True
                    except:
                        raise WebWarmingError("Could not warm website")                        
                response = await self._execute_download(url, uuid, url_type, years, warm_page)                  
                self._log.info("Returning response via queue.")
                
                response_queue.put(response)
                return
            except PlaywrightTimeoutError as exc:
                self._log.warning(
                    "Caught TimeoutError from Playwright. Attempting retry (if available)."
                )
                if i == (MAX_RETRIES-1):
                    error = exc
                    break
            except Exception403 as exc:
                error = exc
                self._log.warning(
                    "Caught Exception403. Attempting retry (if available)."
                )
                break

            except Exception502 as exc: 
                error = exc
                self._log.warning("Caught Exception502 attempting download", exc_info=exc)
                break                  
            except WebWarmingError as exc:
                error = exc
                self._log.warning("Caught WebWarmingError attempting download", exc_info=exc)
                break                           
            except Exception as exc:
                error = exc
                self._log.warning("Caught exception attempting download", exc_info=exc)
                break
        
        response_queue.put(error)

    async def _iterate_requests(self, page: Page):
        request_count = random.randint(11, 27)
        self._log.info(f"Will process {request_count} requests")
        for _ in range(request_count):
            await self._process_request(page)

    async def _use_browser_context(self, browser: Browser):       
        async with (
            await browser.new_page() as page,
        ):
            await page.route("**/*", lambda route: route.continue_(
            headers={
                **route.request.headers,  # Preserve existing headers
                'accept-language': 'zh-CN,zh;q=0.9',
                'sec-ch-ua'  : '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                'sec-ch-ua-platform' : "Windows",
            })
            )
            #####################   UNCOMMENT TO VIEW HEADERS  #####################
            # async def print_request_headers(request):
            #     self._log.debug(f"Request URL: {request.url}")
            #     self._log.debug("Headers:")
            #     for name, value in request.headers.items():
            #         self._log.debug(f"  {name}: {value}")
            #     self._log.debug("-" * 20)
            # page.on("request", print_request_headers)   
            #########################################################################
             
            await self._iterate_requests(page)
            self._log.info("Destroying browser_context.")
            
        self._log.info("Setting additional wait for next request to 0.")
        self._next_additional_wait = 0

    async def run_async(self):
        self._throttle = aiolimiter.AsyncLimiter(self._max_rate, self._time_period)
        self._log.info("start run_async")
        self._log.info("Launching browser.")
        self._log.info("Launching browser context.")
        if self._proxy_url_factory:
            proxy = {}
            proxy_url = self._proxy_url_factory()
            url_pieces = urlsplit(proxy_url)
            if url_pieces.username:
                username = url_pieces.username
                password = url_pieces.password
                netloc = url_pieces.netloc.rsplit("@", 1)[1]
                trimmed_url = url_pieces._replace(netloc=netloc).geturl()
                proxy["username"] = username
                proxy["password"] = password
                proxy["server"] = trimmed_url
            else:
                proxy["server"] = proxy_url
            self._browser_kwargs["proxy"] = proxy
            self._browser_kwargs["ignore_https_errors"] = True       
        async with (
            async_playwright() as pw,
            await pw.chromium.launch_persistent_context("/tmp/persistent_context", **self._browser_kwargs) as browser,
        ):
            self._log.info("Browser launched.")
            while True:
                try:                    
                    await self._use_browser_context(browser)
                except StopCommand:
                    self._log.info("Stopping.")
                    return
             
    
    def log_json(self, json_data):
        try:            
            self._log.info(f"JSON: {json_data}.")
        except Exception as e:
            self._log.info("JSON message successfully captured")    


    def _run(self):
        asyncio.run(self.run_async())

    

    def __enter__(self):
        if self._thread:
            raise RuntimeError("Can only enter a PlaywrightDownloadServer once.")
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._request_queue.put(None)
        self._thread.join()
        self._thread = None

    def __call__(self, workflow_data: WorkflowData) -> DownloadResult:
        if not self._thread:
            raise RuntimeError(
                "Cannot use this DownloadServer outside of its context (with DownloadServer() ...)"
            )
        response_queue = queue.Queue()
        self._request_queue.put((workflow_data.url,workflow_data.uuid, workflow_data.url_type, workflow_data.years, response_queue))
        try:
            response: DownloadResponse = typing.cast(
                DownloadResponse, response_queue.get(True, 600.0)
            )
        except PlaywrightTimeoutError:
            raise    
        except Exception403:
            raise
        except Exception502:
            raise        
        except WebWarmingError:
            raise
        except queue.Empty:
            message = "Received no response within 600 seconds. Don't know how the server will respond now ..."
            self._log.warning(message)
            raise DownloadError()
        if response is PlaywrightTimeoutError:
            self._log.warning("In PlaywrightTimeoutError exception")
            self._log.warning(response)
            raise PlaywrightTimeoutError() from response
        if isinstance(response, Exception403):
            self._log.warning("In Exception403 exception")
            self._log.warning(response)   
            raise  Exception403() from response    
        if isinstance(response, Exception502):
            self._log.warning("In Exception502 exception")
            self._log.warning(response)   
            raise  Exception502() from response     
        if isinstance(response, WebWarmingError):
            self._log.warning("In WebWarmingError exception")
            self._log.warning(response)   
            raise  WebWarmingError() from response                      
        if response is Exception:
            self._log.warning("In general exception")
            self._log.warning(response)
            raise DownloadError() from response
        
        self._log.info(f"The instance of the response is: {type(response)}")
        workflow_data.http_response = response[0]
        workflow_data.screenshot_bytes = response[1]
        workflow_data.pdf_bytes = response[2]
        ### TODO ###
        # workflow_data.json_bytes = response[3]

     
