"""Lazy ZIP over HTTP"""

from __future__ import annotations

import logging
import zipfile
from bisect import bisect_left, bisect_right
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import Any, Iterator
from zipfile import BadZipfile, ZipFile

from requests import Session
from requests.models import CONTENT_CHUNK_SIZE, Response

# from pip 22.0.3 with fixes & remove imports from pip


log = logging.getLogger(__name__)

# If-Match (etag) to detect file changed during fetch would also be nice
HEADERS = {"Accept-Encoding": "identity"}


class HTTPRangeRequestUnsupported(Exception):
    pass


class LazyZipOverHTTP:
    """File-like object mapped to a ZIP file over HTTP.

    This uses HTTP range requests to lazily fetch the file's content,
    which is supposed to be fed to ZipFile.  If such requests are not
    supported by the server, raise HTTPRangeRequestUnsupported
    during initialization.
    """

    def __init__(
        self, url: str, session: Session, chunk_size: int = CONTENT_CHUNK_SIZE
    ) -> None:
        # if CONTENT_CHUNK_SIZE is bigger than the file:
        # In [8]: response.headers["Content-Range"]
        # Out[8]: 'bytes 0-3133374/3133375'

        self._request_count = 0

        self._session, self._url, self._chunk_size = session, url, chunk_size

        # initial range request for the end of the file
        tail = self._stream_response(start="", end=CONTENT_CHUNK_SIZE)
        # e.g. {'accept-ranges': 'bytes', 'content-length': '10240',
        # 'content-range': 'bytes 12824-23063/23064', 'last-modified': 'Sat, 16
        # Apr 2022 13:03:02 GMT', 'date': 'Thu, 21 Apr 2022 11:34:04 GMT'}

        if tail.status_code != 206:
            raise HTTPRangeRequestUnsupported("range request is not supported")

        # lowercase content-range to support s3
        self._length = int(tail.headers["content-range"].partition("/")[-1])
        self._file = NamedTemporaryFile()
        self.truncate(self._length)

        # length is also in Content-Length and Content-Range header
        with self._stay():
            content_length = int(tail.headers["content-length"])
            if hasattr(tail, "content"):
                assert content_length == len(tail.content)
            self.seek(self._length - content_length)
            for chunk in tail.iter_content(self._chunk_size):
                self._file.write(chunk)
        self._left: list[int] = [self._length - content_length]
        self._right: list[int] = [self._length - 1]

    @property
    def mode(self) -> str:
        """Opening mode, which is always rb."""
        return "rb"

    @property
    def name(self) -> str:
        """Path to the underlying file."""
        return self._file.name

    def seekable(self) -> bool:
        """Return whether random access is supported, which is True."""
        return True

    def close(self) -> None:
        """Close the file."""
        self._file.close()

    @property
    def closed(self) -> bool:
        """Whether the file is closed."""
        return self._file.closed

    def read(self, size: int = -1) -> bytes:
        """Read up to size bytes from the object and return them.

        As a convenience, if size is unspecified or -1,
        all bytes until EOF are returned.  Fewer than
        size bytes may be returned if EOF is reached.
        """
        # BUG does not download correctly if size is unspecified
        download_size = size
        start, length = self.tell(), self._length
        stop = length if size < 0 else min(start + download_size, length)
        start = max(0, stop - download_size)
        self._download(start, stop - 1)
        return self._file.read(size)

    def readable(self) -> bool:
        """Return whether the file is readable, which is True."""
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        """Change stream position and return the new absolute position.

        Seek to offset relative position indicated by whence:
        * 0: Start of stream (the default).  pos should be >= 0;
        * 1: Current position - pos may be negative;
        * 2: End of stream - pos usually negative.
        """
        return self._file.seek(offset, whence)

    def tell(self) -> int:
        """Return the current position."""
        return self._file.tell()

    def truncate(self, size: int | None = None) -> int:
        """Resize the stream to the given size in bytes.

        If size is unspecified resize to the current position.
        The current stream position isn't changed.

        Return the new file size.
        """
        return self._file.truncate(size)

    def writable(self) -> bool:
        """Return False."""
        return False

    def __enter__(self) -> LazyZipOverHTTP:
        self._file.__enter__()
        return self

    def __exit__(self, *exc: Any) -> bool | None:
        return self._file.__exit__(*exc)

    @contextmanager
    def _stay(self) -> Iterator[None]:
        """Return a context manager keeping the position.

        At the end of the block, seek back to original position.
        """
        pos = self.tell()
        try:
            yield
        finally:
            self.seek(pos)

    def _check_zip(self) -> None:
        """Check and download until the file is a valid ZIP."""
        end = self._length - 1
        for start in reversed(range(0, end, self._chunk_size)):
            self._download(start, end)
            with self._stay():
                try:
                    # For read-only ZIP files, ZipFile only needs
                    # methods read, seek, seekable and tell.
                    ZipFile(self)  # type: ignore
                except BadZipfile:
                    pass
                else:
                    break

    def _stream_response(
        self, start: int | str, end: int, base_headers: dict[str, str] = HEADERS
    ) -> Response:
        """Return HTTP response to a range request from start to end.

        :param start: if "", request ``end` bytes from end of file."""
        headers = base_headers.copy()
        headers["Range"] = f"bytes={start}-{end}"
        log.debug("%s", headers["Range"])
        # TODO: Get range requests to be correctly cached
        headers["Cache-Control"] = "no-cache"
        self._request_count += 1
        response = self._session.get(self._url, headers=headers, stream=True)
        response.raise_for_status()
        return response

    def _merge(
        self, start: int, end: int, left: int, right: int
    ) -> Iterator[tuple[int, int]]:
        """Return an iterator of intervals to be fetched.

        Args:
            start (int): Start of needed interval
            end (int): End of needed interval
            left (int): Index of first overlapping downloaded data
            right (int): Index after last overlapping downloaded data
        """
        lslice, rslice = self._left[left:right], self._right[left:right]
        i = start = min([start] + lslice[:1])
        end = max([end] + rslice[-1:])
        for j, k in zip(lslice, rslice):
            if j > i:
                yield i, j - 1
            i = k + 1
        if i <= end:
            yield i, end
        self._left[left:right], self._right[left:right] = [start], [end]

    def _download(self, start: int, end: int) -> None:
        """Download bytes from start to end inclusively."""
        with self._stay():
            left = bisect_left(self._right, start)
            right = bisect_right(self._left, end)
            for start, end in self._merge(start, end, left, right):
                response = self._stream_response(start, end)
                self.seek(start)
                for chunk in response.iter_content(self._chunk_size):
                    self._file.write(chunk)


class LazyConda(LazyZipOverHTTP):
    def prefetch(self, conda_file_id):
        """
        Conda fork specific. Prefetch the `.info` range from the remote archive.
        Reduces number of Range requests to 2 or 3 (1 or 2 for the directory, 1
        for the file).

        conda_file_id: name of .conda without path or `.conda` extension
        """
        target_file = f"info-{conda_file_id}.tar.zst"
        with self._stay():  # not strictly necessary
            # try to read entire conda info in one request
            zf = zipfile.ZipFile(self)
            infolist = zf.infolist()
            for i, info in enumerate(infolist):
                if info.filename == target_file:
                    # could be incorrect if zipfile was concatenated to another
                    # file (not likely for .conda)
                    start = info.header_offset
                    try:
                        end = infolist[i + 1].header_offset
                        # or info.header_offset
                        # + len(info.filename)
                        # + len(info.extra)
                        # + info.compress_size
                        # (unless Zip64)
                    except IndexError:
                        end = zf.start_dir
                    self.seek(start)
                    self.read(end - start)
                    log.debug(
                        "prefetch %s-%s",
                        info.header_offset,
                        end,
                    )
                    break
            else:
                log.debug("no zip prefetch")
