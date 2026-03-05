from __future__ import annotations

import typing


class Serializer[*TIn, TOut](typing.Protocol):
    """Converts a value from one type to another."""

    def __call__(self, *input: *TIn) -> TOut: ...


class UniversalSerializer(Serializer[typing.Any, typing.Any]): ...


class UniversalInputSerializer[TOut](Serializer[typing.Any, TOut]): ...


class SelectableOutputSerializer[TIn](typing.Protocol):
    def __call__[TOut](self, input: TIn, cls: typing.Type[TOut]) -> TOut: ...
