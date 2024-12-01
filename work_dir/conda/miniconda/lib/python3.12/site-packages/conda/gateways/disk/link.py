# Copyright (C) 2012 Anaconda, Inc & Jason R. Coombs
# SPDX-License-Identifier: BSD-3-Clause, MIT
"""Disk utility functions for symlinking files and folders.

Portions of the code within this module are taken from https://github.com/jaraco/jaraco.windows
which is MIT licensed by Jason R. Coombs.

https://github.com/jaraco/skeleton/issues/1#issuecomment-285448440
"""

import sys
from logging import getLogger
from os import chmod as os_chmod
from os.path import abspath, isdir
from os.path import islink as os_islink
from os.path import lexists as os_lexists

from ...common.compat import on_win
from ...exceptions import CondaOSError, ParseError

__all__ = ("islink", "lchmod", "lexists", "link", "readlink", "symlink")

log = getLogger(__name__)
PYPY = sys.implementation.name == "pypy"


try:
    from os import lchmod as os_lchmod

    lchmod = os_lchmod
except ImportError:  # pragma: no cover

    def lchmod(path, mode):
        # On systems that don't allow permissions on symbolic links, skip
        # links entirely.
        if not islink(path):
            os_chmod(path, mode)


if not on_win:  # pragma: win no cover
    from os import link, symlink

    link = link
    symlink = symlink

else:  # pragma: unix no cover
    from ctypes import windll, wintypes

    CreateHardLink = windll.kernel32.CreateHardLinkW
    CreateHardLink.restype = wintypes.BOOL
    CreateHardLink.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPVOID]
    try:
        CreateSymbolicLink = windll.kernel32.CreateSymbolicLinkW
        CreateSymbolicLink.restype = wintypes.BOOL
        CreateSymbolicLink.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
    except AttributeError:
        CreateSymbolicLink = None

    def win_hard_link(src, dst):
        """Equivalent to os.link, using the win32 CreateHardLink call."""
        if not CreateHardLink(dst, src, None):
            raise CondaOSError(f"win32 hard link failed\n  src: {src}\n  dst: {dst}")

    def win_soft_link(src, dst):
        """Equivalent to os.symlink, using the win32 CreateSymbolicLink call."""
        if CreateSymbolicLink is None:
            raise CondaOSError("win32 soft link not supported")
        if not CreateSymbolicLink(dst, src, isdir(src)):
            raise CondaOSError(f"win32 soft link failed\n  src: {src}\n  dst: {dst}")

    link = win_hard_link
    symlink = win_soft_link


if not (on_win and PYPY):
    from os import readlink

    islink = os_islink
    lexists = os_lexists
    readlink = readlink

