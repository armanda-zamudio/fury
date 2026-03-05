from __future__ import annotations

import json
import logging
import typing

from ih.collection.interface.awslambda.util import deserialize_eventbridge_event

if typing.TYPE_CHECKING:
    from aws_lambda_typing.events import EventBridgeEvent

logging.getLogger().setLevel("INFO")


def handler(event: EventBridgeEvent, context):
    logging.info(f"Received event: {json.dumps(event, indent=4)}")
    try:
        event_type = deserialize_eventbridge_event(event)
        logging.info(f"Event type is {event_type}.")
    except ModuleNotFoundError as exc:
        logging.warning(exc)
