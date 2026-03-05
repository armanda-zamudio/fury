import typing
from dataclasses import dataclass

type ProxyUrl = str


@dataclass(kw_only=True, frozen=True)
class HttpResponse:
    status_code: int
    status_message: str | None = None
    content: bytes
    headers: typing.Iterable[typing.Tuple[str, str]]
