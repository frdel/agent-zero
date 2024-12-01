import contextlib
import fnmatch
import hashlib
import logging
import os
import re
import shutil
import sys
import warnings as _warnings
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from errno import EACCES, ENOENT, EPERM, EROFS
from itertools import chain
from os.path import (
    abspath,
    basename,
    dirname,
    isdir,
    isfile,
    islink,
    join,
    lexists,
    normpath,
    split,
)
from stat import S_IEXEC, S_IMODE, S_ISDIR, S_ISREG, S_IWRITE
from subprocess import STDOUT, CalledProcessError, check_output, list2cmdline
from tempfile import NamedTemporaryFile, mkdtemp

on_win = sys.platform == "win32"
log = logging.getLogger(__name__)
CONDA_TEMP_EXTENSION = ".c~"


def which(executable):
    from distutils.spawn import find_executable

    return find_executable(executable)


def make_writable(path):
    try:
        mode = os.lstat(path).st_mode
        if S_ISDIR(mode):
            os.chmod(path, S_IMODE(mode) | S_IWRITE | S_IEXEC)
        elif S_ISREG(mode) or islink(path):
            os.chmod(path, S_IMODE(mode) | S_IWRITE)
        else:
            log.debug("path cannot be made writable: %s", path)
        return True
    except Exception as e:
        eno = getattr(e, "errno", None)
        if eno in (ENOENT,):
            log.debug("tried to make writable, but didn't exist: %s", path)
            raise
        elif eno in (EACCES, EPERM, EROFS):
            log.debug("tried make writable but failed: %s\n%r", path, e)
            return False
        else:
            log.warn("Error making path writable: %s\n%r", path, e)
            raise


class DummyExecutor(Executor):
    def map(self, func, *iterables):
        for iterable in iterables:
            for thing in iterable:
                yield func(thing)


def get_executor(processes):
    return DummyExecutor() if processes == 1 else ProcessPoolExecutor(max_workers=processes)


def recursive_make_writable(path):
    # The need for this function was pointed out at
    #   https://github.com/conda/conda/issues/3266#issuecomment-239241915
    # Especially on windows, file removal will often fail because it is marked read-only
    if isdir(path):
        for root, dirs, files in os.walk(path):
            for path in chain.from_iterable((files, dirs)):
                try:
                    make_writable(join(root, path))
                except:
                    pass
    else:
        try:
            make_writable(path)
        except:
            pass


def quote_for_shell(arguments, shell=None):
    if not shell:
        shell = "cmd.exe" if on_win else "bash"
    if shell == "cmd.exe":
        return list2cmdline(arguments)
    else:
        # If any multiline argument gets mixed with any other argument (which is true if we've
        # arrived in this function) then we just quote it. This assumes something like:
        # ['python', '-c', 'a\nmultiline\nprogram\n']
        # It may make sense to allow specifying a replacement character for '\n' too? e.g. ';'
        quoted = []
        # This could all be replaced with some regex wizardry but that is less readable and
        # for code like this, readability is very important.
        for arg in arguments:
            if '"' in arg:
                quote = "'"
            elif "'" in arg:
                quote = '"'
            elif not any(_ in arg for _ in (" ", "\n")):
                quote = ""
            else:
                quote = '"'
            quoted.append(quote + arg + quote)
        return " ".join(quoted)


def rmtree(path, *args, **kwargs):
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

            out = check_output(f'RD /S /Q "{path}" > NUL 2> NUL', shell=True, stderr=STDOUT)
        except:
            try:
                # Try to delete in Unicode
                name = None

                with NamedTemporaryFile(suffix=".bat", delete=False) as batch_file:
                    batch_file.write(f"RD /S {quote_for_shell([path])}\n")
                    batch_file.write("chcp 65001\n")
                    batch_file.write(f"RD /S {quote_for_shell([path])}\n")
                    batch_file.write("EXIT 0\n")
                    name = batch_file.name
                # If the above is bugged we can end up deleting hard-drives, so we check
                # that 'path' appears in it. This is not bulletproof but it could save you (me).
                with open(name) as contents:
                    content = contents.read()
                    assert path in content
                comspec = os.environ["COMSPEC"]
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
                    log.error(f"Removing folder {path} the fast way failed.  Output was: {out}")
                    raise
                else:
                    log.debug(f"removing dir contents the fast way failed.  Output was: {out}")
    else:
        try:
            os.makedirs(".empty")
        except:
            pass
        # yes, this looks strange.  See
        #    https://unix.stackexchange.com/a/79656/34459
        #    https://web.archive.org/web/20130929001850/http://linuxnote.net/jianingy/en/linux/a-fast-way-to-remove-huge-number-of-files.html  # NOQA
        rsync = which("rsync")
        if rsync and isdir(".empty"):
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
                log.debug(f"removing dir contents the fast way failed.  Output was: {out}")
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
                with NamedTemporaryFile(suffix=".bat") as trash_script:
                    with open(trash_script, "w") as f:
                        f.write('@pushd "%1"\n')
                        f.write("@REM Rename src to dest")
                        f.write('@ren "%2" "%3" > NUL 2> NUL")')

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
                        log.warn(
                            "renaming file path {} to trash failed.  Output was: {}".format(
                                path, out
                            )
                        )

            log.warn(
                "Could not remove or rename {}.  Please remove this file manually (you "
                "may need to reboot to free file handles)".format(path)
            )


def remove_empty_parent_paths(path):
    # recurse to clean up empty folders that were created to have a nested hierarchy
    parent_path = dirname(path)
    while isdir(parent_path) and not os.listdir(parent_path):
        rmdir(parent_path)
        parent_path = dirname(parent_path)


