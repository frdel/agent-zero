# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Disk utility functions for deleting files and folders."""

from __future__ import annotations

import fnmatch
import os
import shutil
import sys
from logging import getLogger
from os.path import (
    abspath,
    basename,
    dirname,
    exists,
    isdir,
    isfile,
    join,
    normpath,
    split,
)
from subprocess import STDOUT, CalledProcessError, check_output

from ...base.constants import CONDA_TEMP_EXTENSION
from ...base.context import context
from ...common.compat import on_win
from ...common.constants import TRACE
from ...deprecations import deprecated
from . import MAX_TRIES
from .link import islink, lexists
from .permissions import make_writable

if not on_win:
    from shutil import which


log = getLogger(__name__)


def rmtree(path):
    # subprocessing to delete large folders can be quite a bit faster
    path = normpath(path)
    if on_win:
        try:
            # the fastest way seems to be using DEL to recursively delete files
            # https://www.ghacks.net/2017/07/18/how-to-delete-large-folders-in-windows-super-fast/
            # However, this is not entirely safe, as it can end up following symlinks to folders
            # https://superuser.com/a/306618/184799
            # so, we stick with the slower, but hopefully safer way.  Maybe if we figured out how
            #    to scan for any possible symlinks, we could do the faster way.
            # out = check_output('DEL /F/Q/S *.* > NUL 2> NUL'.format(path), shell=True,
            #                    stderr=STDOUT, cwd=path)

            out = check_output(
                f'RD /S /Q "{path}" > NUL 2> NUL', shell=True, stderr=STDOUT
            )
        except:
            try:
                # Try to delete in Unicode
                name = None
                from ...auxlib.compat import Utf8NamedTemporaryFile
                from ...utils import quote_for_shell

                with Utf8NamedTemporaryFile(
                    mode="w", suffix=".bat", delete=False
                ) as batch_file:
                    batch_file.write(f"RD /S {quote_for_shell(path)}\n")
                    batch_file.write("chcp 65001\n")
                    batch_file.write(f"RD /S {quote_for_shell(path)}\n")
                    batch_file.write("EXIT 0\n")
                    name = batch_file.name
                # If the above is bugged we can end up deleting hard-drives, so we check
                # that 'path' appears in it. This is not bulletproof but it could save you (me).
                with open(name) as contents:
                    content = contents.read()
                    assert path in content
                comspec = os.getenv("COMSPEC")
                CREATE_NO_WINDOW = 0x08000000
                # It is essential that we `pass stdout=None, stderr=None, stdin=None` here because
                # if we do not, then the standard console handles get attached and chcp affects the
                # parent process (and any which share those console handles!)
                out = check_output(
                    [comspec, "/d", "/c", name],
                    shell=False,
                    stdout=None,
                    stderr=None,
                    stdin=None,
                    creationflags=CREATE_NO_WINDOW,
                )

            except CalledProcessError as e:
                if e.returncode != 5:
                    log.error(
                        f"Removing folder {name} the fast way failed.  Output was: {out}"
                    )
                    raise
                else:
                    log.debug(
                        f"removing dir contents the fast way failed.  Output was: {out}"
                    )
    else:
        try:
            os.makedirs(".empty")
        except:
            pass
        # yes, this looks strange.  See
        #    https://unix.stackexchange.com/a/79656/34459
        #    https://web.archive.org/web/20130929001850/http://linuxnote.net/jianingy/en/linux/a-fast-way-to-remove-huge-number-of-files.html  # NOQA

        if isdir(".empty"):
            rsync = which("rsync")

            if rsync:
                try:
                    out = check_output(
                        [
                            rsync,
                            "-a",
                            "--force",
                            "--delete",
                            join(os.getcwd(), ".empty") + "/",
                            path + "/",
                        ],
                        stderr=STDOUT,
                    )
                except CalledProcessError:
                    log.debug(
                        f"removing dir contents the fast way failed.  Output was: {out}"
                    )

            shutil.rmtree(".empty")
    shutil.rmtree(path)


