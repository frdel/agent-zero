# Copyright 2019-2020 Lawrence Livermore National Security, LLC and other
# Archspec Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)
"""
archspec command line interface
"""

import argparse
import typing

import archspec
import archspec.cpu


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        "archspec",
        description="archspec command line interface",
        add_help=False,
    )
    parser.add_argument(
        "--version",
        "-V",
        help="Show the version and exit.",
        action="version",
        version=f"archspec, version {archspec.__version__}",
    )
    parser.add_argument("--help", "-h", help="Show the help and exit.", action="help")

    subcommands = parser.add_subparsers(
        title="command",
        metavar="COMMAND",
        dest="command",
    )

    cpu_command = subcommands.add_parser(
        "cpu",
        help="archspec command line interface for CPU",
        description="archspec command line interface for CPU",
    )
    cpu_command.set_defaults(run=cpu)

    return parser


def cpu() -> int:
    """Run the `archspec cpu` subcommand."""
    try:
        print(archspec.cpu.host())
    except FileNotFoundError as exc:
        print(exc)
        return 1
    return 0


def main(argv: typing.Optional[typing.List[str]] = None) -> int:
    """Run the `archspec` command line interface."""
    parser = _make_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as err:
        return err.code

    if args.command is None:
        parser.print_help()
        return 0

    return args.run()
