# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from .utils import wycheproof_tests

_DIGESTS = {
    "SHA-1": hashes.SHA1(),
    "SHA-224": hashes.SHA224(),
    "SHA-256": hashes.SHA256(),
    "SHA-384": hashes.SHA384(),
    "SHA-512": hashes.SHA512(),
    "SHA3-224": hashes.SHA3_224(),
    "SHA3-256": hashes.SHA3_256(),
    "SHA3-384": hashes.SHA3_384(),
    "SHA3-512": hashes.SHA3_512(),
}


@wycheproof_tests(
    "ecdsa_test.json",
    "ecdsa_brainpoolP224r1_sha224_test.json",
    "ecdsa_brainpoolP256r1_sha256_test.json",
    "ecdsa_brainpoolP320r1_sha384_test.json",
    "ecdsa_brainpoolP384r1_sha384_test.json",
    "ecdsa_brainpoolP512r1_sha512_test.json",
    "ecdsa_secp224r1_sha224_test.json",
    "ecdsa_secp224r1_sha256_test.json",
    "ecdsa_secp224r1_sha512_test.json",
    "ecdsa_secp224r1_sha3_224_test.json",
    "ecdsa_secp224r1_sha3_256_test.json",
    "ecdsa_secp224r1_sha3_512_test.json",
    "ecdsa_secp256k1_sha256_test.json",
    "ecdsa_secp256k1_sha512_test.json",
    "ecdsa_secp256k1_sha3_256_test.json",
    "ecdsa_secp256k1_sha3_512_test.json",
    "ecdsa_secp256r1_sha256_test.json",
    "ecdsa_secp256r1_sha512_test.json",
    "ecdsa_secp256r1_sha3_256_test.json",
    "ecdsa_secp256r1_sha3_512_test.json",
    "ecdsa_secp384r1_sha384_test.json",
    "ecdsa_secp384r1_sha512_test.json",
    "ecdsa_secp384r1_sha3_384_test.json",
    "ecdsa_secp384r1_sha3_512_test.json",
    "ecdsa_secp521r1_sha512_test.json",
    "ecdsa_secp521r1_sha3_512_test.json",
    "ecdsa_secp160k1_sha256_test.json",
    "ecdsa_secp160r1_sha256_test.json",
    "ecdsa_secp160r2_sha256_test.json",
    "ecdsa_secp192k1_sha256_test.json",
    "ecdsa_secp192r1_sha256_test.json",
)
def test_ecdsa_signature(backend, wycheproof):
    try:
        key = wycheproof.cache_value_to_group(
            "cache_key",
            lambda: serialization.load_der_public_key(
                binascii.unhexlify(wycheproof.testgroup["keyDer"])
            ),
        )
        assert isinstance(key, ec.EllipticCurvePublicKey)
    except (UnsupportedAlgorithm, ValueError):
        # In some OpenSSL 1.1.1 versions (RHEL and Fedora), some keys fail to
        # load with ValueError, instead of  Unsupported Algorithm. We can
        # remove handling for that exception when we drop support.
        pytest.skip(
            "unable to load key (curve {})".format(
                wycheproof.testgroup["key"]["curve"]
            )
        )
    digest = _DIGESTS[wycheproof.testgroup["sha"]]

    alg = ec.ECDSA(digest)
    if not backend.elliptic_curve_signature_algorithm_supported(
        alg, key.curve
    ):
        pytest.skip(f"Signature with {digest} and {key.curve} not supported")

    if wycheproof.valid or (
        wycheproof.acceptable and not wycheproof.has_flag("MissingZero")
    ):
        key.verify(
            binascii.unhexlify(wycheproof.testcase["sig"]),
            binascii.unhexlify(wycheproof.testcase["msg"]),
            alg,
        )
    else:
        with pytest.raises(InvalidSignature):
            key.verify(
                binascii.unhexlify(wycheproof.testcase["sig"]),
                binascii.unhexlify(wycheproof.testcase["msg"]),
                alg,
            )