def unlink_or_rename_to_trash(path):
    """If files are in use, especially on windows, we can't remove them.
    The fallback path is to rename them (but keep their folder the same),
    which maintains the file handle validity.  See comments at:
    https://serverfault.com/a/503769
    """
    try:
        make_writable(path)
        os.unlink(path)
    except OSError:
        try:
            os.rename(path, path + ".conda_trash")
        except OSError:
            if on_win:
                # on windows, it is important to use the rename program, as just using python's
                #    rename leads to permission errors when files are in use.
                condabin_dir = join(context.conda_prefix, "condabin")
                trash_script = join(condabin_dir, "rename_tmp.bat")
                if exists(trash_script):
                    _dirname, _fn = split(path)
                    dest_fn = path + ".conda_trash"
                    counter = 1
                    while isfile(dest_fn):
                        dest_fn = dest_fn.splitext[0] + f".conda_trash_{counter}"
                        counter += 1
                    out = "< empty >"
                    try:
                        out = check_output(
                            [
                                "cmd.exe",
                                "/C",
                                trash_script,
                                _dirname,
                                _fn,
                                basename(dest_fn),
                            ],
                            stderr=STDOUT,
                        )
                    except CalledProcessError:
                        log.debug(
                            f"renaming file path {path} to trash failed.  Output was: {out}"
                        )

                else:
                    log.debug(
                        f"{trash_script} is missing.  Conda was not installed correctly or has been "
                        "corrupted.  Please file an issue on the conda github repo."
                    )
            log.warning(
                f"Could not remove or rename {path}.  Please remove this file manually (you "
                "may need to reboot to free file handles)"
            )


def remove_empty_parent_paths(path):
    # recurse to clean up empty folders that were created to have a nested hierarchy
    parent_path = dirname(path)

    while isdir(parent_path) and not next(os.scandir(parent_path), None):
        os.rmdir(parent_path)
        parent_path = dirname(parent_path)


@deprecated.argument("25.3", "25.9", "max_retries")
@deprecated.argument("25.3", "25.9", "trash")
def rm_rf(path: str | os.PathLike, clean_empty_parents: bool = False) -> bool:
    """
    Completely delete path
    max_retries is the number of times to retry on failure. The default is 5. This only applies
    to deleting a directory.
    If removing path fails and trash is True, files will be moved to the trash directory.
    """
    try:
        path = abspath(path)
        log.log(TRACE, "rm_rf %s", path)
        if isdir(path) and not islink(path):
            backoff_rmdir(path)
        elif lexists(path):
            unlink_or_rename_to_trash(path)
        else:
            log.log(TRACE, "rm_rf failed. Not a link, file, or directory: %s", path)
    finally:
        if lexists(path):
            log.info("rm_rf failed for %s", path)
            return False
    if isdir(path):
        delete_trash(path)
    if clean_empty_parents:
        remove_empty_parent_paths(path)
    return True


# aliases that all do the same thing (legacy compat)
deprecated.constant("25.3", "25.9", "try_rmdir_all_empty", rm_rf)
deprecated.constant("25.3", "25.9", "move_to_trash", rm_rf)
deprecated.constant("25.3", "25.9", "move_path_to_trash", rm_rf)


def delete_trash(prefix):
    if not prefix:
        prefix = sys.prefix
    exclude = {"envs", "pkgs"}
    for root, dirs, files in os.walk(prefix, topdown=True):
        dirs[:] = [d for d in dirs if d not in exclude]
        for fn in files:
            if fnmatch.fnmatch(fn, "*.conda_trash*") or fnmatch.fnmatch(
                fn, "*" + CONDA_TEMP_EXTENSION
            ):
                filename = join(root, fn)
                try:
                    os.unlink(filename)
                    remove_empty_parent_paths(filename)
                except OSError as e:
                    log.debug("%r errno %d\nCannot unlink %s.", e, e.errno, filename)


def backoff_rmdir(dirpath, max_tries=MAX_TRIES):
    if not isdir(dirpath):
        return

    try:
        rmtree(dirpath)
    except:
        # we don't really care about errors that much.  We'll catch remaining files
        #    with slower python logic.
        pass

    for root, dirs, files in os.walk(dirpath, topdown=False):
        for file in files:
            unlink_or_rename_to_trash(join(root, file))


def path_is_clean(path):
    """Sometimes we can't completely remove a path because files are considered in use
    by python (hardlinking confusion).  For our tests, it is sufficient that either the
    folder doesn't exist, or nothing but temporary file copies are left.
    """
    clean = not exists(path)
    if not clean:
        for root, dirs, fns in os.walk(path):
            for fn in fns:
                if not (
                    fnmatch.fnmatch(fn, "*.conda_trash*")
                    or fnmatch.fnmatch(fn, "*" + CONDA_TEMP_EXTENSION)
                ):
                    return False
    return True
