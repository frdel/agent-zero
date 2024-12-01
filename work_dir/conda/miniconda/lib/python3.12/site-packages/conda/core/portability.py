# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Tools for cross-OS portability."""

from __future__ import annotations

import os
import re
import struct
import subprocess
from logging import getLogger
from os.path import basename, realpath

from ..auxlib.ish import dals
from ..base.constants import PREFIX_PLACEHOLDER
from ..base.context import context
from ..common.compat import on_linux, on_mac, on_win
from ..exceptions import BinaryPrefixReplacementError, CondaIOError
from ..gateways.disk.update import CancelOperation, update_file_in_place_as_binary
from ..models.enums import FileMode

log = getLogger(__name__)


# three capture groups: whole_shebang, executable, options
SHEBANG_REGEX = (
    rb"^(#!"  # pretty much the whole match string
    rb"(?:[ ]*)"  # allow spaces between #! and beginning of the executable path
    rb"(/(?:\\ |[^ \n\r\t])*)"  # the executable is the next text block without an escaped space or non-space whitespace character  # NOQA
    rb"(.*)"  # the rest of the line can contain option flags
    rb")$"
)  # end whole_shebang group

MAX_SHEBANG_LENGTH = 127 if on_linux else 512  # Not used on Windows

# These are the most common file encodings that we run across when having to replace our
# PREFIX_PLACEHOLDER string. They apply to binary and text formats.
# More information/discussion: https://github.com/conda/conda/pull/9946
POPULAR_ENCODINGS = (
    "utf-8",
    "utf-16-le",
    "utf-16-be",
    "utf-32-le",
    "utf-32-be",
)


class _PaddingError(Exception):
    pass


def _subdir_is_win(subdir: str) -> bool:
    if "-" in subdir:
        os, _ = subdir.lower().split("-", 1)
        return os == "win"
    else:
        # For noarch, check that we are running on windows
        return on_win


def update_prefix(
    path,
    new_prefix,
    placeholder=PREFIX_PLACEHOLDER,
    mode=FileMode.text,
    subdir=context.subdir,
):
    if _subdir_is_win(subdir) and mode == FileMode.text:
        # force all prefix replacements to forward slashes to simplify need to escape backslashes
        # replace with unix-style path separators
        new_prefix = new_prefix.replace("\\", "/")

    def _update_prefix(original_data):
        # Step 1. do all prefix replacement
        data = replace_prefix(mode, original_data, placeholder, new_prefix, subdir)

        # Step 2. if the shebang is too long or the new prefix contains spaces, shorten it using
        # /usr/bin/env trick -- NOTE: this trick assumes the environment WILL BE activated
        if not _subdir_is_win(subdir):
            data = replace_long_shebang(mode, data)

        # Step 3. if the before and after content is the same, skip writing
        if data == original_data:
            raise CancelOperation()

        # Step 4. if we have a binary file, make sure the byte size is the same before
        #         and after the update
        if mode == FileMode.binary and len(data) != len(original_data):
            raise BinaryPrefixReplacementError(
                path, placeholder, new_prefix, len(original_data), len(data)
            )

        return data

    updated = update_file_in_place_as_binary(realpath(path), _update_prefix)

    if updated and mode == FileMode.binary and subdir == "osx-arm64" and on_mac:
        # Apple arm64 needs signed executables
        subprocess.run(
            ["/usr/bin/codesign", "-s", "-", "-f", realpath(path)], capture_output=True
        )


