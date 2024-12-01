# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import os
from functools import lru_cache
from logging import getLogger
from os.path import exists

from ..compat import on_linux

log = getLogger(__name__)


@lru_cache(maxsize=None)
def linux_get_libc_version() -> tuple[str, str] | tuple[None, None]:
    """If on linux, returns (libc_family, version), otherwise (None, None)."""
    if not on_linux:
        return None, None

    for name in ("CS_GNU_LIBC_VERSION", "CS_GNU_LIBPTHREAD_VERSION"):
        try:
            # check if os.confstr returned None
            if value := os.confstr(name):
                family, version = value.strip().split(" ")
                break
        except ValueError:
            # ValueError: name is not defined in os.confstr_names
            # ValueError: value is not of the form "<family> <version>"
            pass
    else:
        family, version = "glibc", "2.5"
        log.warning(
            "Failed to detect libc family and version, assuming %s/%s",
            family,
            version,
        )

    # NPTL is just the name of the threading library, even though the
    # version refers to that of uClibc. os.readlink() can help to try to
    # figure out a better name instead.
    if family == "NPTL":  # pragma: no cover
        for clib in (
            entry.path for entry in os.scandir("/lib") if entry.name[:7] == "libc.so"
        ):
            clib = os.readlink(clib)
            if exists(clib):
                if clib.startswith("libuClibc"):
                    if version.startswith("0."):
                        family = "uClibc"
                    else:
                        family = "uClibc-ng"
                    break
        else:
            # This could be some other C library; it is unlikely though.
            family = "uClibc"
            log.warning(
                "Failed to detect non-glibc family, assuming %s/%s",
                family,
                version,
            )

    return family, version
