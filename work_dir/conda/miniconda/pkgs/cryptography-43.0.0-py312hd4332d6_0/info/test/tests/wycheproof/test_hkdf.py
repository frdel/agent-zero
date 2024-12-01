# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .utils import wycheproof_tests

_HASH_ALGORITHMS = {
    "HKDF-SHA-1": hashes.SHA1(),
    "HKDF-SHA-256": hashes.SHA256(),
    "HKDF-SHA-384": hashes.SHA384(),
    "HKDF-SHA-512": hashes.SHA512(),
}


@wycheproof_tests(
    "hkdf_sha1_test.json",
    "hkdf_sha256_test.json",
    "hkdf_sha384_test.json",
    "hkdf_sha512_test.json",
)
def test_hkdf(backend, wycheproof):
    hash_algo = _HASH_ALGORITHMS[wycheproof.testfiledata["algorithm"]]
    if wycheproof.invalid:
        with pytest.raises(ValueError):
            HKDF(
                algorithm=hash_algo,
                length=wycheproof.testcase["size"],
                salt=binascii.unhexlify(wycheproof.testcase["salt"]),
                info=binascii.unhexlify(wycheproof.testcase["info"]),
                backend=backend,
            )
        return

    h = HKDF(
        algorithm=hash_algo,
        length=wycheproof.testcase["size"],
        salt=binascii.unhexlify(wycheproof.testcase["salt"]),
        info=binascii.unhexlify(wycheproof.testcase["info"]),
        backend=backend,
    )
    result = h.derive(binascii.unhexlify(wycheproof.testcase["ikm"]))
    assert result == binascii.unhexlify(wycheproof.testcase["okm"])