def replace_prefix(
    mode: FileMode,
    data: bytes,
    placeholder: str,
    new_prefix: str,
    subdir: str = "noarch",
) -> bytes:
    """
    Replaces `placeholder` text with the `new_prefix` provided. The `mode` provided can
    either be text or binary.

    We use the `POPULAR_ENCODINGS` module level constant defined above to make several
    passes at replacing the placeholder. We do this to account for as many encodings as
    possible. If this causes any performance problems in the future, it could potentially
    be removed (i.e. just using the most popular "utf-8" encoding").

    More information/discussion available here: https://github.com/conda/conda/pull/9946
    """
    for encoding in POPULAR_ENCODINGS:
        if mode == FileMode.text:
            if not _subdir_is_win(subdir):
                # if new_prefix contains spaces, it might break the shebang!
                # handle this by escaping the spaces early, which will trigger a
                # /usr/bin/env replacement later on
                newline_pos = data.find(b"\n")
                if newline_pos > -1:
                    shebang_line, rest_of_data = data[:newline_pos], data[newline_pos:]
                    shebang_placeholder = f"#!{placeholder}".encode(encoding)
                    if shebang_placeholder in shebang_line:
                        escaped_shebang = f"#!{new_prefix}".replace(" ", "\\ ").encode(
                            encoding
                        )
                        shebang_line = shebang_line.replace(
                            shebang_placeholder, escaped_shebang
                        )
                        data = shebang_line + rest_of_data
            # the rest of the file can be replaced normally
            data = data.replace(
                placeholder.encode(encoding), new_prefix.encode(encoding)
            )
        elif mode == FileMode.binary:
            data = binary_replace(
                data,
                placeholder.encode(encoding),
                new_prefix.encode(encoding),
                encoding=encoding,
                subdir=subdir,
            )
        else:
            raise CondaIOError(f"Invalid mode: {mode!r}")
    return data


def binary_replace(
    data: bytes,
    search: bytes,
    replacement: bytes,
    encoding: str = "utf-8",
    subdir: str = "noarch",
) -> bytes:
    """
    Perform a binary replacement of `data`, where the placeholder `search` is
    replaced with `replacement` and the remaining string is padded with null characters.
    All input arguments are expected to be bytes objects.

    Parameters
    ----------
    data:
        The bytes object that will be searched and replaced
    search:
        The bytes object to find
    replacement:
        The bytes object that will replace `search`
    encoding: str
        The encoding of the expected string in the binary.
    """
    zeros = "\0".encode(encoding)
    if _subdir_is_win(subdir):
        # on Windows for binary files, we currently only replace a pyzzer-type entry point
        #   we skip all other prefix replacement
        if has_pyzzer_entry_point(data):
            return replace_pyzzer_entry_point_shebang(data, search, replacement)
        else:
            return data

    def replace(match):
        occurrences = match.group().count(search)
        padding = (len(search) - len(replacement)) * occurrences
        if padding < 0:
            raise _PaddingError
        return match.group().replace(search, replacement) + b"\0" * padding

    original_data_len = len(data)
    pat = re.compile(
        re.escape(search) + b"(?:(?!(?:" + zeros + b")).)*" + zeros, flags=re.DOTALL
    )
    data = pat.sub(replace, data)
    assert len(data) == original_data_len

    return data


def has_pyzzer_entry_point(data):
    pos = data.rfind(b"PK\x05\x06")
    return pos >= 0


