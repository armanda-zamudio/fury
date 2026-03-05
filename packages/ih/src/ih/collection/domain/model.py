import enum
import typing
from dataclasses import dataclass, field

from ih.eventsourcing.domain.model import (
    AggregateEvent,
    AggregateRoot,
)


class WebResourceState(enum.Enum):
    NEW = "NEW"
    OUT_OF_DATE = "OUT_OF_DATE"
    UP_TO_DATE = "UP_TO_DATE"
    AWAITING_RETRY = "AWAITING_RETRY"
    FAULTED = "FAULTED"
    ARCHIVED = "ARCHIVED"


class WebResourceCreatedArgs(typing.TypedDict):
    content_expiration_seconds: typing.NotRequired[int]


class WebResourceActivated(AggregateEvent): ...


class WebResourceEnteredOutOfDate(AggregateEvent): ...


class WebResourceEnteredUpToDate(AggregateEvent): ...


class WebResourceEnteredAwaitingRetry(AggregateEvent): ...


class WebResourceEnteredFaulted(AggregateEvent): ...


@dataclass(kw_only=True)
class WebResource(AggregateRoot):
    state: WebResourceState = field(default=WebResourceState.NEW)
    update_errors: int = 0
    content_expiration_seconds: int | None = None
    consecutive_update_failures: int = 0

    def __post_init__(self, *args):
        if self.__class__ == WebResource:
            raise TypeError(
                "Cannot instantiate a WebResource object. The class must inherit from WebResource."
            )
        return super().__post_init__()

    def activate(self):
        if self.state == WebResourceState.NEW:
            self._trigger(WebResourceEnteredOutOfDate)
        else:
            self._log.info(f"Ignoring activate() because state == {self.state}")

    def update(self):
        if self.state == WebResourceState.OUT_OF_DATE:
            self._trigger(WebResourceEnteredUpToDate)
            assert self.state == WebResourceState.UP_TO_DATE
        else:
            self._log.info(f"Ignorging update() because state == {self.state}")

    def expire_state(self):
        if self.state == WebResourceState.UP_TO_DATE:
            self._trigger(WebResourceEnteredOutOfDate)
        elif self.state == WebResourceState.AWAITING_RETRY:
            self._trigger(WebResourceEnteredOutOfDate)
        else:
            self._log.info(f"Ignoring expire() because state == {self.state}")

    def _apply_event(self, event):
        self._log.debug(f"Processing event {event}")
        match event:
            case WebResourceEnteredOutOfDate():
                self.state = WebResourceState.OUT_OF_DATE
            case WebResourceEnteredUpToDate():
                self.state = WebResourceState.UP_TO_DATE
            case WebResourceEnteredFaulted():
                self.state = WebResourceState.FAULTED
            case WebResourceEnteredAwaitingRetry():
                self.state = WebResourceState.AWAITING_RETRY
            case _:
                raise TypeError(f"Cannot handle an event of type {type(event)}")

    def fail_update(self):
        if self.state == WebResourceState.OUT_OF_DATE:
            self.consecutive_update_failures += 1
            if self.consecutive_update_failures > 2:
                self._trigger(WebResourceEnteredFaulted)
            else:
                self._trigger(WebResourceEnteredAwaitingRetry)
        else:
            self._log.warning(f"fail_update() was called when state == {self.state}")
            return
