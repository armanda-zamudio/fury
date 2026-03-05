# from __future__ import annotations
import os
import json
import requests
import time
import boto3
import logging
import typing
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fury.adapter.config import StaticProxy,configure_logging_for_lambda, PLAYWRIGHT_CHROMIUM_ARGS
from proxy.adapters import RandomMarsProxyUrlFactory, ProxyIPInfo, IPInfo

##### FOR TESTING ONLY #####
import random
proxy_url_factory:RandomMarsProxyUrlFactory|StaticProxy = None


if typing.TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient       

_country = "ir"    
est_time_zone = ZoneInfo("America/New_York")
def load_vars() -> dict:
    env = os.environ
    kwargs = dict(
        export_bucket=env.get("FURY_EXPORT_BUCKET", ""),   
        export_prefix=env.get("FURY_EXPORT_PREFIX", ""),           
        no_proxy=bool(env.get("FURY_NO_PROXY", "")),                
        static_proxy=bool(env.get("FURY_STATIC_PROXY", "")),        
        accept_language=env.get("BROWSER_ACCEPT_LANGUAGE", ""),        
        sec_ch_ua=env.get("BROWSER_SEC_CH_UA", ""),        
        sec_ch_ua_platform=env.get("BROWSER_SEC_CH_UA_PLATFORM", ""),        
        user_agent=env.get("BROWSER_USER_AGENT", ""),    
        
    )
    return kwargs


def load_string_parameter(name: str, client: SSMClient, **kwargs) -> str:
    parameter_response = client.get_parameter(Name=name, **kwargs)
    parameter = parameter_response["Parameter"]
    return parameter["Value"]

def load_string_list_parameter(name: str, client: SSMClient, **kwargs) -> list[str]:
    return load_string_parameter(name, client, **kwargs).split(",")


def build_random_mars_proxy_generator(
    session: boto3.Session | None = None, cities: list[str] | None = None
):
    session = session or boto3.Session()
    ssm_client = session.client("ssm")
    username, password = load_string_parameter(
        "/test/proxy-auth", ssm_client, WithDecryption=True
    ).split(":", 1)

    
    
    return RandomMarsProxyUrlFactory(
        username=username,
        password=password,
        locations=[(_country, [])],
        persist=False
        # locations=("cn", proxy_cities),
    )

def configure_proxy(env:dict,session:boto3.Session):
    global proxy_url_factory
    if env.get("no_proxy"):
        logging.warning("NO PROXY was set by environment variable.")
        proxy_url_factory = None
    elif env.get("static_proxy"):
        logging.warning("A static proxy was given.")
        proxy_url_factory = StaticProxy(url=env["static_proxy"])
    else:
        proxy_url_factory= build_random_mars_proxy_generator(session)  


def ping_success():    
    if proxy_url_factory is not None:
        logging.info("Invoking Using Proxy")    
        proxy_url = proxy_url_factory() 
        for ip_info in IPInfo:
            info = ProxyIPInfo(ip_info)       
            try:    
                result = info.invoke_ip_info(proxy_url)
                logging.info(f"Result: {result}")
                return result                
            except: 
                logging.warning("Issues with proxy")    
            time.sleep(5)
    return None

def check_for_server_error(url, proxy):

    result = { "success": False,
               "url": url,
               "proxy": "",
               "responseCode":500}

    proxies = {
        "http": "",
        "https": ""
    }
    if proxy:
        logging.info(f"Testing {url} with proxy")
        proxies = {
            "http": proxy,
            "https": proxy
        }        
        if "mars" in proxy:
            result["proxy"] = "mars"
    else:
        logging.info("Testing {url} on AWS")   
    try:
        response = requests.get(url, proxies=proxies, timeout=10) # 10-second timeout for the request
        
        if response.status_code == 500:
            logging.info(f"❌ Website is down: Received a 500 Internal Server Error.")
            # Optional: print response text to see if the server provided details
            # print(f"Response content: {response.text}") 
            result["success"] = False            
        elif 500 <= response.status_code < 600:
            logging.info(f"❌ Website is down: Received a {response.status_code} (5xx) Server Error.")
            result["success"] = False
        else:
            logging.info(f"✅ Website is up: Received status code {response.status_code}.")
            result["success"] = True
        result["responseCode"] = response.status_code

    except requests.exceptions.ConnectionError:
        logging.info("❌ Connection Error: Could not connect to the server (DNS issue, firewall, etc.).")
        result["success"] = False # Consider a connection error as the site being "down"
    except requests.exceptions.Timeout:
        logging.info("❌ Timeout Error: The server did not respond within the time limit.")
        result["success"] = False
    except requests.exceptions.RequestException as e:
        logging.info(f"❌ An unexpected error occurred: {e}")
        result["success"] = False
    return result

