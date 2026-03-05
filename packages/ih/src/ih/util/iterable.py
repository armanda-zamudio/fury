import typing


def make_iterable(value, *, reject_none: bool = False):
    result: typing.Iterable
    if value is None:
        if reject_none:
            raise ValueError("Must call make_iterable with a non-None value.")
        else:
            result = []
    elif isinstance(value, typing.Iterable):
        result = value
    else:
        result = [value]
    return result
