# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii

import pytest

from cryptography.exceptions import (
    AlreadyFinalized,
    InvalidSignature,
    _Reasons,
)
from cryptography.hazmat.primitives import hashes, hmac

from ...doubles import DummyHashAlgorithm
from ...utils import raises_unsupported_algorithm
from .utils import generate_base_hmac_test


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.MD5()),
    skip_message="Does not support MD5",
)
class TestHMACCopy:
    test_copy = generate_base_hmac_test(
        hashes.MD5(),
    )


class TestHMAC:
    def test_hmac_reject_unicode(self, backend):
        h = hmac.HMAC(b"mykey", hashes.SHA1(), backend=backend)
        with pytest.raises(TypeError):
            h.update("\u00fc")  # type: ignore[arg-type]

    def test_hmac_algorithm_instance(self, backend):
        with pytest.raises(TypeError):
            hmac.HMAC(
                b"key",
                hashes.SHA1,  # type: ignore[arg-type]
                backend=backend,
            )

    def test_raises_after_finalize(self, backend):
        h = hmac.HMAC(b"key", hashes.SHA1(), backend=backend)
        h.finalize()

        with pytest.raises(AlreadyFinalized):
            h.update(b"foo")

        with pytest.raises(AlreadyFinalized):
            h.copy()

        with pytest.raises(AlreadyFinalized):
            h.finalize()

    def test_verify(self, backend):
        h = hmac.HMAC(b"", hashes.SHA1(), backend=backend)
        digest = h.finalize()

        h = hmac.HMAC(b"", hashes.SHA1(), backend=backend)
        h.verify(digest)

        with pytest.raises(AlreadyFinalized):
            h.verify(b"")

    def test_invalid_verify(self, backend):
        h = hmac.HMAC(b"", hashes.SHA1(), backend=backend)
        with pytest.raises(InvalidSignature):
            h.verify(b"")

        with pytest.raises(AlreadyFinalized):
            h.verify(b"")

    def test_verify_reject_unicode(self, backend):
        h = hmac.HMAC(b"", hashes.SHA1(), backend=backend)
        with pytest.raises(TypeError):
            h.verify("")  # type: ignore[arg-type]

    def test_unsupported_hash(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            hmac.HMAC(b"key", DummyHashAlgorithm(), backend)

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            hmac.HMAC(b"key", hashes.SHAKE256(digest_size=256), backend)

    def test_buffer_protocol(self, backend):
        key = bytearray(b"2b7e151628aed2a6abf7158809cf4f3c")
        h = hmac.HMAC(key, hashes.SHA256(), backend)
        h.update(bytearray(b"6bc1bee22e409f96e93d7e117393172a"))
        assert h.finalize() == binascii.unhexlify(
            b"a1bf7169c56a501c6585190ff4f07cad6e492a3ee187c0372614fb444b9fc3f0"
        )

    def test_algorithm(self):
        alg = hashes.SHA256()
        h = hmac.HMAC(b"123456", alg)
        assert h.algorithm is alg
