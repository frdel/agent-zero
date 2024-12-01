# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import copy

import pytest

from cryptography.hazmat._oid import ObjectIdentifier


def test_basic_oid():
    assert ObjectIdentifier("1.2.3.4").dotted_string == "1.2.3.4"


def test_oid_equal():
    assert ObjectIdentifier("1.2.3.4") == ObjectIdentifier("1.2.3.4")


def test_oid_deepcopy():
    oid = ObjectIdentifier("1.2.3.4")
    assert oid == copy.deepcopy(oid)


def test_oid_constraint():
    # Too short
    with pytest.raises(ValueError):
        ObjectIdentifier("1")

    # First node too big
    with pytest.raises(ValueError):
        ObjectIdentifier("3.2.1")

    # Outside range
    with pytest.raises(ValueError):
        ObjectIdentifier("1.40")
    with pytest.raises(ValueError):
        ObjectIdentifier("0.42")

    # non-decimal oid
    with pytest.raises(ValueError):
        ObjectIdentifier("1.2.foo.bar")
    with pytest.raises(ValueError):
        ObjectIdentifier("1.2.0xf00.0xba4")

    # negative oid
    with pytest.raises(ValueError):
        ObjectIdentifier("1.2.-3.-4")
