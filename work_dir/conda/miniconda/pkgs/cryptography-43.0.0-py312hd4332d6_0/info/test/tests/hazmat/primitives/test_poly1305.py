# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.exceptions import (
    AlreadyFinalized,
    InvalidSignature,
    _Reasons,
)
from cryptography.hazmat.primitives.poly1305 import Poly1305

from ...utils import (
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)


@pytest.mark.supported(
    only_if=lambda backend: not backend.poly1305_supported(),
    skip_message="Requires OpenSSL without poly1305 support",
)
def test_poly1305_unsupported(backend):
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_MAC):
        Poly1305(b"0" * 32)


@pytest.mark.supported(
    only_if=lambda backend: backend.poly1305_supported(),
    skip_message="Requires OpenSSL with poly1305 support",
)
class TestPoly1305:
    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("poly1305", "rfc7539.txt"), load_nist_vectors
        ),
    )
    def test_vectors(self, vector, backend):
        key = binascii.unhexlify(vector["key"])
        msg = binascii.unhexlify(vector["msg"])
        tag = binascii.unhexlify(vector["tag"])
        poly = Poly1305(key)
        poly.update(msg)
        assert poly.finalize() == tag

        assert Poly1305.generate_tag(key, msg) == tag
        Poly1305.verify_tag(key, msg, tag)

    def test_key_with_no_additional_references(self, backend):
        poly = Poly1305(os.urandom(32))
        assert len(poly.finalize()) == 16

    def test_raises_after_finalize(self, backend):
        poly = Poly1305(b"0" * 32)
        poly.finalize()

        with pytest.raises(AlreadyFinalized):
            poly.update(b"foo")

        with pytest.raises(AlreadyFinalized):
            poly.finalize()

    def test_reject_unicode(self, backend):
        poly = Poly1305(b"0" * 32)
        with pytest.raises(TypeError):
            poly.update("")  # type:ignore[arg-type]

        with pytest.raises(TypeError):
            Poly1305.generate_tag(b"0" * 32, "")  # type:ignore[arg-type]

    def test_verify(self, backend):
        poly = Poly1305(b"0" * 32)
        poly.update(b"msg")
        tag = poly.finalize()

        with pytest.raises(AlreadyFinalized):
            poly.verify(b"")

        poly2 = Poly1305(b"0" * 32)
        poly2.update(b"msg")
        poly2.verify(tag)

        Poly1305.verify_tag(b"0" * 32, b"msg", tag)

    def test_invalid_verify(self, backend):
        poly = Poly1305(b"0" * 32)
        poly.update(b"msg")
        with pytest.raises(InvalidSignature):
            poly.verify(b"")

        p2 = Poly1305(b"0" * 32)
        p2.update(b"msg")
        with pytest.raises(InvalidSignature):
            p2.verify(b"\x00" * 16)

        with pytest.raises(InvalidSignature):
            Poly1305.verify_tag(b"0" * 32, b"msg", b"\x00" * 16)

    def test_verify_reject_unicode(self, backend):
        poly = Poly1305(b"0" * 32)
        with pytest.raises(TypeError):
            poly.verify("")  # type:ignore[arg-type]

        with pytest.raises(TypeError):
            Poly1305.verify_tag(b"0" * 32, b"msg", "")  # type:ignore[arg-type]

    def test_invalid_key_type(self, backend):
        with pytest.raises(TypeError):
            Poly1305(object())  # type:ignore[arg-type]

        with pytest.raises(TypeError):
            Poly1305.generate_tag(object(), b"msg")  # type:ignore[arg-type]

    def test_invalid_key_length(self, backend):
        with pytest.raises(ValueError):
            Poly1305(b"0" * 31)

        with pytest.raises(ValueError):
            Poly1305.generate_tag(b"0" * 31, b"msg")

        with pytest.raises(ValueError):
            Poly1305(b"0" * 33)

        with pytest.raises(ValueError):
            Poly1305.generate_tag(b"0" * 33, b"msg")

    def test_buffer_protocol(self, backend):
        key = binascii.unhexlify(
            b"1c9240a5eb55d38af333888604f6b5f0473917c1402b80099dca5cb"
            b"c207075c0"
        )
        msg = binascii.unhexlify(
            b"2754776173206272696c6c69672c20616e642074686520736c69746"
            b"87920746f7665730a446964206779726520616e642067696d626c65"
            b"20696e2074686520776162653a0a416c6c206d696d7379207765726"
            b"52074686520626f726f676f7665732c0a416e6420746865206d6f6d"
            b"65207261746873206f757467726162652e"
        )
        key = bytearray(key)
        poly = Poly1305(key)
        poly.update(bytearray(msg))
        assert poly.finalize() == binascii.unhexlify(
            b"4541669a7eaaee61e708dc7cbcc5eb62"
        )

        assert Poly1305.generate_tag(key, msg) == binascii.unhexlify(
            b"4541669a7eaaee61e708dc7cbcc5eb62"
        )
