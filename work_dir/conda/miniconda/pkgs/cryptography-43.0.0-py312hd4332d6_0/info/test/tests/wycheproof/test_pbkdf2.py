# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .utils import wycheproof_tests

_HASH_ALGORITHMS = {
    "PBKDF2-HMACSHA1": hashes.SHA1(),
    "PBKDF2-HMACSHA224": hashes.SHA224(),
    "PBKDF2-HMACSHA256": hashes.SHA256(),
    "PBKDF2-HMACSHA384": hashes.SHA384(),
    "PBKDF2-HMACSHA512": hashes.SHA512(),
}


@wycheproof_tests(
    "pbkdf2_hmacsha1_test.json",
    "pbkdf2_hmacsha224_test.json",
    "pbkdf2_hmacsha256_test.json",
    "pbkdf2_hmacsha384_test.json",
    "pbkdf2_hmacsha512_test.json",
    subdir="testvectors_v1",
)
def test_pbkdf2(backend, wycheproof):
    assert wycheproof.valid

    algorithm = _HASH_ALGORITHMS[wycheproof.testfiledata["algorithm"]]

    p = PBKDF2HMAC(
        algorithm=algorithm,
        length=wycheproof.testcase["dkLen"],
        salt=binascii.unhexlify(wycheproof.testcase["salt"]),
        iterations=wycheproof.testcase["iterationCount"],
    )
    assert p.derive(
        binascii.unhexlify(wycheproof.testcase["password"])
    ) == binascii.unhexlify(wycheproof.testcase["dk"])
