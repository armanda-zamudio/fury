import uuid
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class AggregateEventStorageMetadata:
    transaction_id: uuid.UUID
    global_version: int
    aggregate_event_type: type


class CounterNames:
    DOMAIN_VERSION = "global_version"
