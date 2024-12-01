# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii

import pytest

from cryptography.exceptions import AlreadyFinalized, _Reasons
from cryptography.hazmat.primitives import hashes

from ...doubles import DummyHashAlgorithm
from ...utils import raises_unsupported_algorithm
from .utils import generate_base_hash_test


class TestHashContext:
    def test_hash_reject_unicode(self, backend):
        m = hashes.Hash(hashes.SHA1(), backend=backend)
        with pytest.raises(TypeError):
            m.update("\u00fc")  # type: ignore[arg-type]

    def test_hash_algorithm_instance(self, backend):
        with pytest.raises(TypeError):
            hashes.Hash(hashes.SHA1, backend=backend)  # type: ignore[arg-type]

    def test_raises_after_finalize(self, backend):
        h = hashes.Hash(hashes.SHA1(), backend=backend)
        h.finalize()

        with pytest.raises(AlreadyFinalized):
            h.update(b"foo")

        with pytest.raises(AlreadyFinalized):
            h.copy()

        with pytest.raises(AlreadyFinalized):
            h.finalize()

    def test_unsupported_hash(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            hashes.Hash(DummyHashAlgorithm(), backend)


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SHA1()),
    skip_message="Does not support SHA1",
)
class TestSHA1:
    test_sha1 = generate_base_hash_test(
        hashes.SHA1(),
        digest_size=20,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SHA224()),
    skip_message="Does not support SHA224",
)
class TestSHA224:
    test_sha224 = generate_base_hash_test(
        hashes.SHA224(),
        digest_size=28,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SHA256()),
    skip_message="Does not support SHA256",
)
class TestSHA256:
    test_sha256 = generate_base_hash_test(
        hashes.SHA256(),
        digest_size=32,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SHA384()),
    skip_message="Does not support SHA384",
)
class TestSHA384:
    test_sha384 = generate_base_hash_test(
        hashes.SHA384(),
        digest_size=48,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SHA512()),
    skip_message="Does not support SHA512",
)
class TestSHA512:
    test_sha512 = generate_base_hash_test(
        hashes.SHA512(),
        digest_size=64,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.MD5()),
    skip_message="Does not support MD5",
)
class TestMD5:
    test_md5 = generate_base_hash_test(
        hashes.MD5(),
        digest_size=16,
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(
        hashes.BLAKE2b(digest_size=64)
    ),
    skip_message="Does not support BLAKE2b",
)
class TestBLAKE2b:
    test_blake2b = generate_base_hash_test(
        hashes.BLAKE2b(digest_size=64),
        digest_size=64,
    )

    def test_invalid_digest_size(self, backend):
        with pytest.raises(ValueError):
            hashes.BLAKE2b(digest_size=65)

        with pytest.raises(ValueError):
            hashes.BLAKE2b(digest_size=0)

        with pytest.raises(ValueError):
            hashes.BLAKE2b(digest_size=-1)


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(
        hashes.BLAKE2s(digest_size=32)
    ),
    skip_message="Does not support BLAKE2s",
)
class TestBLAKE2s:
    test_blake2s = generate_base_hash_test(
        hashes.BLAKE2s(digest_size=32),
        digest_size=32,
    )

    def test_invalid_digest_size(self, backend):
        with pytest.raises(ValueError):
            hashes.BLAKE2s(digest_size=33)

        with pytest.raises(ValueError):
            hashes.BLAKE2s(digest_size=0)

        with pytest.raises(ValueError):
            hashes.BLAKE2s(digest_size=-1)


def test_buffer_protocol_hash(backend):
    data = binascii.unhexlify(b"b4190e")
    h = hashes.Hash(hashes.SHA256(), backend)
    h.update(bytearray(data))
    assert h.finalize() == binascii.unhexlify(
        b"dff2e73091f6c05e528896c4c831b9448653dc2ff043528f6769437bc7b975c2"
    )


class TestSHAKE:
    @pytest.mark.parametrize("xof", [hashes.SHAKE128, hashes.SHAKE256])
    def test_invalid_digest_type(self, xof):
        with pytest.raises(TypeError):
            xof(digest_size=object())

    @pytest.mark.parametrize("xof", [hashes.SHAKE128, hashes.SHAKE256])
    def test_invalid_digest_size(self, xof):
        with pytest.raises(ValueError):
            xof(digest_size=-5)

        with pytest.raises(ValueError):
            xof(digest_size=0)


@pytest.mark.supported(
    only_if=lambda backend: backend.hash_supported(hashes.SM3()),
    skip_message="Does not support SM3",
)
class TestSM3:
    test_sm3 = generate_base_hash_test(
        hashes.SM3(),
        digest_size=32,
    )
