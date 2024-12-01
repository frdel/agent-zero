# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_env_list` instead.

CLI implementation for `conda-env list`.

Lists available conda environments.
"""

# Import from conda.cli.main_env_list since this module is deprecated.
from conda.cli.main_env_list import configure_parser, execute  # noqa
from conda.deprecations import deprecated

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_env_list` instead.")

description = """
List the Conda environments
"""

example = """
examples:
    conda env list
    conda env list --json
"""
