# Copyright (C) 2012 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""Extends unittest.TestCase to include select pytest fixtures."""

import unittest

import pytest


class BaseTestCase(unittest.TestCase):
    fixture_names = ("tmpdir",)

    @pytest.fixture(autouse=True)
    def auto_injector_fixture(self, request):
        names = self.fixture_names
        for name in names:
            setattr(self, name, request.getfixturevalue(name))
