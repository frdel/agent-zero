# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_env_update` instead.

CLI implementation for `conda-env update`.

Updates the conda environments with the specified packages.
"""

# Import from conda.cli.main_env_update since this module is deprecated.
from conda.cli.main_env_update import configure_parser, execute  # noqa
from conda.deprecations import deprecated

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_env_update` instead.")

description = """
Update the current environment based on environment file
"""

example = """
examples:
    conda env update
    conda env update -n=foo
    conda env update -f=/path/to/environment.yml
    conda env update --name=foo --file=environment.yml
    conda env update vader/deathstar
"""
