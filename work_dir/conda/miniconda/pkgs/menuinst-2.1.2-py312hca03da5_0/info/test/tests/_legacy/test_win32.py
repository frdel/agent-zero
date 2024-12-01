# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import sys
from logging import getLogger

import pytest

if sys.platform == "win32":
    from menuinst._legacy.win32 import quote_args

log = getLogger(__name__)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only tests")
def test_quote_args_1():
    args = [
        "%windir%\\System32\\cmd.exe",
        "/K",
        "c:\\Users\\Francisco García Carrión Martínez\\Anaconda 3\\Scripts\\activate.bat",
        "c:\\Users\\Francisco García Carrión Martínez\\Anaconda 3",
    ]
    assert quote_args(args) == [
        "\"%windir%\\System32\\cmd.exe\"",
        "/K",
        "\"\"c:\\Users\\Francisco García Carrión Martínez\\Anaconda 3\\Scripts\\activate.bat\" \"c:\\Users\\Francisco García Carrión Martínez\\Anaconda 3\"\"",  # noqa
    ]
