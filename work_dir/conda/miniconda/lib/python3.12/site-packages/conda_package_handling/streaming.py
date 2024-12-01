"""
Exception-compatible adapter from conda_package_streaming.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from tarfile import TarError, TarFile, TarInfo
from typing import Iterator
from zipfile import BadZipFile

from conda_package_streaming.extract import exceptions as cps_exceptions
from conda_package_streaming.extract import extract_stream, package_streaming

from . import exceptions


def _stream_components(
    filename: str,
    components: list[str],
    dest_dir: str = "",
) -> Iterator[tuple[TarFile, TarInfo]]:
    if str(filename).endswith(".tar.bz2"):
        assert components == ["pkg"]

    try:
        with open(filename, "rb") as fileobj:
            for component in components:
                # will parse zipfile twice
                yield package_streaming.stream_conda_component(
                    filename, fileobj, component=component
                )
    except cps_exceptions.CaseInsensitiveFileSystemError as e:
        raise exceptions.CaseInsensitiveFileSystemError(filename, dest_dir) from e
    except (OSError, TarError, BadZipFile) as e:
        raise exceptions.InvalidArchiveError(filename, f"failed with error: {str(e)}") from e


def _extract(filename: str, dest_dir: str, components: list[str]):
    """
    Extract .conda or .tar.bz2 package to dest_dir.

    If it's a conda package, components may be ["pkg", "info"]

    If it's a .tar.bz2 package, components must equal ["pkg"]

    Internal. Skip directly to conda-package-streaming if you don't need
    exception compatibility.
    """
    for stream in _stream_components(filename, components, dest_dir=dest_dir):
        try:
            extract_stream(stream, dest_dir)
        except cps_exceptions.CaseInsensitiveFileSystemError as e:
            raise exceptions.CaseInsensitiveFileSystemError(filename, dest_dir) from e
        except (OSError, TarError, BadZipFile) as e:
            raise exceptions.InvalidArchiveError(filename, f"failed with error: {str(e)}") from e


def _list(filename: str, components: list[str], verbose=True):
    memfile = io.StringIO()
    for component in _stream_components(filename, components):
        for tar, _ in component:
            with redirect_stdout(memfile):
                tar.list(verbose=verbose)
            # next iteraton of for loop raises GeneratorExit in stream
            # see comments in conda_package_streaming.extract:extract_stream
            # and docstring in conda_package_streaming.package_streaming:stream_conda_info
            component.close()
    memfile.seek(0)
    if verbose:
        lines = sorted(
            memfile.readlines(),
            # verbose Tarfile.list() produces lines like:
            # ?rw-r--r-- 502/20 2342 2018-10-04 14:02:00 info/about.json
            # We only want the last part but we need to be mindful of paths containing spaces
            key=lambda line: line.split(None, 5)[-1],
        )
    else:
        lines = sorted(memfile.readlines())
    print("".join(lines), end="")
