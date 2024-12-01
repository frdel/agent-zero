# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Backported exports for conda-build."""

import errno
import functools
import os
from builtins import input  # noqa: F401, UP029
from io import StringIO  # noqa: F401, for conda-build

from . import CondaError, plan  # noqa: F401
from .auxlib.entity import EntityEncoder  # noqa: F401
from .base.constants import (  # noqa: F401
    DEFAULT_CHANNELS,
    DEFAULT_CHANNELS_UNIX,
    DEFAULT_CHANNELS_WIN,
    PREFIX_PLACEHOLDER,
)
from .base.context import (  # noqa: F401
    context,
    non_x86_machines,
    reset_context,
    sys_rc_path,
)
from .cli.common import spec_from_line, specs_from_args, specs_from_url  # noqa: F401
from .cli.conda_argparse import ArgumentParser  # noqa: F401
from .cli.helpers import (  # noqa: F401
    add_parser_channels,
    add_parser_prefix,
)
from .common import compat  # noqa: F401
from .common.compat import on_win  # noqa: F401
from .common.path import win_path_to_unix
from .common.toposort import _toposort  # noqa: F401
from .core.index import dist_str_in_index  # noqa: F401
from .core.index import get_index as _get_index
from .core.package_cache_data import ProgressiveFetchExtract  # noqa: F401
from .core.prefix_data import delete_prefix_from_linked_data
from .core.solve import Solver  # noqa: F401
from .core.subdir_data import cache_fn_url  # noqa: F401
from .deprecations import deprecated
from .exceptions import (  # noqa: F401
    CondaHTTPError,
    CondaOSError,
    LinkError,
    LockError,
    PaddingError,
    PathNotFoundError,
    UnsatisfiableError,
)
from .gateways.connection.download import TmpDownload  # noqa: F401
from .gateways.connection.download import download as _download  # noqa: F401
from .gateways.connection.session import CondaSession  # noqa: F401
from .gateways.disk.create import TemporaryDirectory  # noqa: F401
from .gateways.disk.delete import delete_trash  # noqa: F401
from .gateways.disk.delete import rm_rf as move_to_trash
from .gateways.disk.link import lchmod  # noqa: F401
from .gateways.subprocess import ACTIVE_SUBPROCESSES, subprocess_call  # noqa: F401
from .misc import untracked, walk_prefix  # noqa: F401
from .models.channel import Channel, get_conda_build_local_url  # noqa: F401
from .models.dist import Dist
from .models.enums import FileMode, PathType  # noqa: F401
from .models.version import VersionOrder, normalized_version  # noqa: F401
from .plan import display_actions as _display_actions
from .plan import (  # noqa: F401
    execute_actions,
    execute_instructions,
    execute_plan,
    install_actions,
)
from .resolve import (  # noqa: F401
    MatchSpec,
    Resolve,
    ResolvePackageNotFound,
    Unsatisfiable,
)
from .utils import human_bytes, unix_path_to_win, url_path  # noqa: F401

reset_context()  # initialize context when conda.exports is imported


NoPackagesFound = NoPackagesFoundError = ResolvePackageNotFound
non_x86_linux_machines = non_x86_machines
get_default_urls = lambda: DEFAULT_CHANNELS  # noqa: E731
_PREFIX_PLACEHOLDER = prefix_placeholder = PREFIX_PLACEHOLDER
arch_name = context.arch_name
binstar_upload = context.anaconda_upload
bits = context.bits
default_prefix = context.default_prefix
default_python = context.default_python
envs_dirs = context.envs_dirs
pkgs_dirs = context.pkgs_dirs
platform = context.platform
root_dir = context.root_prefix
root_writable = context.root_writable
subdir = context.subdir
conda_build = context.conda_build
get_rc_urls = lambda: list(context.channels)  # noqa: E731
get_local_urls = lambda: list(get_conda_build_local_url()) or []  # noqa: E731
load_condarc = lambda fn: reset_context([fn])  # noqa: E731
PaddingError = PaddingError
LinkError = LinkError
CondaOSError = CondaOSError
# PathNotFoundError is the conda 4.4.x name for it - let's plan ahead.
CondaFileNotFoundError = PathNotFoundError
# Replacements for six exports for compatibility
PY3 = True  # noqa: F401
string_types = str  # noqa: F401
text_type = str  # noqa: F401


