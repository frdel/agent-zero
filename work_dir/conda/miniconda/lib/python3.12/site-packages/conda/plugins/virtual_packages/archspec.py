# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Detect archspec name."""

import os

from .. import CondaVirtualPackage, hookimpl


@hookimpl
def conda_virtual_packages():
    from ...core.index import get_archspec_name

    archspec_name = get_archspec_name()
    archspec_name = os.getenv("CONDA_OVERRIDE_ARCHSPEC", archspec_name)
    if archspec_name:
        yield CondaVirtualPackage("archspec", "1", archspec_name)
