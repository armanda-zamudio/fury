from __future__ import annotations

import json
import logging
import typing
import uuid
from collections import deque
from datetime import datetime

import botocore.errorfactory
from boto3.dynamodb import conditions
from boto3.dynamodb.types import TypeSerializer

from ih.eventsourcing import AggregateRoot, AggregateRootSnapshotWriter
from ih.eventsourcing.domain.model import (
    AggregateEvent,
    Counter,
    DuplicateEventError,
    EventsOutOfOrderError,
    EventStream,
)
from ih.eventsourcing.domain.ports import (
    AggregateEventReader,
    AggregateEventWriter,
    AggregateRootReader,
    AggregateRootSnapshotReader,
)
from ih.eventsourcing.domain.valueobjects import CounterNames
from ih.eventsourcing.util.serialization import DynamoDBDict
from ih.util.datetime import now
from ih.util.serialization import (
    CattrsObjectSerializer,
    DynamoDBDeserializer,
    DynamoDBSerializer,
    SelectableOutputSerializer,
    Serializer,
)
from ih.util.serialization.adapters import CattrsObjectDeserializer
from ih.util.types import DataclassProtocol, get_fully_qualified_name_from_type
from ih.util.uuid import uuid7

if typing.TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_dynamodb.type_defs import (
        PutTypeDef,
        TransactWriteItemsInputTypeDef,
        TransactWriteItemTypeDef,
        UniversalAttributeValueTypeDef,
    )

    LEVEL = logging.ERROR
else:
    LEVEL = logging.DEBUG


class EventMetadata(typing.TypedDict, total=False):
    transaction_id: uuid.UUID
    global_version: typing.NotRequired[int]
    event_type: type
    event_stream: EventStream


class SnapshotMetadata(typing.TypedDict, total=False):
    aggregate_root_type: type
    created_on: datetime


class DynamoDBSnapshotWriter(AggregateRootSnapshotWriter):
    def __init__(
        self,
        *,
        dynamodb_client: DynamoDBClient,
        snapshot_table: str,
        dataclass_to_dict: Serializer[DataclassProtocol | dict, dict] | None = None,
        dict_to_dynamodb_dict: Serializer[
            dict, dict[str, UniversalAttributeValueTypeDef]
        ]
        | None = None,
    ):
        self._dynamodb_client = dynamodb_client
        self._snapshot_table = snapshot_table
        self._dataclass_to_dict = dataclass_to_dict or CattrsObjectSerializer()
        self._dict_to_dynamodb_dict = dict_to_dynamodb_dict or DynamoDBSerializer()
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self)
        )

    def write(self, aggregate_root: AggregateRoot, timestamp: datetime | None = None):
        aggregate_dict = self._dataclass_to_dict(aggregate_root)
        metadata = self._dataclass_to_dict(
            SnapshotMetadata(
                aggregate_root_type=type(aggregate_root), created_on=timestamp or now()
            )
        )
        combined_dict = {**aggregate_dict, **metadata}
        display_dict = {
            key: (type(value), value) for key, value in combined_dict.items()
        }
        self._log.warning(f"combined_dict = {display_dict}")
        dynamodb_dict = self._dict_to_dynamodb_dict(combined_dict)
        self._log.warning(f"dynamodb_dict = {dynamodb_dict}")
        self._dynamodb_client.put_item(
            TableName=self._snapshot_table, Item=dynamodb_dict
        )


class DynamoDBSnapshotReader(AggregateRootSnapshotReader):
    def __init__(
        self,
        *,
        dynamodb_client: DynamoDBClient,
        snapshot_table: str,
        object_deserializer: SelectableOutputSerializer[dict] | None = None,
        dynamodb_deserializer: Serializer[DynamoDBDict, dict] | None = None,
    ):
        self._dynamodb_client = dynamodb_client
        self._snapshot_table = snapshot_table
        self._dynamodb_deserializer = dynamodb_deserializer or DynamoDBDeserializer()
        self._object_deserializer = object_deserializer or CattrsObjectDeserializer()

    def read[T: AggregateRoot](
        self, id: uuid.UUID, *, max_version=None, cls: type[T]
    ) -> T:
        key_condition = conditions.Key("id").eq(str(id))
        if max_version:
            key_condition = key_condition & conditions.Key("version").lte(max_version)

        built = conditions.ConditionExpressionBuilder().build_expression(
            key_condition, True
        )
        response = self._dynamodb_client.query(
            TableName=self._snapshot_table,
            KeyConditionExpression=built.condition_expression,
            ExpressionAttributeNames=built.attribute_name_placeholders,
            ExpressionAttributeValues=built.attribute_value_placeholders,
            ScanIndexForward=False,
            Limit=1,
        )
        if "Items" in response and response["Items"]:
            dynamodb_dict = response["Items"][0]
            combined_dict = self._dynamodb_deserializer(dynamodb_dict)
            metadata = self._object_deserializer(combined_dict, SnapshotMetadata)
            result = self._object_deserializer(
                combined_dict, metadata["aggregate_root_type"]
            )
            return result
        return None


