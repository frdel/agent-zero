# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.env.installers.pip` instead.

Pip-flavored installer.
"""

from conda.deprecations import deprecated
from conda.env.installers.pip import _pip_install_via_requirements, install  # noqa

deprecated.module("24.9", "25.3", addendum="Use `conda.env.installers.pip` instead.")
