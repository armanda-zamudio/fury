import logging
import typing
import uuid
from datetime import date, datetime, timezone

import cattrs
from cattr import Converter

from ih.util.serialization.ports import SelectableOutputSerializer, Serializer
from ih.util.types import (
    DataclassProtocol,
    copy_method_signature,
    get_fully_qualified_name_from_type,
    get_type_from_fully_qualified_name,
)


class CustomCattrsConverter(cattrs.Converter):
    """
    This class is responsible for unstructuring an Entity to a Mapping, and structuring a Mapping to an Entity.
    """

    @copy_method_signature(Converter.__init__)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, omit_if_default=False, **kwargs)
        self.add_type(date, date.isoformat, date.fromisoformat)
        self.add_type(uuid.UUID, str, uuid.UUID)
        self.add_type(
            datetime,
            lambda d: datetime.isoformat(datetime.astimezone(d, timezone.utc)),
            lambda s: datetime.fromisoformat(s).astimezone(timezone.utc),
        )
        self.add_type(
            type,
            get_fully_qualified_name_from_type,
            lambda *args: get_type_from_fully_qualified_name(args[0]),
        )

        def is_generic_type(cls):
            return (
                hasattr(cls, "__origin__")
                and isinstance(cls.__origin__, typing.Type)
                or False
            )

        self.register_structure_hook_func(
            is_generic_type,
            lambda *args: get_type_from_fully_qualified_name(args[0]),
        )
        self.register_unstructure_hook_func(
            is_generic_type,
            get_fully_qualified_name_from_type,
        )

    def add_type[TIn, TOut](
        self,
        cls: type[TIn],
        serializer: typing.Callable[[TIn], TOut],
        deserializer: typing.Callable[[TOut], TIn],
    ):
        self.register_structure_hook(cls, lambda x, _: deserializer(x))
        self.register_unstructure_hook(cls, serializer)


class CattrsObjectSerializer(
    Serializer[DataclassProtocol | typing.Mapping, typing.Mapping[str, typing.Any]]
):
    def __init__(self, converter: cattrs.Converter | None = None):
        self._serializer = converter or CustomCattrsConverter()
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self)
        )

    def __call__(
        self, input: DataclassProtocol | typing.Mapping
    ) -> typing.Mapping[str, typing.Any]:
        if not (
            isinstance(input, typing.Mapping) or isinstance(input, DataclassProtocol)
        ):
            raise TypeError(
                f"Input must be a dataclass or a dict; received {type(input)}."
            )
        unstructured: dict = self._serializer.unstructure(input)
        return unstructured


class CattrsObjectDeserializer(
    SelectableOutputSerializer[typing.Mapping[str, typing.Any]]
):
    def __init__(self, converter: cattrs.Converter | None = None):
        self._serializer = converter or CustomCattrsConverter()
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self)
        )

    def __call__[T: DataclassProtocol | typing.Mapping](
        self, input: typing.Mapping[str, typing.Any], cls: typing.Type[T]
    ) -> T:
        return self._serializer.structure(input, cls)
