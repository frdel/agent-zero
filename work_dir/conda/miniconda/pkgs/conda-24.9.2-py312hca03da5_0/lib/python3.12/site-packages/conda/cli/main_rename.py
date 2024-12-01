# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda rename`.

Renames an existing environment by cloning it and then removing the original environment.
"""

from __future__ import annotations

import os
from argparse import _StoreTrueAction
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from conda.deprecations import deprecated
from conda.exceptions import CondaEnvException
from conda.gateways.disk.test import is_conda_environment

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .helpers import add_output_and_prompt_options, add_parser_prefix

    summary = "Rename an existing environment."
    description = dals(
        f"""
        {summary}

        This command renames a conda environment via its name (-n/--name) or
        its prefix (-p/--prefix).

        The base environment and the currently-active environment cannot be renamed.
        """
    )
    epilog = dals(
        """
        Examples::

            conda rename -n test123 test321

            conda rename --name test123 test321

            conda rename -p path/to/test123 test321

            conda rename --prefix path/to/test123 test321

        """
    )

    p = sub_parsers.add_parser(
        "rename",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    # Add name and prefix args
    add_parser_prefix(p)

    p.add_argument("destination", help="New name for the conda environment.")
    p.add_argument(
        "-f",
        "--force",
        dest="yes",
        help="Force rename of an environment.",
        action=deprecated.action(
            "24.9",
            "25.3",
            _StoreTrueAction,
            addendum="Use `--yes` instead.",
        ),
        default=False,
    )

    add_output_and_prompt_options(p)

    p.set_defaults(func="conda.cli.main_rename.execute")

    return p


def check_protected_dirs(prefix: str | Path, json: bool = False) -> None:
    """Ensure that the new prefix does not contain protected directories."""

    if is_conda_environment(Path(prefix).parent):
        raise CondaEnvException(
            f"The specified prefix '{prefix}' "
            "appears to be a top level directory within an existing conda environment "
            "(i.e., {history_file} exists). Creating an environment in this location "
            "has the potential to irreversibly corrupt your conda installation and/or "
            "other conda environments, please choose a different location for your "
            "new conda environment. Aborting.",
            json,
        )


def validate_src() -> str:
    """
    Ensure that we are receiving at least one valid value for the environment
    to be renamed and that the "base" environment is not being renamed
    """
    from ..base.context import context
    from .install import validate_prefix_exists

    prefix = Path(context.target_prefix)
    validate_prefix_exists(prefix)

    if prefix.samefile(context.root_prefix):
        raise CondaEnvException("The 'base' environment cannot be renamed")
    if context.active_prefix and prefix.samefile(context.active_prefix):
        raise CondaEnvException("Cannot rename the active environment")
    else:
        check_protected_dirs(prefix)

    return str(prefix)


@deprecated(
    "25.3",
    "25.9",
    addendum="Use `conda.cli.install.validate_new_prefix` instead.",
)
def validate_destination(dest: str, force: bool = False) -> str:
    """Ensure that our destination does not exist"""
    from ..base.context import context, validate_prefix_name
    from ..common.path import expand
    from ..exceptions import CondaEnvException

    if os.sep in dest:
        dest = expand(dest)
    else:
        dest = validate_prefix_name(dest, ctx=context, allow_base=False)
    if not force and os.path.exists(dest):
        env_name = os.path.basename(os.path.normpath(dest))
        raise CondaEnvException(
            f"The environment '{env_name}' already exists. Override with --yes."
        )
    return dest


def execute(args: Namespace, parser: ArgumentParser) -> int:
    """Executes the command for renaming an existing environment."""
    from ..base.constants import DRY_RUN_PREFIX
    from ..base.context import context
    from ..cli import install
    from ..gateways.disk.delete import rm_rf
    from ..gateways.disk.update import rename_context
    from .install import validate_new_prefix

    source = validate_src()
    destination = validate_new_prefix(args.destination, force=args.yes)

    def clone_and_remove() -> None:
        actions: tuple[partial, ...] = (
            partial(
                install.clone,
                source,
                destination,
                quiet=context.quiet,
                json=context.json,
            ),
            partial(rm_rf, source),
        )

        # We now either run collected actions or print dry run statement
        for func in actions:
            if args.dry_run:
                print(f"{DRY_RUN_PREFIX} {func.func.__name__} {','.join(func.args)}")
            else:
                func()

    if args.yes:
        with rename_context(destination, dry_run=args.dry_run):
            clone_and_remove()
    else:
        clone_and_remove()
    return 0
