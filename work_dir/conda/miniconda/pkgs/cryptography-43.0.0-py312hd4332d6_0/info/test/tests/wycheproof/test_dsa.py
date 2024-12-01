# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dsa

from .utils import wycheproof_tests

_DIGESTS = {
    "SHA-1": hashes.SHA1(),
    "SHA-224": hashes.SHA224(),
    "SHA-256": hashes.SHA256(),
}


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Requires OpenSSL with DSA support",
)
@wycheproof_tests(
    "dsa_test.json",
    "dsa_2048_224_sha224_test.json",
    "dsa_2048_224_sha256_test.json",
    "dsa_2048_256_sha256_test.json",
    "dsa_3072_256_sha256_test.json",
)
def test_dsa_signature(backend, wycheproof):
    key = serialization.load_der_public_key(
        binascii.unhexlify(wycheproof.testgroup["keyDer"]), backend
    )
    assert isinstance(key, dsa.DSAPublicKey)
    digest = _DIGESTS[wycheproof.testgroup["sha"]]

    if wycheproof.valid or (
        wycheproof.acceptable and not wycheproof.has_flag("NoLeadingZero")
    ):
        key.verify(
            binascii.unhexlify(wycheproof.testcase["sig"]),
            binascii.unhexlify(wycheproof.testcase["msg"]),
            digest,
        )
    else:
        with pytest.raises(InvalidSignature):
            key.verify(
                binascii.unhexlify(wycheproof.testcase["sig"]),
                binascii.unhexlify(wycheproof.testcase["msg"]),
                digest,
            )
