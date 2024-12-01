# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import copy
import os

import pytest

from cryptography.exceptions import _Reasons
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

from ...doubles import DummyKeySerializationEncryption
from ...utils import (
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)


@pytest.mark.supported(
    only_if=lambda backend: not backend.x25519_supported(),
    skip_message="Requires OpenSSL without X25519 support",
)
def test_x25519_unsupported(backend):
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X25519PublicKey.from_public_bytes(b"0" * 32)

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X25519PrivateKey.from_private_bytes(b"0" * 32)

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_EXCHANGE_ALGORITHM):
        X25519PrivateKey.generate()


@pytest.mark.supported(
    only_if=lambda backend: backend.x25519_supported(),
    skip_message="Requires OpenSSL with X25519 support",
)
class TestX25519Exchange:
    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "X25519", "rfc7748.txt"),
            load_nist_vectors,
        ),
    )
    def test_rfc7748(self, vector, backend):
        private = binascii.unhexlify(vector["input_scalar"])
        public = binascii.unhexlify(vector["input_u"])
        shared_key = binascii.unhexlify(vector["output_u"])
        private_key = X25519PrivateKey.from_private_bytes(private)
        public_key = X25519PublicKey.from_public_bytes(public)
        computed_shared_key = private_key.exchange(public_key)
        assert computed_shared_key == shared_key

    def test_rfc7748_1000_iteration(self, backend):
        old_private = private = public = binascii.unhexlify(
            b"090000000000000000000000000000000000000000000000000000000000"
            b"0000"
        )
        shared_key = binascii.unhexlify(
            b"684cf59ba83309552800ef566f2f4d3c1c3887c49360e3875f2eb94d9953"
            b"2c51"
        )
        private_key = X25519PrivateKey.from_private_bytes(private)
        public_key = X25519PublicKey.from_public_bytes(public)
        for _ in range(1000):
            computed_shared_key = private_key.exchange(public_key)
            private_key = X25519PrivateKey.from_private_bytes(
                computed_shared_key
            )
            public_key = X25519PublicKey.from_public_bytes(old_private)
            old_private = computed_shared_key

        assert computed_shared_key == shared_key

    def test_null_shared_key_raises_error(self, backend):
        """
        The vector used here is taken from wycheproof's x25519 test vectors
        """
        public = binascii.unhexlify(
            "5f9c95bca3508c24b1d0b1559c83ef5b04445cc4581c8e86d8224eddd09f1157"
        )
        private = binascii.unhexlify(
            "78f1e8edf14481b389448dac8f59c70b038e7cf92ef2c7eff57a72466e115296"
        )
        private_key = X25519PrivateKey.from_private_bytes(private)
        public_key = X25519PublicKey.from_public_bytes(public)
        with pytest.raises(ValueError):
            private_key.exchange(public_key)

    def test_public_bytes_bad_args(self, backend):
        key = X25519PrivateKey.generate().public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                None,  # type: ignore[arg-type]
                serialization.PublicFormat.Raw,
            )
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.Raw
            )
        with pytest.raises(TypeError):
            key.public_bytes(
                serialization.Encoding.DER,
                None,  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.SMIME,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )

    # These vectors are also from RFC 7748
    # https://tools.ietf.org/html/rfc7748#section-6.1
    @pytest.mark.parametrize(
        ("private_bytes", "public_bytes"),
        [
            (
                binascii.unhexlify(
                    b"77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba"
                    b"51db92c2a"
                ),
                binascii.unhexlify(
                    b"8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98"
                    b"eaa9b4e6a"
                ),
            ),
            (
                binascii.unhexlify(
                    b"5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b2"
                    b"7ff88e0eb"
                ),
                binascii.unhexlify(
                    b"de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e1"
                    b"46f882b4f"
                ),
            ),
        ],
    )
    def test_pub_priv_bytes_raw(self, private_bytes, public_bytes, backend):
        private_key = X25519PrivateKey.from_private_bytes(private_bytes)
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
        public_key = X25519PublicKey.from_public_bytes(public_bytes)
        assert (
            public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == public_bytes
        )
        assert public_key.public_bytes_raw() == public_bytes

    def test_generate(self, backend):
        key = X25519PrivateKey.generate()
        assert key
        assert key.public_key()

    def test_invalid_type_exchange(self, backend):
        key = X25519PrivateKey.generate()
        with pytest.raises(TypeError):
            key.exchange(object())  # type: ignore[arg-type]

    def test_invalid_length_from_public_bytes(self, backend):
        with pytest.raises(ValueError):
            X25519PublicKey.from_public_bytes(b"a" * 31)

        with pytest.raises(ValueError):
            X25519PublicKey.from_public_bytes(b"a" * 33)

    def test_invalid_length_from_private_bytes(self, backend):
        with pytest.raises(ValueError):
            X25519PrivateKey.from_private_bytes(b"a" * 31)

        with pytest.raises(ValueError):
            X25519PrivateKey.from_private_bytes(b"a" * 33)

    def test_invalid_private_bytes(self, backend):
        key = X25519PrivateKey.generate()
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

        with pytest.raises(TypeError):
            key.private_bytes(None, None, None)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.Raw,
                None,  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
            )

        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                object(),  # type: ignore[arg-type]
            )

        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.BestAvailableEncryption(b"a" * 1024),
            )

        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.SMIME,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )

        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )

    def test_invalid_public_bytes(self, backend):
        key = X25519PrivateKey.generate().public_key()
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
        key = X25519PrivateKey.generate()
        serialized = key.private_bytes(encoding, fmt, encryption)
        loaded_key = load_func(serialized, passwd, backend)
        assert isinstance(loaded_key, X25519PrivateKey)

    def test_buffer_protocol(self, backend):
        private_bytes = bytearray(os.urandom(32))
        key = X25519PrivateKey.from_private_bytes(private_bytes)
        assert (
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            == private_bytes
        )


@pytest.mark.supported(
    only_if=lambda backend: backend.x25519_supported(),
    skip_message="Requires OpenSSL with X25519 support",
)
def test_public_key_equality(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "X25519", "x25519-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = serialization.load_der_private_key(key_bytes, None).public_key()
    key3 = X25519PrivateKey.generate().public_key()
    assert key1 == key2
    assert key1 != key3
    assert key1 != object()
    with pytest.raises(TypeError):
        key1 < key2  # type: ignore[operator]


@pytest.mark.supported(
    only_if=lambda backend: backend.x25519_supported(),
    skip_message="Requires OpenSSL with X25519 support",
)
def test_public_key_copy(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "X25519", "x25519-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = copy.copy(key1)

    assert key1 == key2
