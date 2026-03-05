from __future__ import annotations

import typing
import uuid

from ih.eventsourcing.domain.model import AggregateEvent, AggregateRoot, EventStream


class UnitOfWork(typing.Protocol):
    def commit(self): ...

    def add(self, *aggregate_roots: AggregateRoot): ...

    def load[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        version: int | None = None,
        add: bool = True,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T: ...

    def __enter__(self) -> UnitOfWork: ...

    def __exit__(self, exc_type, exc_value, traceback) -> None: ...


class AggregateEventWriter(typing.Protocol):
    def __enter__(self) -> typing.Self: ...

    def __exit__(self, *args): ...

    def write(
        self,
        events: AggregateEvent | typing.Iterable[AggregateEvent],
        event_stream: EventStream = "DOMAIN",
    ): ...
    def commit(self): ...


class AggregateEventReader(typing.Protocol):
    def read(
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream = "DOMAIN",
        min_version: int = 1,
        limit: int | None = None,
        descending: bool = False,
    ) -> typing.Iterator[AggregateEvent]: ...


class AggregateRootReader(typing.Protocol):
    def read[T: AggregateRoot](
        self,
        id: uuid.UUID,
        version: int | None = None,
        event_stream: EventStream = "DOMAIN",
        *,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T: ...


class AggregateRootSnapshotReader(typing.Protocol):
    def read[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        max_version: int | None = None,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T | None: ...


class AggregateRootSnapshotWriter(typing.Protocol):
    def write(self, aggregate_root: AggregateRoot): ...
