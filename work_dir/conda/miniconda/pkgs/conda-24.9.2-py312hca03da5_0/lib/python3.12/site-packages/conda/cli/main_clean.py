# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""CLI implementation for `conda clean`.

Removes cached package tarballs, index files, package metadata, temporary files, and log files.
"""

from __future__ import annotations

import os
import sys
from logging import getLogger
from os.path import isdir, join
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace, _SubParsersAction
    from typing import Any, Iterable

log = getLogger(__name__)


def configure_parser(sub_parsers: _SubParsersAction, **kwargs) -> ArgumentParser:
    from ..auxlib.ish import dals
    from .actions import ExtendConstAction
    from .helpers import add_output_and_prompt_options

    summary = "Remove unused packages and caches."
    description = summary
    epilog = dals(
        """
        Examples::

            conda clean --tarballs
        """
    )

    p = sub_parsers.add_parser(
        "clean",
        help=summary,
        description=description,
        epilog=epilog,
        **kwargs,
    )

    removal_target_options = p.add_argument_group("Removal Targets")
    removal_target_options.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Remove index cache, lock files, unused cache packages, tarballs, and logfiles.",
    )
    removal_target_options.add_argument(
        "-i",
        "--index-cache",
        action="store_true",
        help="Remove index cache.",
    )
    removal_target_options.add_argument(
        "-p",
        "--packages",
        action="store_true",
        help="Remove unused packages from writable package caches. "
        "WARNING: This does not check for packages installed using "
        "symlinks back to the package cache.",
    )
    removal_target_options.add_argument(
        "-t",
        "--tarballs",
        action="store_true",
        help="Remove cached package tarballs.",
    )
    removal_target_options.add_argument(
        "-f",
        "--force-pkgs-dirs",
        action="store_true",
        help="Remove *all* writable package caches. This option is not included with the --all "
        "flag. WARNING: This will break environments with packages installed using symlinks "
        "back to the package cache.",
    )
    removal_target_options.add_argument(
        "-c",  # for tempfile extension (.c~)
        "--tempfiles",
        const=sys.prefix,
        action=ExtendConstAction,
        help=(
            "Remove temporary files that could not be deleted earlier due to being in-use.  "
            "The argument for the --tempfiles flag is a path (or list of paths) to the "
            "environment(s) where the tempfiles should be found and removed."
        ),
    )
    removal_target_options.add_argument(
        "-l",
        "--logfiles",
        action="store_true",
        help="Remove log files.",
    )

    add_output_and_prompt_options(p)

    p.set_defaults(func="conda.cli.main_clean.execute")

    return p


def _get_size(*parts: str, warnings: list[str] | None) -> int:
    path = join(*parts)
    try:
        stat = os.lstat(path)
    except OSError as e:
        if warnings is None:
            raise
        warnings.append(f"WARNING: {path}: {e}")

        # let the user deal with the issue
        raise NotImplementedError
    else:
        # TODO: This doesn't handle packages that have hard links to files within
        # themselves, like bin/python3.3 and bin/python3.3m in the Python package
        if stat.st_nlink > 1:
            raise NotImplementedError

        return stat.st_size


def _get_pkgs_dirs(pkg_sizes: dict[str, dict[str, int]]) -> dict[str, tuple[str, ...]]:
    return {pkgs_dir: tuple(pkgs) for pkgs_dir, pkgs in pkg_sizes.items()}


def _get_total_size(pkg_sizes: dict[str, dict[str, int]]) -> int:
    return sum(sum(pkgs.values()) for pkgs in pkg_sizes.values())


def _rm_rf(*parts: str, quiet: bool, verbose: bool) -> None:
    from ..gateways.disk.delete import rm_rf

    path = join(*parts)
    try:
        if rm_rf(path):
            if not quiet and verbose:
                print(f"Removed {path}")
        elif not quiet:
            print(f"WARNING: cannot remove, file permissions: {path}")
    except OSError as e:
        if not quiet:
            print(f"WARNING: cannot remove, file permissions: {path}\n{e!r}")
        else:
            log.info("%r", e)


def find_tarballs() -> dict[str, Any]:
    from ..base.constants import CONDA_PACKAGE_EXTENSIONS, CONDA_PACKAGE_PARTS

    warnings: list[str] = []
    pkg_sizes: dict[str, dict[str, int]] = {}
    for pkgs_dir in find_pkgs_dirs():
        # tarballs are files in pkgs_dir
        _, _, tars = next(os.walk(pkgs_dir))
        for tar in tars:
            # tarballs also end in .tar.bz2, .conda, .tar.bz2.part, or .conda.part
            if not tar.endswith((*CONDA_PACKAGE_EXTENSIONS, *CONDA_PACKAGE_PARTS)):
                continue

            # get size
            try:
                size = _get_size(pkgs_dir, tar, warnings=warnings)
            except NotImplementedError:
                pass
            else:
                pkg_sizes.setdefault(pkgs_dir, {})[tar] = size

    return {
        "warnings": warnings,
        "pkg_sizes": pkg_sizes,
        "pkgs_dirs": _get_pkgs_dirs(pkg_sizes),
        "total_size": _get_total_size(pkg_sizes),
    }


def find_pkgs() -> dict[str, Any]:
    warnings: list[str] = []
    pkg_sizes: dict[str, dict[str, int]] = {}
    for pkgs_dir in find_pkgs_dirs():
        # pkgs are directories in pkgs_dir
        _, pkgs, _ = next(os.walk(pkgs_dir))
        for pkg in pkgs:
            # pkgs also have an info directory
            if not isdir(join(pkgs_dir, pkg, "info")):
                continue

            # get size
            try:
                size = sum(
                    _get_size(root, file, warnings=warnings)
                    for root, _, files in os.walk(join(pkgs_dir, pkg))
                    for file in files
                )
            except NotImplementedError:
                pass
            else:
                pkg_sizes.setdefault(pkgs_dir, {})[pkg] = size

    return {
        "warnings": warnings,
        "pkg_sizes": pkg_sizes,
        "pkgs_dirs": _get_pkgs_dirs(pkg_sizes),
        "total_size": _get_total_size(pkg_sizes),
    }


def rm_pkgs(
    pkgs_dirs: dict[str, tuple[str]],
    warnings: list[str],
    total_size: int,
    pkg_sizes: dict[str, dict[str, int]],
    *,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
    name: str,
) -> None:
    from ..base.context import context
    from ..utils import human_bytes
    from .common import confirm_yn

    if not quiet and warnings:
        for warning in warnings:
            print(warning)

    if not any(pkgs for pkgs in pkg_sizes.values()):
        if not quiet:
            print(f"There are no unused {name} to remove.")
        return

    if not quiet:
        if verbose:
            print(f"Will remove the following {name}:")
            for pkgs_dir, pkgs in pkg_sizes.items():
                print(f"  {pkgs_dir}")
                print(f"  {'-' * len(pkgs_dir)}")
                for pkg, size in pkgs.items():
                    print(f"  - {pkg:<40} {human_bytes(size):>10}")
                print()
            print("-" * 17)
            print(f"Total: {human_bytes(total_size):>10}")
            print()
        else:
            count = sum(len(pkgs) for pkgs in pkg_sizes.values())
            print(f"Will remove {count} ({human_bytes(total_size)}) {name}.")

    if dry_run:
        return
    if not context.json or not context.always_yes:
        confirm_yn()

    for pkgs_dir, pkgs in pkg_sizes.items():
        for pkg in pkgs:
            _rm_rf(pkgs_dir, pkg, quiet=quiet, verbose=verbose)


def find_index_cache() -> list[str]:
    files = []
    for pkgs_dir in find_pkgs_dirs():
        # caches are directories in pkgs_dir
        path = join(pkgs_dir, "cache")
        if isdir(path):
            files.append(path)
    return files


def find_pkgs_dirs() -> list[str]:
    from ..core.package_cache_data import PackageCacheData

    return [
        pc.pkgs_dir for pc in PackageCacheData.writable_caches() if isdir(pc.pkgs_dir)
    ]


def find_tempfiles(paths: Iterable[str]) -> list[str]:
    from ..base.constants import CONDA_TEMP_EXTENSIONS

    tempfiles = []
    for path in sorted(set(paths or [sys.prefix])):
        # tempfiles are files in path
        for root, _, files in os.walk(path):
            for file in files:
                # tempfiles also end in .c~ or .trash
                if not file.endswith(CONDA_TEMP_EXTENSIONS):
                    continue

                tempfiles.append(join(root, file))

    return tempfiles


def find_logfiles() -> list[str]:
    from ..base.constants import CONDA_LOGS_DIR

    files = []
    for pkgs_dir in find_pkgs_dirs():
        # .logs are directories in pkgs_dir
        path = join(pkgs_dir, CONDA_LOGS_DIR)
        if not isdir(path):
            continue

        try:
            # logfiles are files in .logs
            _, _, logs = next(os.walk(path))
            files.extend([join(path, log) for log in logs])
        except StopIteration:
            # StopIteration: .logs is empty
            pass

    return files


def rm_items(
    items: list[str],
    *,
    quiet: bool,
    verbose: bool,
    dry_run: bool,
    name: str,
) -> None:
    from ..base.context import context
    from .common import confirm_yn

    if not items:
        if not quiet:
            print(f"There are no {name} to remove.")
        return

    if not quiet:
        if verbose:
            print(f"Will remove the following {name}:")
            for item in items:
                print(f"  - {item}")
            print()
        else:
            print(f"Will remove {len(items)} {name}.")

    if dry_run:
        return
    if not context.json or not context.always_yes:
        confirm_yn()

    for item in items:
        _rm_rf(item, quiet=quiet, verbose=verbose)


def _execute(args, parser):
    from ..base.context import context

    json_result = {"success": True}
    kwargs = {
        "quiet": context.json or context.quiet,
        "verbose": context.verbose,
        "dry_run": context.dry_run,
    }

    if args.force_pkgs_dirs:
        json_result["pkgs_dirs"] = pkgs_dirs = find_pkgs_dirs()
        rm_items(pkgs_dirs, **kwargs, name="package cache(s)")

        # we return here because all other clean operations target individual parts of
        # package caches
        return json_result

    if not (
        args.all
        or args.tarballs
        or args.index_cache
        or args.packages
        or args.tempfiles
        or args.logfiles
    ):
        from ..exceptions import ArgumentError

        raise ArgumentError(
            "At least one removal target must be given. See 'conda clean --help'."
        )

    if args.tarballs or args.all:
        json_result["tarballs"] = tars = find_tarballs()
        rm_pkgs(**tars, **kwargs, name="tarball(s)")

    if args.index_cache or args.all:
        cache = find_index_cache()
        json_result["index_cache"] = {"files": cache}
        rm_items(cache, **kwargs, name="index cache(s)")

    if args.packages or args.all:
        json_result["packages"] = pkgs = find_pkgs()
        rm_pkgs(**pkgs, **kwargs, name="package(s)")

    if args.tempfiles or args.all:
        json_result["tempfiles"] = tmps = find_tempfiles(args.tempfiles)
        rm_items(tmps, **kwargs, name="tempfile(s)")

    if args.logfiles or args.all:
        json_result["logfiles"] = logs = find_logfiles()
        rm_items(logs, **kwargs, name="logfile(s)")

    return json_result


def execute(args: Namespace, parser: ArgumentParser) -> int:
    from ..base.context import context
    from .common import stdout_json

    json_result = _execute(args, parser)
    if context.json:
        stdout_json(json_result)
    if args.dry_run:
        from ..exceptions import DryRunExit

        raise DryRunExit
    return 0