def replace_pyzzer_entry_point_shebang(all_data, placeholder, new_prefix):
    """Code adapted from pyzzer.  This is meant to deal with entry point exe's created by distlib,
    which consist of a launcher, then a shebang, then a zip archive of the entry point code to run.
    We need to change the shebang.
    https://bitbucket.org/vinay.sajip/pyzzer/src/5d5740cb04308f067d5844a56fbe91e7a27efccc/pyzzer/__init__.py?at=default&fileviewer=file-view-default#__init__.py-112  # NOQA
    """
    # Copyright (c) 2013 Vinay Sajip.
    #
    # Permission is hereby granted, free of charge, to any person obtaining a copy
    # of this software and associated documentation files (the "Software"), to deal
    # in the Software without restriction, including without limitation the rights
    # to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    # copies of the Software, and to permit persons to whom the Software is
    # furnished to do so, subject to the following conditions:
    #
    # The above copyright notice and this permission notice shall be included in
    # all copies or substantial portions of the Software.
    #
    # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    # AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    # OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    # THE SOFTWARE.
    launcher = shebang = None
    pos = all_data.rfind(b"PK\x05\x06")
    if pos >= 0:
        end_cdr = all_data[pos + 12 : pos + 20]
        cdr_size, cdr_offset = struct.unpack("<LL", end_cdr)
        arc_pos = pos - cdr_size - cdr_offset
        data = all_data[arc_pos:]
        if arc_pos > 0:
            pos = all_data.rfind(b"#!", 0, arc_pos)
            if pos >= 0:
                shebang = all_data[pos:arc_pos]
                if pos > 0:
                    launcher = all_data[:pos]

        if data and shebang and launcher:
            if hasattr(placeholder, "encode"):
                placeholder = placeholder.encode("utf-8")
            if hasattr(new_prefix, "encode"):
                new_prefix = new_prefix.encode("utf-8")
            shebang = shebang.replace(placeholder, new_prefix)
            all_data = b"".join([launcher, shebang, data])
    return all_data


def replace_long_shebang(mode, data):
    # this function only changes a shebang line if it exists and is greater than 127 characters
    if mode == FileMode.text:
        if not isinstance(data, bytes):
            try:
                data = bytes(data, encoding="utf-8")
            except:
                data = data.encode("utf-8")

        shebang_match = re.match(SHEBANG_REGEX, data, re.MULTILINE)
        if shebang_match:
            whole_shebang, executable, options = shebang_match.groups()
            prefix, executable_name = executable.decode("utf-8").rsplit("/", 1)
            if len(whole_shebang) > MAX_SHEBANG_LENGTH or "\\ " in prefix:
                new_shebang = (
                    f"#!/usr/bin/env {executable_name}{options.decode('utf-8')}"
                )
                data = data.replace(whole_shebang, new_shebang.encode("utf-8"))

    else:
        # TODO: binary shebangs exist; figure this out in the future if text works well
        pass
    return data


def generate_shebang_for_entry_point(executable, with_usr_bin_env=False):
    """
    This function can be used to generate a shebang line for Python entry points.

    Use cases:
    - At install/link time, to generate the `noarch: python` entry points.
    - conda init uses it to create its own entry point during conda-build
    """
    shebang = f"#!{executable}\n"
    if os.environ.get("CONDA_BUILD") == "1" and "/_h_env_placehold" in executable:
        # This is being used during a conda-build process,
        # which uses long prefixes on purpose. This will be replaced
        # with the real environment prefix at install time. Do not
        # do nothing for now.
        return shebang

    # In principle, the naive shebang will work as long as the path
    # to the python executable does not contain spaces AND it's not
    # longer than 127 characters. Otherwise, we must fix it
    if len(shebang) > MAX_SHEBANG_LENGTH or " " in executable:
        if with_usr_bin_env:
            # This approach works well for all cases BUT it requires
            # the executable to be in PATH. In other words, the environment
            # needs to be activated!
            shebang = f"#!/usr/bin/env {basename(executable)}\n"
        else:
            # This approach follows a method inspired by `pypa/distlib`
            # https://github.com/pypa/distlib/blob/91aa92e64/distlib/scripts.py#L129
            # Explanation: these lines are both valid Python and shell :)
            # 1. Python will read it as a triple-quoted string; end of story
            # 2. The shell will see:
            #    * '' (empty string)
            #    * 'exec' "path/with spaces/to/python" "this file" "arguments"
            #    * # ''' (inline comment with three quotes, ignored by shell)
            # This method works well BUT in some shells, $PS1 is dropped, which
            # makes the prompt disappear. This is very problematic for the conda
            # entry point! Details: https://github.com/conda/conda/issues/11885
            shebang = dals(
                f"""
                #!/bin/sh
                '''exec' "{executable}" "$0" "$@" #'''
                """
            )

    return shebang
