# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Disk utility functions for creating new files or directories."""

import codecs
import os
import sys
import tempfile
import warnings as _warnings
from errno import EACCES, EPERM, EROFS
from logging import getLogger
from os.path import dirname, isdir, isfile, join, splitext
from shutil import copyfileobj, copystat

from ... import CondaError
from ...auxlib.ish import dals
from ...base.constants import CONDA_PACKAGE_EXTENSION_V1, PACKAGE_CACHE_MAGIC_FILE
from ...base.context import context
from ...common.compat import on_linux, on_win
from ...common.constants import TRACE
from ...common.path import ensure_pad, expand, win_path_double_escape, win_path_ok
from ...common.serialize import json_dump
from ...exceptions import BasicClobberError, CondaOSError, maybe_raise
from ...models.enums import LinkType
from . import mkdir_p
from .delete import path_is_clean, rm_rf
from .link import islink, lexists, link, readlink, symlink
from .permissions import make_executable
from .update import touch


# we have our own TemporaryDirectory implementation both for historical reasons and because
#     using our rm_rf function is more robust than the shutil equivalent
class TemporaryDirectory:
    """Create and return a temporary directory.  This has the same
    behavior as mkdtemp but can be used as a context manager.  For
    example:

        with TemporaryDirectory() as tmpdir:
            ...

    Upon exiting the context, the directory and everything contained
    in it are removed.
    """

    # Handle mkdtemp raising an exception
    name = None
    _closed = False

    def __init__(self, suffix="", prefix="tmp", dir=None):
        self.name = tempfile.mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __enter__(self):
        return self.name

    def cleanup(self, _warn=False, _warnings=_warnings):
        from .delete import rm_rf as _rm_rf

        if self.name and not self._closed:
            try:
                _rm_rf(self.name)
            except (TypeError, AttributeError) as ex:
                if "None" not in f"{ex}":
                    raise
                _rm_rf(self.name)
            self._closed = True

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        # Issue a ResourceWarning if implicit cleanup needed
        self.cleanup(_warn=True)


log = getLogger(__name__)
stdoutlog = getLogger("conda.stdoutlog")

# in __init__.py to help with circular imports
mkdir_p = mkdir_p

python_entry_point_template = dals(
    r"""
# -*- coding: utf-8 -*-
import re
import sys

from %(module)s import %(import_name)s

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw?|\.exe)?$', '', sys.argv[0])
    sys.exit(%(func)s())
"""
)  # NOQA

application_entry_point_template = dals(
    """
# -*- coding: utf-8 -*-
if __name__ == '__main__':
    import os
    import sys
    args = ["%(source_full_path)s"]
    if len(sys.argv) > 1:
        args += sys.argv[1:]
    os.execv(args[0], args)
"""
)


def write_as_json_to_file(file_path, obj):
    log.log(TRACE, "writing json to file %s", file_path)
    with codecs.open(file_path, mode="wb", encoding="utf-8") as fo:
        json_str = json_dump(obj)
        fo.write(json_str)


def create_python_entry_point(target_full_path, python_full_path, module, func):
    if lexists(target_full_path):
        maybe_raise(
            BasicClobberError(
                source_path=None,
                target_path=target_full_path,
                context=context,
            ),
            context,
        )

    import_name = func.split(".")[0]
    pyscript = python_entry_point_template % {
        "module": module,
        "func": func,
        "import_name": import_name,
    }
    if python_full_path is not None:
        from ...core.portability import generate_shebang_for_entry_point

        shebang = generate_shebang_for_entry_point(python_full_path)
    else:
        shebang = None

    with codecs.open(target_full_path, mode="wb", encoding="utf-8") as fo:
        if shebang is not None:
            fo.write(shebang)
        fo.write(pyscript)

    if shebang is not None:
        make_executable(target_full_path)

    return target_full_path


def create_application_entry_point(
    source_full_path, target_full_path, python_full_path
):
    # source_full_path: where the entry point file points to
    # target_full_path: the location of the new entry point file being created
    if lexists(target_full_path):
        maybe_raise(
            BasicClobberError(
                source_path=None,
                target_path=target_full_path,
                context=context,
            ),
            context,
        )

    entry_point = application_entry_point_template % {
        "source_full_path": win_path_double_escape(source_full_path),
    }
    if not isdir(dirname(target_full_path)):
        mkdir_p(dirname(target_full_path))
    with open(target_full_path, "w") as fo:
        if " " in python_full_path:
            python_full_path = ensure_pad(python_full_path, '"')
        fo.write(f"#!{python_full_path}\n")
        fo.write(entry_point)
    make_executable(target_full_path)


class ProgressFileWrapper:
    def __init__(self, fileobj, progress_update_callback):
        self.progress_file = fileobj
        self.progress_update_callback = progress_update_callback
        self.progress_file_size = max(1, os.fstat(fileobj.fileno()).st_size)
        self.progress_max_pos = 0

    def __getattr__(self, name):
        return getattr(self.progress_file, name)

    def __setattr__(self, name, value):
        if name.startswith("progress_"):
            super().__setattr__(name, value)
        else:
            setattr(self.progress_file, name, value)

    def read(self, size=-1):
        data = self.progress_file.read(size)
        self.progress_update()
        return data

    def progress_update(self):
        pos = max(self.progress_max_pos, self.progress_file.tell())
        pos = min(pos, self.progress_file_size)
        self.progress_max_pos = pos
        rel_pos = pos / self.progress_file_size
        self.progress_update_callback(rel_pos)


