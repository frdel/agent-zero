# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import copy
import os

import pytest

from cryptography.exceptions import InvalidSignature, _Reasons
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import (
    Ed448PrivateKey,
    Ed448PublicKey,
)

from ...doubles import DummyKeySerializationEncryption
from ...utils import (
    load_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)


@pytest.mark.supported(
    only_if=lambda backend: not backend.ed448_supported(),
    skip_message="Requires OpenSSL without Ed448 support",
)
def test_ed448_unsupported(backend):
    with raises_unsupported_algorithm(
        _Reasons.UNSUPPORTED_PUBLIC_KEY_ALGORITHM
    ):
        Ed448PublicKey.from_public_bytes(b"0" * 57)

    with raises_unsupported_algorithm(
        _Reasons.UNSUPPORTED_PUBLIC_KEY_ALGORITHM
    ):
        Ed448PrivateKey.from_private_bytes(b"0" * 57)

    with raises_unsupported_algorithm(
        _Reasons.UNSUPPORTED_PUBLIC_KEY_ALGORITHM
    ):
        Ed448PrivateKey.generate()


@pytest.mark.supported(
    only_if=lambda backend: backend.ed448_supported(),
    skip_message="Requires OpenSSL with Ed448 support",
)
class TestEd448Signing:
    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "rfc8032.txt"),
            load_nist_vectors,
        ),
    )
    def test_sign_input(self, vector, backend):
        if vector.get("context") is not None:
            pytest.skip("ed448 contexts are not currently supported")

        sk = binascii.unhexlify(vector["secret"])
        pk = binascii.unhexlify(vector["public"])
        message = binascii.unhexlify(vector["message"])
        signature = binascii.unhexlify(vector["signature"])
        private_key = Ed448PrivateKey.from_private_bytes(sk)
        computed_sig = private_key.sign(message)
        assert computed_sig == signature
        public_key = private_key.public_key()
        assert (
            public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == pk
        )
        public_key.verify(signature, message)

    def test_invalid_signature(self, backend):
        key = Ed448PrivateKey.generate()
        signature = key.sign(b"test data")
        with pytest.raises(InvalidSignature):
            key.public_key().verify(signature, b"wrong data")

        with pytest.raises(InvalidSignature):
            key.public_key().verify(b"0" * 64, b"test data")

    def test_sign_verify_buffer(self, backend):
        key = Ed448PrivateKey.generate()
        data = bytearray(b"test data")
        signature = key.sign(data)
        key.public_key().verify(bytearray(signature), data)

    def test_generate(self, backend):
        key = Ed448PrivateKey.generate()
        assert key
        assert key.public_key()

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "rfc8032.txt"),
            load_nist_vectors,
        ),
    )
    def test_pub_priv_bytes_raw(self, vector, backend):
        sk = binascii.unhexlify(vector["secret"])
        pk = binascii.unhexlify(vector["public"])
        private_key = Ed448PrivateKey.from_private_bytes(sk)
        assert (
            private_key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            == sk
        )
        assert private_key.private_bytes_raw() == sk
        assert (
            private_key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == pk
        )
        assert private_key.public_key().public_bytes_raw() == pk
        public_key = Ed448PublicKey.from_public_bytes(pk)
        assert (
            public_key.public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
            == pk
        )
        assert public_key.public_bytes_raw() == pk

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
        key = Ed448PrivateKey.generate()
        serialized = key.private_bytes(encoding, fmt, encryption)
        loaded_key = load_func(serialized, passwd, backend)
        assert isinstance(loaded_key, Ed448PrivateKey)

    def test_invalid_type_public_bytes(self, backend):
        with pytest.raises(TypeError):
            Ed448PublicKey.from_public_bytes(
                object()  # type: ignore[arg-type]
            )

    def test_invalid_type_private_bytes(self, backend):
        with pytest.raises(TypeError):
            Ed448PrivateKey.from_private_bytes(
                object()  # type: ignore[arg-type]
            )

    def test_invalid_length_from_public_bytes(self, backend):
        with pytest.raises(ValueError):
            Ed448PublicKey.from_public_bytes(b"a" * 56)
        with pytest.raises(ValueError):
            Ed448PublicKey.from_public_bytes(b"a" * 58)

    def test_invalid_length_from_private_bytes(self, backend):
        with pytest.raises(ValueError):
            Ed448PrivateKey.from_private_bytes(b"a" * 56)
        with pytest.raises(ValueError):
            Ed448PrivateKey.from_private_bytes(b"a" * 58)

    def test_invalid_private_bytes(self, backend):
        key = Ed448PrivateKey.generate()
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
        key = Ed448PrivateKey.generate().public_key()
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
        private_bytes = os.urandom(57)
        key = Ed448PrivateKey.from_private_bytes(bytearray(private_bytes))
        assert (
            key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            == private_bytes
        )

    def test_malleability(self, backend):
        # This is a signature where r > the group order. It should be
        # rejected to prevent signature malleability issues. This test can
        # be removed when wycheproof grows ed448 vectors
        public_bytes = binascii.unhexlify(
            "fedb02a658d74990244d9d10cf338e977565cbbda6b24c716829ed6ee1e4f28cf"
            "2620c052db8d878f6243bffc22242816c1aaa67d2f3603600"
        )
        signature = binascii.unhexlify(
            "0cc16ba24d69277f927c1554b0f08a2a711bbdd20b058ccc660d00ca13542a3ce"
            "f9e5c44c54ab23a2eb14f947e167b990b080863e28b399380f30db6e54d5d1406"
            "d23378ffde11b1fb81b2b438a3b8e8aa7f7f4e1befcc905023fab5a5465053844"
            "f04cf0c1b51d84760f869588687f57500"
        )
        key = Ed448PublicKey.from_public_bytes(public_bytes)
        with pytest.raises(InvalidSignature):
            key.verify(signature, b"8")


@pytest.mark.supported(
    only_if=lambda backend: backend.ed448_supported(),
    skip_message="Requires OpenSSL with Ed448 support",
)
def test_public_key_equality(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "Ed448", "ed448-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = serialization.load_der_private_key(key_bytes, None).public_key()
    key3 = Ed448PrivateKey.generate().public_key()
    assert key1 == key2
    assert key1 != key3
    assert key1 != object()

    with pytest.raises(TypeError):
        key1 < key2  # type: ignore[operator]


@pytest.mark.supported(
    only_if=lambda backend: backend.ed448_supported(),
    skip_message="Requires OpenSSL with Ed448 support",
)
def test_public_key_copy(backend):
    key_bytes = load_vectors_from_file(
        os.path.join("asymmetric", "Ed448", "ed448-pkcs8.der"),
        lambda derfile: derfile.read(),
        mode="rb",
    )
    key1 = serialization.load_der_private_key(key_bytes, None).public_key()
    key2 = copy.copy(key1)

    assert key1 == key2
