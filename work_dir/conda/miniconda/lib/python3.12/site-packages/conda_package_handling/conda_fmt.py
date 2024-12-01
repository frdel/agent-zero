"""
The 'new' conda format, introduced in late 2018/early 2019.

https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/packages.html
"""

from __future__ import annotations

import json
import os
import tarfile
from typing import Callable
from zipfile import ZIP_STORED, ZipFile

import zstandard

from . import utils
from .interface import AbstractBaseFormat
from .streaming import _extract, _list

CONDA_PACKAGE_FORMAT_VERSION = 2
DEFAULT_COMPRESSION_TUPLE = (".tar.zst", "zstd", "zstd:compression-level=19")

# increase to reduce speed and increase compression (22 = conda's default)
ZSTD_COMPRESS_LEVEL = 19
# increase to reduce compression (slightly) and increase speed
ZSTD_COMPRESS_THREADS = 1


class CondaFormat_v2(AbstractBaseFormat):
    """If there's another conda format or breaking changes, please create a new class and keep this
    one, so that handling of v2 stays working."""

    @staticmethod
    def supported(fn):
        return fn.endswith(".conda")

    @staticmethod
    def extract(fn, dest_dir, **kw):
        components = utils.ensure_list(kw.get("components")) or ("info", "pkg")
        if not os.path.isabs(fn):
            fn = os.path.normpath(os.path.join(os.getcwd(), fn))
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)

        _extract(str(fn), str(dest_dir), components=components)

    @staticmethod
    def extract_info(fn, dest_dir=None):
        return CondaFormat_v2.extract(fn, dest_dir, components=["info"])

    @staticmethod
    def create(
        prefix,
        file_list,
        out_fn,
        out_folder=None,
        compressor: Callable[[], zstandard.ZstdCompressor] | None = None,
        compression_tuple=(None, None, None),
    ):
        if out_folder is None:
            out_folder = os.getcwd()
        if os.path.isabs(out_fn):
            out_folder = os.path.dirname(out_fn)
            out_fn = os.path.basename(out_fn)
        conda_pkg_fn = os.path.join(out_folder, out_fn)
        file_id = out_fn.replace(".conda", "")
        pkg_files = utils.filter_info_files(file_list, prefix)
        # preserve order
        pkg_files_set = set(pkg_files)
        info_files = list(f for f in file_list if f not in pkg_files_set)

        if compressor and (compression_tuple != (None, None, None)):
            raise ValueError("Supply one of compressor= or (deprecated) compression_tuple=")

        if compressor is None:
            compressor = lambda: zstandard.ZstdCompressor(
                level=ZSTD_COMPRESS_LEVEL,
                threads=ZSTD_COMPRESS_THREADS,
            )

            # legacy libarchive-ish compatibility
            ext, comp_filter, filter_opts = compression_tuple
            if filter_opts and filter_opts.startswith("zstd:compression-level="):
                compressor = lambda: zstandard.ZstdCompressor(
                    level=int(filter_opts.split("=", 1)[-1]),
                    threads=ZSTD_COMPRESS_THREADS,
                )

        class NullWriter:
            """
            zstd uses less memory on extract if size is known.
            """

            def __init__(self):
                self.size = 0

            def write(self, bytes):
                self.size += len(bytes)
                return len(bytes)

            def tell(self):
                return self.size

        with ZipFile(conda_pkg_fn, "w", compression=ZIP_STORED) as conda_file, utils.tmp_chdir(
            prefix
        ):
            pkg_metadata = {"conda_pkg_format_version": CONDA_PACKAGE_FORMAT_VERSION}
            conda_file.writestr("metadata.json", json.dumps(pkg_metadata))

            components_files = (f"pkg-{file_id}.tar.zst", pkg_files), (
                f"info-{file_id}.tar.zst",
                info_files,
            )

            # put the info last, for parity with updated transmute.
            compress = compressor()
            for component, files in components_files:
                # If size is known, the decompressor may be able to allocate less memory.
                # The compressor will error if size is not correct.
                with tarfile.TarFile(fileobj=NullWriter(), mode="w") as sizer:  # type: ignore
                    for file in files:
                        sizer.add(file, filter=utils.anonymize_tarinfo)
                size = sizer.fileobj.size  # type: ignore

                with conda_file.open(component, "w") as component_file:
                    # only one stream_writer() per compressor() must be in use at a time
                    component_stream = compress.stream_writer(
                        component_file, size=size, closefd=False
                    )
                    component_tar = tarfile.TarFile(fileobj=component_stream, mode="w")

                    for file in files:
                        component_tar.add(file, filter=utils.anonymize_tarinfo)

                    component_tar.close()
                    component_stream.close()

        return conda_pkg_fn

    @staticmethod
    def get_pkg_details(in_file):
        stat_result = os.stat(in_file)
        size = stat_result.st_size
        md5, sha256 = utils.checksums(in_file, ("md5", "sha256"))
        return {"size": size, "md5": md5, "sha256": sha256}

    @staticmethod
    def list_contents(fn, verbose=False, **kw):
        components = utils.ensure_list(kw.get("components")) or ("info", "pkg")
        if not os.path.isabs(fn):
            fn = os.path.abspath(fn)
        _list(fn, components=components, verbose=verbose)