def handler(event, context):       
    logging.info("Starting application")
    
    
    # logging.debug(event)
    env = load_vars()
    session = boto3.Session()
    s3 = boto3.resource("s3") 
    bucket = env["export_bucket"]
    prefix = env["export_prefix"]
    ssm_client = session.client("ssm")
    configure_proxy(env=env,session=session)
    web_sites = load_string_list_parameter(f"/test/{_country}-website", ssm_client)
    logging.info(f"Testing the following Web sites{web_sites}")

    # Using amazon
    results = []
    for web_site in web_sites:
        result = check_for_server_error(web_site, None)
        time.sleep(5)
        # logging.info(f"Results: {result}")
        results.append(result)
    
    proxy_url = proxy_url_factory()
    count = 0
    all_sucess = False
    bad_results = []
    while count < 5 and all_sucess == False:
        if count == 0:
            for web_site in web_sites:                     
                result = check_for_server_error(web_site, proxy_url)
                time.sleep(5)
                if result["success"] == True:
                    results.append(result)
                else:
                    bad_results.append(result)
        else:
            if bad_results:
                tmp_bad_results = bad_results
                bad_results = []
                for bad_result in tmp_bad_results:
                    result = check_for_server_error(bad_result["url"], proxy_url)
                    time.sleep(5)
                    if result["success"] == True:
                        results.append(result)
                    else:
                        bad_results.append(result)                                
        if bad_results:
            count += 1
            proxy_url = proxy_url_factory()
        else:
            all_sucess = True
    
    if bad_results:
        results.extend(bad_results)
    
        

        



        
        # bad_results = 
            
                



            
            # while count < 5 and result["success"] == False:
            #     count += 1
            #     time.sleep(5)
            #     proxy_url = proxy_url_factory()
            #     result = check_for_server_error(web_site, proxy_url)
            # results.append(result)
    logging.info("-"*80)
    logging.info(results)
    logging.info("-"*80)
    if bucket:
        if results:            
            current_time_est = datetime.now(est_time_zone)
            today = current_time_est.strftime("%Y/%m/%d/")
            prefix += f"{today}"    
            object_key = f"{prefix}endpoints/{_country}/results_{current_time_est.strftime("%H_%M_%S")}.json"
            s3.Object(bucket, object_key).put(Body=json.dumps(results))

        
        



            
        # logging.info(f"Results: {result}")




    

    
    



    # logging.info("Invoking Using Amazon")    
    # for ip_info in IPInfo:
    #     info = ProxyIPInfo(ip_info) 
    #     result = info.invoke_ip_info()
    #     logging.info(f"Result: {result}")
    #     time.sleep(5)

    
    # if type(proxy_url_factory) is RandomMarsProxyUrlFactory:
    #     proxy_type = "mars"
    # elif type(proxy_url_factory) is StaticProxy:
    #     proxy_type = "cyberghost"
    # else:
    #     proxy_type = ""

    # for i in range(5):
    #     result = ping_success()
    #     if result:
    #         json_results = [{
    #             "country": _country,
    #             "sucessfulPing": True,
    #             "result": result,
    #             "proxyType": proxy_type
    #         }]
    #         break
    
    
    # if not json_results:
    #     json_results = [{
    #         "country": _country,
    #         "sucessfulPing": False,
    #         "result": "",
    #         "proxyType": proxy_type

    #     }]
    # if bucket:
    #     if json_results:            
    #         current_time_est = datetime.now(est_time_zone)
    #         today = current_time_est.strftime("%Y/%m/%d/")
    #         prefix += f"{today}"    
    #         object_key = f"{prefix}ping/{_country}/results_{current_time_est.strftime("%H_%M_%S")}.json"
    #         s3.Object(bucket, object_key).put(Body=json.dumps(json_results))
            
    

    

    

    
    





    
    
    


    

    
    



if __name__ != "__main__":  
    configure_logging_for_lambda() 