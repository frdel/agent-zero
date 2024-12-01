from __future__ import annotations

import functools as _functools
import os as _os
import warnings as _warnings
from glob import glob as _glob

# expose these two exceptions as part of the API.  Everything else should feed into these.
from .exceptions import ConversionError, InvalidArchiveError  # NOQA
from .interface import AbstractBaseFormat
from .tarball import CondaTarBZ2 as _CondaTarBZ2
from .utils import filter_info_files
from .utils import get_executor as _get_executor
from .utils import rm_rf as _rm_rf

SUPPORTED_EXTENSIONS: dict[str, type[AbstractBaseFormat]] = {".tar.bz2": _CondaTarBZ2}

libarchive_enabled = False  #: Old API meaning "can extract .conda" (now without libarchive)

try:
    from .conda_fmt import ZSTD_COMPRESS_LEVEL, ZSTD_COMPRESS_THREADS
    from .conda_fmt import CondaFormat_v2 as _CondaFormat_v2

    SUPPORTED_EXTENSIONS[".conda"] = _CondaFormat_v2

    libarchive_enabled = True

except ImportError:
    _warnings.warn("Install zstandard Python bindings for .conda support")

THREADSAFE_EXTRACT = True  #: Not present in conda-package-handling<2.0.


def _collect_paths(prefix):
    dir_paths, file_paths = [], []
    for dp, dn, filenames in _os.walk(prefix):
        for f in filenames:
            file_paths.append(_os.path.relpath(_os.path.join(dp, f), prefix))
        dir_paths.extend(_os.path.relpath(_os.path.join(dp, _), prefix) for _ in dn)
    file_list = file_paths + [
        dp for dp in dir_paths if not any(f.startswith(dp + _os.sep) for f in file_paths)
    ]
    return file_list


def get_default_extracted_folder(in_file, abspath=True):
    dirname = None
    for ext in SUPPORTED_EXTENSIONS:
        if in_file.endswith(ext):
            dirname = in_file[: -len(ext)]
    if dirname and not abspath:
        dirname = _os.path.basename(dirname)
    return dirname


def extract(fn, dest_dir=None, components=None, prefix=None):
    if dest_dir:
        if _os.path.isabs(dest_dir) and prefix:
            raise ValueError(
                "dest_dir and prefix both provided as abs paths.  If providing both, "
                "prefix can be abspath, but dest dir must be relative (relative to "
                "prefix)"
            )
        if not _os.path.isabs(dest_dir):
            dest_dir = _os.path.normpath(_os.path.join(prefix or _os.getcwd(), dest_dir))
    else:
        dest_dir = _os.path.join(
            prefix or _os.path.dirname(fn),
            get_default_extracted_folder(fn, abspath=False),
        )

    if not _os.path.isdir(dest_dir):
        _os.makedirs(dest_dir)

    for format in SUPPORTED_EXTENSIONS.values():
        if format.supported(fn):
            format.extract(fn, dest_dir, components=components)
            break
    else:
        raise ValueError(
            "Didn't recognize extension for file '{}'.  Supported extensions are: {}".format(
                fn, list(SUPPORTED_EXTENSIONS.keys())
            )
        )


def create(prefix, file_list, out_fn, out_folder=None, **kw):
    if not out_folder:
        out_folder = _os.getcwd()

    # simplify arguments to format.create()
    if _os.path.isabs(out_fn):
        out_folder = _os.path.dirname(out_fn)
        out_fn = _os.path.basename(out_fn)

    if file_list is None:
        file_list = _collect_paths(prefix)
    elif isinstance(file_list, str):
        try:
            with open(file_list) as f:
                data = f.readlines()
            file_list = [_.strip() for _ in data]
        except:
            raise

    out = None
    for format in SUPPORTED_EXTENSIONS.values():
        if format.supported(out_fn):
            try:
                out = format.create(prefix, file_list, out_fn, out_folder, **kw)
                break
            except BaseException as err:
                # don't leave broken files around
                abs_out_fn = _os.path.join(out_folder, out_fn)
                if _os.path.isfile(abs_out_fn):
                    _rm_rf(abs_out_fn)
                raise err
    else:
        raise ValueError(
            "Didn't recognize extension for file '{}'.  Supported extensions are: {}".format(
                out_fn, list(SUPPORTED_EXTENSIONS.keys())
            )
        )

    return out


