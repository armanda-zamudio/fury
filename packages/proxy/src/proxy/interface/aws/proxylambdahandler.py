import os
import json
import time
import logging


from proxy.adapters import(DomainProxyTable,
                           ProxyTable,
                           RandomMarsProxyUrlFactory,
                           MarsProxyUrlFactory,
                           IPInfo,
                           ProxyIPInfo)

# Get the root logger
logger = logging.getLogger()

logger.setLevel(logging.DEBUG)
# try:
#     from proxy.adapters import (IPInfo)
# except Exception as e:
#     logger.info(f"Exception: {e}")

def handler(event, context):
    logger.info("Received event: %s", json.dumps(event, indent=2))

    for record in event["Records"]:
        body = record.get("body")
        message_id = record.get("messageId")
        receipt_handle = record.get("receiptHandle")
        logger.info(f"Processing message {message_id}: {body}")
        queue_url = os.getenv("QUEUE_URL")
        logger.info(f"Queue URL {queue_url}")


def test_handler(event, context):
    logger.info("Received event: %s", json.dumps(event, indent=2))    
    if "country" in event:
        country:str = event["country"]
        logger.info(f"received country element: {country}")
        try:

            ip_info_tmp = [member for member in IPInfo if country.lower() in member.name.lower() ]
            if not ip_info_tmp:
                ip_info = IPInfo.IP_INFO
            else:
                ip_info = ip_info_tmp[0]
            # tmp = []
            logger.info(f"Will use the following IP endpoint: {ip_info}")
        except Exception as e:
            logger.info(f"something went wrong: {e}")
    else:
        ip_info = IPInfo.IP_INFO

    proxy_ip_info = ProxyIPInfo(ip_info)    

    for i in range(5):
        try:
            if "proxy" in event:
                proxy_element:str = event["proxy"]
                if "mars" in proxy_element:
                    # need to generate random proxy
                    logger.info("Generating random proxy URL")
                    mpuf = RandomMarsProxyUrlFactory(username=None,
                                                    password=None,
                                                    persist=False)
                    mpuf.populate_user_pass_from_ssm("/test/proxy-auth")
                    mpuf.populate_location_from_ssm(ssm_location_path="/test/proxy-city-list-cn-test", country_code=country)
                    proxy_element = mpuf()
            else:
                proxy_element = None    
            proxy_ip_info.invoke_ip_info(proxy_element)
            logger.info(f"IP INFO: {proxy_ip_info}")
            break
        except:
            if i == 4:
                raise
            time.sleep(10)
    if not proxy_ip_info.proxy_url:
        proxy_ip_info.proxy_url = "AWS_IP_NO_PROXY"
    ProxyTable.store_connection_by_proxyipinfo(ipinfo=proxy_ip_info,domain="example.com",country_city=None)

def test_purge(event, context):
    with ProxyTable.batch_write() as batch:
        for item in ProxyTable.scan():
            batch.delete(item)

if __name__ != "__main__":  
    NOISY_LOGGERS = ["botocore", "boto3"]    
    for l in NOISY_LOGGERS:
        logging.getLogger(l).setLevel(logging.WARNING)      
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)