class DynamoDBAggregateEventWriter(AggregateEventWriter):
    def __init__(
        self,
        *,
        dynamodb_client: DynamoDBClient,
        event_table: str,
        dataclass_to_dict: Serializer[DataclassProtocol | dict, dict] | None = None,
        dict_to_dynamodb_dict: Serializer[
            dict, dict[str, UniversalAttributeValueTypeDef]
        ]
        | None = None,
        aggregate_root_reader: AggregateRootReader,
    ):
        self._dynamodb_client = dynamodb_client
        self._event_table = event_table
        self._queue: deque[tuple[AggregateEvent, EventStream]] | None = None
        self._last_version: dict[uuid.UUID, int] | None = None
        self._dataclass_to_dict = dataclass_to_dict or CattrsObjectSerializer()
        self._dict_to_dynamodb_dict = dict_to_dynamodb_dict or DynamoDBSerializer()
        self._aggregate_root_reader = aggregate_root_reader
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self)
        )

    @property
    def is_in_context(self) -> bool:
        """
        Is the object in a 'with ...' block, or has __enter__ been called?
        """
        return self._queue is not None

    def __enter__(self) -> typing.Self:
        """At the beginning of a managed context, this Initializes the variables which store events prior to commit()."""
        if self.is_in_context:
            raise RuntimeError(
                "Already in the managed context for DynamoDBAggregateEventWriter. Cannot __enter__ more than once."
            )
        self._queue = deque()
        self._last_version = {}
        self._transaction_id = uuid7()

    def __exit__(self, *args):
        """At the conclusion of a managed context, this clears the variables which store events prior to commit()"""
        if not self.is_in_context:
            raise RuntimeError("Already outside a managed context. Cannot re-exit.")
        self._queue = None
        self._last_version = None
        self._transaction_id = None

    def _set_last_version(self, event_id: uuid.UUID, version: int):
        """
        Records the last-written version number for a given aggregate event ID. This is used to ensure that events are stored in order, and in strict sequence."""
        last_version = self._last_version.get(event_id)
        expected_version = None if last_version is None else last_version + 1
        if expected_version and expected_version != version:
            raise EventsOutOfOrderError(
                f"Event submitted out-of-order: expected version {expected_version} but received version={version}."
            )
        self._last_version[event_id] = version

    def write(
        self,
        events: AggregateEvent | typing.Iterable[AggregateEvent],
        event_stream: EventStream = "DOMAIN",
    ):
        """
        Adds events to the write queue. Events are not flushed to DynamoDB until commit() is called.
        """
        if not self.is_in_context:
            raise RuntimeError(
                "Cannot call add(...) outside a managed context. Must use 'with transaction_builder ...' or 'transaction_builder.__enter__()'."
            )
        if not events:
            self._log.warning(".write(...) called with no events. Exiting write(...)")
            return
        if not isinstance(events, typing.Iterable):
            events = [events]
        if not all(isinstance(event, AggregateEvent) for event in events):
            raise ValueError("All events must inherit from AggregateEvent")
        for event in events:
            self._set_last_version(event.id, event.version)
            self._queue.append((event, event_stream))

    def _get_or_create_global_version(self) -> Counter:
        global_version_id = Counter.identify(name=CounterNames.DOMAIN_VERSION)
        existing_version = self._aggregate_root_reader.read(
            id=global_version_id, event_stream="SYSTEM", cls=Counter
        )
        return existing_version or Counter.new(name=CounterNames.DOMAIN_VERSION)

    def _build_transaction(self, queue: deque[tuple[AggregateEvent, EventStream]]):
        global_version = self._get_or_create_global_version()
        transaction: TransactWriteItemsInputTypeDef = {
            "TransactItems": [],
        }
        current_global_version = global_version.value
        event_count = (
            len(queue) + len(global_version.unsaved_events) + 1
        )  # The counter update.
        global_version.increment(event_count)
        global_version.commit()
        complete_queue: deque[tuple[AggregateEvent, EventStream]] = deque(
            [
                *queue,
                *[(event, "SYSTEM") for event in global_version.pop_unsaved_events()],
            ]
        )
        transact_write_items: list[TransactWriteItemTypeDef] = []
        while complete_queue:
            event, event_stream = complete_queue.popleft()
            current_global_version += 1
            event_metadata = EventMetadata(
                transaction_id=self._transaction_id,
                global_version=current_global_version,
                event_type=type(event),
                event_stream=event_stream,
            )
            event_dict = {
                **self._dataclass_to_dict(event),
                **self._dataclass_to_dict(event_metadata),
            }
            dynamodb_dict = self._dict_to_dynamodb_dict(event_dict)
            put = self._build_put(dynamodb_dict)
            transact_write_items.append({"Put": put})
        transaction["TransactItems"] = transact_write_items
        return transaction

    def _execute_commit(self):
        queue = deque(self._queue)
        if not queue:
            self._log.info("_execute_commit() called with no pending writes. Exiting.")
            return True
        transaction = self._build_transaction(queue)
        self._log.warning(transaction)
        with open("/tmp/transaction.json", "w") as outf:
            json.dump(transaction, outf, indent=4)
        try:
            self._dynamodb_client.transact_write_items(**transaction)
        except botocore.errorfactory.ClientError as exc:
            reasons = getattr(exc, "response", {}).get("CancellationReasons", [])
            if any(reason["Code"] == "ConditionalCheckFailed" for reason in reasons):
                raise DuplicateEventError(
                    f"Transaction failed because one or more events are duplicates: {reasons}"
                )
            else:
                raise exc

    def commit(self):
        """
        Flushes all pending writes to DynamoDB."""
        if not self.is_in_context:
            raise RuntimeError(
                "Cannot call commit(...) outside a managed context. Must use 'with <variable name> ...' or '<variable name>.__enter__()'."
            )
        if not self._queue:
            self._log.info("commit() called with no pending writes. Exiting.")
            return
        self._log.debug(
            f"Building DynamoDB transaction with {len(self._queue)} events."
        )
        self._execute_commit()
        # transaction: TransactWriteItemsInputTypeDef = {
        #     "TransactItems": [],
        # }

        # while self._queue:
        #     event, event_stream = self._queue.popleft()
        #     item_dict = self._dataclass_to_dict(event)
        #     decorated_item_dict = self._decorate_item_dict(item_dict, event_stream)
        #     dynamodb_dict = self._dict_to_dynamodb_dict(decorated_item_dict)
        #     transaction["TransactItems"].append(
        #         {"Put": self._build_put(dynamodb_dict, event_stream)}
        #     )
        # self._dynamodb_client.transact_write_items(**transaction)

    def _build_put(self, item: dict[str, UniversalAttributeValueTypeDef]) -> PutTypeDef:
        return {
            "Item": item,
            "TableName": self._event_table,
            "ConditionExpression": "attribute_not_exists(id) AND attribute_not_exists(version)",
            "ReturnValuesOnConditionCheckFailure": "ALL_OLD",
        }


