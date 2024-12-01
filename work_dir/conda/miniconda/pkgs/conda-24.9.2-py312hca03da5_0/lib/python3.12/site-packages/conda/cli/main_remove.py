# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda remove`.

Removes the specified packages from an existing environment.
"""

import logging
from argparse import ArgumentParser, Namespace, _SubParsersAction
from os.path import isfile, join

from .common import confirm_yn

log = logging.getLogger(__name__)


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from ..common.constants import NULL
    from .actions import NullCountAction
    from .helpers import (
        add_output_and_prompt_options,
        add_parser_channels,
        add_parser_networking,
        add_parser_prefix,
        add_parser_prune,
        add_parser_pscheck,
        add_parser_solver,
    )

    summary = "Remove a list of packages from a specified conda environment. "
    description = dals(
        f"""
        {summary}

        Use `--all` flag to remove all packages and the environment itself.

        This command will also remove any package that depends on any of the
        specified packages as well---unless a replacement can be found without
        that dependency. If you wish to skip this dependency checking and remove
        just the requested packages, add the '--force' option. Note however that
        this may result in a broken environment, so use this with caution.
        """
    )
    epilog = dals(
        """
        Examples:

        Remove the package 'scipy' from the currently-active environment::

            conda remove scipy

        Remove a list of packages from an environment 'myenv'::

            conda remove -n myenv scipy curl wheel

        Remove all packages from environment `myenv` and the environment itself::

            conda remove -n myenv --all

        Remove all packages from the environment `myenv` but retain the environment::

            conda remove -n myenv --all --keep-env

        """
    )

    p = sub_parsers.add_parser(
        "remove",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )
    add_parser_pscheck(p)

    add_parser_prefix(p)
    add_parser_channels(p)

    solver_mode_options = p.add_argument_group("Solver Mode Modifiers")
    solver_mode_options.add_argument(
        "--features",
        action="store_true",
        help="Remove features (instead of packages).",
    )
    solver_mode_options.add_argument(
        "--force-remove",
        "--force",
        action="store_true",
        help="Forces removal of a package without removing packages that depend on it. "
        "Using this option will usually leave your environment in a broken and "
        "inconsistent state.",
        dest="force_remove",
    )
    solver_mode_options.add_argument(
        "--no-pin",
        action="store_true",
        dest="ignore_pinned",
        default=NULL,
        help="Ignore pinned package(s) that apply to the current operation. "
        "These pinned packages might come from a .condarc file or a file in "
        "<TARGET_ENVIRONMENT>/conda-meta/pinned.",
    )
    add_parser_prune(solver_mode_options)
    add_parser_solver(solver_mode_options)

    add_parser_networking(p)
    add_output_and_prompt_options(p)

    p.add_argument(
        "--all",
        action="store_true",
        help="Remove all packages, i.e., the entire environment.",
    )
    p.add_argument(
        "--keep-env",
        action="store_true",
        help="Used with `--all`, delete all packages but keep the environment.",
    )
    p.add_argument(
        "package_names",
        metavar="package_name",
        action="store",
        nargs="*",
        help="Package names to remove from the environment.",
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

    p.set_defaults(func="conda.cli.main_remove.execute")

    return p


def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from ..core.envs_manager import unregister_env
    from ..core.link import PrefixSetup, UnlinkLinkTransaction
    from ..core.prefix_data import PrefixData
    from ..exceptions import (
        CondaEnvironmentError,
        CondaValueError,
        DirectoryNotACondaEnvironmentError,
        EnvironmentLocationNotFound,
        PackagesNotFoundError,
    )
    from ..gateways.disk.delete import path_is_clean, rm_rf
    from ..gateways.disk.test import is_conda_environment
    from ..models.match_spec import MatchSpec
    from .common import check_non_admin, specs_from_args
    from .install import handle_txn

    if not (args.all or args.package_names):
        raise CondaValueError(
            "no package names supplied,\n"
            '       try "conda remove -h" for more details'
        )

    prefix = context.target_prefix
    check_non_admin()

    if not is_conda_environment(prefix):
        raise EnvironmentLocationNotFound(prefix)

    if args.all and prefix == context.default_prefix:
        msg = "Cannot remove current environment. Deactivate and run conda remove again"
        raise CondaEnvironmentError(msg)

    if args.all and path_is_clean(prefix):
        return 0

    if args.all:
        if prefix == context.root_prefix:
            raise CondaEnvironmentError(
                "cannot remove root environment, add -n NAME or -p PREFIX option"
            )
        if not isfile(join(prefix, "conda-meta", "history")):
            raise DirectoryNotACondaEnvironmentError(prefix)
        if not args.json:
            print(f"\nRemove all packages in environment {prefix}:\n")

        if "package_names" in args:
            stp = PrefixSetup(
                target_prefix=prefix,
                unlink_precs=tuple(PrefixData(prefix).iter_records()),
                link_precs=(),
                remove_specs=(),
                update_specs=(),
                neutered_specs={},
            )
            txn = UnlinkLinkTransaction(stp)
            try:
                handle_txn(txn, prefix, args, False, True)
            except PackagesNotFoundError:
                if not args.json:
                    print(
                        f"No packages found in {prefix}. Continuing environment removal"
                    )
        if not context.dry_run:
            if not args.keep_env:
                if not args.json:
                    confirm_yn(
                        f"Everything found within the environment ({prefix}), including any conda environment configurations and any non-conda files, will be deleted. Do you wish to continue?\n",
                        default="no",
                        dry_run=False,
                    )
                rm_rf(prefix)
                unregister_env(prefix)

        return 0

    else:
        if args.features:
            specs = tuple(MatchSpec(track_features=f) for f in set(args.package_names))
        else:
            specs = specs_from_args(args.package_names)
        channel_urls = ()
        subdirs = ()
        solver_backend = context.plugin_manager.get_cached_solver_backend()
        solver = solver_backend(prefix, channel_urls, subdirs, specs_to_remove=specs)
        txn = solver.solve_for_transaction()
        handle_txn(txn, prefix, args, False, True)
        return 0