def extract_tarball(
    tarball_full_path, destination_directory=None, progress_update_callback=None
):
    import conda_package_handling.api

    if destination_directory is None:
        if tarball_full_path[-8:] == CONDA_PACKAGE_EXTENSION_V1:
            destination_directory = tarball_full_path[:-8]
        else:
            destination_directory = tarball_full_path.splitext()[0]
    log.debug("extracting %s\n  to %s", tarball_full_path, destination_directory)

    # the most common reason this happens is due to hard-links, windows thinks
    #    files in the package cache are in-use. rm_rf should have moved them to
    #    have a .conda_trash extension though, so it's ok to just write into
    #    the same existing folder.
    if not path_is_clean(destination_directory):
        log.debug(
            "package folder %s was not empty, but we're writing there.",
            destination_directory,
        )

    conda_package_handling.api.extract(
        tarball_full_path, dest_dir=destination_directory
    )

    if hasattr(conda_package_handling.api, "THREADSAFE_EXTRACT"):
        return  # indicates conda-package-handling 2.x, which implements --no-same-owner

    if on_linux and os.getuid() == 0:  # pragma: no cover
        # When extracting as root, tarfile will by restore ownership
        # of extracted files.  However, we want root to be the owner
        # (our implementation of --no-same-owner).
        for root, dirs, files in os.walk(destination_directory):
            for fn in files:
                p = join(root, fn)
                os.lchown(p, 0, 0)


def make_menu(prefix, file_path, remove=False):
    """
    Create cross-platform menu items (e.g. Windows Start Menu)

    Passes all menu config files %PREFIX%/Menu/*.json to ``menuinst.install``.
    ``remove=True`` will remove the menu items.
    """
    try:
        import menuinst

        menuinst.install(
            join(prefix, win_path_ok(file_path)),
            remove=remove,
            prefix=prefix,
            root_prefix=context.root_prefix,
        )
    except Exception:
        stdoutlog.error("menuinst Exception", exc_info=True)


def create_hard_link_or_copy(src, dst):
    if islink(src):
        message = dals(
            f"""
        Cannot hard link a soft link
          source: {src}
          destination: {dst}
        """
        )
        raise CondaOSError(message)

    try:
        log.log(TRACE, "creating hard link %s => %s", src, dst)
        link(src, dst)
    except OSError:
        log.info("hard link failed, so copying %s => %s", src, dst)
        _do_copy(src, dst)


def _is_unix_executable_using_ORIGIN(path):
    if on_win:
        return False
    else:
        return isfile(path) and not islink(path) and os.access(path, os.X_OK)


def _do_softlink(src, dst):
    if _is_unix_executable_using_ORIGIN(src):
        # for extra details, see https://github.com/conda/conda/pull/4625#issuecomment-280696371
        # We only need to do this copy for executables which have an RPATH containing $ORIGIN
        #   on Linux, so `is_executable()` is currently overly aggressive.
        # A future optimization will be to copy code from @mingwandroid's virtualenv patch.
        copy(src, dst)
    else:
        log.log(TRACE, "soft linking %s => %s", src, dst)
        symlink(src, dst)


def create_fake_executable_softlink(src, dst):
    assert on_win
    src_root, _ = splitext(src)
    # TODO: this open will clobber, consider raising
    with open(dst, "w") as f:
        f.write(f'@echo off\ncall "{src_root}" %*\n')
    return dst


def copy(src, dst):
    # on unix, make sure relative symlinks stay symlinks
    if not on_win and islink(src):
        src_points_to = readlink(src)
        if not src_points_to.startswith("/"):
            # copy relative symlinks as symlinks
            log.log(TRACE, "soft linking %s => %s", src, dst)
            symlink(src_points_to, dst)
            return
    _do_copy(src, dst)


def _do_copy(src, dst):
    log.log(TRACE, "copying %s => %s", src, dst)
    # src and dst are always files. So we can bypass some checks that shutil.copy does.
    # Also shutil.copy calls shutil.copymode, which we can skip because we are explicitly
    # calling copystat.

    # Same size as used by Linux cp command (has performance advantage).
    # Python's default is 16k.
    buffer_size = 4194304  # 4 * 1024 * 1024  == 4 MB
    with open(src, "rb") as fsrc:
        with open(dst, "wb") as fdst:
            copyfileobj(fsrc, fdst, buffer_size)

    try:
        copystat(src, dst)
    except OSError as e:  # pragma: no cover
        # shutil.copystat gives a permission denied when using the os.setxattr function
        # on the security.selinux property.
        log.debug("%r", e)


