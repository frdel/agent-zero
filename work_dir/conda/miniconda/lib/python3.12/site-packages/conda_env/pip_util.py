# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.pip_util` instead.

Environment object describing the conda environment.yaml file.
"""

import re

from conda.deprecations import deprecated
from conda.env.pip_util import (  # noqa: F401
    get_pip_installed_packages,
    pip_subprocess,
)
from conda.exceptions import CondaEnvException  # noqa: F401

deprecated.module("24.9", "25.3", addendum="Use `conda.env.pip_util` instead.")


# canonicalize_{regex,name} inherited from packaging/utils.py
# Used under BSD license
_canonicalize_regex = re.compile(r"[-_.]+")
