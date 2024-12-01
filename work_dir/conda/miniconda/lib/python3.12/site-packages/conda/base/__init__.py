# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Code in ``conda.base`` is the lowest level of the application stack.  It is loaded and executed
virtually every time the application is executed. Any code within, and any of its imports, must
be highly performant.

Conda modules importable from ``conda.base`` are

- ``conda._vendor``
- ``conda.base``
- ``conda.common``

Modules prohibited from importing ``conda.base`` are:

- ``conda._vendor``
- ``conda.common``

All other ``conda`` modules may import from ``conda.base``.
"""
