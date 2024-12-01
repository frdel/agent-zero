# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""DEPRECATED: Use `conda.cli.main_env` instead.

Entry point for all conda-env subcommands.
"""

import os
import sys
from importlib import import_module

from conda.base.context import context
from conda.cli.main import init_loggers
from conda.cli.main_env import configure_parser  # noqa
from conda.deprecations import deprecated
from conda.exceptions import conda_exception_handler
from conda.gateways.logging import initialize_logging

deprecated.module("24.9", "25.3", addendum="Use `conda.cli.main_env` instead.")


def show_help_on_empty_command():
    if len(sys.argv) == 1:  # sys.argv == ['/path/to/bin/conda-env']
        sys.argv.append("--help")


def create_parser():
    # Ensure that if a downstream project invokes
    # conda_env.cli.main.create_parser() WITH NO
    # ARGUMENTS that the function will succeed and
    # return a valid ArgumentParser
    return configure_parser(None)


def do_call(arguments, parser):
    relative_mod, func_name = arguments.func.rsplit(".", 1)
    # func_name should always be 'execute'

    # Run the pre_command actions
    command = relative_mod.replace(".main_", "")

    context.plugin_manager.invoke_pre_commands(f"env_{command}")
    module = import_module(relative_mod, "conda_env.cli")
    exit_code = getattr(module, func_name)(arguments, parser)
    context.plugin_manager.invoke_post_commands(f"env_{command}")

    return exit_code


def main():
    initialize_logging()
    parser = create_parser()
    args = parser.parse_args()
    os.environ["CONDA_AUTO_UPDATE_CONDA"] = "false"
    context.__init__(argparse_args=args)
    init_loggers()
    return conda_exception_handler(do_call, args, parser)


if __name__ == "__main__":
    sys.exit(main())
