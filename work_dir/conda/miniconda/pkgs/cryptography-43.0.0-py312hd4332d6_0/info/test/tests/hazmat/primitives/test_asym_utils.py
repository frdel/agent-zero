# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    decode_dss_signature,
    encode_dss_signature,
)


def test_dss_signature():
    sig = encode_dss_signature(1, 1)
    assert sig == b"0\x06\x02\x01\x01\x02\x01\x01"
    assert decode_dss_signature(sig) == (1, 1)

    r_s1 = (
        1037234182290683143945502320610861668562885151617,
        559776156650501990899426031439030258256861634312,
    )
    sig2 = encode_dss_signature(*r_s1)
    assert sig2 == (
        b"0-\x02\x15\x00\xb5\xaf0xg\xfb\x8bT9\x00\x13\xccg\x02\r\xdf\x1f,\x0b"
        b'\x81\x02\x14b\r;"\xabP1D\x0c>5\xea\xb6\xf4\x81)\x8f\x9e\x9f\x08'
    )
    assert decode_dss_signature(sig2) == r_s1

    sig3 = encode_dss_signature(0, 0)
    assert sig3 == b"0\x06\x02\x01\x00\x02\x01\x00"
    assert decode_dss_signature(sig3) == (0, 0)


def test_encode_dss_non_integer():
    with pytest.raises(TypeError):
        encode_dss_signature("h", 3)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        encode_dss_signature("3", "2")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        encode_dss_signature(3, "h")  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        encode_dss_signature(3.3, 1.2)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        encode_dss_signature("hello", "world")  # type: ignore[arg-type]


def test_encode_dss_negative():
    with pytest.raises(ValueError):
        encode_dss_signature(-1, 0)
    with pytest.raises(ValueError):
        encode_dss_signature(0, -1)


def test_decode_dss_trailing_bytes():
    with pytest.raises(ValueError):
        decode_dss_signature(b"0\x06\x02\x01\x01\x02\x01\x01\x00\x00\x00")


def test_decode_dss_invalid_asn1():
    with pytest.raises(ValueError):
        # This byte sequence has an invalid ASN.1 sequence length as well as
        # an invalid integer length for the second integer.
        decode_dss_signature(b"0\x07\x02\x01\x01\x02\x02\x01")

    with pytest.raises(ValueError):
        # This is the BER "end-of-contents octets".
        decode_dss_signature(b"\x00\x00")


def test_pass_invalid_prehashed_arg():
    with pytest.raises(TypeError):
        Prehashed(object())  # type: ignore[arg-type]


def test_prehashed_digest_size():
    p = Prehashed(hashes.SHA256())
    assert p.digest_size == 32
