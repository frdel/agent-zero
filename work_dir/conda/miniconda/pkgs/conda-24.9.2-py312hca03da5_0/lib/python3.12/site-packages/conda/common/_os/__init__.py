# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
from logging import getLogger

from ..compat import on_win

if on_win:
    from .windows import get_free_space_on_windows as get_free_space
    from .windows import is_admin_on_windows as is_admin
else:
    from .unix import get_free_space_on_unix as get_free_space  # noqa
    from .unix import is_admin_on_unix as is_admin  # noqa


log = getLogger(__name__)
