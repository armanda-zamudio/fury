from __future__ import annotations

import abc
import json
import logging
import typing
import uuid
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import cached_property

from ih.util.datetime import now
from ih.util.iterable import make_iterable
from ih.util.types import get_fully_qualified_name_from_type

type EventStream = typing.Literal["DOMAIN", "SYSTEM", "SNAPSHOT"]


class EventsOutOfOrderError(Exception): ...


class EventMissingError(Exception): ...


class DuplicateEventError(Exception): ...


@dataclass(frozen=True, kw_only=True)
class AggregateEvent:
    id: uuid.UUID
    timestamp: datetime
    version: int


@dataclass(kw_only=True)
class AggregateRoot(abc.ABC):
    id: uuid.UUID
    version: int
    created_on: datetime
    modified_on: datetime

    @dataclass(frozen=True, kw_only=True)
    class Created(AggregateEvent):
        aggregate_type: type[AggregateRoot]
        version: int = 1

    @cached_property
    def _log(self) -> logging.Logger:
        return logging.getLogger().getChild(get_fully_qualified_name_from_type(self))

    def __post_init__(self):
        if not isinstance(self.id, uuid.UUID):
            raise ValueError(
                f"{self.__class__.__qualname__}.id requires a UUID, but received a {type(self.id)} ({self.id})."
            )
        if not isinstance(self.version, int):
            raise ValueError(
                f"{self.__class__.__qualname__}.version requires an int, but received a {type(self.version)} ({self.version})."
            )
        if not isinstance(self.created_on, datetime):
            raise ValueError(
                f"{self.__class__.__qualname__}.created_on requires a datetime, but received a {type(self.created_on)} ({self.created_on})."
            )
        if not isinstance(self.modified_on, datetime):
            raise ValueError(
                f"{self.__class__.__qualname__}.modified_on requires a datetime, but received a {type(self.modified_on)} ({self.modified_on})."
            )

    @property
    def unsaved_events(self) -> deque[AggregateEvent]:
        if not hasattr(self, "_unsaved_events"):
            self._force_set("_unsaved_events", deque())
        return getattr(self, "_unsaved_events")

    @unsaved_events.setter
    def unsaved_events(self, value: deque[AggregateEvent]):
        self._force_set("_unsaved_events", value)

    @property
    def log(self) -> logging.Logger:
        if not hasattr(self, "_log"):
            object.__setattr__(
                self,
                "_log",
                logging.getLogger().getChild(
                    get_fully_qualified_name_from_type(self) + f"{str(self.id)}"
                ),
            )
        return self._log

    ##########################################################################
    # Class methods
    ##########################################################################
    @classmethod
    @abc.abstractmethod
    def identify(cls: typing.Type[AggregateRoot], **kwargs) -> uuid.UUID:
        id_dict = {"__type": f"{__name__}.{cls.__qualname__}", **kwargs}
        json_serialized = json.dumps(id_dict, sort_keys=True, default=str)
        return uuid.uuid5(uuid.NAMESPACE_URL, json_serialized)

    @classmethod
    def load(
        cls, events: AggregateEvent | typing.Iterable[AggregateEvent]
    ) -> typing.Self | None:
        log = logging.getLogger().getChild(get_fully_qualified_name_from_type(cls))
        log.debug(f"Starting load() with events = {events}")
        event_iterator = iter(make_iterable(events))
        log.debug(f"event_iterator = {event_iterator}")
        first_event = next(event_iterator, None)
        if not first_event:
            log.info("There is no first event. Returning None")
            return None
        log.debug(f"First event received from event_iterator = {first_event}")
        aggregate_root = cls._apply_created(first_event)
        aggregate_root._apply(event_iterator)
        return aggregate_root

    @classmethod
    def _apply_created(self, event: Created) -> typing.Self:
        if event is None:
            logging.warning(f"event = {event}")
            return None
        if not isinstance(event, self.Created):
            raise TypeError(
                f"The first event sent to load() must inherit from AggregateRoot.Created. Received type {type(event)}"
            )
        if not 1 == event.version:
            raise EventsOutOfOrderError(
                f"The first event in an AggregateRoot's event stream must have version=1; received version={event.version}."
            )
        kwargs = asdict(event)
        aggregate_type = kwargs.pop("aggregate_type")
        timestamp = kwargs.pop("timestamp")
        kwargs["created_on"] = timestamp
        kwargs["modified_on"] = timestamp

        return aggregate_type(**kwargs)

    @classmethod
    @abc.abstractmethod
    def new(cls: type[AggregateRoot], *, timestamp: datetime | None = None, **kwargs):
        if cls == AggregateRoot:
            raise TypeError(
                "Cannot instantiate an AggregateRoot; you must use an inherited type."
            )
        id = cls.identify(**kwargs)
        timestamp = timestamp or now()
        event: AggregateRoot.Created = cls.Created(
            id=id, timestamp=timestamp, aggregate_type=cls, **kwargs
        )
        result = cls.load(event)
        result.unsaved_events.append(event)
        return result

    # Instance method

    def _apply(
        self, events: AggregateEvent | typing.Iterable[AggregateEvent]
    ) -> typing.Self:
        event_iterable = make_iterable(events)
        for event in event_iterable:
            if not event.version == self.version + 1:
                raise EventsOutOfOrderError(
                    f"Expected event to have version={self.version + 1}; received version={event.version}."
                )
            self.version = event.version
            self.modified_on = event.timestamp
            self._apply_event(event)
        return self

    def _force_set(self, name, value):
        object.__setattr__(self, name, value)

    def pop_unsaved_events(self) -> typing.Iterator["AggregateEvent"]:
        while self.unsaved_events:
            yield self.unsaved_events.popleft()

    @abc.abstractmethod
    def _apply_event(self, event: AggregateEvent) -> typing.Self:
        raise TypeError(f"Cannot handle an event of type {type(event)}.")

    def _trigger[T](
        self, cls: type[AggregateEvent], *, timestamp: datetime | None = None, **kwargs
    ):
        event = cls(
            id=self.id, version=self.version + 1, timestamp=timestamp or now(), **kwargs
        )
        self._apply(event)
        self.unsaved_events.append(event)
        return event


