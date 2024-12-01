# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda install`.

Installs the specified packages into an existing environment.
"""

from __future__ import annotations

import sys
from argparse import _StoreTrueAction
from typing import TYPE_CHECKING

from ..deprecations import deprecated
from ..notices import notices

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from ..common.constants import NULL
    from .actions import NullCountAction
    from .helpers import (
        add_parser_create_install_update,
        add_parser_prune,
        add_parser_solver,
        add_parser_update_modifiers,
    )

    summary = "Install a list of packages into a specified conda environment."
    description = dals(
        f"""
        {summary}

        This command accepts a list of package specifications (e.g, bitarray=0.8)
        and installs a set of packages consistent with those specifications and
        compatible with the underlying environment. If full compatibility cannot
        be assured, an error is reported and the environment is not changed.

        Conda attempts to install the newest versions of the requested packages. To
        accomplish this, it may update some packages that are already installed, or
        install additional packages. To prevent existing packages from updating,
        use the --freeze-installed option. This may force conda to install older
        versions of the requested packages, and it does not prevent additional
        dependency packages from being installed.

        If you wish to skip dependency checking altogether, use the '--no-deps'
        option. This may result in an environment with incompatible packages, so
        this option must be used with great caution.

        conda can also be called with a list of explicit conda package filenames
        (e.g. ./lxml-3.2.0-py27_0.tar.bz2). Using conda in this mode implies the
        --no-deps option, and should likewise be used with great caution. Explicit
        filenames and package specifications cannot be mixed in a single command.
        """
    )
    epilog = dals(
        """
        Examples:

        Install the package 'scipy' into the currently-active environment::

            conda install scipy

        Install a list of packages into an environment, myenv::

            conda install -n myenv scipy curl wheel

        Install a specific version of 'python' into an environment, myenv::

            conda install -p path/to/myenv python=3.11

        """
    )

    p = sub_parsers.add_parser(
        "install",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    p.add_argument(
        "--revision",
        action="store",
        help="Revert to the specified REVISION.",
        metavar="REVISION",
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
        "-m",
        "--mkdir",
        action=deprecated.action(
            "24.9",
            "25.3",
            _StoreTrueAction,
            addendum="Use `conda create` instead.",
        ),
    )
    package_install_options.add_argument(
        "--clobber",
        action="store_true",
        default=NULL,
        help="Allow clobbering (i.e. overwriting) of overlapping file paths "
        "within packages and suppress related warnings.",
    )
    p.add_argument(
        "--dev",
        action=NullCountAction,
        help="Use `sys.executable -m conda` in wrapper scripts instead of CONDA_EXE. "
        "This is mainly for use during tests where we test new conda sources "
        "against old Python versions.",
        dest="dev",
        default=NULL,
    )
    p.set_defaults(func="conda.cli.main_install.execute")

    return p


@notices
def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from .install import install

    if context.force:
        print(
            "\n\n"
            "WARNING: The --force flag will be removed in a future conda release.\n"
            "         See 'conda install --help' for details about the --force-reinstall\n"
            "         and --clobber flags.\n"
            "\n",
            file=sys.stderr,
        )

    return install(args, parser, "install")
