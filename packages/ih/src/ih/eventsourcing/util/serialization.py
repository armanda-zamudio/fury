import logging

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from ih.eventsourcing.domain.model import AggregateEvent
from ih.eventsourcing.domain.valueobjects import AggregateEventStorageMetadata
from ih.util.serialization import Serializer
from ih.util.serialization.adapters.aws import DynamoDBDict
from ih.util.serialization.adapters.cattrs import CustomCattrsConverter
from ih.util.types import get_fully_qualified_name_from_type


class AggregateEventToDynamoDBDictSerializer(
    Serializer[AggregateEvent, AggregateEventStorageMetadata, DynamoDBDict]
):
    def __init__(self):
        self._object_serializer = CustomCattrsConverter()
        self._type_serializer = TypeSerializer()
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self.__class__)
        )

    def __call__(
        self, event: AggregateEvent, metadata: AggregateEventStorageMetadata
    ) -> DynamoDBDict:
        self._log.info(f"Serializing {event} and {metadata}")
        serialized_event = self._object_serializer.unstructure(event)
        self._log.info(f"serialized_event = {serialized_event}")
        serialized_metadata = self._object_serializer.unstructure(metadata)
        self._log.info(f"serialized_metadata = {serialized_metadata}")
        combined_dict = {**serialized_event, **serialized_metadata}
        result = {
            key: self._type_serializer.serialize(value)
            for key, value in combined_dict.items()
        }
        self._log.info(f"result = {result}")
        return result


class DynamoDBDictToAggregateEventDeserializer(
    Serializer[DynamoDBDict, AggregateEvent]
):
    def __init__(self):
        self._type_deserializer = TypeDeserializer()
        self._object_serializer = CustomCattrsConverter()
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self.__class__)
        )

    def __call__(
        self, input: DynamoDBDict
    ) -> tuple[AggregateEvent, AggregateEventStorageMetadata]:
        combined_dict = {
            key: self._type_deserializer.deserialize(value)
            for key, value in input.items()
        }
        metadata = self._object_serializer.structure(
            combined_dict, AggregateEventStorageMetadata
        )
        event = self._object_serializer.structure(
            combined_dict, metadata.aggregate_event_type
        )
        return event, metadata
