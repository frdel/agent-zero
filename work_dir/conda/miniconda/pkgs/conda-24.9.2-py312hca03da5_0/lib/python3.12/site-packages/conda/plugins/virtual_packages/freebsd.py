# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Detect whether this is FeeBSD."""

from ...base.context import context
from .. import CondaVirtualPackage, hookimpl


@hookimpl
def conda_virtual_packages():
    if not context.subdir.startswith("freebsd-"):
        return

    yield CondaVirtualPackage("unix", None, None)
