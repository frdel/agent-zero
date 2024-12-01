# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
import os
from logging import getLogger

log = getLogger(__name__)


def get_free_space_on_unix(dir_name):
    st = os.statvfs(dir_name)
    return st.f_bavail * st.f_frsize


def is_admin_on_unix():
    # http://stackoverflow.com/a/1026626/2127762
    return os.geteuid() == 0
