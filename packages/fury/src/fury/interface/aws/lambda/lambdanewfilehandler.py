# from __future__ import annotations
import os
import boto3
import json
import time
import boto3
import logging
import typing
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fury.adapter.config import StaticProxy,configure_logging_for_lambda

s3 = boto3.client("s3")
sns_client = boto3.client("sns")
##### FOR TESTING ONLY #####
import random

def load_vars() -> dict:
    env = os.environ
    kwargs = dict(
        internal_bucket=env.get("FURY_INTERNAL_BUCKET", ""),
        aler_topic=env.get("ALERT_TOPIC", ""),           #ALERT_TOPIC
        
    )
    return kwargs

if typing.TYPE_CHECKING:
    from mypy_boto3_ssm.client import SSMClient       



def get_current_file_content(bucket_name, key_name):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key_name)
        object_content = response["Body"].read().decode("utf-8")
        return object_content
    except s3.exceptions.ClientError as e:
        logging.warning(e)

    return None    

def copy_s3_object(src_bucket, src_key, dst_bucket, dst_key):
    try:
        s3.copy_object(CopySource={"Bucket": src_bucket, "Key": src_key}, 
                       Bucket=dst_bucket,
                       Key=dst_key)
    except Exception as e:
        logging.info(f"Failed to copy object: {e}")


def handler(event, context):       
    logging.info("Starting application")    
    records = event["Records"]
    env = load_vars()
    for record in records:        
        body = record["body"]
        logging.info(body)
        s3_message = json.loads(json.loads(body)["Message"])
        s3_records = s3_message["Records"]
        for s3_record in s3_records:    
            logging.info("s3_record")
            logging.info(s3_record)
            bucket = s3_record["s3"]["bucket"]["name"]
            file_key = s3_record["s3"]["object"]["key"]
            content = get_current_file_content(bucket,file_key)    
            logging.info(content)
            if content:
                json_content = json.loads(content)            
                if "ping" in file_key:
                        ping_result = json_content[0]
                        old_result_path = "ping/"+ping_result["country"]+"/ping_latest_result.json"
                        old_result = get_current_file_content(env["internal_bucket"], old_result_path)
                        if old_result:
                            json_old_result = json.loads(old_result)
                            old_status = json_old_result[0]["sucessfulPing"]
                            new_status = ping_result["sucessfulPing"]                             
                            if old_status == new_status:
                                logging.info("Status has not changed")
                            else:
                                logging.info("Status has changed. Sending notification!")
                                sns_client.publish(
                                    TopicArn=env["aler_topic"],
                                    Message=f"Ping for proxy in {ping_result["country"]} changed from success:{old_status} to status of sucess:{new_status}",
                                    Subject='Status change for proxy' # Optional, primarily used for email subscriptions
                                )
                                                            
                                



                        copy_s3_object(bucket,file_key,env["internal_bucket"],old_result_path)




        




        # if file_key[-1] == "/":       
        #     logger.info(f"{file_key} is a directory, so this event will be ignored")
        # else:
        #     logger.info(f"reading URLs in file {file_key} inside of the {bucket} bucket")
        #     file_content = read_file_from_s3(bucket_name=bucket, file_name=file_key, client=s3)                
        #     logger.debug(file_content)
        #     json_content:list|None = load_content(file_content)
        #     if json_content:
        #         store_json_records(json_content)    

            
    

    

    

    
    





    
    
    


    

    
    



if __name__ != "__main__":  
    configure_logging_for_lambda() 