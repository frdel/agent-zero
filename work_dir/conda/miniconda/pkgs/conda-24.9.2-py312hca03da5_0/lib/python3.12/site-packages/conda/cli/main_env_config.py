# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda-env config`.

Allows for programmatically interacting with conda-env's configuration files (e.g., `~/.condarc`).
"""

from argparse import ArgumentParser, Namespace, _SubParsersAction


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .main_env_vars import configure_parser as configure_vars_parser

    summary = "Configure a conda environment."
    description = summary
    epilog = dals(
        """
        Examples::

            conda env config vars list
            conda env config --append channels conda-forge

        """
    )

    p = sub_parsers.add_parser(
        "config",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    p.set_defaults(func="conda.cli.main_env_config.execute")
    config_subparser = p.add_subparsers()
    configure_vars_parser(config_subparser)

    return p


def execute(args: Namespace, parser: ArgumentParser) -> int:
    parser.parse_args(["env", "config", "--help"])

    return 0
