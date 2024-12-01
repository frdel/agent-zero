# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Implements object describing a symbolic link from the base environment to a private environment.

Since private environments are an unrealized feature of conda and has been deprecated this data
model no longer serves a purpose and has also been deprecated.
"""

from logging import getLogger

from ..deprecations import deprecated

log = getLogger(__name__)


deprecated.module("25.3", "25.9", addendum="Nothing to import.")
