# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
Gateways isolate interaction of conda code with the outside world.  Disk manipulation,
database interaction, and remote requests should all be through various gateways.  Functions
and methods in ``conda.gateways`` must use ``conda.models`` for arguments and return values.

Conda modules importable from ``conda.gateways`` are

- ``conda._vendor``
- ``conda.common``
- ``conda.models``
- ``conda.gateways``

Conda modules off limits for import within ``conda.gateways`` are

- ``conda.api``
- ``conda.cli``
- ``conda.client``
- ``conda.core``

Conda modules strictly prohibited from importing ``conda.gateways`` are

- ``conda.api``
- ``conda.cli``
- ``conda.client``

"""