deprecated.constant(
    "25.3",
    "25.9",
    "win_path_to_unix",
    win_path_to_unix,
    addendum="Use `conda.common.path.win_path_to_unix` instead.",
)
del win_path_to_unix
deprecated.constant(
    "25.3",
    "25.9",
    "unix_path_to_win",
    unix_path_to_win,
    addendum="Use `conda.common.path.unix_path_to_win` instead.",
)
del unix_path_to_win


@deprecated(
    "25.3",
    "25.9",
    addendum="Use builtin `dict.items()` instead.",
)
def iteritems(d, **kw):
    return iter(d.items(**kw))


@deprecated("25.3", "25.9", addendum="Unused.")
class Completer:  # pragma: no cover
    def get_items(self):
        return self._get_items()

    def __contains__(self, item):
        return True

    def __iter__(self):
        return iter(self.get_items())


@deprecated("25.3", "25.9", addendum="Unused.")
class InstalledPackages:
    pass


deprecated.constant(
    "25.3",
    "25.9",
    "move_to_trash",
    move_to_trash,
    addendum="Use `conda.gateways.disk.delete.rm_rf` instead.",
)
del move_to_trash


def rm_rf(path, max_retries=5, trash=True):
    from .gateways.disk.delete import rm_rf

    rm_rf(path)
    delete_prefix_from_linked_data(path)


deprecated.constant("25.3", "25.9", "KEYS", None, addendum="Unused.")
deprecated.constant("25.3", "25.9", "KEYS_DIR", None, addendum="Unused.")


@deprecated("25.3", "25.9", addendum="Unused.")
def hash_file(_):
    return None  # pragma: no cover


@deprecated("25.3", "25.9", addendum="Unused.")
def verify(_):
    return False  # pragma: no cover


def display_actions(
    actions, index, show_channel_urls=None, specs_to_remove=(), specs_to_add=()
):
    if "FETCH" in actions:
        actions["FETCH"] = [index[d] for d in actions["FETCH"]]
    if "LINK" in actions:
        actions["LINK"] = [index[d] for d in actions["LINK"]]
    if "UNLINK" in actions:
        actions["UNLINK"] = [index[d] for d in actions["UNLINK"]]
    index = {prec: prec for prec in index.values()}
    return _display_actions(
        actions, index, show_channel_urls, specs_to_remove, specs_to_add
    )


def get_index(
    channel_urls=(),
    prepend=True,
    platform=None,
    use_local=False,
    use_cache=False,
    unknown=None,
    prefix=None,
):
    index = _get_index(
        channel_urls, prepend, platform, use_local, use_cache, unknown, prefix
    )
    return {Dist(prec): prec for prec in index.values()}


def package_cache():
    from .core.package_cache_data import PackageCacheData

    class package_cache:
        def __contains__(self, dist):
            return bool(
                PackageCacheData.first_writable().get(Dist(dist).to_package_ref(), None)
            )

        def keys(self):
            return (Dist(v) for v in PackageCacheData.first_writable().values())

        def __delitem__(self, dist):
            PackageCacheData.first_writable().remove(Dist(dist).to_package_ref())

    return package_cache()


@deprecated("25.3", "25.9", addendum="Use `conda.activate` instead.")
def symlink_conda(prefix, root_dir, shell=None):  # pragma: no cover
    # do not symlink root env - this clobbers activate incorrectly.
    # prefix should always be longer than, or outside the root dir.
    if os.path.normcase(os.path.normpath(prefix)) in os.path.normcase(
        os.path.normpath(root_dir)
    ):
        return
    if on_win:
        where = "condabin"
        symlink_fn = functools.partial(win_conda_bat_redirect, shell=shell)
    else:
        where = "bin"
        symlink_fn = os.symlink
    if not os.path.isdir(os.path.join(prefix, where)):
        os.makedirs(os.path.join(prefix, where))
    _symlink_conda_hlp(prefix, root_dir, where, symlink_fn)


