# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Topological sorting implementation."""

from functools import reduce as _reduce
from logging import getLogger

log = getLogger(__name__)


def _toposort(data):
    """Dependencies are expressed as a dictionary whose keys are items
    and whose values are a set of dependent items. Output is a list of
    sets in topological order. The first set consists of items with no
    dependences, each subsequent set consists of items that depend upon
    items in the preceding sets.
    """
    # Special case empty input.
    if len(data) == 0:
        return

    # Ignore self dependencies.
    for k, v in data.items():
        v.discard(k)
    # Find all items that don't depend on anything.
    extra_items_in_deps = _reduce(set.union, data.values()) - set(data.keys())
    # Add empty dependences where needed.
    data.update({item: set() for item in extra_items_in_deps})
    while True:
        ordered = sorted({item for item, dep in data.items() if len(dep) == 0})
        if not ordered:
            break

        for item in ordered:
            yield item
            data.pop(item, None)

        for dep in sorted(data.values()):
            dep -= set(ordered)

    if len(data) != 0:
        from ..exceptions import CondaValueError

        msg = "Cyclic dependencies exist among these items: {}"
        raise CondaValueError(msg.format(" -> ".join(repr(x) for x in data.keys())))


def pop_key(data):
    """
    Pop an item from the graph that has the fewest dependencies in the case of a tie
    The winners will be sorted alphabetically
    """
    items = sorted(data.items(), key=lambda item: (len(item[1]), item[0]))
    key = items[0][0]

    data.pop(key)

    for dep in data.values():
        dep.discard(key)

    return key


def _safe_toposort(data):
    """Dependencies are expressed as a dictionary whose keys are items
    and whose values are a set of dependent items. Output is a list of
    sets in topological order. The first set consists of items with no
    dependencies, each subsequent set consists of items that depend upon
    items in the preceding sets.
    """
    # Special case empty input.
    if len(data) == 0:
        return

    t = _toposort(data)

    while True:
        try:
            value = next(t)
            yield value
        except ValueError as err:
            log.debug(err.args[0])

            if not data:
                return  # pragma: nocover

            yield pop_key(data)

            t = _toposort(data)

            continue
        except StopIteration:
            return


def toposort(data, safe=True):
    data = {k: set(v) for k, v in data.items()}

    if "python" in data:
        # Special case: Remove circular dependency between python and pip,
        # to ensure python is always installed before anything that needs it.
        # For more details:
        # - https://github.com/conda/conda/issues/1152
        # - https://github.com/conda/conda/pull/1154
        # - https://github.com/conda/conda-build/issues/401
        # - https://github.com/conda/conda/pull/1614
        data["python"].discard("pip")

    if safe:
        return list(_safe_toposort(data))
    else:
        return list(_toposort(data))
