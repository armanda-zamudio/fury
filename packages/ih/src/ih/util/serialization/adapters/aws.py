import decimal
import typing

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from ih.util.serialization.ports import Serializer

if typing.TYPE_CHECKING:
    from mypy_boto3_dynamodb.type_defs import UniversalAttributeValueTypeDef

    type DynamoDBDict = typing.Mapping[str, UniversalAttributeValueTypeDef]
else:
    type DynamoDBDict = dict[str, typing.Any]


class IHTypeSerializer(TypeSerializer):
    def serialize(self, value):
        match value:
            case float():
                return super().serialize(decimal.Decimal(str(value)))
        return super().serialize(value)


class DynamoDBSerializer(Serializer[typing.Mapping[str, typing.Any], DynamoDBDict]):
    def __init__(self, type_serializer: TypeSerializer | None = None):
        self._type_serializer = type_serializer or IHTypeSerializer()

    def __call__(self, input: typing.Mapping[str, typing.Any]):
        if not isinstance(input, typing.Mapping):
            raise TypeError("input must be a Mapping (dict or somesuch).")
        if not all([isinstance(key, str) for key in input.keys()]):
            raise ValueError("All keys in input must be strings.")
        return {
            key: self._type_serializer.serialize(value) for key, value in input.items()
        }


class DynamoDBDeserializer(Serializer[DynamoDBDict, typing.Mapping[str, typing.Any]]):
    def __init__(self):
        self._type_deserializer = TypeDeserializer()

    def __call__(self, input: DynamoDBDict) -> typing.Mapping[str, typing.Any]:
        if not isinstance(input, typing.Mapping):
            raise TypeError("input must be a Mapping (dict or somesuch).")
        if not all([isinstance(key, str) for key in input.keys()]):
            raise ValueError("All keys in input must be strings.")
        return {
            key: self._type_deserializer.deserialize(value)
            for key, value in input.items()
        }