def _convert(
    fn,
    out_ext,
    out_folder,
    force=False,
    zstd_compress_level=None,
    zstd_compress_threads=None,
    **kw,
):
    # allow package to work in degraded mode when zstandard is not available
    import conda_package_streaming.transmute
    import zstandard

    basename = get_default_extracted_folder(fn, abspath=False)
    from .validate import validate_converted_files_match_streaming

    if not basename:
        return (
            fn,
            "",
            "Input file %s doesn't have a supported extension (%s), skipping it"
            % (fn, SUPPORTED_EXTENSIONS),
        )
    out_fn = str(_os.path.join(out_folder, basename + out_ext))
    errors = ""
    if not _os.path.lexists(out_fn) or force:
        if force and _os.path.lexists(out_fn):
            _os.unlink(out_fn)

        if out_ext == ".conda":
            # ZSTD_COMPRESS_* constants are only defined if we have zstandard
            if zstd_compress_level is None:
                zstd_compress_level = ZSTD_COMPRESS_LEVEL
            if zstd_compress_threads is None:
                zstd_compress_threads = ZSTD_COMPRESS_THREADS

            def compressor():
                return zstandard.ZstdCompressor(
                    level=zstd_compress_level, threads=zstd_compress_threads
                )

            def is_info(filename):
                return filter_info_files([filename], prefix=".") == []

            transmute = _functools.partial(
                conda_package_streaming.transmute.transmute,
                fn,
                out_folder,
                compressor=compressor,
                is_info=is_info,
            )

        else:
            transmute = _functools.partial(
                conda_package_streaming.transmute.transmute_tar_bz2, fn, out_folder
            )

        try:
            transmute()
            result = validate_converted_files_match_streaming(out_fn, fn)
            _, missing_files, mismatching_sizes = result
            if missing_files or mismatching_sizes:
                errors = str(ConversionError(missing_files, mismatching_sizes))
        except BaseException as e:
            # don't leave partial package around
            if _os.path.isfile(out_fn):
                _rm_rf(out_fn)
            if not isinstance(e, Exception):
                raise
            errors = str(e)

    return fn, out_fn, errors


def transmute(in_file, out_ext, out_folder=None, processes=1, **kw):
    if not out_folder:
        out_folder = _os.path.dirname(in_file) or _os.getcwd()

    flist = set(_glob(in_file))
    if in_file.endswith(".tar.bz2"):
        flist = flist - set(_glob(in_file.replace(".tar.bz2", out_ext)))
    elif in_file.endswith(".conda"):
        flist = flist - set(_glob(in_file.replace(".conda", out_ext)))

    failed_files = {}
    with _get_executor(processes) as executor:
        convert_f = _functools.partial(_convert, out_ext=out_ext, out_folder=out_folder, **kw)
        for fn, out_fn, errors in executor.map(convert_f, flist):
            if errors:
                failed_files[fn] = errors
                _rm_rf(out_fn)
    return failed_files


def get_pkg_details(in_file):
    """For the new pkg format, we return the size and hashes of the inner pkg part of the file"""
    for format in SUPPORTED_EXTENSIONS.values():
        if format.supported(in_file):
            return format.get_pkg_details(in_file)
    raise ValueError(f"Don't know what to do with file {in_file}")


def list_contents(in_file, verbose=False):
    for format in SUPPORTED_EXTENSIONS.values():
        if format.supported(in_file):
            return format.list_contents(in_file, verbose=verbose)
    raise ValueError(f"Don't know what to do with file {in_file}")