@deprecated("25.3", "25.9", addendum="Use `conda.activate` instead.")
def _symlink_conda_hlp(prefix, root_dir, where, symlink_fn):  # pragma: no cover
    scripts = ["conda", "activate", "deactivate"]
    prefix_where = os.path.join(prefix, where)
    if not os.path.isdir(prefix_where):
        os.makedirs(prefix_where)
    for f in scripts:
        root_file = os.path.join(root_dir, where, f)
        prefix_file = os.path.join(prefix_where, f)
        try:
            # try to kill stale links if they exist
            if os.path.lexists(prefix_file):
                rm_rf(prefix_file)
            # if they're in use, they won't be killed.  Skip making new symlink.
            if not os.path.lexists(prefix_file):
                symlink_fn(root_file, prefix_file)
        except OSError as e:
            if os.path.lexists(prefix_file) and (
                e.errno in (errno.EPERM, errno.EACCES, errno.EROFS, errno.EEXIST)
            ):
                # Cannot symlink root_file to prefix_file. Ignoring since link already exists
                pass
            else:
                raise


if on_win:  # pragma: no cover

    @deprecated("25.3", "25.9", addendum="Use `conda.activate` instead.")
    def win_conda_bat_redirect(src, dst, shell):
        """Special function for Windows XP where the `CreateSymbolicLink`
        function is not available.

        Simply creates a `.bat` file at `dst` which calls `src` together with
        all command line arguments.

        Works of course only with callable files, e.g. `.bat` or `.exe` files.
        """
        from .utils import _SHELLS

        try:
            os.makedirs(os.path.dirname(dst))
        except OSError as exc:  # Python >2.5
            if exc.errno == errno.EEXIST and os.path.isdir(os.path.dirname(dst)):
                pass
            else:
                raise

        # bat file redirect
        if not os.path.isfile(dst + ".bat"):
            with open(dst + ".bat", "w") as f:
                f.write(f'@echo off\ncall "{src}" %*\n')

        # TODO: probably need one here for powershell at some point

        # This one is for bash/cygwin/msys
        # set default shell to bash.exe when not provided, as that's most common
        if not shell:
            shell = "bash.exe"

        # technically these are "links" - but islink doesn't work on win
        if not os.path.isfile(dst):
            with open(dst, "w") as f:
                f.write("#!/usr/bin/env bash \n")
                if src.endswith("conda"):
                    f.write('{} "$@"'.format(_SHELLS[shell]["path_to"](src + ".exe")))
                else:
                    f.write('source {} "$@"'.format(_SHELLS[shell]["path_to"](src)))
            # Make the new file executable
            # http://stackoverflow.com/a/30463972/1170370
            mode = os.stat(dst).st_mode
            mode |= (mode & 292) >> 2  # copy R bits to X
            os.chmod(dst, mode)


def linked_data(prefix, ignore_channels=False):
    """Return a dictionary of the linked packages in prefix."""
    from .core.prefix_data import PrefixData
    from .models.dist import Dist

    pd = PrefixData(prefix)
    return {
        Dist(prefix_record): prefix_record
        for prefix_record in pd._prefix_records.values()
    }


def linked(prefix, ignore_channels=False):
    """Return the Dists of linked packages in prefix."""
    from .models.enums import PackageType

    conda_package_types = PackageType.conda_package_types()
    ld = linked_data(prefix, ignore_channels=ignore_channels).items()
    return {
        dist
        for dist, prefix_rec in ld
        if prefix_rec.package_type in conda_package_types
    }


# exports
def is_linked(prefix, dist):
    """
    Return the install metadata for a linked package in a prefix, or None
    if the package is not linked in the prefix.
    """
    # FIXME Functions that begin with `is_` should return True/False
    from .core.prefix_data import PrefixData

    pd = PrefixData(prefix)
    prefix_record = pd.get(dist.name, None)
    if prefix_record is None:
        return None
    elif MatchSpec(dist).match(prefix_record):
        return prefix_record
    else:
        return None


def download(
    url,
    dst_path,
    session=None,
    md5sum=None,
    urlstxt=False,
    retries=3,
    sha256=None,
    size=None,
):
    return _download(url, dst_path, md5=md5sum, sha256=sha256, size=size)
