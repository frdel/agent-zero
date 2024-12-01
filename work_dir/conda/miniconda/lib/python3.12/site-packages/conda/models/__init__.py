# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Models are data transfer objects or "light-weight" domain objects with no appreciable logic
other than their own validation. Models are used to pass data between layers of the stack. In
many ways they are similar to ORM objects.  Unlike ORM objects, they are NOT themselves allowed
to load data from a remote resource.  Thought of another way, they cannot import from
``conda.gateways``, but rather ``conda.gateways`` imports from ``conda.models`` as appropriate
to create model objects from remote resources.

Conda modules importable from ``conda.models`` are

- ``conda._vendor``
- ``conda.common``
- ``conda.models``

"""
