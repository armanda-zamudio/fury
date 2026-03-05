# from __future__ import annotations
import os
import json
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

def handler(event, context):       
    logging.info("Starting application")
    logging.debug(event)
    env = load_vars()
    session = boto3.Session()
    s3 = boto3.resource("s3") 
    records = []
    batch_item_failures = []
    browser_kwargs = {"args": PLAYWRIGHT_CHROMIUM_ARGS}
    browser_kwargs["user_agent"] = env["user_agent"]
    browser_kwargs["extra_http_headers"] = {
        "accept-language": env["accept_language"],
        "sec-ch-ua":  env["sec_ch_ua"],
        "sec-ch-ua-platform": env["sec_ch_ua_platform"],
        "user-agent": env["user_agent"]
        }    
    bucket = env["export_bucket"]
    prefix = env["export_prefix"]

    
    logging.info(env)
    logging.info(browser_kwargs)

    logging.info("Invoking Amazon IP INFO")

    

    json_results = {}
    configure_proxy(env=env,session=session)



    logging.info("Invoking Using Amazon")    
    for ip_info in IPInfo:
        info = ProxyIPInfo(ip_info) 
        result = info.invoke_ip_info()
        logging.info(f"Result: {result}")
        time.sleep(5)

    
    if type(proxy_url_factory) is RandomMarsProxyUrlFactory:
        proxy_type = "mars"
    elif type(proxy_url_factory) is StaticProxy:
        proxy_type = "cyberghost"
    else:
        proxy_type = ""

    for i in range(5):
        result = ping_success()
        if result:
            json_results = [{
                "country": _country,
                "sucessfulPing": True,
                "result": result,
                "proxyType": proxy_type
            }]
            break
    
    
    if not json_results:
        json_results = [{
            "country": _country,
            "sucessfulPing": False,
            "result": "",
            "proxyType": proxy_type

        }]
    if bucket:
        if json_results:            
            current_time_est = datetime.now(est_time_zone)
            today = current_time_est.strftime("%Y/%m/%d/")
            prefix += f"{today}"    
            object_key = f"{prefix}ping/{_country}/results_{current_time_est.strftime("%H_%M_%S")}.json"
            s3.Object(bucket, object_key).put(Body=json.dumps(json_results))
            
    

    

    

    
    





    
    
    


    

    
    



if __name__ != "__main__":  
    configure_logging_for_lambda() 