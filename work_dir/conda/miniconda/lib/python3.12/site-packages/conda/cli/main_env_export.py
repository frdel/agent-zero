# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_export` instead.

CLI implementation for `conda-env export`.

Dumps specified environment package specifications to the screen.
"""

# Import from conda.cli.main_export since this module is deprecated.
from conda.cli.main_export import configure_parser, execute  # noqa
from conda.deprecations import deprecated

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_export` instead.")
