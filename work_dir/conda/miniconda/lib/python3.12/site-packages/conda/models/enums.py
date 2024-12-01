# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Collection of enums used throughout conda."""

import sys
from enum import Enum
from platform import machine

from ..auxlib.decorators import classproperty
from ..auxlib.ish import dals
from ..auxlib.type_coercion import TypeCoercionError, boolify
from ..exceptions import CondaUpgradeError


class Arch(Enum):
    x86 = "x86"
    x86_64 = "x86_64"
    # arm64 is for macOS and Windows
    arm64 = "arm64"
    armv6l = "armv6l"
    armv7l = "armv7l"
    # aarch64 is for Linux only
    aarch64 = "aarch64"
    ppc64 = "ppc64"
    ppc64le = "ppc64le"
    riscv64 = "riscv64"
    s390x = "s390x"
    wasm32 = "wasm32"
    z = "z"

    @classmethod
    def from_sys(cls):
        if sys.platform == "zos":
            return cls["z"]
        return cls[machine()]

    def __json__(self):
        return self.value


class Platform(Enum):
    freebsd = "freebsd"
    linux = "linux"
    win = "win32"
    openbsd = "openbsd5"
    osx = "darwin"
    zos = "zos"
    emscripten = "emscripten"
    wasi = "wasi"

    @classmethod
    def from_sys(cls):
        return cls(sys.platform)

    def __json__(self):
        return self.value


class FileMode(Enum):
    text = "text"
    binary = "binary"

    def __str__(self):
        return f"{self.value}"


class LinkType(Enum):
    # directory is not a link type, and copy is not a path type
    # LinkType is still probably the best name here
    hardlink = 1
    softlink = 2
    copy = 3
    directory = 4

    def __int__(self):
        return self.value

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name


class PathType(Enum):
    """
    Refers to if the file in question is hard linked or soft linked. Originally designed to be used
    in paths.json
    """

    hardlink = "hardlink"
    softlink = "softlink"
    directory = "directory"

    # these additional types should not be included by conda-build in packages
    linked_package_record = (
        "linked_package_record"  # a package's .json file in conda-meta
    )
    pyc_file = "pyc_file"
    unix_python_entry_point = "unix_python_entry_point"
    windows_python_entry_point_script = "windows_python_entry_point_script"
    windows_python_entry_point_exe = "windows_python_entry_point_exe"

    @classproperty
    def basic_types(self):
        return (PathType.hardlink, PathType.softlink, PathType.directory)

    def __str__(self):
        return self.name

    def __json__(self):
        return self.name


class PackageType(Enum):
    NOARCH_GENERIC = "noarch_generic"
    NOARCH_PYTHON = "noarch_python"
    VIRTUAL_PRIVATE_ENV = "virtual_private_env"
    VIRTUAL_PYTHON_WHEEL = "virtual_python_wheel"  # manageable
    VIRTUAL_PYTHON_EGG_MANAGEABLE = "virtual_python_egg_manageable"
    VIRTUAL_PYTHON_EGG_UNMANAGEABLE = "virtual_python_egg_unmanageable"
    VIRTUAL_PYTHON_EGG_LINK = "virtual_python_egg_link"  # unmanageable
    VIRTUAL_SYSTEM = "virtual_system"  # virtual packages representing system attributes

    @staticmethod
    def conda_package_types():
        return {
            None,
            PackageType.NOARCH_GENERIC,
            PackageType.NOARCH_PYTHON,
        }

    @staticmethod
    def unmanageable_package_types():
        return {
            PackageType.VIRTUAL_PYTHON_EGG_UNMANAGEABLE,
            PackageType.VIRTUAL_PYTHON_EGG_LINK,
            PackageType.VIRTUAL_SYSTEM,
        }


class NoarchType(Enum):
    generic = "generic"
    python = "python"

    @staticmethod
    def coerce(val):
        # what a mess
        if isinstance(val, NoarchType):
            return val
        valtype = getattr(val, "type", None)
        if isinstance(valtype, NoarchType):  # see issue #8311
            return valtype
        if isinstance(val, bool):
            val = NoarchType.generic if val else None
        if isinstance(val, str):
            val = val.lower()
            if val == "python":
                val = NoarchType.python
            elif val == "generic":
                val = NoarchType.generic
            else:
                try:
                    val = NoarchType.generic if boolify(val) else None
                except TypeCoercionError:
                    raise CondaUpgradeError(
                        dals(
                            f"""
                    The noarch type for this package is set to '{val}'.
                    The current version of conda is too old to install this package.
                    Please update conda.
                    """
                        )
                    )
        return val
