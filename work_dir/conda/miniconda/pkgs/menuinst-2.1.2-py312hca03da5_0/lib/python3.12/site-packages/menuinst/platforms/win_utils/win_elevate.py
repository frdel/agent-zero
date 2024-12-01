# -*- coding: utf-8; mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vim: fileencoding=utf-8 tabstop=4 expandtab shiftwidth=4
#
# Copied from http://stackoverflow.com/a/19719292/1170370 on 20160407 MCS
#
# (C) COPYRIGHT © Preston Landers 2010
# Released under the same license as Python 2.6.5


from __future__ import print_function

import os
import sys
import traceback
from enum import IntEnum
from subprocess import list2cmdline


def isUserAdmin():
    if os.name != 'nt':
        raise RuntimeError("This function is only implemented on Windows.")

    import ctypes

    # Requires Windows XP SP2 or higher!
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:  # noqa
        traceback.print_exc()
        print("Admin check failed, assuming not an admin.")
        return False


# Taken from conda/common/_os/windows.py
if os.name == 'nt':

    def ensure_binary(value):
        try:
            return value.encode('utf-8')
        except AttributeError:  # pragma: no cover
            # AttributeError: '<>' object has no attribute 'encode'
            # In this case assume already binary type and do nothing
            return value

    from ctypes import (
        POINTER,
        Structure,
        WinError,
        byref,
        c_char_p,
        c_int,
        c_ulong,
        c_void_p,
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

    GetExitCodeProcess = windll.kernel32.GetExitCodeProcess
    GetExitCodeProcess.argtypes = (HANDLE, PDWORD)
    GetExitCodeProcess.restype = BOOL

    class ShellExecuteInfo(Structure):
        """
        https://docs.microsoft.com/en-us/windows/desktop/api/shellapi/nf-shellapi-shellexecuteexa
        https://docs.microsoft.com/en-us/windows/desktop/api/shellapi/ns-shellapi-_shellexecuteinfoa
        """

        _fields_ = [
            ('cbSize', DWORD),
            ('fMask', c_ulong),
            ('hwnd', HWND),
            ('lpVerb', c_char_p),
            ('lpFile', c_char_p),
            ('lpParameters', c_char_p),
            ('lpDirectory', c_char_p),
            ('nShow', c_int),
            ('hInstApp', HINSTANCE),
            ('lpIDList', c_void_p),
            ('lpClass', c_char_p),
            ('hKeyClass', HKEY),
            ('dwHotKey', DWORD),
            ('hIcon', HANDLE),
            ('hProcess', HANDLE),
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


def runAsAdmin(cmdLine=None, wait=True):
    if os.name != 'nt':
        raise RuntimeError("This function is only implemented on Windows.")

    python_exe = sys.executable

    if cmdLine is None:
        cmdLine = [python_exe] + sys.argv
    elif not hasattr(cmdLine, "__iter__") or isinstance(cmdLine, str):
        raise ValueError("cmdLine is not a sequence.")

    cmd = '"%s"' % (cmdLine[0],)
    params = list2cmdline(cmdLine[1:])
    showCmd = SW.HIDE
    lpVerb = 'runas'  # causes UAC elevation prompt.

    # ShellExecute() doesn't seem to allow us to fetch the PID or handle
    # of the process, so we can't get anything useful from it. Therefore
    # the more complex ShellExecuteEx() must be used.

    # procHandle = win32api.ShellExecute(0, lpVerb, cmd, params, cmdDir, showCmd)
    execute_info = ShellExecuteInfo(
        nShow=showCmd,
        fMask=SEE_MASK_NOCLOSEPROCESS,
        lpVerb=lpVerb,
        lpFile=cmd,
        lpParameters=params,
        hwnd=None,
        lpDirectory=None,
    )

    successful = ShellExecuteEx(byref(execute_info))

    if not successful:
        raise WinError()

    if wait:
        procHandle = execute_info.hProcess
        WaitForSingleObject(procHandle, INFINITE)
        err = DWORD()
        GetExitCodeProcess(procHandle, byref(err))
        rc = err.value
    else:
        rc = None

    return rc


if __name__ == '__main__':
    userIsAdmin = isUserAdmin()
    with open("output.txt", "a") as f:
        print('userIsAdmin = %d' % (userIsAdmin), file=f)
    if not userIsAdmin:
        runAsAdmin([sys.executable] + sys.argv, wait=True)