else:  # pragma: no cover
    import builtins
    import inspect
    import sys
    from ctypes import POINTER, Structure, byref, c_uint64, cast, windll, wintypes
    from os import getcwd
    from os.path import isfile

    def islink(path):
        """Determine if the given path is a symlink"""
        return is_reparse_point(path) and is_symlink(path)

    def lexists(path):
        if islink(path):
            return True
        if isdir(path):
            return True
        if isfile(path):
            return True
        return False

    MAX_PATH = 260
    IO_REPARSE_TAG_SYMLINK = 0xA000000C
    INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
    FILE_ATTRIBUTE_REPARSE_POINT = 0x400
    NULL = 0
    ERROR_NO_MORE_FILES = 0x12

    class WIN32_FIND_DATA(Structure):
        _fields_ = [
            ("file_attributes", wintypes.DWORD),
            ("creation_time", wintypes.FILETIME),
            ("last_access_time", wintypes.FILETIME),
            ("last_write_time", wintypes.FILETIME),
            ("file_size_words", wintypes.DWORD * 2),
            ("reserved", wintypes.DWORD * 2),
            ("filename", wintypes.WCHAR * MAX_PATH),
            ("alternate_filename", wintypes.WCHAR * 14),
        ]

        @property
        def file_size(self):
            return cast(self.file_size_words, POINTER(c_uint64)).contents

    LPWIN32_FIND_DATA = POINTER(WIN32_FIND_DATA)
    FindFirstFile = windll.kernel32.FindFirstFileW
    FindFirstFile.argtypes = (wintypes.LPWSTR, LPWIN32_FIND_DATA)
    FindFirstFile.restype = wintypes.HANDLE
    FindNextFile = windll.kernel32.FindNextFileW
    FindNextFile.argtypes = (wintypes.HANDLE, LPWIN32_FIND_DATA)
    FindNextFile.restype = wintypes.BOOLEAN
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    GetFileAttributes = windll.kernel32.GetFileAttributesW
    GetFileAttributes.restype = wintypes.DWORD
    GetFileAttributes.argtypes = (wintypes.LPWSTR,)

    def handle_nonzero_success(result):
        if result == 0:
            raise OSError()

    def format_system_message(errno):
        """
        Call FormatMessage with a system error number to retrieve
        the descriptive error message.
        """
        # first some flags used by FormatMessageW
        ALLOCATE_BUFFER = 0x100
        FROM_SYSTEM = 0x1000

        # Let FormatMessageW allocate the buffer (we'll free it below)
        # Also, let it know we want a system error message.
        flags = ALLOCATE_BUFFER | FROM_SYSTEM
        source = None
        message_id = errno
        language_id = 0
        result_buffer = wintypes.LPWSTR()
        buffer_size = 0
        arguments = None
        bytes = windll.kernel32.FormatMessageW(
            flags,
            source,
            message_id,
            language_id,
            byref(result_buffer),
            buffer_size,
            arguments,
        )
        # note the following will cause an infinite loop if GetLastError
        #  repeatedly returns an error that cannot be formatted, although
        #  this should not happen.
        handle_nonzero_success(bytes)
        message = result_buffer.value
        windll.kernel32.LocalFree(result_buffer)
        return message

    class WindowsError(builtins.WindowsError):
        # more info about errors at http://msdn.microsoft.com/en-us/library/ms681381(VS.85).aspx

        def __init__(self, value=None):
            if value is None:
                value = windll.kernel32.GetLastError()
            strerror = format_system_message(value)
            args = 0, strerror, None, value
            super().__init__(*args)

        @property
        def message(self):
            return self.strerror

        @property
        def code(self):
            return self.winerror

        def __str__(self):
            return self.message

        def __repr__(self):
            return "{self.__class__.__name__}({self.winerror})".format(**vars())

    def _is_symlink(find_data):
        return find_data.reserved[0] == IO_REPARSE_TAG_SYMLINK

    def _patch_path(path):
        r"""
        Paths have a max length of api.MAX_PATH characters (260). If a target path
        is longer than that, it needs to be made absolute and prepended with
        \\?\ in order to work with API calls.
        See http://msdn.microsoft.com/en-us/library/aa365247%28v=vs.85%29.aspx for
        details.
        """  # NOQA
        if path.startswith("\\\\?\\"):
            return path
        path = abspath(path)
        if not path[1] == ":":
            # python doesn't include the drive letter, but \\?\ requires it
            path = getcwd()[:2] + path
        return "\\\\?\\" + path

    def local_format(string):
        """Format the string using variables in the caller's local namespace.

        .. code-block:: pycon
            >>> a = 3
            >>> local_format("{a:5}")
            '    3'
        """
        context = inspect.currentframe().f_back.f_locals
        return string.format_map(context)

    def is_symlink(path):
        """Assuming path is a reparse point, determine if it's a symlink."""
        path = _patch_path(path)
        try:
            return _is_symlink(next(find_files(path)))
        except OSError as orig_error:  # NOQA
            tmpl = "Error accessing {path}: {orig_error.message}"
            raise OSError(local_format(tmpl))

    def find_files(spec):
        r"""
        A pythonic wrapper around the FindFirstFile/FindNextFile win32 api.
        >>> root_files = tuple(find_files(r'c:\*'))
        >>> len(root_files) > 1
        True
        >>> root_files[0].filename == root_files[1].filename
        False
        >>> # This test might fail on a non-standard installation
        >>> 'Windows' in (fd.filename for fd in root_files)
        True
        """  # NOQA
        fd = WIN32_FIND_DATA()
        handle = FindFirstFile(spec, byref(fd))
        while True:
            if handle == INVALID_HANDLE_VALUE:
                raise OSError()
            yield fd
            fd = WIN32_FIND_DATA()
            res = FindNextFile(handle, byref(fd))
            if res == 0:  # error
                error = WindowsError()
                if error.code == ERROR_NO_MORE_FILES:
                    break
                else:
                    raise error
        # todo: how to close handle when generator is destroyed?
        # hint: catch GeneratorExit
        windll.kernel32.FindClose(handle)

    def is_reparse_point(path):
        """
        Determine if the given path is a reparse point.
        Return False if the file does not exist or the file attributes cannot
        be determined.
        """
        res = GetFileAttributes(path)
        return res != INVALID_FILE_ATTRIBUTES and bool(
            res & FILE_ATTRIBUTE_REPARSE_POINT
        )

    OPEN_EXISTING = 3
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FLAG_BACKUP_SEMANTICS = 0x2000000
    FSCTL_GET_REPARSE_POINT = 0x900A8
    LPDWORD = POINTER(wintypes.DWORD)
    LPOVERLAPPED = wintypes.LPVOID
    # VOLUME_NAME_DOS = 0

    class SECURITY_ATTRIBUTES(Structure):
        _fields_ = (
            ("length", wintypes.DWORD),
            ("p_security_descriptor", wintypes.LPVOID),
            ("inherit_handle", wintypes.BOOLEAN),
        )

    LPSECURITY_ATTRIBUTES = POINTER(SECURITY_ATTRIBUTES)

    CreateFile = windll.kernel32.CreateFileW
    CreateFile.argtypes = (
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        LPSECURITY_ATTRIBUTES,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    CreateFile.restype = wintypes.HANDLE

    CloseHandle = windll.kernel32.CloseHandle
    CloseHandle.argtypes = (wintypes.HANDLE,)
    CloseHandle.restype = wintypes.BOOLEAN

    from ctypes import Array, c_byte, c_ulong, c_ushort, create_string_buffer, sizeof

    class REPARSE_DATA_BUFFER(Structure):
        _fields_ = [
            ("tag", c_ulong),
            ("data_length", c_ushort),
            ("reserved", c_ushort),
            ("substitute_name_offset", c_ushort),
            ("substitute_name_length", c_ushort),
            ("print_name_offset", c_ushort),
            ("print_name_length", c_ushort),
            ("flags", c_ulong),
            ("path_buffer", c_byte * 1),
        ]

        def get_print_name(self):
            wchar_size = sizeof(wintypes.WCHAR)
            arr_typ = wintypes.WCHAR * (self.print_name_length // wchar_size)
            data = byref(self.path_buffer, self.print_name_offset)
            return cast(data, POINTER(arr_typ)).contents.value

        def get_substitute_name(self):
            wchar_size = sizeof(wintypes.WCHAR)
            arr_typ = wintypes.WCHAR * (self.substitute_name_length // wchar_size)
            data = byref(self.path_buffer, self.substitute_name_offset)
            return cast(data, POINTER(arr_typ)).contents.value

    def readlink(link):
        """Return a string representing the path to which the symbolic link points.

        readlink(link) -> target
        """
        handle = CreateFile(
            link,
            0,
            0,
            None,
            OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )

        if handle == INVALID_HANDLE_VALUE:
            raise OSError()

        res = reparse_DeviceIoControl(handle, FSCTL_GET_REPARSE_POINT, None, 10240)

        bytes = create_string_buffer(res)
        p_rdb = cast(bytes, POINTER(REPARSE_DATA_BUFFER))
        rdb = p_rdb.contents
        if not rdb.tag == IO_REPARSE_TAG_SYMLINK:
            raise ParseError("Expected IO_REPARSE_TAG_SYMLINK, but got %d" % rdb.tag)

        handle_nonzero_success(CloseHandle(handle))
        return rdb.get_substitute_name()

    DeviceIoControl = windll.kernel32.DeviceIoControl
    DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        LPDWORD,
        LPOVERLAPPED,
    ]
    DeviceIoControl.restype = wintypes.BOOL

    def reparse_DeviceIoControl(
        device, io_control_code, in_buffer, out_buffer, overlapped=None
    ):
        if overlapped is not None:
            raise NotImplementedError("overlapped handles not yet supported")

        if isinstance(out_buffer, int):
            out_buffer = create_string_buffer(out_buffer)

        in_buffer_size = len(in_buffer) if in_buffer is not None else 0
        out_buffer_size = len(out_buffer)
        assert isinstance(out_buffer, Array)

        returned_bytes = wintypes.DWORD()

        res = DeviceIoControl(
            device,
            io_control_code,
            in_buffer,
            in_buffer_size,
            out_buffer,
            out_buffer_size,
            returned_bytes,
            overlapped,
        )

        handle_nonzero_success(res)
        handle_nonzero_success(returned_bytes)
        return out_buffer[: returned_bytes.value]
