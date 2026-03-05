from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone

from proxy.adapters import ProxyTable

def handler(event, context):   
    logging.info("ensuring proxy connections have not expired")
    valid_connections:list[ProxyTable] = ProxyTable.get_valid_connections()
    # with ProxyTable.batch_write() as batch:
    invalid_connections:list[ProxyTable] = []

    for vc in valid_connections:
        if datetime.now(timezone.utc) > (vc.expiration_time-timedelta(minutes=5)):
            vc.has_expired = "true"
            vc.proxy_connection_in_use = False
            invalid_connections.append(vc)
    
    if invalid_connections:
        logging.info("Found invalid connections")
        with ProxyTable.batch_write() as batch:
            for ivc in invalid_connections:
                batch.save(ivc)
    else:
        logging.info("All proxy connections are still valid")



        


    





if __name__ != "__main__":  
    NOISY_LOGGERS = ["botocore", "boto3"]    
    for l in NOISY_LOGGERS:
        logging.getLogger(l).setLevel(logging.WARNING)      
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)