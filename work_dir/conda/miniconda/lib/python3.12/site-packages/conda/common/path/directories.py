# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Common directory utilities."""

from __future__ import annotations

from functools import reduce
from itertools import accumulate, chain
from logging import getLogger
from os.path import join
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable, Sequence

log = getLogger(__name__)


def tokenized_startswith(test_iterable, startswith_iterable):
    return all(t == sw for t, sw in zip(test_iterable, startswith_iterable))


def get_all_directories(files: Iterable[str]) -> list[tuple[str, ...]]:
    return sorted(filter(None, {tuple(f.split("/")[:-1]) for f in files}))


def get_leaf_directories(files: Iterable[str]) -> Sequence[str]:
    # give this function a list of files, and it will hand back a list of leaf
    # directories to pass to os.makedirs()
    directories = get_all_directories(files)
    if not directories:
        return ()

    leaves = []

    def _process(x, y):
        if not tokenized_startswith(y, x):
            leaves.append(x)
        return y

    last = reduce(_process, directories)

    if not leaves:
        leaves.append(directories[-1])
    elif not tokenized_startswith(last, leaves[-1]):
        leaves.append(last)

    return tuple("/".join(leaf) for leaf in leaves)


def explode_directories(child_directories: Iterable[tuple[str, ...]]) -> set[str]:
    # get all directories including parents
    # child_directories must already be split with os.path.split
    return set(
        chain.from_iterable(
            accumulate(directory, join) for directory in child_directories if directory
        )
    )
