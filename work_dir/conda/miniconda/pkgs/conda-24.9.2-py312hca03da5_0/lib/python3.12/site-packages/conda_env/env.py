# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.env` instead.

Environment object describing the conda environment.yaml file.
"""

from conda.deprecations import deprecated
from conda.env.env import (  # noqa: F401
    VALID_KEYS,
    Dependencies,
    Environment,
    _expand_channels,
    from_environment,
    from_file,
    from_yaml,
    validate_keys,
)
from conda.exceptions import EnvironmentFileNotFound  # noqa: F401

deprecated.module("24.9", "25.3", addendum="Use `conda.env.env` instead.")
