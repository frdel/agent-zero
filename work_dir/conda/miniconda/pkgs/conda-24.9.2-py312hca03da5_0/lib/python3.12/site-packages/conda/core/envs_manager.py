# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for managing conda environments."""

from __future__ import annotations

import os
from errno import EACCES, ENOENT, EROFS
from logging import getLogger
from os.path import dirname, isdir, isfile, join, normpath
from typing import TYPE_CHECKING

from ..base.context import context
from ..common._os import is_admin
from ..common.compat import ensure_text_type, on_win, open_utf8
from ..common.path import expand
from ..gateways.disk.read import yield_lines
from ..gateways.disk.test import is_conda_environment
from .prefix_data import PrefixData

if TYPE_CHECKING:
    from typing import Iterator

log = getLogger(__name__)


def get_user_environments_txt_file(userhome: str = "~") -> str:
    """
    Gets the path to the user's environments.txt file.

    :param userhome: The home directory of the user.
    :type userhome: str
    :return: Path to the environments.txt file.
    :rtype: str
    """
    return expand(join(userhome, ".conda", "environments.txt"))


def register_env(location: str) -> None:
    """
    Registers an environment by adding it to environments.txt file.

    :param location: The file path of the environment to register.
    :type location: str
    :return: None
    """
    if not context.register_envs:
        return

    user_environments_txt_file = get_user_environments_txt_file()
    location = normpath(location)
    folder = dirname(location)
    try:
        os.makedirs(folder)
    except:
        pass

    if (
        "placehold_pl" in location
        or "skeleton_" in location
        or user_environments_txt_file == os.devnull
    ):
        # Don't record envs created by conda-build.
        return

    if location in yield_lines(user_environments_txt_file):
        # Nothing to do. Location is already recorded in a known environments.txt file.
        return

    user_environments_txt_directory = os.path.dirname(user_environments_txt_file)
    try:
        os.makedirs(user_environments_txt_directory, exist_ok=True)
    except OSError as exc:
        log.warning(
            "Unable to register environment. "
            f"Could not create {user_environments_txt_directory}. "
            f"Reason: {exc}"
        )
        return

    try:
        with open_utf8(user_environments_txt_file, "a") as fh:
            fh.write(ensure_text_type(location))
            fh.write("\n")
    except OSError as e:
        if e.errno in (EACCES, EROFS, ENOENT):
            log.warning(
                "Unable to register environment. Path not writable or missing.\n"
                "  environment location: %s\n"
                "  registry file: %s",
                location,
                user_environments_txt_file,
            )
        else:
            raise


def unregister_env(location: str) -> None:
    """
    Unregisters an environment by removing its entry from the environments.txt file if certain conditions are met.

    The environment is only unregistered if its associated 'conda-meta' directory exists and contains no significant files other than 'history'. If these conditions are met, the environment's path is removed from environments.txt.

    :param location: The file path of the environment to unregister.
    :type location: str
    :return: None
    """
    if isdir(location):
        meta_dir = join(location, "conda-meta")
        if isdir(meta_dir):
            meta_dir_contents = tuple(entry.name for entry in os.scandir(meta_dir))
            if len(meta_dir_contents) > 1:
                # if there are any files left other than 'conda-meta/history'
                #   then don't unregister
                return

    _clean_environments_txt(get_user_environments_txt_file(), location)


def list_all_known_prefixes() -> list[str]:
    """
    Lists all known conda environment prefixes.

    :return: A list of all known conda environment prefixes.
    :rtype: List[str]
    """
    all_env_paths = set()
    # If the user is an admin, load environments from all user home directories
    if is_admin():
        if on_win:
            home_dir_dir = dirname(expand("~"))
            search_dirs = tuple(entry.path for entry in os.scandir(home_dir_dir))
        else:
            from pwd import getpwall

            search_dirs = tuple(pwentry.pw_dir for pwentry in getpwall()) or (
                expand("~"),
            )
    else:
        search_dirs = (expand("~"),)
    for home_dir in filter(None, search_dirs):
        environments_txt_file = get_user_environments_txt_file(home_dir)
        if isfile(environments_txt_file):
            try:
                # When the user is an admin, some environments.txt files might
                # not be readable (if on network file system for example)
                all_env_paths.update(_clean_environments_txt(environments_txt_file))
            except PermissionError:
                log.warning(f"Unable to access {environments_txt_file}")

    # in case environments.txt files aren't complete, also add all known conda environments in
    # all envs_dirs
    envs_dirs = (envs_dir for envs_dir in context.envs_dirs if isdir(envs_dir))
    all_env_paths.update(
        path
        for path in (
            entry.path for envs_dir in envs_dirs for entry in os.scandir(envs_dir)
        )
        if path not in all_env_paths and is_conda_environment(path)
    )

    all_env_paths.add(context.root_prefix)
    return sorted(all_env_paths)


def query_all_prefixes(spec: str) -> Iterator[tuple[str, tuple]]:
    """
    Queries all known prefixes for a given specification.

    :param spec: The specification to query for.
    :type spec: str
    :return: An iterator of tuples containing the prefix and the query results.
    :rtype: Iterator[Tuple[str, Tuple]]
    """
    for prefix in list_all_known_prefixes():
        prefix_recs = tuple(PrefixData(prefix).query(spec))
        if prefix_recs:
            yield prefix, prefix_recs


def _clean_environments_txt(
    environments_txt_file: str,
    remove_location: str | None = None,
) -> tuple[str, ...]:
    """
    Cleans the environments.txt file by removing specified locations.

    :param environments_txt_file: The file path of environments.txt.
    :param remove_location: Optional location to remove from the file.
    :type environments_txt_file: str
    :type remove_location: Optional[str]
    :return: A tuple of the cleaned lines.
    :rtype: Tuple[str, ...]
    """
    if not isfile(environments_txt_file):
        return ()

    if remove_location:
        remove_location = normpath(remove_location)
    environments_txt_lines = tuple(yield_lines(environments_txt_file))
    environments_txt_lines_cleaned = tuple(
        prefix
        for prefix in environments_txt_lines
        if prefix != remove_location and is_conda_environment(prefix)
    )
    if environments_txt_lines_cleaned != environments_txt_lines:
        _rewrite_environments_txt(environments_txt_file, environments_txt_lines_cleaned)
    return environments_txt_lines_cleaned


def _rewrite_environments_txt(environments_txt_file: str, prefixes: list[str]) -> None:
    """
    Rewrites the environments.txt file with the specified prefixes.

    :param environments_txt_file: The file path of environments.txt.
    :param prefixes: List of prefixes to write into the file.
    :type environments_txt_file: str
    :type prefixes: List[str]
    :return: None
    """
    try:
        with open_utf8(environments_txt_file, "w") as fh:
            fh.write("\n".join(prefixes))
            fh.write("\n")
    except OSError as e:
        log.info("File not cleaned: %s", environments_txt_file)
        log.debug("%r", e, exc_info=True)
