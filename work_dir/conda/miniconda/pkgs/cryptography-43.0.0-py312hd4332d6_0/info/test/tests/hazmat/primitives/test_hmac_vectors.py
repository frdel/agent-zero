# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii

import pytest

from cryptography.hazmat.primitives import hashes, hmac

from ...utils import load_hash_vectors
from .utils import generate_hmac_test


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.MD5()),
    skip_message="Does not support MD5",
)
class TestHMACMD5:
    test_hmac_md5 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-2202-md5.txt"],
        hashes.MD5(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA1()),
    skip_message="Does not support SHA1",
)
class TestHMACSHA1:
    test_hmac_sha1 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-2202-sha1.txt"],
        hashes.SHA1(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA224()),
    skip_message="Does not support SHA224",
)
class TestHMACSHA224:
    test_hmac_sha224 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-4231-sha224.txt"],
        hashes.SHA224(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA256()),
    skip_message="Does not support SHA256",
)
class TestHMACSHA256:
    test_hmac_sha256 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-4231-sha256.txt"],
        hashes.SHA256(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA384()),
    skip_message="Does not support SHA384",
)
class TestHMACSHA384:
    test_hmac_sha384 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-4231-sha384.txt"],
        hashes.SHA384(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(hashes.SHA512()),
    skip_message="Does not support SHA512",
)
class TestHMACSHA512:
    test_hmac_sha512 = generate_hmac_test(
        load_hash_vectors,
        "HMAC",
        ["rfc-4231-sha512.txt"],
        hashes.SHA512(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.hmac_supported(
        hashes.BLAKE2b(digest_size=64)
    ),
    skip_message="Does not support BLAKE2",
)
class TestHMACBLAKE2:
    def test_blake2b(self, backend):
        h = hmac.HMAC(b"0" * 64, hashes.BLAKE2b(digest_size=64), backend)
        h.update(b"test")
        digest = h.finalize()
        assert digest == binascii.unhexlify(
            b"b5319122f8a24ba134a0c9851922448104e25be5d1b91265c0c68b22722f0f29"
            b"87dba4aeaa69e6bed7edc44f48d6b1be493a3ce583f9c737c53d6bacc09e2f32"
        )

    def test_blake2s(self, backend):
        h = hmac.HMAC(b"0" * 32, hashes.BLAKE2s(digest_size=32), backend)
        h.update(b"test")
        digest = h.finalize()
        assert digest == binascii.unhexlify(
            b"51477cc5bdf1faf952cf97bb934ee936de1f4d5d7448a84eeb6f98d23b392166"
        )
