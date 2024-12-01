#!/bin/python

import os
import re
import sys
from pathlib import Path

v_hpp = Path(os.environ['PREFIX']) / "include" / "mamba" / "version.hpp"
v_re = re.compile(r'^.*#define LIBMAMBA_VERSION_STRING "(\d+.\d+.\d+)".*$', re.MULTILINE)

with open(v_hpp, "r") as f:
    r1 = re.search(v_re, f.read())
    assert r1.groups()[0] == sys.argv[-1]
