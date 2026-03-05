import functools
import importlib
import typing
from collections.abc import Callable
from typing import Any, Concatenate, ParamSpec

P = ParamSpec("P")
T = typing.TypeVar("T")


def copy_callable_signature[T](
    source: Callable[P, T],
) -> Callable[[Callable[..., T]], Callable[P, T]]:
    """
    Use this decorator on a function to rewrite its signature
    to match another function. Useful when you have to accept *args, **kwargs
    but want to have usable autocomplete.
    """

    def wrapper(target: Callable[..., T]) -> Callable[P, T]:
        @functools.wraps(source)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            return target(*args, **kwargs)

        return wrapped

    return wrapper


def copy_method_signature[T](
    source: Callable[Concatenate[Any, P], T],
) -> Callable[[Callable[..., T]], Callable[Concatenate[Any, P], T]]:
    """
    Use this decorator on a class's method to rewrite its signature
    to match another function. Useful when you have to accept *args, **kwargs
    but want to have usable autocomplete.
    """

    def wrapper(target: Callable[..., T]) -> Callable[Concatenate[Any, P], T]:
        @functools.wraps(source)
        def wrapped(self: Any, /, *args: P.args, **kwargs: P.kwargs) -> T:
            return target(self, *args, **kwargs)

        return wrapped

    return wrapper


def _find_module_name(pieces: list[str]) -> tuple[str, list[str]]:
    for i in range(len(pieces) - 1):
        index = -1 - i
        module_name = ".".join(pieces[0:index])
        try:
            # print(f"({index}) Looking for {module_name}")
            module = importlib.import_module(module_name)
            return module, pieces[len(pieces) + index :]
        except ModuleNotFoundError:
            continue
    raise ModuleNotFoundError(f"Could not find a module in {'.'.join(pieces)}")


def get_type_from_fully_qualified_name(fully_qualified_name: str | Callable):
    pieces = fully_qualified_name.split(".")
    module, classnames = _find_module_name(pieces)
    parent = module
    for classname in classnames:
        parent = getattr(parent, classname)
    return parent


def _get_type_from_fully_qualified_name(fully_qualified_name: str | Callable):
    match fully_qualified_name:
        case Callable():
            return fully_qualified_name
        case str():
            module_path, class_name = fully_qualified_name.rsplit(":", 1)
            if not module_path:
                raise ValueError(
                    f"path {fully_qualified_name} does not include a module name."
                )
            module = importlib.import_module(module_path)
            class_parts = [piece for piece in class_name.split(".") if piece]
            try:
                return functools.reduce(getattr, class_parts, module)
                # return getattr(module, class_name)
            except AttributeError:
                raise NameError(
                    f"Path {fully_qualified_name} specifies an invalid class '{class_name}'."
                )
        case _:
            raise TypeError(f"Invalid type ({type(fully_qualified_name)})")


def get_fully_qualified_name_from_type(obj: Any) -> str:
    if isinstance(obj, type):
        klass = obj
    else:
        klass = obj.__class__
    module = klass.__module__
    if module == "builtins":
        return klass.__qualname__  # avoid outputs like 'builtins.str'
    return module + "." + klass.__qualname__
    # return module + ":" + klass.__qualname__


class classinstancemethod(typing.Generic[T]):
    """
    Use this as a decorator to create a method which can be used as either a class method or an instance method."""

    def __init__(self, method: typing.Callable[..., T]):
        self._method = method

    def __get__(
        self, obj: typing.Any, cls: typing.Type[Any]
    ) -> typing.Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            if obj is not None:
                return self._method(cls, *args, instance=obj, **kwargs)
            return self._method(cls, *args, **kwargs)

        return wrapper


@typing.runtime_checkable
class DataclassProtocol(typing.Protocol):
    @property
    def __dataclass_fields__(self) -> dict: ...
