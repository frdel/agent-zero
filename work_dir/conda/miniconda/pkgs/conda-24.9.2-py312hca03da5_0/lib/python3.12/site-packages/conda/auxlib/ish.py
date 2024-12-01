from logging import getLogger
from textwrap import dedent

log = getLogger(__name__)


def dals(string):
    """dedent and left-strip"""
    return dedent(string).lstrip()


def _get_attr(obj, attr_name, aliases=()):
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        for alias in aliases:
            try:
                return getattr(obj, alias)
            except AttributeError:
                continue
        else:
            raise


def find_or_none(key, search_maps, aliases=(), _map_index=0):
    """Return the value of the first key found in the list of search_maps,
    otherwise return None.

    Examples:
        >>> from .collection import AttrDict
        >>> d1 = AttrDict({'a': 1, 'b': 2, 'c': 3, 'e': None})
        >>> d2 = AttrDict({'b': 5, 'e': 6, 'f': 7})
        >>> find_or_none('c', (d1, d2))
        3
        >>> find_or_none('f', (d1, d2))
        7
        >>> find_or_none('b', (d1, d2))
        2
        >>> print(find_or_none('g', (d1, d2)))
        None
        >>> find_or_none('e', (d1, d2))
        6

    """
    try:
        attr = _get_attr(search_maps[_map_index], key, aliases)
        return attr if attr is not None else find_or_none(key, search_maps[1:], aliases)
    except AttributeError:
        # not found in current map object, so go to next
        return find_or_none(key, search_maps, aliases, _map_index+1)
    except IndexError:
        # ran out of map objects to search
        return None


def find_or_raise(key, search_maps, aliases=(), _map_index=0):
    try:
        attr = _get_attr(search_maps[_map_index], key, aliases)
        return attr if attr is not None else find_or_raise(key, search_maps[1:], aliases)
    except AttributeError:
        # not found in current map object, so go to next
        return find_or_raise(key, search_maps, aliases, _map_index+1)
    except IndexError:
        # ran out of map objects to search
        raise AttributeError()
