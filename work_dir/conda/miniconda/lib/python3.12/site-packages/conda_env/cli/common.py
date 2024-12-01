# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.env` instead.

Common utilities for conda-env command line tools.
"""

from conda.base.constants import ROOT_ENV_NAME
from conda.deprecations import deprecated

# Import from conda.env.env since this module is deprecated.
from conda.env.env import get_filename, print_result  # noqa: F401

deprecated.module("24.9", "25.3", addendum="Use `conda.env.env` instead.")
deprecated.constant(
    "24.9",
    "25.3",
    "base_env_name",
    ROOT_ENV_NAME,
    addendum="Use `conda.base.constants.ROOT_ENV_NAME` instead.",
)
