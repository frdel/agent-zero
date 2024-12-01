# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Register the built-in post_solves hook implementations."""

from . import signature_verification

#: The list of post-solve plugins for easier registration with pluggy
plugins = [signature_verification]
