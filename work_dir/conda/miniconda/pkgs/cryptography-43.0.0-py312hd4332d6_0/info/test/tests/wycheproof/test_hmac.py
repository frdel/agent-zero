# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, hmac

from .utils import wycheproof_tests

_HMAC_ALGORITHMS = {
    "HMACSHA1": hashes.SHA1(),
    "HMACSHA224": hashes.SHA224(),
    "HMACSHA256": hashes.SHA256(),
    "HMACSHA384": hashes.SHA384(),
    "HMACSHA512": hashes.SHA512(),
    "HMACSHA3-224": hashes.SHA3_224(),
    "HMACSHA3-256": hashes.SHA3_256(),
    "HMACSHA3-384": hashes.SHA3_384(),
    "HMACSHA3-512": hashes.SHA3_512(),
}


@wycheproof_tests(
    "hmac_sha1_test.json",
    "hmac_sha224_test.json",
    "hmac_sha256_test.json",
    "hmac_sha384_test.json",
    "hmac_sha3_224_test.json",
    "hmac_sha3_256_test.json",
    "hmac_sha3_384_test.json",
    "hmac_sha3_512_test.json",
    "hmac_sha512_test.json",
)
def test_hmac(backend, wycheproof):
    hash_algo = _HMAC_ALGORITHMS[wycheproof.testfiledata["algorithm"]]
    if wycheproof.testgroup["tagSize"] // 8 != hash_algo.digest_size:
        pytest.skip("Truncated HMAC not supported")
    if not backend.hmac_supported(hash_algo):
        pytest.skip(f"Hash {hash_algo.name} not supported")

    h = hmac.HMAC(
        key=binascii.unhexlify(wycheproof.testcase["key"]),
        algorithm=hash_algo,
        backend=backend,
    )
    h.update(binascii.unhexlify(wycheproof.testcase["msg"]))

    if wycheproof.invalid:
        with pytest.raises(InvalidSignature):
            h.verify(binascii.unhexlify(wycheproof.testcase["tag"]))
    else:
        tag = h.finalize()
        assert tag == binascii.unhexlify(wycheproof.testcase["tag"])

        h = hmac.HMAC(
            key=binascii.unhexlify(wycheproof.testcase["key"]),
            algorithm=hash_algo,
            backend=backend,
        )
        h.update(binascii.unhexlify(wycheproof.testcase["msg"]))
        h.verify(binascii.unhexlify(wycheproof.testcase["tag"]))
