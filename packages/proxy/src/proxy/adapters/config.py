import logging
import json
from datetime import datetime

NOISY_LOGGERS = ["botocore", "boto3"]
format_string = "%Y%m%d"

def configure_logging_for_cli():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)-10s - %(asctime)s - %(name)s - %(message)s",
    )
    for logger in NOISY_LOGGERS:
        logging.getLogger(logger).setLevel(logging.WARNING)


def configure_logging_for_lambda():
    logging.getLogger().setLevel(logging.DEBUG)
    for logger in NOISY_LOGGERS:
        logging.getLogger(logger).setLevel(logging.WARNING)

def time_converter(date_str:str):
    try:
        return datetime.strptime(date_str, format_string)
    except:
        return None