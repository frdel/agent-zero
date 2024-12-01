# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import pytest

from cryptography.hazmat.primitives import constant_time


class TestConstantTimeBytesEq:
    def test_reject_unicode(self):
        with pytest.raises(TypeError):
            constant_time.bytes_eq(b"foo", "foo")  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            constant_time.bytes_eq("foo", b"foo")  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            constant_time.bytes_eq("foo", "foo")  # type: ignore[arg-type]

    def test_compares(self):
        assert constant_time.bytes_eq(b"foo", b"foo") is True

        assert constant_time.bytes_eq(b"foo", b"bar") is False

        assert constant_time.bytes_eq(b"foobar", b"foo") is False

        assert constant_time.bytes_eq(b"foo", b"foobar") is False