def create_link(src, dst, link_type=LinkType.hardlink, force=False):
    if link_type == LinkType.directory:
        # A directory is technically not a link.  So link_type is a misnomer.
        #   Naming is hard.
        if lexists(dst) and not isdir(dst):
            if not force:
                maybe_raise(BasicClobberError(src, dst, context), context)
            log.info(f"file exists, but clobbering for directory: {dst!r}")
            rm_rf(dst)
        mkdir_p(dst)
        return

    if not lexists(src):
        raise CondaError(
            f"Cannot link a source that does not exist. {src}\n"
            "Running `conda clean --packages` may resolve your problem."
        )

    if lexists(dst):
        if not force:
            maybe_raise(BasicClobberError(src, dst, context), context)
        log.info(f"file exists, but clobbering: {dst!r}")
        rm_rf(dst)

    if link_type == LinkType.hardlink:
        if isdir(src):
            raise CondaError(f"Cannot hard link a directory. {src}")
        try:
            log.log(TRACE, "hard linking %s => %s", src, dst)
            link(src, dst)
        except OSError as e:
            log.debug("%r", e)
            log.debug(
                "hard-link failed. falling back to copy\n"
                "  error: %r\n"
                "  src: %s\n"
                "  dst: %s",
                e,
                src,
                dst,
            )

            copy(src, dst)
    elif link_type == LinkType.softlink:
        _do_softlink(src, dst)
    elif link_type == LinkType.copy:
        copy(src, dst)
    else:
        raise CondaError(f"Did not expect linktype={link_type!r}")


def compile_multiple_pyc(
    python_exe_full_path, py_full_paths, pyc_full_paths, prefix, py_ver
):
    py_full_paths = tuple(py_full_paths)
    pyc_full_paths = tuple(pyc_full_paths)
    if len(py_full_paths) == 0:
        return []

    fd, filename = tempfile.mkstemp()
    try:
        for f in py_full_paths:
            f = os.path.relpath(f, prefix)
            if hasattr(f, "encode"):
                f = f.encode(sys.getfilesystemencoding(), errors="replace")
            os.write(fd, f + b"\n")
        os.close(fd)
        command = ["-Wi", "-m", "compileall", "-q", "-l", "-i", filename]
        # if the python version in the prefix is 3.5+, we have some extra args.
        #    -j 0 will do the compilation in parallel, with os.cpu_count() cores
        if int(py_ver[0]) >= 3 and int(py_ver.split(".")[1]) > 5:
            command.extend(["-j", "0"])
        command[0:0] = [python_exe_full_path]
        # command[0:0] = ['--cwd', prefix, '--dev', '-p', prefix, python_exe_full_path]
        log.log(TRACE, command)
        from ..subprocess import any_subprocess

        # from ...common.io import env_vars
        # This stack does not maintain its _argparse_args correctly?
        # from ...base.context import stack_context_default
        # with env_vars({}, stack_context_default):
        #     stdout, stderr, rc = run_command(Commands.RUN, *command)
        stdout, stderr, rc = any_subprocess(command, prefix)
    finally:
        os.remove(filename)

    created_pyc_paths = []
    for py_full_path, pyc_full_path in zip(py_full_paths, pyc_full_paths):
        if not isfile(pyc_full_path):
            message = dals(
                """
            pyc file failed to compile successfully (run_command failed)
            python_exe_full_path: %s
            py_full_path: %s
            pyc_full_path: %s
            compile rc: %s
            compile stdout: %s
            compile stderr: %s
            """
            )
            log.info(
                message,
                python_exe_full_path,
                py_full_path,
                pyc_full_path,
                rc,
                stdout,
                stderr,
            )
        else:
            created_pyc_paths.append(pyc_full_path)

    return created_pyc_paths


def create_package_cache_directory(pkgs_dir):
    # returns False if package cache directory cannot be created
    try:
        log.log(TRACE, "creating package cache directory '%s'", pkgs_dir)
        sudo_safe = expand(pkgs_dir).startswith(expand("~"))
        touch(join(pkgs_dir, PACKAGE_CACHE_MAGIC_FILE), mkdir=True, sudo_safe=sudo_safe)
        touch(join(pkgs_dir, "urls"), sudo_safe=sudo_safe)
    except OSError as e:
        if e.errno in (EACCES, EPERM, EROFS):
            log.log(TRACE, "cannot create package cache directory '%s'", pkgs_dir)
            return False
        else:
            raise
    return True


def create_envs_directory(envs_dir):
    # returns False if envs directory cannot be created

    # The magic file being used here could change in the future.  Don't write programs
    # outside this code base that rely on the presence of this file.
    # This value is duplicated in conda.base.context._first_writable_envs_dir().
    envs_dir_magic_file = join(envs_dir, ".conda_envs_dir_test")
    try:
        log.log(TRACE, "creating envs directory '%s'", envs_dir)
        sudo_safe = expand(envs_dir).startswith(expand("~"))
        touch(join(envs_dir, envs_dir_magic_file), mkdir=True, sudo_safe=sudo_safe)
    except OSError as e:
        if e.errno in (EACCES, EPERM, EROFS):
            log.log(TRACE, "cannot create envs directory '%s'", envs_dir)
            return False
        else:
            raise
    return True
