# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .utils import wycheproof_tests


@pytest.mark.supported(
    only_if=lambda backend: backend.ed25519_supported(),
    skip_message="Requires OpenSSL with Ed25519 support",
)
@wycheproof_tests("eddsa_test.json")
def test_ed25519_signature(backend, wycheproof):
    # We want to fail if/when wycheproof adds more edwards curve tests
    # so we can add them as well.
    assert wycheproof.testgroup["key"]["curve"] == "edwards25519"

    key = Ed25519PublicKey.from_public_bytes(
        binascii.unhexlify(wycheproof.testgroup["key"]["pk"])
    )

    if wycheproof.valid or wycheproof.acceptable:
        key.verify(
            binascii.unhexlify(wycheproof.testcase["sig"]),
            binascii.unhexlify(wycheproof.testcase["msg"]),
        )
    else:
        with pytest.raises(InvalidSignature):
            key.verify(
                binascii.unhexlify(wycheproof.testcase["sig"]),
                binascii.unhexlify(wycheproof.testcase["msg"]),
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.ed448_supported(),
    skip_message="Requires OpenSSL with Ed448 support",
)
@wycheproof_tests("ed448_test.json")
def test_ed448_signature(backend, wycheproof):
    key = Ed448PublicKey.from_public_bytes(
        binascii.unhexlify(wycheproof.testgroup["key"]["pk"])
    )

    if wycheproof.valid or wycheproof.acceptable:
        key.verify(
            binascii.unhexlify(wycheproof.testcase["sig"]),
            binascii.unhexlify(wycheproof.testcase["msg"]),
        )
    else:
        with pytest.raises(InvalidSignature):
            key.verify(
                binascii.unhexlify(wycheproof.testcase["sig"]),
                binascii.unhexlify(wycheproof.testcase["msg"]),
            )
