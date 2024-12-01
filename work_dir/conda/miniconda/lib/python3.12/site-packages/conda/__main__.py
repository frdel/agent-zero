# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Conda as a module entry point."""

import sys

from .cli import main

sys.exit(main())
