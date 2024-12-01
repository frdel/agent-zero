# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from enum import IntEnum
from logging import getLogger

from ..compat import ensure_binary, on_win

log = getLogger(__name__)

if on_win:
    from ctypes import (
        POINTER,
        Structure,
        WinError,
        byref,
        c_char_p,
        c_int,
        c_ulong,
        c_ulonglong,
        c_void_p,
        c_wchar_p,
        pointer,
        sizeof,
        windll,
    )
    from ctypes.wintypes import BOOL, DWORD, HANDLE, HINSTANCE, HKEY, HWND

    PHANDLE = POINTER(HANDLE)
    PDWORD = POINTER(DWORD)
    SEE_MASK_NOCLOSEPROCESS = 0x00000040
    INFINITE = -1

    WaitForSingleObject = windll.kernel32.WaitForSingleObject
    WaitForSingleObject.argtypes = (HANDLE, DWORD)
    WaitForSingleObject.restype = DWORD

    CloseHandle = windll.kernel32.CloseHandle
    CloseHandle.argtypes = (HANDLE,)
    CloseHandle.restype = BOOL

    class ShellExecuteInfo(Structure):
        """
        https://docs.microsoft.com/en-us/windows/desktop/api/shellapi/nf-shellapi-shellexecuteexa
        https://docs.microsoft.com/en-us/windows/desktop/api/shellapi/ns-shellapi-_shellexecuteinfoa
        """

        _fields_ = [
            ("cbSize", DWORD),
            ("fMask", c_ulong),
            ("hwnd", HWND),
            ("lpVerb", c_char_p),
            ("lpFile", c_char_p),
            ("lpParameters", c_char_p),
            ("lpDirectory", c_char_p),
            ("nShow", c_int),
            ("hInstApp", HINSTANCE),
            ("lpIDList", c_void_p),
            ("lpClass", c_char_p),
            ("hKeyClass", HKEY),
            ("dwHotKey", DWORD),
            ("hIcon", HANDLE),
            ("hProcess", HANDLE),
        ]

        def __init__(self, **kwargs):
            Structure.__init__(self)
            self.cbSize = sizeof(self)
            for field_name, field_value in kwargs.items():
                if isinstance(field_value, str):
                    field_value = ensure_binary(field_value)
                setattr(self, field_name, field_value)

    PShellExecuteInfo = POINTER(ShellExecuteInfo)
    ShellExecuteEx = windll.Shell32.ShellExecuteExA
    ShellExecuteEx.argtypes = (PShellExecuteInfo,)
    ShellExecuteEx.restype = BOOL


class SW(IntEnum):
    HIDE = 0
    MAXIMIZE = 3
    MINIMIZE = 6
    RESTORE = 9
    SHOW = 5
    SHOWDEFAULT = 10
    SHOWMAXIMIZED = 3
    SHOWMINIMIZED = 2
    SHOWMINNOACTIVE = 7
    SHOWNA = 8
    SHOWNOACTIVATE = 4
    SHOWNORMAL = 1


class ERROR(IntEnum):
    ZERO = 0
    FILE_NOT_FOUND = 2
    PATH_NOT_FOUND = 3
    BAD_FORMAT = 11
    ACCESS_DENIED = 5
    ASSOC_INCOMPLETE = 27
    DDE_BUSY = 30
    DDE_FAIL = 29
    DDE_TIMEOUT = 28
    DLL_NOT_FOUND = 32
    NO_ASSOC = 31
    OOM = 8
    SHARE = 26


def get_free_space_on_windows(dir_name):
    result = None
    free_bytes = c_ulonglong(0)
    try:
        windll.kernel32.GetDiskFreeSpaceExW(
            c_wchar_p(dir_name),
            None,
            None,
            pointer(free_bytes),
        )
        result = free_bytes.value
    except Exception as e:
        log.info("%r", e)
    return result


def is_admin_on_windows():  # pragma: unix no cover
    # http://stackoverflow.com/a/1026626/2127762
    result = False
    try:
        result = windll.shell32.IsUserAnAdmin() != 0
    except Exception as e:  # pragma: no cover
        log.info("%r", e)
        # result = 'unknown'
    return result


def _wait_and_close_handle(process_handle):
    """Waits until spawned process finishes and closes the handle for it."""
    try:
        WaitForSingleObject(process_handle, INFINITE)
        CloseHandle(process_handle)
    except Exception as e:
        log.info("%r", e)


def run_as_admin(args, wait=True):
    """
    Run command line argument list (`args`) with elevated privileges.

    If `wait` is True, the process will block until completion.

    NOTES:
        - no stdin / stdout / stderr pipe support
        - does not automatically quote arguments (i.e. for paths that may contain spaces)
    See:
    - http://stackoverflow.com/a/19719292/1170370 on 20160407 MCS.
    - msdn.microsoft.com/en-us/library/windows/desktop/bb762153(v=vs.85).aspx
    - https://github.com/ContinuumIO/menuinst/blob/master/menuinst/windows/win_elevate.py
    - https://github.com/saltstack/salt-windows-install/blob/master/deps/salt/python/App/Lib/site-packages/win32/Demos/pipes/runproc.py  # NOQA
    - https://github.com/twonds/twisted/blob/master/twisted/internet/_dumbwin32proc.py
    - https://stackoverflow.com/a/19982092/2127762
    - https://www.codeproject.com/Articles/19165/Vista-UAC-The-Definitive-Guide
    - https://github.com/JustAMan/pyWinClobber/blob/master/win32elevate.py
    """
    arg0 = args[0]
    param_str = " ".join(args[1:] if len(args) > 1 else ())
    hprocess = None
    error_code = None
    try:
        execute_info = ShellExecuteInfo(
            fMask=SEE_MASK_NOCLOSEPROCESS,
            hwnd=None,
            lpVerb="runas",
            lpFile=arg0,
            lpParameters=param_str,
            lpDirectory=None,
            nShow=SW.HIDE,
        )
        successful = ShellExecuteEx(byref(execute_info))
        hprocess = execute_info.hProcess
    except Exception as e:
        successful = False
        error_code = e
        log.info("%r", e)

    if not successful:
        error_code = WinError()
    elif wait:
        _wait_and_close_handle(execute_info.hProcess)

    return hprocess, error_code
