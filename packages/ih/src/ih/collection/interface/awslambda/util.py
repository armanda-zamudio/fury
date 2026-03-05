from __future__ import annotations

import typing

from ih.util.types import get_type_from_fully_qualified_name

if typing.TYPE_CHECKING:
    from aws_lambda_typing.events import EventBridgeEvent


def deserialize_eventbridge_event(event: EventBridgeEvent):
    event_type_str = event.get("detail-type", None)
    if event_type_str:
        try:
            return get_type_from_fully_qualified_name(event_type_str)
        except Exception:
            pass
    raise ModuleNotFoundError(
        f"Could not find a module for type string '{event_type_str}'",
        name=event_type_str,
    )
