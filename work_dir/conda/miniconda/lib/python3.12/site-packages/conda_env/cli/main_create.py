# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_env_create` instead.

CLI implementation for `conda-env create`.

Creates new conda environments with the specified packages.
"""

# Import from conda.cli.main_env_create since this module is deprecated.
from conda.cli.main_env_create import configure_parser, execute  # noqa
from conda.deprecations import deprecated

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_env_create` instead.")

description = """
Create an environment based on an environment definition file.

If using an environment.yml file (the default), you can name the
environment in the first line of the file with 'name: envname' or
you can specify the environment name in the CLI command using the
-n/--name argument. The name specified in the CLI will override
the name specified in the environment.yml file.

Unless you are in the directory containing the environment definition
file, use -f to specify the file path of the environment definition
file you want to use.
"""

example = """
examples:
    conda env create
    conda env create -n envname
    conda env create folder/envname
    conda env create -f /path/to/environment.yml
    conda env create -f /path/to/requirements.txt -n envname
    conda env create -f /path/to/requirements.txt -p /home/user/envname
"""
