# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda update`.

Updates the specified packages in an existing environment.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ..notices import notices

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from ..common.constants import NULL
    from .helpers import (
        add_parser_create_install_update,
        add_parser_prune,
        add_parser_solver,
        add_parser_update_modifiers,
    )

    summary = "Update conda packages to the latest compatible version."
    description = dals(
        f"""
        {summary}

        This command accepts a list of package names and updates them to the latest
        versions that are compatible with all other packages in the environment.

        Conda attempts to install the newest versions of the requested packages. To
        accomplish this, it may update some packages that are already installed, or
        install additional packages. To prevent existing packages from updating,
        use the --no-update-deps option. This may force conda to install older
        versions of the requested packages, and it does not prevent additional
        dependency packages from being installed.
        """
    )
    epilog = dals(
        """
        Examples:

            conda update -n myenv scipy

        """
    )

    p = sub_parsers.add_parser(
        "update",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    solver_mode_options, package_install_options, _ = add_parser_create_install_update(
        p
    )

    add_parser_prune(solver_mode_options)
    add_parser_solver(solver_mode_options)
    solver_mode_options.add_argument(
        "--force-reinstall",
        action="store_true",
        default=NULL,
        help="Ensure that any user-requested package for the current operation is uninstalled and "
        "reinstalled, even if that package already exists in the environment.",
    )
    add_parser_update_modifiers(solver_mode_options)

    package_install_options.add_argument(
        "--clobber",
        action="store_true",
        default=NULL,
        help="Allow clobbering of overlapping file paths within packages, "
        "and suppress related warnings.",
    )
    p.set_defaults(func="conda.cli.main_update.execute")

    return p


@notices
def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from .install import install

    if context.force:
        print(
            "\n\n"
            "WARNING: The --force flag will be removed in a future conda release.\n"
            "         See 'conda update --help' for details about the --force-reinstall\n"
            "         and --clobber flags.\n"
            "\n",
            file=sys.stderr,
        )

    install(args, parser, "update")
    return 0
