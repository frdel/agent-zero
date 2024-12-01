"""Common collection classes."""
from functools import reduce
from collections.abc import Mapping, Set

from .compat import isiterable
from ..deprecations import deprecated

try:
    from frozendict import frozendict
except ImportError:
    from .._vendor.frozendict import frozendict


@deprecated("24.9", "25.3", addendum="Use `frozendict.deepfreeze` instead.")
def make_immutable(value):
    # this function is recursive, and if nested data structures fold back on themselves,
    #   there will likely be recursion errors
    if isinstance(value, Mapping):
        if isinstance(value, frozendict):
            return value
        return frozendict((k, make_immutable(v)) for k, v in value.items())
    elif isinstance(value, Set):
        if isinstance(value, frozenset):
            return value
        return frozenset(make_immutable(v) for v in value)
    elif isiterable(value):
        if isinstance(value, tuple):
            return value
        return tuple(make_immutable(v) for v in value)
    else:
        return value


# http://stackoverflow.com/a/14620633/2127762
class AttrDict(dict):
    """Sub-classes dict, and further allows attribute-like access to dictionary items.

    Examples:
        >>> d = AttrDict({'a': 1})
        >>> d.a, d['a'], d.get('a')
        (1, 1, 1)
        >>> d.b = 2
        >>> d.b, d['b']
        (2, 2)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__dict__ = self


def first(seq, key=bool, default=None, apply=lambda x: x):
    """Give the first value that satisfies the key test.

    Args:
        seq (iterable):
        key (callable): test for each element of iterable
        default: returned when all elements fail test
        apply (callable): applied to element before return, but not to default value

    Returns: first element in seq that passes key, mutated with optional apply

    Examples:
        >>> first([0, False, None, [], (), 42])
        42
        >>> first([0, False, None, [], ()]) is None
        True
        >>> first([0, False, None, [], ()], default='ohai')
        'ohai'
        >>> import re
        >>> m = first(re.match(regex, 'abc') for regex in ['b.*', 'a(.*)'])
        >>> m.group(1)
        'bc'

        The optional `key` argument specifies a one-argument predicate function
        like that used for `filter()`.  The `key` argument, if supplied, must be
        in keyword form.  For example:
        >>> first([1, 1, 3, 4, 5], key=lambda x: x % 2 == 0)
        4

    """
    return next((apply(x) for x in seq if key(x)), default() if callable(default) else default)


def last(seq, key=bool, default=None, apply=lambda x: x):
    return next((apply(x) for x in reversed(seq) if key(x)), default)
