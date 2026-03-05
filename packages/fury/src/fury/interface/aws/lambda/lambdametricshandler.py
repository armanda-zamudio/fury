import os
import boto3
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo
import pandas as pd
from fury.adapter.config import StaticProxy,configure_logging_for_lambda

s3 = boto3.resource("s3")
est_time_zone = ZoneInfo("America/New_York")

def load_vars() -> dict:
    env = os.environ
    kwargs = dict(
        data_bucket=env.get("FURY_DATA_BUCKET", ""),
        internal_bucket=env.get("FURY_INTERNAL_BUCKET", ""),
        data_prefix=env.get("FURY_DATA_PREFIX", ""),           #ALERT_TOPIC
        
    )
    return kwargs


def handler(event, context):   


    # main_key_prefix = "davide/mission_data/fury/"
    current_time_est = datetime.now(est_time_zone)
    date_key_prefix = current_time_est.strftime("%Y/%m/%d/")
    env = load_vars()
    bucket_name = env["data_bucket"]
    main_key_prefix = env["data_prefix"]
    key_prefix=main_key_prefix+date_key_prefix
    results = []
    bucket = s3.Bucket(bucket_name)

    for obj in bucket.objects.filter(Prefix=key_prefix):
        if not obj.key.endswith("/"):
            try:
                file_content = obj.get()["Body"].read().decode("utf-8")
                file_last_mofied = obj.last_modified.astimezone(est_time_zone)
                file_content_json = json.loads(file_content)

                for json_element in file_content_json:    
                    
                    json_element["pingTime"] = file_last_mofied.strftime("%Y-%m-%d %H:%M")          
                    results.append(json_element)

                # print(f"File: {obj.key}")
                # print(file_content_json)
                # print("-"*80)
            except Exception as e:
                print(f"Error reading {obj.key}: {e}")

    
    if results:
        df_normalized  = pd.json_normalize(results)
        df_normalized_ir = df_normalized[df_normalized["country"] == "ir"]
        
        file_name = "proxy.xlsx"
        with pd.ExcelWriter(f"/tmp/{file_name}") as writer:
            df_normalized_ir.to_excel(writer,sheet_name="IR Ping", index=False)
            workbook = writer.book
            worksheet = writer.sheets["IR Ping"]

            for i, col in enumerate(df_normalized_ir.columns):
                # Calculate the maximum length of the column data
                max_len = df_normalized_ir[col].map(lambda x: len(str(x))).max() + 2

                # Set the column width
                worksheet.set_column(i,i,max_len)
        s3.meta.client.upload_file(
            Filename=f"/tmp/{file_name}",
            Bucket=env["internal_bucket"],
            Key=date_key_prefix+file_name
        )
        os.remove(f"/tmp/{file_name}")
    

    
        



if __name__ != "__main__":  
    configure_logging_for_lambda() 