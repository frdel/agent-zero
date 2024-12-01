# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Detect whether this is Linux."""

import os
import re

from ...base.context import context
from ...common._os.linux import linux_get_libc_version
from .. import CondaVirtualPackage, hookimpl


@hookimpl
def conda_virtual_packages():
    if not context.subdir.startswith("linux-"):
        return

    yield CondaVirtualPackage("unix", None, None)

    # By convention, the kernel release string should be three or four
    # numeric components, separated by dots, followed by vendor-specific
    # bits.  For the purposes of versioning the `__linux` virtual package,
    # discard everything after the last digit of the third or fourth
    # numeric component; note that this breaks version ordering for
    # development (`-rcN`) kernels, but that can be a TODO for later.
    _, dist_version = context.platform_system_release
    dist_version = os.environ.get("CONDA_OVERRIDE_LINUX", dist_version)
    m = re.match(r"\d+\.\d+(\.\d+)?(\.\d+)?", dist_version)
    yield CondaVirtualPackage("linux", m.group() if m else "0", None)

    libc_family, libc_version = linux_get_libc_version()
    if not (libc_family and libc_version):
        # Default to glibc when using CONDA_SUBDIR var
        libc_family = "glibc"
    libc_version = os.getenv(f"CONDA_OVERRIDE_{libc_family.upper()}", libc_version)
    if libc_version:
        yield CondaVirtualPackage(libc_family, libc_version, None)
