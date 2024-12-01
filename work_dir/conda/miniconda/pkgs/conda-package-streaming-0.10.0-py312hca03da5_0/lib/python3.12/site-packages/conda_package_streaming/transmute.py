"""
Convert .tar.bz2 to .conda

Uses `tempfile.SpooledTemporaryFile` to buffer `pkg-*` `.tar` and `info-*`
`.tar`, then compress directly into an open `ZipFile` at the end.
`SpooledTemporaryFile` buffers the first 10MB of the package and its metadata in
memory, but writes out to disk for larger packages.

Conda packages created this way have `info-*` as the last element in the
`ZipFile`, instead of the first for `.conda` packages created with pre-2.0
`conda-package-handling`.
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Callable

import zstandard

# streams everything in .tar.bz2 mode
from .package_streaming import CondaComponent, stream_conda_component

# increase to reduce speed and increase compression (levels above 19 use much
# more memory)
ZSTD_COMPRESS_LEVEL = 19
# increase to reduce compression and increase speed
ZSTD_COMPRESS_THREADS = 1

CONDA_PACKAGE_FORMAT_VERSION = 2

# Account for growth from "2 GB of /dev/urandom" to not exceed ZIP64_LIMIT after
# compression
CONDA_ZIP64_LIMIT = zipfile.ZIP64_LIMIT - (1 << 18) - 1


def transmute(
    package,
    path,
    *,
    compressor: Callable[
        [], zstandard.ZstdCompressor
    ] = lambda: zstandard.ZstdCompressor(
        level=ZSTD_COMPRESS_LEVEL, threads=ZSTD_COMPRESS_THREADS
    ),
    is_info: Callable[[str], bool] = lambda filename: filename.startswith("info/"),
) -> Path:
    """
    Convert .tar.bz2 conda :package to .conda-format under path.

    :param package: path to .tar.bz2 conda package
    :param path: destination path for transmuted .conda package
    :param compressor: A function that creates instances of
        ``zstandard.ZstdCompressor()`` to override defaults.
    :param is_info: A function that returns True if a file belongs in the
        ``info`` component of a `.conda` package.  ``conda-package-handling``
        (not this package ``conda-package-streaming``) uses a set of regular
        expressions to keep expected items in the info- component, while other
        items starting with ``info/`` wind up in the pkg- component.

    :return: Path to transmuted package.
    """
    assert package.endswith(".tar.bz2"), "can only convert .tar.bz2 to .conda"
    assert os.path.isdir(path)
    file_id = os.path.basename(package)[: -len(".tar.bz2")]
    output_path = Path(path, f"{file_id}.conda")

    with tempfile.SpooledTemporaryFile() as info_file, tempfile.SpooledTemporaryFile() as pkg_file:
        with tarfile.TarFile(fileobj=info_file, mode="w") as info_tar, tarfile.TarFile(
            fileobj=pkg_file, mode="w"
        ) as pkg_tar:
            # If we wanted to compress these at a low setting to save temporary
            # space, we could insert a file object that counts bytes written in
            # front of a zstd (level between 1..3) compressor.
            stream = iter(stream_conda_component(package))
            for tar, member in stream:
                tar_get = info_tar if is_info(member.name) else pkg_tar
                if member.isfile():
                    tar_get.addfile(member, tar.extractfile(member))
                else:
                    tar_get.addfile(member)

            info_tar.close()
            pkg_tar.close()

            info_size = info_file.tell()
            pkg_size = pkg_file.tell()

            info_file.seek(0)
            pkg_file.seek(0)

        with zipfile.ZipFile(
            output_path,
            "x",  # x to not append to existing
            compresslevel=zipfile.ZIP_STORED,
        ) as conda_file:
            # Use a maximum of one Zstd compressor, stream_writer at a time to save memory.
            data_compress = compressor()

            pkg_metadata = {"conda_pkg_format_version": CONDA_PACKAGE_FORMAT_VERSION}
            conda_file.writestr("metadata.json", json.dumps(pkg_metadata))

            with conda_file.open(
                f"pkg-{file_id}.tar.zst",
                "w",
                force_zip64=(pkg_size > CONDA_ZIP64_LIMIT),
            ) as pkg_file_zip, data_compress.stream_writer(
                pkg_file_zip, size=pkg_size, closefd=False
            ) as pkg_stream:
                shutil.copyfileobj(pkg_file._file, pkg_stream)

            with conda_file.open(
                f"info-{file_id}.tar.zst",
                "w",
                force_zip64=(info_size > CONDA_ZIP64_LIMIT),
            ) as info_file_zip, data_compress.stream_writer(
                info_file_zip,
                size=info_size,
                closefd=False,
            ) as info_stream:
                shutil.copyfileobj(info_file._file, info_stream)

    return output_path


def transmute_tar_bz2(
    package: str,
    path,
) -> Path:
    """
    Convert .conda :package to .tar.bz2 format under path.

    Can recompress .tar.bz2 packages.

    :param package: path to `.conda` or `.tar.bz2` package.
    :param path: destination path for transmuted package.

    :return: Path to transmuted package.
    """
    assert package.endswith((".tar.bz2", ".conda")), "Unknown extension"
    assert os.path.isdir(path)

    incoming_format = ".conda" if package.endswith(".conda") else ".tar.bz2"

    file_id = os.path.basename(package)[: -len(incoming_format)]

    if incoming_format == ".conda":
        # .tar.bz2 MUST place info/ first.
        components = [CondaComponent.info, CondaComponent.pkg]
    else:
        # .tar.bz2 doesn't filter by component
        components = [CondaComponent.pkg]

    output_path = Path(path, f"{file_id}.tar.bz2")

    with open(package, "rb") as fileobj, tarfile.open(output_path, "x:bz2") as pkg_tar:
        for component in components:
            stream = iter(stream_conda_component(package, fileobj, component=component))
            for tar, member in stream:
                if member.isfile():
                    pkg_tar.addfile(member, tar.extractfile(member))
                else:
                    pkg_tar.addfile(member)

    return output_path
