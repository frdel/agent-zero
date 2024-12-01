# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Detect whether this is macOS."""

import os

from ...base.context import context
from .. import CondaVirtualPackage, hookimpl


@hookimpl
def conda_virtual_packages():
    if not context.subdir.startswith("osx-"):
        return

    yield CondaVirtualPackage("unix", None, None)

    _, dist_version = context.os_distribution_name_version
    dist_version = os.environ.get("CONDA_OVERRIDE_OSX", dist_version)
    if dist_version:
        yield CondaVirtualPackage("osx", dist_version, None)
