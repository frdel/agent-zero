# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Define binstar spec."""

from __future__ import annotations

import re
from functools import cached_property
from typing import TYPE_CHECKING

from ...deprecations import deprecated
from ...env.env import from_yaml
from ...exceptions import EnvironmentFileNotDownloaded
from ...models.version import normalized_version

if TYPE_CHECKING:
    from types import ModuleType

    from ...env.env import Environment

deprecated.module("24.7", "25.9")

deprecated.constant("24.7", "25.9", "ENVIRONMENT_TYPE", "env")


@deprecated("24.7", "25.9")
class BinstarSpec:
    """
    spec = BinstarSpec('darth/deathstar')
    spec.can_handle() # => True / False
    spec.environment # => YAML string
    spec.msg # => Error messages
    :raises: EnvironmentFileNotDownloaded
    """

    msg = None

    def __init__(self, name=None):
        self.name = name

    def can_handle(self) -> bool:
        """
        Validates loader can process environment definition.
        :return: True or False
        """
        # TODO: log information about trying to find the package in binstar.org
        if self.valid_name():
            if not self.binstar:
                self.msg = (
                    "Anaconda Client is required to interact with anaconda.org or an "
                    "Anaconda API. Please run `conda install anaconda-client -n base`."
                )
                return False

            return self.package is not None and self.valid_package()
        return False

    def valid_name(self) -> bool:
        """
        Validates name
        :return: True or False
        """
        if re.match("^(.+)/(.+)$", str(self.name)) is not None:
            return True
        elif self.name is None:
            self.msg = "Can't process without a name"
        else:
            self.msg = f"Invalid name {self.name!r}, try the format: user/package"
        return False

    def valid_package(self) -> bool:
        """
        Returns True if package has an environment file
        :return: True or False
        """
        return len(self.file_data) > 0

    @cached_property
    def binstar(self) -> ModuleType | None:
        try:
            from binstar_client.utils import get_server_api

            return get_server_api()
        except ImportError:
            return None

    @cached_property
    def file_data(self) -> list[dict[str, str]]:
        return [data for data in self.package["files"] if data["type"] == "env"]

    @cached_property
    def environment(self) -> Environment:
        versions = [
            {"normalized": normalized_version(d["version"]), "original": d["version"]}
            for d in self.file_data
        ]
        latest_version = max(versions, key=lambda x: x["normalized"])["original"]
        file_data = [
            data for data in self.package["files"] if data["version"] == latest_version
        ]
        req = self.binstar.download(
            self.username, self.packagename, latest_version, file_data[0]["basename"]
        )
        if req is None:
            raise EnvironmentFileNotDownloaded(self.username, self.packagename)
        return from_yaml(req.text)

    @cached_property
    def package(self):
        try:
            return self.binstar.package(self.username, self.packagename)
        except (IndexError, AttributeError):
            self.msg = (
                f"{self.name} was not found on anaconda.org.\n"
                "You may need to be logged in. Try running:\n"
                "    anaconda login"
            )

    @cached_property
    def username(self) -> str:
        return self.name.split("/", 1)[0]

    @cached_property
    def packagename(self) -> str:
        return self.name.split("/", 1)[1]
