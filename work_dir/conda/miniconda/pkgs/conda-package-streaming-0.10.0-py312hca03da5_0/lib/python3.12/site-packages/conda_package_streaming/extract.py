"""
Extract package to directory, with checks against tar members extracting outside
the target directory.
"""

from __future__ import annotations

import os
import tarfile
from errno import ELOOP
from pathlib import Path
from typing import Generator

from . import exceptions, package_streaming

__all__ = ["extract_stream", "extract"]


def extract_stream(
    stream: Generator[tuple[tarfile.TarFile, tarfile.TarInfo], None, None],
    dest_dir: Path | str,
):
    """
    Pipe ``stream_conda_component`` output here to extract every member into
    dest_dir.

    For ``.conda`` will need to be called twice (for info and pkg components);
    for ``.tar.bz2`` every member is extracted.
    """
    dest_dir = os.path.realpath(dest_dir)

    def is_within_dest_dir(name):
        abs_target = os.path.realpath(os.path.join(dest_dir, name))
        prefix = os.path.commonpath((dest_dir, abs_target))
        return prefix == dest_dir

    for tar_file, _ in stream:
        # careful not to seek backwards
        def checked_members():
            # from conda_package_handling
            for member in tar_file:
                if not is_within_dest_dir(member.name):
                    raise exceptions.SafetyError(f"contains unsafe path: {member.name}")
                yield member

        try:
            tar_file.extractall(path=dest_dir, members=checked_members())
        except OSError as e:
            if e.errno == ELOOP:
                raise exceptions.CaseInsensitiveFileSystemError() from e
            raise

        # next iteraton of for loop raises GeneratorExit in stream
        stream.close()


def extract(filename, dest_dir=None, fileobj=None):
    """
    Extract all components of conda package to dest_dir.

    fileobj: must be seekable if provided, if a ``.conda`` package.
    """
    assert dest_dir, "dest_dir is required"
    if str(filename).endswith(".conda"):
        components = [
            package_streaming.CondaComponent.pkg,
            package_streaming.CondaComponent.info,
        ]
    else:  # .tar.bz2 doesn't filter by component
        components = [package_streaming.CondaComponent.pkg]

    closefd = False
    if not fileobj:
        fileobj = open(filename, "rb")
        closefd = True

    try:
        for component in components:
            stream = package_streaming.stream_conda_component(
                filename, fileobj, component=component
            )
            extract_stream(stream, dest_dir)
    finally:
        if closefd:
            fileobj.close()
