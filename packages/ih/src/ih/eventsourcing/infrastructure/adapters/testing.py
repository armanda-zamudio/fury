import logging
import typing
import uuid
from collections import defaultdict
from dataclasses import asdict

from ih.eventsourcing.domain.model import (
    AggregateEvent,
    AggregateRoot,
    DuplicateEventError,
    EventStream,
)
from ih.eventsourcing.domain.ports import (
    AggregateEventReader,
    AggregateEventWriter,
    AggregateRootSnapshotReader,
    AggregateRootSnapshotWriter,
)
from ih.util.types import get_fully_qualified_name_from_type

type EventStore = dict[EventStream, typing.List[AggregateEvent]]
type SnapshotStore = dict[typing.Tuple[uuid.UUID, int], AggregateRoot]


class FakeAggregateEventReader(AggregateEventReader):
    def __init__(self, return_value: AggregateEvent | typing.Iterable[AggregateEvent]):
        self._return_value = return_value or []

    @property
    def return_value(self):
        return self._return_value

    @return_value.setter
    def _(self, value):
        self._return_value = value

    def read(
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream = "DOMAIN",
        min_version: int = 1,
        limit: int | None = None,
        descending: bool = False,
    ) -> typing.Iterator[AggregateEvent]:
        yield from self._return_value


class InMemoryAggregateEventReader(AggregateEventReader):
    def __init__(self, data: EventStore):
        self._data: EventStore = data

    def read(
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream = "DOMAIN",
        min_version: int = 1,
        limit: int | None = None,
        descending: bool = False,
    ) -> typing.Iterable[AggregateEvent]:
        if descending:
            raise ValueError("Cannot do descending reads.")
        all_above_min = (
            event
            for event in self._data[event_stream]
            if event.id == id and (event.version >= min_version)
        )
        if limit and limit > 0:
            max_version = min_version + limit - 1
            matching = (
                event for event in all_above_min if event.version <= max_version
            )
        else:
            matching = all_above_min
        yield from matching


class InMemoryAggregateEventWriter(AggregateEventWriter):
    def __init__(self, data: EventStore):
        self._data = data
        self._in_context = False
        self._pending: dict[EventStream, typing.List[AggregateEvent]] | None = None

    def __enter__(self):
        if self._in_context:
            raise RuntimeError("Cannot enter a managed context multiple times.")
        self._in_context = True
        self._pending = defaultdict(list)

    def __exit__(self, *args):
        if not self._in_context:
            raise RuntimeError("Cannot exit a managed context multiple times.")
        self._pending = None
        self._in_context = False

    def write(self, events, event_stream="DOMAIN"):
        if not self._in_context:
            raise RuntimeError("Cannot call write outside a managed context.")
        events = isinstance(events, typing.Iterable) and events or [events]
        self._pending[event_stream].extend(events)

    def commit(self):
        if not self._in_context:
            raise RuntimeError("Cannot call write outside a managed context.")
        for event_stream, events in self._pending.items():
            existing_events = self._data.get(event_stream, [])
            existing_keys = set(
                [(existing.id, existing.version) for existing in existing_events]
            )
            new_keys = set([(event.id, event.version) for event in events])
            duplicates = existing_keys & new_keys
            if duplicates:
                raise DuplicateEventError(
                    f"Found the following duplicate events: {duplicates}"
                )
            self._data[event_stream] = [*self._data.get(event_stream, []), *events]
        self._pending = defaultdict(list)


class InMemoryAggregateRootSnapshotWriter(AggregateRootSnapshotWriter):
    def __init__(self, data: SnapshotStore):
        self._data = data

    def write(self, aggregate_root: AggregateRoot):
        self._data[(aggregate_root.id, aggregate_root.version)] = (
            aggregate_root.__class__(**asdict(aggregate_root))
        )


class InMemoryAggregateRootSnapshotReader(AggregateRootSnapshotReader):
    def __init__(self, data: SnapshotStore):
        self._data: SnapshotStore = data

    def read[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream,
        max_version: int | None = None,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T | None:
        keys = [key for key in self._data if key[0] == id]
        if max_version:
            keys = [key for key in keys if key[1] <= max_version]
        if keys:
            return keys[-1]
        else:
            return None


class FakeAggregateRootSnapshotReader(AggregateRootSnapshotReader):
    def __init__(self, return_value: AggregateRoot | None):
        self._log = logging.getLogger().getChild(
            get_fully_qualified_name_from_type(self)
        )
        self._return_value = None
        self.return_value = return_value

    @property
    def return_value(self) -> AggregateRoot | None:
        result = self._return_value
        self._log.debug(f"Returning {result}")
        return result

    @return_value.setter
    def return_value(self, value: AggregateRoot | None):
        self._log.debug(f"Setting return value to {value}")
        self._return_value = value

    def read[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream,
        max_version: int | None = None,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T | None:
        return self.return_value
