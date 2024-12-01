# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Code in ``conda.common`` is not conda-specific.  Technically, it sits *aside* the application
stack and not *within* the stack.  It is able to stand independently on its own.
The *only* allowed imports of conda code in ``conda.common`` modules are imports of other
``conda.common`` modules and imports from ``conda._vendor``.

If objects are needed from other parts of conda, they should be passed directly as arguments to
functions and methods.
"""
