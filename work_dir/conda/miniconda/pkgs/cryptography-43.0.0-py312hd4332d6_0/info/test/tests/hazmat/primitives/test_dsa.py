# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import copy
import itertools
import os
import typing

import pytest

from cryptography import utils
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric.utils import (
    Prehashed,
    encode_dss_signature,
)

from ...doubles import DummyHashAlgorithm, DummyKeySerializationEncryption
from ...utils import (
    load_fips_dsa_key_pair_vectors,
    load_fips_dsa_sig_vectors,
    load_vectors_from_file,
)
from .fixtures_dsa import DSA_KEY_1024, DSA_KEY_2048, DSA_KEY_3072
from .utils import skip_fips_traditional_openssl

_ALGORITHMS_DICT: typing.Dict[str, hashes.HashAlgorithm] = {
    "SHA1": hashes.SHA1(),
    "SHA224": hashes.SHA224(),
    "SHA256": hashes.SHA256(),
    "SHA384": hashes.SHA384(),
    "SHA512": hashes.SHA512(),
}


def _skip_if_dsa_not_supported(
    backend: typing.Any,
    algorithm: hashes.HashAlgorithm,
    p: int,
    q: int,
    g: int,
) -> None:
    if not backend.dsa_hash_supported(algorithm):
        pytest.skip(
            f"{backend} does not support the provided args. "
            f"p: {p.bit_length()}, hash: {algorithm.name}"
        )


