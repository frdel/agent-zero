# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
In this module, you will find everything relevant to conda's plugin system.
It contains all of the code that plugin authors will use to write plugins,
as well as conda's internal implementations of plugins.

**Modules relevant for plugin authors**

- :mod:`conda.plugins.hookspec`: all available hook specifications are listed here, including
  examples of how to use them
- :mod:`conda.plugins.types`: important types to use when defining plugin hooks

**Modules relevant for internal development**

- :mod:`conda.plugins.manager`: includes our custom subclass of pluggy's
  `PluginManager <https://pluggy.readthedocs.io/en/stable/api_reference.html#pluggy.PluginManager>`_ class

**Modules with internal plugin implementations**

- :mod:`conda.plugins.solvers`: implementation of the "classic" solver
- :mod:`conda.plugins.subcommands.doctor`: ``conda doctor`` subcommand
- :mod:`conda.plugins.virtual_packages`: registers virtual packages in conda

"""  # noqa: E501

from .hookspec import hookimpl  # noqa: F401
from .types import (  # noqa: F401
    CondaAuthHandler,
    CondaHealthCheck,
    CondaPostCommand,
    CondaPostSolve,
    CondaPreCommand,
    CondaPreSolve,
    CondaSetting,
    CondaSolver,
    CondaSubcommand,
    CondaVirtualPackage,
)
