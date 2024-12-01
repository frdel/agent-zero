# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda search`.

Query channels for packages matching the provided package spec.
"""

from __future__ import annotations

from argparse import SUPPRESS
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction

    from ..models.records import PackageRecord


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from ..common.constants import NULL
    from .helpers import (
        add_parser_channels,
        add_parser_json,
        add_parser_known,
        add_parser_networking,
    )

    summary = "Search for packages and display associated information using the MatchSpec format."
    description = dals(
        f"""
        {summary}

        MatchSpec is a query language for conda packages.
        """
    )
    epilog = dals(
        """
        Examples:

        Search for a specific package named 'scikit-learn'::

            conda search scikit-learn

        Search for packages containing 'scikit' in the package name::

            conda search *scikit*

        Note that your shell may expand '*' before handing the command over to conda.
        Therefore, it is sometimes necessary to use single or double quotes around the query::

            conda search '*scikit'
            conda search "*scikit*"

        Search for packages for 64-bit Linux (by default, packages for your current
        platform are shown)::

            conda search numpy[subdir=linux-64]

        Search for a specific version of a package::

            conda search 'numpy>=1.12'

        Search for a package on a specific channel::

            conda search conda-forge::numpy
            conda search 'numpy[channel=conda-forge, subdir=osx-64]'
        """
    )

    p = sub_parsers.add_parser(
        "search",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    p.add_argument(
        "--envs",
        action="store_true",
        help="Search all of the current user's environments. If run as Administrator "
        "(on Windows) or UID 0 (on unix), search all known environments on the system.",
    )
    p.add_argument(
        "-i",
        "--info",
        action="store_true",
        help="Provide detailed information about each package.",
    )
    p.add_argument(
        "--subdir",
        "--platform",
        action="store",
        dest="subdir",
        help="Search the given subdir. Should be formatted like 'osx-64', 'linux-32', "
        "'win-64', and so on. The default is to search the current platform.",
        default=NULL,
    )
    p.add_argument(
        "--skip-flexible-search",
        action="store_true",
        help="Do not perform flexible search if initial search fails.",
    )
    p.add_argument(
        "match_spec",
        default="*",
        nargs="?",
        help=SUPPRESS,
    )
    p.add_argument(
        "--canonical",
        action="store_true",
        help=SUPPRESS,
    )
    p.add_argument(
        "-f",
        "--full-name",
        action="store_true",
        help=SUPPRESS,
    )
    p.add_argument(
        "--names-only",
        action="store_true",
        help=SUPPRESS,
    )
    add_parser_known(p)
    p.add_argument(
        "-o",
        "--outdated",
        action="store_true",
        help=SUPPRESS,
    )
    p.add_argument(
        "--spec",
        action="store_true",
        help=SUPPRESS,
    )
    p.add_argument(
        "--reverse-dependency",
        action="store_true",
        # help="Perform a reverse dependency search. Use 'conda search package --info' "
        #      "to see the dependencies of a package.",
        help=SUPPRESS,  # TODO: re-enable once we have --reverse-dependency working again
    )

    add_parser_channels(p)
    add_parser_networking(p)
    add_parser_json(p)
    p.set_defaults(func="conda.cli.main_search.execute")

    return p


def execute(args: Namespace, parser: ArgumentParser) -> int:
    """
    Implements `conda search` commands.

    `conda search <spec>` searches channels for packages.
    `conda search <spec> --envs` searches environments for packages.

    """
    from ..base.context import context
    from ..cli.common import stdout_json
    from ..common.io import Spinner
    from ..core.envs_manager import query_all_prefixes
    from ..core.index import calculate_channel_urls
    from ..core.subdir_data import SubdirData
    from ..models.match_spec import MatchSpec
    from ..models.records import PackageRecord
    from ..models.version import VersionOrder

    spec = MatchSpec(args.match_spec)
    if spec.get_exact_value("subdir"):
        subdirs = (spec.get_exact_value("subdir"),)
    else:
        subdirs = context.subdirs

    if args.envs:
        with Spinner(
            f"Searching environments for {spec}",
            not context.verbose and not context.quiet,
            context.json,
        ):
            prefix_matches = query_all_prefixes(spec)
            ordered_result = tuple(
                {
                    "location": prefix,
                    "package_records": tuple(
                        sorted(
                            (
                                PackageRecord.from_objects(prefix_rec)
                                for prefix_rec in prefix_recs
                            ),
                            key=lambda prec: prec._pkey,
                        )
                    ),
                }
                for prefix, prefix_recs in prefix_matches
            )
        if context.json:
            stdout_json(ordered_result)
        elif args.info:
            for pkg_group in ordered_result:
                for prec in pkg_group["package_records"]:
                    pretty_record(prec)
        else:
            builder = [
                "# %-13s %15s %15s  %-20s %-20s"
                % (
                    "Name",
                    "Version",
                    "Build",
                    "Channel",
                    "Location",
                )
            ]
            for pkg_group in ordered_result:
                for prec in pkg_group["package_records"]:
                    builder.append(
                        "%-15s %15s %15s  %-20s %-20s"
                        % (
                            prec.name,
                            prec.version,
                            prec.build,
                            prec.channel.name,
                            pkg_group["location"],
                        )
                    )
            print("\n".join(builder))
        return 0

    with Spinner(
        "Loading channels",
        not context.verbose and not context.quiet,
        context.json,
    ):
        spec_channel = spec.get_exact_value("channel")
        channel_urls = (spec_channel,) if spec_channel else context.channels

        matches = sorted(
            SubdirData.query_all(spec, channel_urls, subdirs),
            key=lambda rec: (rec.name, VersionOrder(rec.version), rec.build),
        )
    if not matches and not args.skip_flexible_search and spec.get_exact_value("name"):
        flex_spec = MatchSpec(spec, name=f"*{spec.name}*")
        if not context.json:
            print(f"No match found for: {spec}. Search: {flex_spec}")
        matches = sorted(
            SubdirData.query_all(flex_spec, channel_urls, subdirs),
            key=lambda rec: (rec.name, VersionOrder(rec.version), rec.build),
        )

    if not matches:
        channels_urls = tuple(
            calculate_channel_urls(
                channel_urls=context.channels,
                prepend=not args.override_channels,
                platform=subdirs[0],
                use_local=args.use_local,
            )
        )
        from ..exceptions import PackagesNotFoundError

        raise PackagesNotFoundError((str(spec),), channels_urls)

    if context.json:
        json_obj = defaultdict(list)
        for match in matches:
            json_obj[match.name].append(match)
        stdout_json(json_obj)

    elif args.info:
        for record in matches:
            pretty_record(record)

    else:
        builder = [
            "# %-18s %15s %15s  %-20s"
            % (
                "Name",
                "Version",
                "Build",
                "Channel",
            )
        ]
        for record in matches:
            builder.append(
                "%-20s %15s %15s  %-20s"
                % (
                    record.name,
                    record.version,
                    record.build,
                    record.channel.name,
                )
            )
        print("\n".join(builder))
    return 0


def pretty_record(record: PackageRecord) -> None:
    """
    Pretty prints a `PackageRecord`.

    :param record:  The `PackageRecord` object to print.
    """
    from ..common.io import dashlist
    from ..utils import human_bytes

    def push_line(display_name, attr_name):
        value = getattr(record, attr_name, None)
        if value is not None:
            builder.append("%-12s: %s" % (display_name, value))

    builder = []
    builder.append(record.name + " " + record.version + " " + record.build)
    builder.append("-" * len(builder[0]))

    push_line("file name", "fn")
    push_line("name", "name")
    push_line("version", "version")
    push_line("build", "build")
    push_line("build number", "build_number")
    size = getattr(record, "size", None)
    if size is not None:
        builder.append("%-12s: %s" % ("size", human_bytes(size)))
    push_line("license", "license")
    push_line("subdir", "subdir")
    push_line("url", "url")
    push_line("md5", "md5")
    if record.timestamp:
        date_str = datetime.fromtimestamp(record.timestamp, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )
        builder.append("%-12s: %s" % ("timestamp", date_str))
    if record.track_features:
        builder.append(
            "%-12s: %s" % ("track_features", dashlist(record.track_features))
        )
    if record.constrains:
        builder.append("%-12s: %s" % ("constraints", dashlist(record.constrains)))
    builder.append(
        "%-12s: %s"
        % ("dependencies", dashlist(record.depends) if record.depends else "[]")
    )
    builder.append("\n")
    print("\n".join(builder))
