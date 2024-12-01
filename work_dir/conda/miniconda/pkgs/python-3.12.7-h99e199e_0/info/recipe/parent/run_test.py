import os
import platform
import sys
import subprocess

armv6l = bool(platform.machine() == 'armv6l')
armv7l = bool(platform.machine() == 'armv7l')
ppc64le = bool(platform.machine() == 'ppc64le')
arm64 = bool(platform.machine() == 'arm64')
if sys.platform == 'darwin':
    osx105 = b'10.5.' in subprocess.check_output('sw_vers')
else:
    osx105 = False

print('sys.version:', sys.version)
print('sys.platform:', sys.platform)
print('tuple.__itemsize__:', tuple.__itemsize__)
if sys.platform == 'win32':
    assert 'MSC v.19' in sys.version
print('sys.maxunicode:', sys.maxunicode)
print('platform.architecture:', platform.architecture())
print('platform.python_version:', platform.python_version())

import _bisect
import _codecs_cn
import _codecs_hk
import _codecs_iso2022
import _codecs_jp
import _codecs_kr
import _codecs_tw
import _collections
import _csv
import _ctypes
import _ctypes_test
import _decimal
import _elementtree
import _functools
import _hashlib
import _heapq
import _io
import _json
import _locale
import _lsprof
import _lzma
import _multibytecodec
import _multiprocessing
import _random
import _socket
import _sqlite3
import _ssl
import _struct
import _testcapi
import array
import audioop
import binascii
import bz2
import cmath
import datetime
import itertools
import lzma
import math
import mmap
import operator
import pyexpat
import select
import time
import test
import test.support
import unicodedata
import zlib
from os import urandom
import os

t = 100 * b'Foo '
assert lzma.decompress(lzma.compress(t)) == t

if sys.platform != 'win32':
    if not (ppc64le or armv7l):
        import _curses
        import _curses_panel
    import crypt
    import fcntl
    import grp
    import nis
    import readline
    import resource
    import syslog
    import termios


if not (armv6l or armv7l or ppc64le or osx105 or arm64):
    import tkinter
    import turtle
    import _tkinter
    print('TK_VERSION: %s' % _tkinter.TK_VERSION)
    print('TCL_VERSION: %s' % _tkinter.TCL_VERSION)
    TCLTK_VER = os.getenv("tk")
    assert _tkinter.TK_VERSION == _tkinter.TCL_VERSION == TCLTK_VER

import ssl
print('OPENSSL_VERSION:', ssl.OPENSSL_VERSION)
CONDA_OPENSSL_VERSION = os.getenv("openssl")
assert CONDA_OPENSSL_VERSION in ssl.OPENSSL_VERSION
