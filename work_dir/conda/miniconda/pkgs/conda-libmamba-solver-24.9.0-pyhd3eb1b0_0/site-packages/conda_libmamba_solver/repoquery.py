# Copyright (C) 2019, QuantStack
# Copyright (C) 2022 Anaconda, Inc
# Copyright (C) 2023 conda
# SPDX-License-Identifier: BSD-3-Clause
import argparse
import json
import sys

from conda.base.context import context
from conda.cli import conda_argparse
from conda.common.io import Spinner
from conda.core.prefix_data import PrefixData
from libmambapy import QueryFormat

from .index import LibMambaIndexHelper


def configure_parser(parser: argparse.ArgumentParser):
    package_cmds = argparse.ArgumentParser(add_help=False)
    package_cmds.add_argument("package_query", help="The target package.")
    package_grp = package_cmds.add_argument_group("Subcommand options")
    package_grp.add_argument(
        "-i",
        "--installed",
        action="store_true",
        default=True,
        help=argparse.SUPPRESS,
    )

    package_grp.add_argument(
        "-p",
        "--platform",
        default=context.subdir,
        help="Platform/subdir to search packages for. Defaults to current platform.",
    )
    package_grp.add_argument(
        "--no-installed", action="store_true", help="Do not search currently installed packages."
    )
    package_grp.add_argument(
        "--pretty", action="store_true", help="Prettier output with more details."
    )

    package_grp.add_argument(
        "-a",
        "--all-channels",
        action="store_true",
        help="Look at all channels (for depends / whoneeds).",
    )

    view_cmds = argparse.ArgumentParser(add_help=False)
    view_grp = view_cmds.add_argument_group("Dependency options")
    view_grp.add_argument(
        "-t", "--tree", action="store_true", help="Show dependencies in a tree-like format."
    )
    view_grp.add_argument(
        "--recursive", action="store_true", help="Show dependencies recursively."
    )

    subparser = parser.add_subparsers(dest="subcmd")

    whoneeds = subparser.add_parser(
        "whoneeds",
        help="Show packages that depend on this package.",
        parents=[package_cmds, view_cmds],
    )

    depends = subparser.add_parser(
        "depends",
        help="Show dependencies of this package.",
        parents=[package_cmds, view_cmds],
    )

    search = subparser.add_parser(
        "search",
        help="Show all available package versions.",
        parents=[package_cmds],
    )

    for cmd in (whoneeds, search, depends):
        conda_argparse.add_parser_channels(cmd)
        conda_argparse.add_parser_networking(cmd)
        conda_argparse.add_parser_known(cmd)
        conda_argparse.add_parser_json(cmd)


def repoquery(args):
    if not args.subcmd:
        print("repoquery needs a subcommand (search, depends or whoneeds), e.g.:", file=sys.stderr)
        print("    conda repoquery search python\n", file=sys.stderr)
        return 1

    cli_flags = [getattr(args, attr, False) for attr in ("tree", "recursive", "pretty")]
    if sum([context.json, *cli_flags]) > 1:
        print("Use only one of --json, --tree, --recursive and --pretty.", file=sys.stderr)
        return 1

    if hasattr(args, "channel"):
        channels = args.channel
    else:
        channels = None
    if args.all_channels or (channels is None and args.subcmd == "search"):
        if channels:
            print("WARNING: Using all channels instead of configured channels\n", file=sys.stderr)
        channels = context.channels

    use_installed = args.installed
    if args.no_installed:
        use_installed = False

    # if we're asking for depends and channels are given, disregard
    # installed packages to prevent weird mixing
    if args.subcmd in ("depends", "whoneeds") and use_installed and channels:
        use_installed = False

    if args.subcmd == "search" and not args.installed:
        only_installed = False
    elif args.all_channels or (channels and len(channels)):
        only_installed = False
    else:
        only_installed = True

    if only_installed and args.no_installed:
        print("No channels selected. Use -a to search all channels.", file=sys.stderr)
        return 1

    if use_installed:
        prefix_data = PrefixData(context.target_prefix)
        prefix_data.load()
        installed_records = prefix_data.iter_records()
    else:
        installed_records = ()

    if context.json:
        query_format = QueryFormat.JSON
    elif getattr(args, "tree", None):
        query_format = QueryFormat.TREE
    elif getattr(args, "recursive", None):
        query_format = QueryFormat.RECURSIVETABLE
    elif getattr(args, "pretty", None):
        query_format = QueryFormat.PRETTY
    else:
        query_format = QueryFormat.TABLE

    with Spinner(
        "Collecting package metadata",
        enabled=not context.verbosity and not context.quiet,
        json=context.json,
    ):
        index = LibMambaIndexHelper(
            installed_records=installed_records,
            channels=channels,
            subdirs=(args.platform, "noarch"),
            repodata_fn=context.repodata_fns[-1],
            query_format=query_format,
        )

    result = getattr(index, args.subcmd)(args.package_query, records=False)
    if context.json:
        print(json.dumps(result, indent=2))
    else:
        print(result)
