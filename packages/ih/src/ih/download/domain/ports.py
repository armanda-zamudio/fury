import typing

from ih.download.domain.model import ProxyUrl


class Parser[T](typing.Protocol):
    def __call__(self, content: str | bytes) -> T: ...


class ProxyUrlFactory(typing.Protocol):
    def __call__(self, *args, **kwargs) -> ProxyUrl: ...