@dataclass(frozen=True, kw_only=True)
class CounterIncremented(AggregateEvent):
    increment: int = 1

    def __post_init__(self):
        # super().__post_init__()
        if not isinstance(self.increment, int):
            raise TypeError("The 'increment' key must have an integer value > 0.")
        if self.increment < 1:
            raise ValueError("increment must be greater than 0.")


@dataclass(kw_only=True)
class Counter(AggregateRoot):
    name: str
    value: int

    @dataclass(frozen=True, kw_only=True)
    class Created(AggregateRoot.Created):
        name: str
        value: int | None = 0

    @classmethod
    def identify(cls, *, name: str, **kwargs):
        return super().identify(name=name)

    def _apply_event(self, event):
        match event:
            case CounterIncremented():
                self.value += event.increment
            case _:
                raise TypeError(f"Cannot handle event of type {type(event)}.")

    @classmethod
    def new(
        cls,
        *,
        name: str,
        value: int | None = None,
        timestamp: datetime | None = None,
    ) -> typing.Self:
        kwargs = dict(timestamp=timestamp, name=name)
        if value:
            kwargs["value"] = value
        return super().new(**kwargs)

    @property
    def unsaved_increment(self) -> int:
        return getattr(self, "_unsaved_increment", 0)

    @unsaved_increment.setter
    def unsaved_increment(self, value: int):
        self._force_set("_unsaved_increment", value)

    @property
    def logger(self) -> logging.Logger:
        if not getattr(self, "_logger", None):
            self._force_set(
                "_logger",
                logging.getLogger().getChild(get_fully_qualified_name_from_type(self)),
            )
        return self._logger

    def increment(self, increment: int = 1):
        """
        This does some ugly stuff to compress all unsaved global event ID increases into a single event. The reason to do this is avoid doubling the number of events being saved.
        """
        original_number = self.value - self.unsaved_increment
        self.unsaved_increment += increment
        self.value = original_number + self.unsaved_increment
        return self.value

    def commit(self):
        if not self.unsaved_increment:
            self.logger.warning(
                "Ignoring call to update() because there are no unsaved increments."
            )
        else:
            increment = self.unsaved_increment
            self.unsaved_increment = 0
            self.value -= increment
            self._trigger(CounterIncremented, increment=increment)