def rm_rf(path, clean_empty_parents=False, *args, **kw):
    """
    Completely delete path
    max_retries is the number of times to retry on failure. The default is 5. This only applies
    to deleting a directory.
    If removing path fails and trash is True, files will be moved to the trash directory.
    """
    recursive_make_writable(path)
    try:
        path = abspath(path)
        if isdir(path) and not islink(path):
            rmdir(path)
        elif lexists(path):
            unlink_or_rename_to_trash(path)
        else:
            log.debug("rm_rf failed. Not a link, file, or directory: %s", path)
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
try_rmdir_all_empty = move_to_trash = move_path_to_trash = rm_rf


def delete_trash(prefix):
    if not prefix:
        prefix = sys.prefix
    exclude = {"envs"}
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


def rmdir(dirpath):
    if not isdir(dirpath):
        return
    try:
        rmtree(dirpath)
    # we don't really care about errors that much.  We'll catch remaining files
    #    with slower python logic.
    except:
        pass

    for root, dirs, files in os.walk(dirpath, topdown=False):
        for f in files:
            unlink_or_rename_to_trash(join(root, f))


# we have our own TemporaryDirectory class because it's faster and handles disk issues better.
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

    def __init__(self, suffix="", prefix=".cph_tmp", dir=os.getcwd()):
        self.name = mkdtemp(suffix, prefix, dir)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name!r}>"

    def __enter__(self):
        return self.name

    def cleanup(self, _warn=False, _warnings=_warnings):
        if self.name and not self._closed:
            try:
                rm_rf(self.name)
            except:
                _warnings.warn(
                    'Conda-package-handling says: "I tried to clean up, '
                    "but I could not.  There is a mess in %s that you might "
                    'want to clean up yourself.  Sorry..."' % self.name
                )
            self._closed = True
            if _warn and _warnings.warn:
                _warnings.warn(
                    f"Implicitly cleaning up {self!r}",
                    _warnings.ResourceWarning,
                )

    def __exit__(self, exc, value, tb):
        self.cleanup()

    def __del__(self):
        # Issue a ResourceWarning if implicit cleanup needed
        self.cleanup(_warn=True)


@contextlib.contextmanager
def tmp_chdir(dest):
    curdir = os.getcwd()
    try:
        os.chdir(dest)
        yield
    finally:
        os.chdir(curdir)


def ensure_list(arg):
    if isinstance(arg, str) or not hasattr(arg, "__iter__"):
        if arg is not None:
            arg = [arg]
        else:
            arg = []
    return arg


def filter_files(
    files_list,
    prefix,
    filter_patterns=(
        r"(.*[\\\\/])?\.git[\\\\/].*",
        r"(.*[\\\\/])?\.git$",
        r"(.*)?\.DS_Store.*",
        r".*\.la$",
        r"conda-meta.*",
    ),
):
    """Remove things like the .git directory from the list of files to be copied"""
    for pattern in filter_patterns:
        r = re.compile(pattern)
        files_list = set(files_list) - set(filter(r.match, files_list))
    return [
        f
        for f in files_list
        if
        # `islink` prevents symlinks to directories from being removed
        os.path.islink(os.path.join(prefix, f)) or not os.path.isdir(os.path.join(prefix, f))
    ]


def filter_info_files(files_list, prefix):
    return filter_files(
        files_list,
        prefix,
        filter_patterns=(
            "info[\\\\/]index\\.json",
            "info[\\\\/]files",
            "info[\\\\/]paths\\.json",
            "info[\\\\/]about\\.json",
            "info[\\\\/]has_prefix",
            "info[\\\\/]hash_input_files",  # legacy, not used anymore
            "info[\\\\/]hash_input\\.json",
            "info[\\\\/]run_exports\\.yaml",  # legacy
            "info[\\\\/]run_exports\\.json",  # current
            "info[\\\\/]git",
            "info[\\\\/]recipe[\\\\/].*",
            "info[\\\\/]recipe_log.json",
            "info[\\\\/]recipe.tar",
            "info[\\\\/]test[\\\\/].*",
            "info[\\\\/]LICENSE.*",
            "info[\\\\/]requires",
            "info[\\\\/]meta",
            "info[\\\\/]platform",
            "info[\\\\/]no_link",
            "info[\\\\/]link\\.json",
            "info[\\\\/]icon\\.png",
        ),
    )


def _checksum(fd, algorithm, buffersize=65536):
    hash_impl = getattr(hashlib, algorithm)
    if not hash_impl:
        raise ValueError(f"Unrecognized hash algorithm: {algorithm}")
    else:
        hash_impl = hash_impl()
    for block in iter(lambda: fd.read(buffersize), b""):
        hash_impl.update(block)
    return hash_impl.hexdigest()


def sha256_checksum(fd):
    return _checksum(fd, "sha256")


def md5_checksum(fd):
    return _checksum(fd, "md5")


def checksum(fn, algorithm, buffersize=1 << 18):
    """
    Calculate a checksum for a filename (not an open file).
    """
    with open(fn, "rb") as fd:
        return _checksum(fd, algorithm, buffersize)


def checksums(fn, algorithms, buffersize=1 << 18):
    """
    Calculate multiple checksums for a filename in parallel.
    """
    with ThreadPoolExecutor(max_workers=len(algorithms)) as e:
        # take care not to share hash_impl between threads
        results = [e.submit(checksum, fn, algorithm, buffersize) for algorithm in algorithms]
    return [result.result() for result in results]


def anonymize_tarinfo(tarinfo):
    """
    Remove user id, name from tarinfo.
    """
    # also remove timestamps?
    tarinfo.uid = 0
    tarinfo.uname = ""
    tarinfo.gid = 0
    tarinfo.gname = ""
    return tarinfo