def test_skip_if_dsa_not_supported(backend):
    with pytest.raises(pytest.skip.Exception):
        _skip_if_dsa_not_supported(backend, DummyHashAlgorithm(), 1, 1, 1)


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Does not support DSA.",
)
class TestDSA:
    def test_generate_dsa_parameters(self, backend):
        parameters = dsa.generate_parameters(2048, backend)
        assert isinstance(parameters, dsa.DSAParameters)

    def test_generate_invalid_dsa_parameters(self, backend):
        with pytest.raises(ValueError):
            dsa.generate_parameters(1, backend)

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "DSA", "FIPS_186-3", "KeyPair.rsp"),
            load_fips_dsa_key_pair_vectors,
        ),
    )
    def test_generate_dsa_keys(self, vector, backend):
        parameters = dsa.DSAParameterNumbers(
            p=vector["p"], q=vector["q"], g=vector["g"]
        ).parameters(backend)
        skey = parameters.generate_private_key()
        numbers = skey.private_numbers()
        skey_parameters = numbers.public_numbers.parameter_numbers
        pkey = skey.public_key()
        parameters = pkey.parameters()
        parameter_numbers = parameters.parameter_numbers()
        assert parameter_numbers.p == skey_parameters.p
        assert parameter_numbers.q == skey_parameters.q
        assert parameter_numbers.g == skey_parameters.g
        assert skey_parameters.p == vector["p"]
        assert skey_parameters.q == vector["q"]
        assert skey_parameters.g == vector["g"]
        assert skey.key_size == vector["p"].bit_length()
        assert pkey.key_size == skey.key_size
        public_numbers = pkey.public_numbers()
        assert numbers.public_numbers.y == public_numbers.y
        assert numbers.public_numbers.y == pow(
            skey_parameters.g, numbers.x, skey_parameters.p
        )

    def test_generate_dsa_private_key_and_parameters(self, backend):
        skey = dsa.generate_private_key(2048, backend)
        assert skey
        numbers = skey.private_numbers()
        skey_parameters = numbers.public_numbers.parameter_numbers
        assert numbers.public_numbers.y == pow(
            skey_parameters.g, numbers.x, skey_parameters.p
        )

    @pytest.mark.parametrize(
        ("p", "q", "g"),
        [
            (
                2**1000,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
            ),
            (
                2**2000,
                DSA_KEY_2048.public_numbers.parameter_numbers.q,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
            ),
            (
                2**3000,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
            ),
            (
                2**3100,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                2**150,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
            ),
            (
                DSA_KEY_2048.public_numbers.parameter_numbers.p,
                2**250,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
            ),
            (
                DSA_KEY_3072.public_numbers.parameter_numbers.p,
                2**260,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                0,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                1,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                2**1200,
            ),
        ],
    )
    def test_invalid_parameters_values(self, p, q, g, backend):
        with pytest.raises(ValueError):
            dsa.DSAParameterNumbers(p, q, g).parameters(backend)

    @pytest.mark.parametrize(
        ("p", "q", "g", "y", "x"),
        [
            (
                2**1000,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                DSA_KEY_1024.x,
            ),
            (
                2**2000,
                DSA_KEY_2048.public_numbers.parameter_numbers.q,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
                DSA_KEY_2048.public_numbers.y,
                DSA_KEY_2048.x,
            ),
            (
                2**3000,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
                DSA_KEY_3072.x,
            ),
            (
                2**3100,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
                DSA_KEY_3072.x,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                2**150,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                DSA_KEY_1024.x,
            ),
            (
                DSA_KEY_2048.public_numbers.parameter_numbers.p,
                2**250,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
                DSA_KEY_2048.public_numbers.y,
                DSA_KEY_2048.x,
            ),
            (
                DSA_KEY_3072.public_numbers.parameter_numbers.p,
                2**260,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
                DSA_KEY_3072.x,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                0,
                DSA_KEY_1024.public_numbers.y,
                DSA_KEY_1024.x,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                1,
                DSA_KEY_1024.public_numbers.y,
                DSA_KEY_1024.x,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                2**1200,
                DSA_KEY_1024.public_numbers.y,
                DSA_KEY_1024.x,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                0,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                -2,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                2**159,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
                2**200,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                2**100,
                DSA_KEY_1024.x,
            ),
        ],
    )
    def test_invalid_dsa_private_key_arguments(self, p, q, g, y, x, backend):
        with pytest.raises(ValueError):
            dsa.DSAPrivateNumbers(
                public_numbers=dsa.DSAPublicNumbers(
                    parameter_numbers=dsa.DSAParameterNumbers(p=p, q=q, g=g),
                    y=y,
                ),
                x=x,
            ).private_key(backend)

    @pytest.mark.parametrize(
        ("p", "q", "g", "y"),
        [
            (
                2**1000,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
            ),
            (
                2**2000,
                DSA_KEY_2048.public_numbers.parameter_numbers.q,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
                DSA_KEY_2048.public_numbers.y,
            ),
            (
                2**3000,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
            ),
            (
                2**3100,
                DSA_KEY_3072.public_numbers.parameter_numbers.q,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                2**150,
                DSA_KEY_1024.public_numbers.parameter_numbers.g,
                DSA_KEY_1024.public_numbers.y,
            ),
            (
                DSA_KEY_2048.public_numbers.parameter_numbers.p,
                2**250,
                DSA_KEY_2048.public_numbers.parameter_numbers.g,
                DSA_KEY_2048.public_numbers.y,
            ),
            (
                DSA_KEY_3072.public_numbers.parameter_numbers.p,
                2**260,
                DSA_KEY_3072.public_numbers.parameter_numbers.g,
                DSA_KEY_3072.public_numbers.y,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                0,
                DSA_KEY_1024.public_numbers.y,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                1,
                DSA_KEY_1024.public_numbers.y,
            ),
            (
                DSA_KEY_1024.public_numbers.parameter_numbers.p,
                DSA_KEY_1024.public_numbers.parameter_numbers.q,
                2**1200,
                DSA_KEY_1024.public_numbers.y,
            ),
        ],
    )
    def test_invalid_dsa_public_key_arguments(self, p, q, g, y, backend):
        with pytest.raises(ValueError):
            dsa.DSAPublicNumbers(
                parameter_numbers=dsa.DSAParameterNumbers(p=p, q=q, g=g), y=y
            ).public_key(backend)

    def test_large_p(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PEM_Serialization", "dsa_4096.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read(), None, backend
            ),
            mode="rb",
        )
        assert isinstance(key, dsa.DSAPrivateKey)
        pn = key.private_numbers()
        assert pn.public_numbers.parameter_numbers.p.bit_length() == 4096
        # Turn it back into a key to confirm that values this large pass
        # verification
        dsa.DSAPrivateNumbers(
            public_numbers=dsa.DSAPublicNumbers(
                parameter_numbers=dsa.DSAParameterNumbers(
                    p=pn.public_numbers.parameter_numbers.p,
                    q=pn.public_numbers.parameter_numbers.q,
                    g=pn.public_numbers.parameter_numbers.g,
                ),
                y=pn.public_numbers.y,
            ),
            x=pn.x,
        ).private_key(backend)

    def test_public_key_equality(self, backend):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: pemfile.read().encode(),
        )
        key1 = serialization.load_pem_private_key(key_bytes, None).public_key()
        key2 = serialization.load_pem_private_key(key_bytes, None).public_key()
        key3 = DSA_KEY_2048.private_key().public_key()
        assert key1 == key2
        assert key1 != key3
        assert key1 != object()
        with pytest.raises(TypeError):
            key1 < key2  # type: ignore[operator]

    def test_public_key_copy(self):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: pemfile.read().encode(),
        )
        key1 = serialization.load_pem_private_key(key_bytes, None).public_key()
        key2 = copy.copy(key1)

        assert key1 == key2


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Does not support DSA.",
)
class TestDSAVerification:
    def test_dsa_verification(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("asymmetric", "DSA", "FIPS_186-3", "SigVer.rsp"),
            load_fips_dsa_sig_vectors,
        )
        for vector in vectors:
            with subtests.test():
                digest_algorithm = vector["digest_algorithm"].replace("-", "")
                algorithm = _ALGORITHMS_DICT[digest_algorithm]

                _skip_if_dsa_not_supported(
                    backend, algorithm, vector["p"], vector["q"], vector["g"]
                )

                public_key = dsa.DSAPublicNumbers(
                    parameter_numbers=dsa.DSAParameterNumbers(
                        vector["p"], vector["q"], vector["g"]
                    ),
                    y=vector["y"],
                ).public_key(backend)
                sig = encode_dss_signature(vector["r"], vector["s"])

                if vector["result"] == "F":
                    with pytest.raises(InvalidSignature):
                        public_key.verify(sig, vector["msg"], algorithm)
                else:
                    public_key.verify(sig, vector["msg"], algorithm)

    def test_dsa_verify_invalid_asn1(self, backend):
        public_key = DSA_KEY_1024.public_numbers.public_key(backend)
        with pytest.raises(InvalidSignature):
            public_key.verify(b"fakesig", b"fakemsg", hashes.SHA1())

    def test_verify(self, backend):
        message = b"one little message"
        algorithm = hashes.SHA1()
        private_key = DSA_KEY_1024.private_key(backend)
        signature = private_key.sign(message, algorithm)
        public_key = private_key.public_key()
        public_key.verify(signature, message, algorithm)

    def test_prehashed_verify(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        message = b"one little message"
        h = hashes.Hash(hashes.SHA1(), backend)
        h.update(message)
        digest = h.finalize()
        prehashed_alg = Prehashed(hashes.SHA1())
        signature = private_key.sign(message, hashes.SHA1())
        public_key = private_key.public_key()
        public_key.verify(signature, digest, prehashed_alg)

    def test_prehashed_digest_mismatch(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        public_key = private_key.public_key()
        message = b"one little message"
        h = hashes.Hash(hashes.SHA1(), backend)
        h.update(message)
        digest = h.finalize()
        prehashed_alg = Prehashed(hashes.SHA224())
        with pytest.raises(ValueError):
            public_key.verify(b"\x00" * 128, digest, prehashed_alg)


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Does not support DSA.",
)
class TestDSASignature:
    def test_dsa_signing(self, backend, subtests):
        vectors = load_vectors_from_file(
            os.path.join("asymmetric", "DSA", "FIPS_186-3", "SigGen.txt"),
            load_fips_dsa_sig_vectors,
        )
        for vector in vectors:
            with subtests.test():
                digest_algorithm = vector["digest_algorithm"].replace("-", "")
                algorithm = _ALGORITHMS_DICT[digest_algorithm]

                _skip_if_dsa_not_supported(
                    backend, algorithm, vector["p"], vector["q"], vector["g"]
                )

                private_key = dsa.DSAPrivateNumbers(
                    public_numbers=dsa.DSAPublicNumbers(
                        parameter_numbers=dsa.DSAParameterNumbers(
                            vector["p"], vector["q"], vector["g"]
                        ),
                        y=vector["y"],
                    ),
                    x=vector["x"],
                ).private_key(backend)
                signature = private_key.sign(vector["msg"], algorithm)
                assert signature

                private_key.public_key().verify(
                    signature, vector["msg"], algorithm
                )

    def test_sign(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        message = b"one little message"
        algorithm = hashes.SHA1()
        signature = private_key.sign(message, algorithm)
        public_key = private_key.public_key()
        public_key.verify(signature, message, algorithm)

    def test_sign_verify_buffer(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        message = bytearray(b"one little message")
        algorithm = hashes.SHA1()
        signature = private_key.sign(message, algorithm)
        public_key = private_key.public_key()
        public_key.verify(bytearray(signature), message, algorithm)

    def test_prehashed_sign(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        message = b"one little message"
        h = hashes.Hash(hashes.SHA1(), backend)
        h.update(message)
        digest = h.finalize()
        prehashed_alg = Prehashed(hashes.SHA1())
        signature = private_key.sign(digest, prehashed_alg)
        public_key = private_key.public_key()
        public_key.verify(signature, message, hashes.SHA1())

    def test_prehashed_digest_mismatch(self, backend):
        private_key = DSA_KEY_1024.private_key(backend)
        message = b"one little message"
        h = hashes.Hash(hashes.SHA1(), backend)
        h.update(message)
        digest = h.finalize()
        prehashed_alg = Prehashed(hashes.SHA224())
        with pytest.raises(ValueError):
            private_key.sign(digest, prehashed_alg)


class TestDSANumbers:
    def test_dsa_parameter_numbers(self):
        parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
        assert parameter_numbers.p == 1
        assert parameter_numbers.q == 2
        assert parameter_numbers.g == 3

    def test_dsa_parameter_numbers_invalid_types(self):
        with pytest.raises(TypeError):
            dsa.DSAParameterNumbers(p=None, q=2, g=3)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            dsa.DSAParameterNumbers(p=1, q=None, g=3)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            dsa.DSAParameterNumbers(p=1, q=2, g=None)  # type: ignore[arg-type]

    def test_dsa_public_numbers(self):
        parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
        public_numbers = dsa.DSAPublicNumbers(
            y=4, parameter_numbers=parameter_numbers
        )
        assert public_numbers.y == 4
        assert public_numbers.parameter_numbers == parameter_numbers

    def test_dsa_public_numbers_invalid_types(self):
        with pytest.raises(TypeError):
            dsa.DSAPublicNumbers(
                y=4,
                parameter_numbers=None,  # type: ignore[arg-type]
            )

        with pytest.raises(TypeError):
            parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
            dsa.DSAPublicNumbers(
                y=None,  # type: ignore[arg-type]
                parameter_numbers=parameter_numbers,
            )

    def test_dsa_private_numbers(self):
        parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
        public_numbers = dsa.DSAPublicNumbers(
            y=4, parameter_numbers=parameter_numbers
        )
        private_numbers = dsa.DSAPrivateNumbers(
            x=5, public_numbers=public_numbers
        )
        assert private_numbers.x == 5
        assert private_numbers.public_numbers == public_numbers

    def test_dsa_private_numbers_invalid_types(self):
        parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
        public_numbers = dsa.DSAPublicNumbers(
            y=4, parameter_numbers=parameter_numbers
        )
        with pytest.raises(TypeError):
            dsa.DSAPrivateNumbers(
                x=4,
                public_numbers=None,  # type: ignore[arg-type]
            )

        with pytest.raises(TypeError):
            dsa.DSAPrivateNumbers(
                x=None,  # type: ignore[arg-type]
                public_numbers=public_numbers,
            )

    def test_repr(self):
        parameter_numbers = dsa.DSAParameterNumbers(p=1, q=2, g=3)
        assert (
            repr(parameter_numbers) == "<DSAParameterNumbers(p=1, q=2, g=3)>"
        )

        public_numbers = dsa.DSAPublicNumbers(
            y=4, parameter_numbers=parameter_numbers
        )
        assert repr(public_numbers) == (
            "<DSAPublicNumbers(y=4, parameter_numbers=<DSAParameterNumbers(p=1"
            ", q=2, g=3)>)>"
        )


class TestDSANumberEquality:
    def test_parameter_numbers_eq(self):
        param = dsa.DSAParameterNumbers(1, 2, 3)
        assert param == dsa.DSAParameterNumbers(1, 2, 3)

    def test_parameter_numbers_ne(self):
        param = dsa.DSAParameterNumbers(1, 2, 3)
        assert param != dsa.DSAParameterNumbers(1, 2, 4)
        assert param != dsa.DSAParameterNumbers(1, 1, 3)
        assert param != dsa.DSAParameterNumbers(2, 2, 3)
        assert param != object()

    def test_public_numbers_eq(self):
        pub = dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        assert pub == dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))

    def test_public_numbers_ne(self):
        pub = dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        assert pub != dsa.DSAPublicNumbers(2, dsa.DSAParameterNumbers(1, 2, 3))
        assert pub != dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(2, 2, 3))
        assert pub != dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 3, 3))
        assert pub != dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 4))
        assert pub != object()

    def test_private_numbers_eq(self):
        pub = dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        priv = dsa.DSAPrivateNumbers(1, pub)
        assert priv == dsa.DSAPrivateNumbers(
            1, dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        )

    def test_private_numbers_ne(self):
        pub = dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        priv = dsa.DSAPrivateNumbers(1, pub)
        assert priv != dsa.DSAPrivateNumbers(
            2, dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 3))
        )
        assert priv != dsa.DSAPrivateNumbers(
            1, dsa.DSAPublicNumbers(2, dsa.DSAParameterNumbers(1, 2, 3))
        )
        assert priv != dsa.DSAPrivateNumbers(
            1, dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(2, 2, 3))
        )
        assert priv != dsa.DSAPrivateNumbers(
            1, dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 3, 3))
        )
        assert priv != dsa.DSAPrivateNumbers(
            1, dsa.DSAPublicNumbers(1, dsa.DSAParameterNumbers(1, 2, 4))
        )
        assert priv != object()


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Does not support DSA.",
)
class TestDSASerialization:
    @pytest.mark.parametrize(
        ("fmt", "password"),
        itertools.product(
            [
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.PrivateFormat.PKCS8,
            ],
            [
                b"s",
                b"longerpassword",
                b"!*$&(@#$*&($T@%_somesymbols",
                b"\x01" * 1000,
            ],
        ),
    )
    def test_private_bytes_encrypted_pem(self, backend, fmt, password):
        skip_fips_traditional_openssl(backend, fmt)
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: pemfile.read().encode(),
        )
        key = serialization.load_pem_private_key(key_bytes, None, backend)
        assert isinstance(key, dsa.DSAPrivateKey)
        serialized = key.private_bytes(
            serialization.Encoding.PEM,
            fmt,
            serialization.BestAvailableEncryption(password),
        )
        loaded_key = serialization.load_pem_private_key(
            serialized, password, backend
        )
        assert isinstance(loaded_key, dsa.DSAPrivateKey)
        loaded_priv_num = loaded_key.private_numbers()
        priv_num = key.private_numbers()
        assert loaded_priv_num == priv_num

    @pytest.mark.parametrize(
        ("encoding", "fmt"),
        [
            (serialization.Encoding.Raw, serialization.PrivateFormat.PKCS8),
            (serialization.Encoding.DER, serialization.PrivateFormat.Raw),
            (serialization.Encoding.Raw, serialization.PrivateFormat.Raw),
            (serialization.Encoding.X962, serialization.PrivateFormat.PKCS8),
            (
                serialization.Encoding.SMIME,
                serialization.PrivateFormat.TraditionalOpenSSL,
            ),
        ],
    )
    def test_private_bytes_rejects_invalid(self, encoding, fmt, backend):
        key = DSA_KEY_1024.private_key(backend)
        with pytest.raises(ValueError):
            key.private_bytes(encoding, fmt, serialization.NoEncryption())

    @pytest.mark.parametrize(
        ("fmt", "password"),
        [
            [serialization.PrivateFormat.PKCS8, b"s"],
            [serialization.PrivateFormat.PKCS8, b"longerpassword"],
            [serialization.PrivateFormat.PKCS8, b"!*$&(@#$*&($T@%_somesymbol"],
            [serialization.PrivateFormat.PKCS8, b"\x01" * 1000],
        ],
    )
    def test_private_bytes_encrypted_der(self, backend, fmt, password):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: pemfile.read().encode(),
        )
        key = serialization.load_pem_private_key(key_bytes, None, backend)
        assert isinstance(key, dsa.DSAPrivateKey)
        serialized = key.private_bytes(
            serialization.Encoding.DER,
            fmt,
            serialization.BestAvailableEncryption(password),
        )
        loaded_key = serialization.load_der_private_key(
            serialized, password, backend
        )
        assert isinstance(loaded_key, dsa.DSAPrivateKey)
        loaded_priv_num = loaded_key.private_numbers()
        priv_num = key.private_numbers()
        assert loaded_priv_num == priv_num

    @pytest.mark.parametrize(
        ("encoding", "fmt", "loader_func"),
        [
            [
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.load_pem_private_key,
            ],
            [
                serialization.Encoding.DER,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.load_der_private_key,
            ],
            [
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.load_pem_private_key,
            ],
            [
                serialization.Encoding.DER,
                serialization.PrivateFormat.PKCS8,
                serialization.load_der_private_key,
            ],
        ],
    )
    def test_private_bytes_unencrypted(
        self, backend, encoding, fmt, loader_func
    ):
        key = DSA_KEY_1024.private_key(backend)
        serialized = key.private_bytes(
            encoding, fmt, serialization.NoEncryption()
        )
        loaded_key = loader_func(serialized, None, backend)
        loaded_priv_num = loaded_key.private_numbers()
        priv_num = key.private_numbers()
        assert loaded_priv_num == priv_num

    @pytest.mark.skip_fips(
        reason="Traditional OpenSSL key format is not supported in FIPS mode."
    )
    @pytest.mark.parametrize(
        ("key_path", "encoding", "loader_func"),
        [
            [
                os.path.join(
                    "asymmetric",
                    "Traditional_OpenSSL_Serialization",
                    "dsa.1024.pem",
                ),
                serialization.Encoding.PEM,
                serialization.load_pem_private_key,
            ],
            [
                os.path.join(
                    "asymmetric", "DER_Serialization", "dsa.1024.der"
                ),
                serialization.Encoding.DER,
                serialization.load_der_private_key,
            ],
        ],
    )
    def test_private_bytes_traditional_openssl_unencrypted(
        self, backend, key_path, encoding, loader_func
    ):
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        key = loader_func(key_bytes, None, backend)
        serialized = key.private_bytes(
            encoding,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        assert serialized == key_bytes

    def test_private_bytes_traditional_der_encrypted_invalid(self, backend):
        key = DSA_KEY_1024.private_key(backend)
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.BestAvailableEncryption(b"password"),
            )

    def test_private_bytes_invalid_encoding(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read().encode(), None, backend
            ),
        )
        with pytest.raises(TypeError):
            key.private_bytes(
                "notencoding",  # type: ignore[arg-type]
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_format(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read().encode(), None, backend
            ),
        )
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                "invalidformat",  # type: ignore[arg-type]
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_encryption_algorithm(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read().encode(), None, backend
            ),
        )
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                "notanencalg",  # type: ignore[arg-type]
            )

    def test_private_bytes_unsupported_encryption_type(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read().encode(), None, backend
            ),
        )
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                DummyKeySerializationEncryption(),
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.dsa_supported(),
    skip_message="Does not support DSA.",
)
class TestDSAPEMPublicKeySerialization:
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "encoding"),
        [
            (
                os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pub.pem"),
                serialization.load_pem_public_key,
                serialization.Encoding.PEM,
            ),
            (
                os.path.join(
                    "asymmetric",
                    "DER_Serialization",
                    "unenc-dsa-pkcs8.pub.der",
                ),
                serialization.load_der_public_key,
                serialization.Encoding.DER,
            ),
        ],
    )
    def test_public_bytes_match(
        self, key_path, loader_func, encoding, backend
    ):
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        key = loader_func(key_bytes, backend)
        serialized = key.public_bytes(
            encoding,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        assert serialized == key_bytes

    def test_public_bytes_openssh(self, backend):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pub.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = serialization.load_pem_public_key(key_bytes, backend)

        with pytest.warns(utils.DeprecatedIn40):
            ssh_bytes = key.public_bytes(
                serialization.Encoding.OpenSSH,
                serialization.PublicFormat.OpenSSH,
            )
        assert ssh_bytes == (
            b"ssh-dss AAAAB3NzaC1kc3MAAACBAKoJMMwUWCUiHK/6KKwolBlqJ4M95ewhJweR"
            b"aJQgd3Si57I4sNNvGySZosJYUIPrAUMpJEGNhn+qIS3RBx1NzrJ4J5StOTzAik1K"
            b"2n9o1ug5pfzTS05ALYLLioy0D+wxkRv5vTYLA0yqy0xelHmSVzyekAmcGw8FlAyr"
            b"5dLeSaFnAAAAFQCtwOhps28KwBOmgf301ImdaYIEUQAAAIEAjGtFia+lOk0QSL/D"
            b"RtHzhsp1UhzPct2qJRKGiA7hMgH/SIkLv8M9ebrK7HHnp3hQe9XxpmQi45QVvgPn"
            b"EUG6Mk9bkxMZKRgsiKn6QGKDYGbOvnS1xmkMfRARBsJAq369VOTjMB/Qhs5q2ski"
            b"+ycTorCIfLoTubxozlz/8kHNMkYAAACAKyYOqX3GoSrpMsZA5989j/BKigWgMk+N"
            b"Xxsj8V+hcP8/QgYRJO/yWGyxG0moLc3BuQ/GqE+xAQnLZ9tdLalxrq8Xvl43KEVj"
            b"5MZNnl/ISAJYsxnw3inVTYNQcNnih5FNd9+BSR9EI7YtqYTrP0XrKin86l2uUlrG"
            b"q2vM4Ev99bY="
        )

    def test_public_bytes_invalid_encoding(self, backend):
        key = DSA_KEY_2048.private_key(backend).public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                "notencoding",  # type: ignore[arg-type]
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )

    def test_public_bytes_invalid_format(self, backend):
        key = DSA_KEY_2048.private_key(backend).public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                serialization.Encoding.PEM,
                "invalidformat",  # type: ignore[arg-type]
            )

    def test_public_bytes_pkcs1_unsupported(self, backend):
        key = DSA_KEY_2048.private_key(backend).public_key()
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.PKCS1
            )

    @pytest.mark.parametrize(
        ("encoding", "fmt"),
        [
            (
                serialization.Encoding.Raw,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            (serialization.Encoding.Raw, serialization.PublicFormat.PKCS1),
            *itertools.product(
                [
                    serialization.Encoding.Raw,
                    serialization.Encoding.X962,
                    serialization.Encoding.PEM,
                    serialization.Encoding.DER,
                ],
                [
                    serialization.PublicFormat.Raw,
                    serialization.PublicFormat.UncompressedPoint,
                    serialization.PublicFormat.CompressedPoint,
                ],
            ),
        ],
    )
    def test_public_bytes_rejects_invalid(self, encoding, fmt, backend):
        key = DSA_KEY_2048.private_key(backend).public_key()
        with pytest.raises(ValueError):
            key.public_bytes(encoding, fmt)
