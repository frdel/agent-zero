# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

from . import archspec, conda, cuda, freebsd, linux, osx, windows

#: The list of virtual package plugins for easier registration with pluggy
plugins = [archspec, conda, cuda, freebsd, linux, osx, windows]
