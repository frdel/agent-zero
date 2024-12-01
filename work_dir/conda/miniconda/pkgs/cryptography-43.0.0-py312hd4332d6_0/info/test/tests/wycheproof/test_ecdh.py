# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import binascii

import pytest

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ..hazmat.primitives.test_ec import _skip_exchange_algorithm_unsupported
from .utils import wycheproof_tests

_CURVES = {
    "secp224r1": ec.SECP224R1(),
    "secp256r1": ec.SECP256R1(),
    "secp384r1": ec.SECP384R1(),
    "secp521r1": ec.SECP521R1(),
    "secp224k1": None,
    "secp256k1": ec.SECP256K1(),
    "sect283r1": ec.SECT283R1(),
    "sect409r1": ec.SECT409R1(),
    "sect571r1": ec.SECT571R1(),
    "sect283k1": ec.SECT283K1(),
    "sect409k1": ec.SECT409K1(),
    "sect571k1": ec.SECT571K1(),
    "brainpoolP224r1": None,
    "brainpoolP256r1": ec.BrainpoolP256R1(),
    "brainpoolP320r1": None,
    "brainpoolP384r1": ec.BrainpoolP384R1(),
    "brainpoolP512r1": ec.BrainpoolP512R1(),
    "brainpoolP224t1": None,
    "brainpoolP256t1": None,
    "brainpoolP320t1": None,
    "brainpoolP384t1": None,
    "brainpoolP512t1": None,
    "FRP256v1": None,
}


@wycheproof_tests(
    "ecdh_test.json",
    "ecdh_brainpoolP224r1_test.json",
    "ecdh_brainpoolP256r1_test.json",
    "ecdh_brainpoolP320r1_test.json",
    "ecdh_brainpoolP384r1_test.json",
    "ecdh_brainpoolP512r1_test.json",
    "ecdh_secp224r1_test.json",
    "ecdh_secp256k1_test.json",
    "ecdh_secp256r1_test.json",
    "ecdh_secp384r1_test.json",
    "ecdh_secp521r1_test.json",
    "ecdh_sect283k1_test.json",
    "ecdh_sect283r1_test.json",
    "ecdh_sect409k1_test.json",
    "ecdh_sect409r1_test.json",
    "ecdh_sect571k1_test.json",
    "ecdh_sect571r1_test.json",
)
def test_ecdh(backend, wycheproof):
    curve = _CURVES[wycheproof.testgroup["curve"]]
    if curve is None:
        pytest.skip(
            "Unsupported curve ({})".format(wycheproof.testgroup["curve"])
        )
    _skip_exchange_algorithm_unsupported(backend, ec.ECDH(), curve)
    private_key = wycheproof.cache_value_to_group(
        f"private_key_{wycheproof.testcase['private']}",
        lambda: ec.derive_private_key(
            int(wycheproof.testcase["private"], 16), curve
        ),
    )

    try:
        # caching these values shows no performance improvement
        public_key = serialization.load_der_public_key(
            binascii.unhexlify(wycheproof.testcase["public"]), backend
        )
        assert isinstance(public_key, ec.EllipticCurvePublicKey)
    except ValueError:
        assert wycheproof.invalid or wycheproof.acceptable
        return
    except UnsupportedAlgorithm:
        return

    if wycheproof.valid or wycheproof.acceptable:
        computed_shared = private_key.exchange(ec.ECDH(), public_key)
        expected_shared = binascii.unhexlify(wycheproof.testcase["shared"])
        assert computed_shared == expected_shared
    else:
        with pytest.raises(ValueError):
            private_key.exchange(ec.ECDH(), public_key)


@wycheproof_tests(
    "ecdh_secp224r1_ecpoint_test.json",
    "ecdh_secp256r1_ecpoint_test.json",
    "ecdh_secp384r1_ecpoint_test.json",
    "ecdh_secp521r1_ecpoint_test.json",
)
def test_ecdh_ecpoint(backend, wycheproof):
    curve = _CURVES[wycheproof.testgroup["curve"]]
    assert isinstance(curve, ec.EllipticCurve)
    _skip_exchange_algorithm_unsupported(backend, ec.ECDH(), curve)

    private_key = wycheproof.cache_value_to_group(
        f"private_key_{wycheproof.testcase['private']}",
        lambda: ec.derive_private_key(
            int(wycheproof.testcase["private"], 16), curve
        ),
    )

    if wycheproof.invalid:
        with pytest.raises(ValueError):
            ec.EllipticCurvePublicKey.from_encoded_point(
                curve, binascii.unhexlify(wycheproof.testcase["public"])
            )
        return

    assert wycheproof.valid or wycheproof.acceptable
    # caching these values shows no performance improvement
    public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        curve, binascii.unhexlify(wycheproof.testcase["public"])
    )
    computed_shared = private_key.exchange(ec.ECDH(), public_key)
    expected_shared = binascii.unhexlify(wycheproof.testcase["shared"])
    assert computed_shared == expected_shared
