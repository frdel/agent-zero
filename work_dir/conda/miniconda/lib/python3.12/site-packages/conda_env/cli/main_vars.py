# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_env_vars` instead.

CLI implementation for `conda-env config vars`.

Allows for configuring conda-env's vars.
"""

# Import conda.cli.main_env_vars since this module is deprecated.
from conda.cli.main_env_vars import (  # noqa
    configure_parser,
    execute_list,
    execute_set,
    execute_unset,
)
from conda.deprecations import deprecated

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_env_vars` instead.")

var_description = """
Interact with environment variables associated with Conda environments
"""

var_example = """
examples:
    conda env config vars list -n my_env
    conda env config vars set MY_VAR=something OTHER_THING=ohhhhya
    conda env config vars unset MY_VAR
"""

list_description = """
List environment variables for a conda environment
"""

list_example = """
examples:
    conda env config vars list -n my_env
"""

set_description = """
Set environment variables for a conda environment
"""

set_example = """
example:
    conda env config vars set MY_VAR=weee
"""

unset_description = """
Unset environment variables for a conda environment
"""

unset_example = """
example:
    conda env config vars unset MY_VAR
"""
