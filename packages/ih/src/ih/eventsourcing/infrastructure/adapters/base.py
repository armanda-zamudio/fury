import logging
import typing
import uuid

from ih.eventsourcing.domain.model import (
    AggregateRoot,
    EventStream,
)
from ih.eventsourcing.domain.ports import (
    AggregateEventReader,
    AggregateEventWriter,
    AggregateRootReader,
    AggregateRootSnapshotReader,
    UnitOfWork,
)


class BaseAggregateRootReader(AggregateRootReader):
    def __init__(
        self,
        snapshot_reader: AggregateRootSnapshotReader,
        event_reader: AggregateEventReader,
    ):
        self._snapshot_reader = snapshot_reader
        self._event_reader = event_reader
        self._log = logging.getLogger().getChild(self.__class__.__qualname__)

    def _read_from_snapshot[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream,
        version: int | None,
        cls: typing.Type[T],
    ) -> T | None:
        snapshot = self._snapshot_reader.read(
            id, event_stream=event_stream, max_version=version, cls=cls
        )
        self._log.debug(f"snapshot_read returned {snapshot}")
        if not snapshot:
            return None
        if version:
            limit = version - snapshot.version
        else:
            limit = None
        events = self._event_reader.read(
            id, event_stream=event_stream, min_version=snapshot.version + 1, limit=limit
        )
        if events:
            self._log.debug(f"Before .apply, snapshot = {snapshot}")
            snapshot = snapshot._apply(events)
            self._log.debug(f"After .apply, snapshot = {snapshot}")
        return snapshot

    def _read_from_events[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        event_stream: EventStream,
        version: int | None = None,
        cls: typing.Type[T],
    ) -> T | None:
        events = self._event_reader.read(
            id, event_stream=event_stream, min_version=1, limit=version
        )
        return AggregateRoot.load(events)

    def read[T: AggregateRoot](
        self,
        id: uuid.UUID,
        version: int | None = None,
        event_stream: EventStream = "DOMAIN",
        *,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T | None:
        return self._read_from_snapshot(
            id, event_stream=event_stream, version=version, cls=cls
        ) or self._read_from_events(
            id, event_stream=event_stream, version=version, cls=cls
        )


class BaseUnitOfWork(UnitOfWork):
    def __init__(
        self,
        aggregate_event_writer: AggregateEventWriter,
        aggregate_root_reader: AggregateRootReader,
    ):
        self._in_context = False
        self._known: set[uuid.UUID] = set()
        self._objects: dict[uuid.UUID, AggregateRoot] = {}
        self._aggregate_event_writer = aggregate_event_writer
        self._aggregate_root_reader = aggregate_root_reader

    def _require_context(self):
        if not self._in_context:
            raise RuntimeError("Must be in context manager to use this method.")

    def commit(self):
        self._require_context()
        with self._aggregate_event_writer:
            for root in self._objects.values():
                self._aggregate_event_writer.write(root.pop_unsaved_events())
            self._aggregate_event_writer.commit()

    def add(self, *aggregate_roots: AggregateRoot):
        self._require_context()
        for root in aggregate_roots:
            id = root.id
            self._known.add(id)
            self._objects[id] = root

    def load[T: AggregateRoot](
        self,
        id: uuid.UUID,
        *,
        version: int | None = None,
        add: bool = True,
        cls: typing.Type[T] = AggregateRoot,
    ) -> T:
        self._require_context()
        result = self._aggregate_root_reader.read(id, version, cls=cls)
        if add:
            self.add(result)
        return result

    def __enter__(self):
        if self._in_context:
            raise RuntimeError("This UnitOfWork is already within a managed context.")
        self._in_context = True
        self._known = set()
        self._objects = {}
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._require_context()
        self._in_context = False
        self._known = set()
