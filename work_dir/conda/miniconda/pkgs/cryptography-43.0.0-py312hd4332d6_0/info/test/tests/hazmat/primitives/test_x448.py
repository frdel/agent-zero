# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import copy
import os

import pytest

from cryptography.exceptions import _Reasons
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x448 import (
    X448PrivateKey,
    X448PublicKey,
)

from ...doubles import DummyKeySerializationEncryption
from ...utils import (
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)


@pytest.mark.supported(
    only_if=lambda backend: not backend.x448_supported(),
    skip_message="Requires OpenSSL without X448 support",
)
def test_x448_unsupported(backend):
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X448PublicKey.from_public_bytes(b"0" * 56)

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X448PrivateKey.from_private_bytes(b"0" * 56)

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X448PrivateKey.generate()


@pytest.mark.supported(
    only_if=lambda backend: backend.x448_supported(),
    skip_message="Requires OpenSSL with X448 support",
)
class TestX448Exchange:
    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "X448", "rfc7748.txt"),
            load_nist_vectors,
        ),
    )
    def test_rfc7748(self, vector, backend):
        private = binascii.unhexlify(vector["input_scalar"])
        public = binascii.unhexlify(vector["input_u"])
        shared_key = binascii.unhexlify(vector["output_u"])
        private_key = X448PrivateKey.from_private_bytes(private)
        public_key = X448PublicKey.from_public_bytes(public)
        computed_shared_key = private_key.exchange(public_key)
        assert computed_shared_key == shared_key

    def test_rfc7748_1000_iteration(self, backend):
        old_private = private = public = binascii.unhexlify(
            b"05000000000000000000000000000000000000000000000000000000"
            b"00000000000000000000000000000000000000000000000000000000"
        )
        shared_key = binascii.unhexlify(
            b"aa3b4749d55b9daf1e5b00288826c467274ce3ebbdd5c17b975e09d4"
            b"af6c67cf10d087202db88286e2b79fceea3ec353ef54faa26e219f38"
        )
        private_key = X448PrivateKey.from_private_bytes(private)
        public_key = X448PublicKey.from_public_bytes(public)
        for _ in range(1000):
            computed_shared_key = private_key.exchange(public_key)
            private_key = X448PrivateKey.from_private_bytes(
                computed_shared_key
            )
            public_key = X448PublicKey.from_public_bytes(old_private)
            old_private = computed_shared_key

        assert computed_shared_key == shared_key

    # These vectors are also from RFC 7748
    # https://tools.ietf.org/html/rfc7748#section-6.2
    @pytest.mark.parametrize(
        ("private_bytes", "public_bytes"),
        [
            (
                binascii.unhexlify(
                    b"9a8f4925d1519f5775cf46b04b5800d4ee9ee8bae8bc5565d498c28d"
                    b"d9c9baf574a9419744897391006382a6f127ab1d9ac2d8c0a598726b"
                ),
                binascii.unhexlify(
                    b"9b08f7cc31b7e3e67d22d5aea121074a273bd2b83de09c63faa73d2c"
                    b"22c5d9bbc836647241d953d40c5b12da88120d53177f80e532c41fa0"
                ),
            ),
            (
                binascii.unhexlify(
                    b"1c306a7ac2a0e2e0990b294470cba339e6453772b075811d8fad0d1d"
                    b"6927c120bb5ee8972b0d3e21374c9c921b09d1b0366f10b65173992d"
                ),
                binascii.unhexlify(
                    b"3eb7a829b0cd20f5bcfc0b599b6feccf6da4627107bdb0d4f345b430"
                    b"27d8b972fc3e34fb4232a13ca706dcb57aec3dae07bdc1c67bf33609"
                ),
            ),
        ],
    )
    def test_pub_priv_bytes_raw(self, private_bytes, public_bytes, backend):
        private_key = X448PrivateKey.from_private_bytes(private_bytes)
        assert (
            private_key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            == private_bytes
        )
        assert private_key.private_bytes_raw() == private_bytes
        assert (
            private_key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == public_bytes
        )
        assert private_key.public_key().public_bytes_raw() == public_bytes
        public_key = X448PublicKey.from_public_bytes(public_bytes)
        assert (
            public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == public_bytes
        )
        assert public_key.public_bytes_raw() == public_bytes

    @pytest.mark.parametrize(
        ("encoding", "fmt", "encryption", "passwd", "load_func"),
        [
            (
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(b"password"),
                b"password",
                serialization.load_pem_private_key,
            ),
            (
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(b"password"),
                b"password",
                serialization.load_der_private_key,
            ),
            (
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
                None,
                serialization.load_pem_private_key,
            ),
            (
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
                None,
                serialization.load_der_private_key,
            ),
        ],
    )
    def test_round_trip_private_serialization(
        self, encoding, fmt, encryption, passwd, load_func, backend
    ):
        key = X448PrivateKey.generate()
        serialized = key.private_bytes(encoding, fmt, encryption)
        loaded_key = load_func(serialized, passwd, backend)
        assert isinstance(loaded_key, X448PrivateKey)

    def test_generate(self, backend):
        key = X448PrivateKey.generate()
        assert key
        assert key.public_key()

    def test_invalid_type_exchange(self, backend):
        key = X448PrivateKey.generate()
        with pytest.raises(TypeError):
            key.exchange(object())  # type: ignore[arg-type]

    def test_invalid_length_from_public_bytes(self, backend):
        with pytest.raises(ValueError):
            X448PublicKey.from_public_bytes(b"a" * 55)

        with pytest.raises(ValueError):
            X448PublicKey.from_public_bytes(b"a" * 57)

    def test_invalid_length_from_private_bytes(self, backend):
        with pytest.raises(ValueError):
            X448PrivateKey.from_private_bytes(b"a" * 55)

        with pytest.raises(ValueError):
            X448PrivateKey.from_private_bytes(b"a" * 57)

    def test_invalid_private_bytes(self, backend):
        key = X448PrivateKey.generate()
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                None,  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                DummyKeySerializationEncryption(),
            )

        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.PKCS8,
                DummyKeySerializationEncryption(),
            )

        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )

    def test_invalid_public_bytes(self, backend):
        key = X448PrivateKey.generate().public_key()
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )

        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.PKCS1
            )

        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.Raw
            )

    def test_buffer_protocol(self, backend):
        private_bytes = binascii.unhexlify(
            b"9a8f4925d1519f5775cf46b04b5800d4ee9ee8bae8bc5565d498c28d"
            b"d9c9baf574a9419744897391006382a6f127ab1d9ac2d8c0a598726b"
        )
        key = X448PrivateKey.from_private_bytes(bytearray(private_bytes))
        assert (
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            == private_bytes
        )


@pytest.mark.supported(
    only_if=lambda backend: backend.x448_supported(),
    skip_message="Requires OpenSSL with X448 support",
)
def test_public_key_equality(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "X448", "x448-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = serialization.load_der_private_key(key_bytes, None).public_key()
    key3 = X448PrivateKey.generate().public_key()
    assert key1 == key2
    assert key1 != key3
    assert key1 != object()
    with pytest.raises(TypeError):
        key1 < key2  # type: ignore[operator]


@pytest.mark.supported(
    only_if=lambda backend: backend.x448_supported(),
    skip_message="Requires OpenSSL with X448 support",
)
def test_public_key_copy(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "X448", "x448-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = copy.copy(key1)

    assert key1 == key2
