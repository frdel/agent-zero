# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda list`.

Lists all packages installed into an environment.
"""

import logging
import re
from argparse import ArgumentParser, Namespace, _SubParsersAction
from os.path import isdir, isfile

from .. import __version__

log = logging.getLogger(__name__)


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .helpers import (
        add_parser_json,
        add_parser_prefix,
        add_parser_show_channel_urls,
    )

    summary = "List installed packages in a conda environment."
    description = summary
    epilog = dals(
        """
        Examples:

        List all packages in the current environment::

            conda list

        List all packages in reverse order::

            conda list --reverse

        List all packages installed into the environment 'myenv'::

            conda list -n myenv

        List all packages that begin with the letters "py", using regex::

            conda list ^py

        Save packages for future use::

            conda list --export > package-list.txt

        Reinstall packages from an export file::

            conda create -n myenv --file package-list.txt

        """
    )

    p = sub_parsers.add_parser(
        "list",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    add_parser_prefix(p)
    add_parser_json(p)
    add_parser_show_channel_urls(p)
    p.add_argument(
        "--reverse",
        action="store_true",
        default=False,
        help="List installed packages in reverse order.",
    )
    p.add_argument(
        "-c",
        "--canonical",
        action="store_true",
        help="Output canonical names of packages only.",
    )
    p.add_argument(
        "-f",
        "--full-name",
        action="store_true",
        help="Only search for full names, i.e., ^<regex>$. "
        "--full-name NAME is identical to regex '^NAME$'.",
    )
    p.add_argument(
        "--explicit",
        action="store_true",
        help="List explicitly all installed conda packages with URL "
        "(output may be used by conda create --file).",
    )
    p.add_argument(
        "--md5",
        action="store_true",
        help="Add MD5 hashsum when using --explicit.",
    )
    p.add_argument(
        "--sha256",
        action="store_true",
        help="Add SHA256 hashsum when using --explicit.",
    )
    p.add_argument(
        "-e",
        "--export",
        action="store_true",
        help="Output explicit, machine-readable requirement strings instead of "
        "human-readable lists of packages. This output may be used by "
        "conda create --file.",
    )
    p.add_argument(
        "-r",
        "--revisions",
        action="store_true",
        help="List the revision history.",
    )
    p.add_argument(
        "--no-pip",
        action="store_false",
        default=True,
        dest="pip",
        help="Do not include pip-only installed packages.",
    )
    p.add_argument(
        "--auth",
        action="store_false",
        default=True,
        dest="remove_auth",
        help="In explicit mode, leave authentication details in package URLs. "
        "They are removed by default otherwise.",
    )
    p.add_argument(
        "regex",
        action="store",
        nargs="?",
        help="List only packages matching this regular expression.",
    )
    p.set_defaults(func="conda.cli.main_list.execute")

    return p


def print_export_header(subdir):
    print("# This file may be used to create an environment using:")
    print("# $ conda create --name <env> --file <this file>")
    print(f"# platform: {subdir}")
    print(f"# created-by: conda {__version__}")


def get_packages(installed, regex):
    pat = re.compile(regex, re.I) if regex else None
    for prefix_rec in sorted(installed, key=lambda x: x.name.lower()):
        if pat and pat.search(prefix_rec.name) is None:
            continue
        yield prefix_rec


def list_packages(
    prefix,
    regex=None,
    format="human",
    reverse=False,
    show_channel_urls=None,
):
    from ..base.constants import DEFAULTS_CHANNEL_NAME
    from ..base.context import context
    from ..core.prefix_data import PrefixData
    from .common import disp_features

    res = 0

    installed = sorted(
        PrefixData(prefix, pip_interop_enabled=True).iter_records(),
        key=lambda x: x.name,
    )

    packages = []
    for prec in get_packages(installed, regex) if regex else installed:
        if format == "canonical":
            packages.append(
                prec.dist_fields_dump() if context.json else prec.dist_str()
            )
            continue
        if format == "export":
            packages.append("=".join((prec.name, prec.version, prec.build)))
            continue

        features = set(prec.get("features") or ())
        disp = "%(name)-25s %(version)-15s %(build)15s" % prec
        disp += f"  {disp_features(features)}"
        schannel = prec.get("schannel")
        show_channel_urls = show_channel_urls or context.show_channel_urls
        if (
            show_channel_urls
            or show_channel_urls is None
            and schannel != DEFAULTS_CHANNEL_NAME
        ):
            disp += f"  {schannel}"

        packages.append(disp)

    if reverse:
        packages = reversed(packages)

    result = []
    if format == "human":
        result = [
            f"# packages in environment at {prefix}:",
            "#",
            "# %-23s %-15s %15s  Channel" % ("Name", "Version", "Build"),
        ]
    result.extend(packages)

    return res, result


def print_packages(
    prefix,
    regex=None,
    format="human",
    reverse=False,
    piplist=False,
    json=False,
    show_channel_urls=None,
):
    from ..base.context import context
    from .common import stdout_json

    if not isdir(prefix):
        from ..exceptions import EnvironmentLocationNotFound

        raise EnvironmentLocationNotFound(prefix)

    if not json:
        if format == "export":
            print_export_header(context.subdir)

    exitcode, output = list_packages(
        prefix,
        regex,
        format=format,
        reverse=reverse,
        show_channel_urls=show_channel_urls,
    )
    if context.json:
        stdout_json(output)

    else:
        print("\n".join(map(str, output)))

    return exitcode


def print_explicit(prefix, add_md5=False, remove_auth=True, add_sha256=False):
    from ..base.constants import UNKNOWN_CHANNEL
    from ..base.context import context
    from ..common import url as common_url
    from ..core.prefix_data import PrefixData

    if add_md5 and add_sha256:
        raise ValueError("Only one of add_md5 and add_sha256 can be chosen")
    if not isdir(prefix):
        from ..exceptions import EnvironmentLocationNotFound

        raise EnvironmentLocationNotFound(prefix)
    print_export_header(context.subdir)
    print("@EXPLICIT")
    for prefix_record in PrefixData(prefix).iter_records_sorted():
        url = prefix_record.get("url")
        if not url or url.startswith(UNKNOWN_CHANNEL):
            print("# no URL for: {}".format(prefix_record["fn"]))
            continue
        if remove_auth:
            url = common_url.remove_auth(common_url.split_anaconda_token(url)[0])
        if add_md5 or add_sha256:
            hash_key = "md5" if add_md5 else "sha256"
            hash_value = prefix_record.get(hash_key)
            print(url + (f"#{hash_value}" if hash_value else ""))
        else:
            print(url)


def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from ..gateways.disk.test import is_conda_environment
    from ..history import History
    from .common import stdout_json

    prefix = context.target_prefix
    if not is_conda_environment(prefix):
        from ..exceptions import EnvironmentLocationNotFound

        raise EnvironmentLocationNotFound(prefix)

    if args.md5 and args.sha256:
        from ..exceptions import ArgumentError

        raise ArgumentError(
            "Only one of --md5 and --sha256 can be specified at the same time"
        )

    regex = args.regex
    if args.full_name:
        regex = rf"^{regex}$"

    if args.revisions:
        h = History(prefix)
        if isfile(h.path):
            if not context.json:
                h.print_log()
            else:
                stdout_json(h.object_log())
        else:
            from ..exceptions import PathNotFoundError

            raise PathNotFoundError(h.path)
        return 0

    if args.explicit:
        print_explicit(prefix, args.md5, args.remove_auth, args.sha256)
        return 0

    if args.canonical:
        format = "canonical"
    elif args.export:
        format = "export"
    else:
        format = "human"

    if context.json:
        format = "canonical"

    return print_packages(
        prefix,
        regex,
        format,
        reverse=args.reverse,
        piplist=args.pip,
        json=context.json,
        show_channel_urls=context.show_channel_urls,
    )