class DynamoDBAggregateEventReader(AggregateEventReader):
    def __init__(
        self,
        *,
        dynamodb_client: DynamoDBClient,
        event_table: str,
        dynamodb_deserializer: Serializer[DynamoDBDict, dict] | None = None,
        object_deserializer: SelectableOutputSerializer[dict, AggregateEvent]
        | None = None,
    ):
        self._dynamodb_client = dynamodb_client
        self._event_table = event_table
        self._dynamodb_deserializer = dynamodb_deserializer or DynamoDBDeserializer()
        self._object_deserializer = object_deserializer or CattrsObjectDeserializer()
        self._log = logging.getLogger().getChild(self.__class__.__name__)

    def read(
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream = "DOMAIN",
        min_version: int = 1,
        limit: int | None = None,
        descending: bool = False,
    ) -> typing.Iterator[AggregateEvent]:
        type_serializer = TypeSerializer()
        serialized_id = type_serializer.serialize(str(id))
        serialized_min_version = type_serializer.serialize(min_version)
        key_condition = conditions.Key("id").eq(serialized_id)
        key_condition = key_condition & conditions.Key("version").gte(
            serialized_min_version
        )
        key_condition_expression = (
            conditions.ConditionExpressionBuilder().build_expression(
                key_condition, is_key_condition=True
            )
        )
        pages = self._dynamodb_client.get_paginator("query").paginate(
            TableName=self._event_table,
            KeyConditionExpression=key_condition_expression.condition_expression,
            ExpressionAttributeNames=key_condition_expression.attribute_name_placeholders,
            ExpressionAttributeValues=key_condition_expression.attribute_value_placeholders,
            ScanIndexForward=(not descending),
        )
        returned = 0
        for page in pages:
            items = page.get("Items", [])
            if limit:
                remaining = limit - returned
                wanted = items[:remaining]
            else:
                wanted = items
            for item in wanted:
                try:
                    raw_dict = self._dynamodb_deserializer(item)
                except:
                    self._log.error(item)
                    raise
                metadata: EventMetadata = self._object_deserializer(
                    raw_dict, EventMetadata
                )
                if metadata["event_stream"] != event_stream:
                    continue
                yield self._object_deserializer(raw_dict, metadata["event_type"])
                returned += 1
            if limit and returned >= limit:
                break
