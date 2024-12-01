# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""JLAP reader."""

from __future__ import annotations

import logging
from collections import UserList
from hashlib import blake2b
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Iterable, Iterator

log = logging.getLogger(__name__)


DIGEST_SIZE = 32  # 160 bits a minimum 'for security' length?
DEFAULT_IV = b"\0" * DIGEST_SIZE


def keyed_hash(data: bytes, key: bytes):
    """Keyed hash."""
    return blake2b(data, key=key, digest_size=DIGEST_SIZE)


def line_and_pos(lines: Iterable[bytes], pos=0) -> Iterator[tuple[int, bytes]]:
    r"""
    :param lines: iterator over input split by '\n', with '\n' removed.
    :param pos: initial position
    """
    for line in lines:
        yield pos, line
        pos += len(line) + 1


class JLAP(UserList):
    @classmethod
    def from_lines(cls, lines: Iterable[bytes], iv: bytes, pos=0, verify=True):
        r"""
        :param lines: iterator over input split by b'\n', with b'\n' removed
        :param pos: initial position
        :param iv: initialization vector (first line of .jlap stream, hex
            decoded). Ignored if pos==0.
        :param verify: assert last line equals computed checksum of previous
            line. Useful for writing new .jlap files if False.

        :raises ValueError: if trailing and computed checksums do not match

        :return: list of (offset, line, checksum)
        """
        # save initial iv in case there were no new lines
        buffer: list[tuple[int, str, str]] = [(-1, iv.hex(), iv.hex())]
        initial_pos = pos

        for pos, line in line_and_pos(lines, pos=pos):
            if pos == 0:
                iv = bytes.fromhex(line.decode("utf-8"))
                buffer = [(0, iv.hex(), iv.hex())]
            else:
                iv = keyed_hash(line, iv).digest()
                buffer.append((pos, line.decode("utf-8"), iv.hex()))

        log.debug("%d bytes read", pos - initial_pos)  # maybe + length of last line

        if verify:
            if buffer[-1][1] != buffer[-2][-1]:
                raise ValueError("checksum mismatch")
            else:
                log.info("Checksum OK")

        return cls(buffer)

    @classmethod
    def from_path(cls, path: Path | str, verify=True):
        # in binary mode, line separator is hardcoded as \n
        with Path(path).open("rb") as p:
            return cls.from_lines(
                (line.rstrip(b"\n") for line in p), b"", verify=verify
            )

    def add(self, line: str):
        """
        Add line to buffer, following checksum rules.

        Buffer must not be empty.

        (Remember to pop trailing checksum and possibly trailing metadata line, if
        appending to a complete jlap file)

        Less efficient than creating a new buffer from many lines and our last iv,
        and extending.

        :return: self
        """
        if "\n" in line:
            raise ValueError("\\n not allowed in line")
        pos, last_line, iv = self[-1]
        # include last line's utf-8 encoded length, plus 1 in pos?
        pos += len(last_line.encode("utf-8")) + 1
        self.extend(
            JLAP.from_lines(
                (line.encode("utf-8"),), bytes.fromhex(iv), pos, verify=False
            )[1:]
        )
        return self

    def terminate(self):
        """
        Add trailing checksum to buffer.

        :return: self
        """
        _, _, iv = self[-1]
        self.add(iv)
        return self

    def write(self, path: Path):
        """Write buffer to path."""
        with Path(path).open("w", encoding="utf-8", newline="\n") as p:
            return p.write("\n".join(b[1] for b in self))

    @property
    def body(self):
        """All lines except the first, and last two."""
        return self[1:-2]

    @property
    def penultimate(self):
        """Next-to-last line. Should contain the footer."""
        return self[-2]

    @property
    def last(self):
        """Last line. Should contain the trailing checksum."""
        return self[-1]
