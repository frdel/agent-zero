# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Replacements for parts of the toolz library."""

from __future__ import annotations

import collections
import itertools
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Generator, Sequence


def groupby_to_dict(keyfunc, sequence):
    """A `toolz`-style groupby implementation.

    Returns a dictionary of { key: [group] } instead of iterators.
    """
    result = collections.defaultdict(list)
    for key, group in itertools.groupby(sequence, keyfunc):
        result[key].extend(group)
    return dict(result)


def unique(sequence: Sequence[Any]) -> Generator[Any, None, None]:
    """A `toolz` inspired `unique` implementation.

    Returns a generator of unique elements in the sequence
    """
    seen: set[Any] = set()
    yield from (
        # seen.add always returns None so we will always return element
        seen.add(element) or element
        for element in sequence
        # only pass along novel elements
        if element not in seen
    )
