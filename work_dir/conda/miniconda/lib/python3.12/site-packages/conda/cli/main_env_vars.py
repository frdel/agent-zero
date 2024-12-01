# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda-env config vars`.

Allows for configuring conda-env's vars.
"""

from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
from os.path import lexists

from ..base.context import context, determine_target_prefix
from ..core.prefix_data import PrefixData
from ..exceptions import EnvironmentLocationNotFound


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .helpers import add_parser_json, add_parser_prefix

    var_summary = (
        "Interact with environment variables associated with Conda environments."
    )
    var_description = var_summary
    var_epilog = dals(
        """
        Examples::

            conda env config vars list -n my_env
            conda env config vars set MY_VAR=something OTHER_THING=ohhhhya
            conda env config vars unset MY_VAR

        """
    )

    var_parser = sub_parsers.add_parser(
        "vars",
        help=var_summary,
        description=var_description,
        epilog=var_epilog,
        **kwargs,
    )
    var_subparser = var_parser.add_subparsers()

    list_summary = "List environment variables for a conda environment."
    list_description = list_summary
    list_epilog = dals(
        """
        Example::

            conda env config vars list -n my_env

        """
    )

    list_parser = var_subparser.add_parser(
        "list",
        help=list_summary,
        description=list_description,
        epilog=list_epilog,
    )
    add_parser_prefix(list_parser)
    add_parser_json(list_parser)
    list_parser.set_defaults(func="conda.cli.main_env_vars.execute_list")

    set_summary = "Set environment variables for a conda environment."
    set_description = set_summary
    set_epilog = dals(
        """
        Example::

            conda env config vars set MY_VAR=weee

        """
    )

    set_parser = var_subparser.add_parser(
        "set",
        help=set_summary,
        description=set_description,
        epilog=set_epilog,
    )

    set_parser.add_argument(
        "vars",
        action="store",
        nargs="*",
        help="Environment variables to set in the form <KEY>=<VALUE> separated by spaces",
    )
    add_parser_prefix(set_parser)
    set_parser.set_defaults(func="conda.cli.main_env_vars.execute_set")

    unset_summary = "Unset environment variables for a conda environment."
    unset_description = unset_summary
    unset_epilog = dals(
        """
        Example::

            conda env config vars unset MY_VAR

        """
    )
    unset_parser = var_subparser.add_parser(
        "unset",
        help=unset_summary,
        description=unset_description,
        epilog=unset_epilog,
    )
    unset_parser.add_argument(
        "vars",
        action="store",
        nargs="*",
        help="Environment variables to unset in the form <KEY> separated by spaces",
    )
    add_parser_prefix(unset_parser)
    unset_parser.set_defaults(func="conda.cli.main_env_vars.execute_unset")


def execute_list(args: Namespace, parser: ArgumentParser) -> int:
    from . import common

    prefix = determine_target_prefix(context, args)
    if not lexists(prefix):
        raise EnvironmentLocationNotFound(prefix)

    pd = PrefixData(prefix)

    env_vars = pd.get_environment_env_vars()
    if args.json:
        common.stdout_json(env_vars)
    else:
        for k, v in env_vars.items():
            print(f"{k} = {v}")

    return 0


def execute_set(args: Namespace, parser: ArgumentParser) -> int:
    prefix = determine_target_prefix(context, args)
    pd = PrefixData(prefix)
    if not lexists(prefix):
        raise EnvironmentLocationNotFound(prefix)

    env_vars_to_add = {}
    for var in args.vars:
        var_def = var.split("=")
        env_vars_to_add[var_def[0].strip()] = "=".join(var_def[1:]).strip()
    pd.set_environment_env_vars(env_vars_to_add)
    if prefix == context.active_prefix:
        print("To make your changes take effect please reactivate your environment")

    return 0


def execute_unset(args: Namespace, parser: ArgumentParser) -> int:
    prefix = determine_target_prefix(context, args)
    pd = PrefixData(prefix)
    if not lexists(prefix):
        raise EnvironmentLocationNotFound(prefix)

    vars_to_unset = [var.strip() for var in args.vars]
    pd.unset_environment_env_vars(vars_to_unset)
    if prefix == context.active_prefix:
        print("To make your changes take effect please reactivate your environment")

    return 0
