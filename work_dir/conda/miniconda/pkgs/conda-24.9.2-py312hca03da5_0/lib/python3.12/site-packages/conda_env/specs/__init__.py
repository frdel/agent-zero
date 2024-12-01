# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.specs` instead.

Dynamic installer loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from conda.deprecations import deprecated
from conda.env.specs import detect, get_spec_class_from_file  # noqa

if TYPE_CHECKING:
    from conda.env.specs import FileSpecTypes, SpecTypes  # noqa

deprecated.module("24.9", "25.3", addendum="Use `conda.env.specs` instead.")
