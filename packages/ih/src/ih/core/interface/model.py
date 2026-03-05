import typing
import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    class Args(typing.TypedDict): ...

    id: uuid.UUID
    timestamp: datetime
    data: Args | None = None
