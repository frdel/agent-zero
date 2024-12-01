# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Define requirements.txt spec."""

import os

from ..env import Environment


class RequirementsSpec:
    """
    Reads dependencies from a requirements.txt file
    and returns an Environment object from it.
    """

    msg = None
    extensions = {".txt"}

    def __init__(self, filename=None, name=None, **kwargs):
        self.filename = filename
        self.name = name
        self.msg = None

    def _valid_file(self):
        if os.path.exists(self.filename):
            return True
        else:
            self.msg = "There is no requirements.txt"
            return False

    def _valid_name(self):
        if self.name is None:
            self.msg = "Environment with requirements.txt file needs a name"
            return False
        else:
            return True

    def can_handle(self):
        return self._valid_file() and self._valid_name()

    @property
    def environment(self):
        dependencies = []
        with open(self.filename) as reqfile:
            for line in reqfile:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                dependencies.append(line)
        return Environment(name=self.name, dependencies=dependencies)
