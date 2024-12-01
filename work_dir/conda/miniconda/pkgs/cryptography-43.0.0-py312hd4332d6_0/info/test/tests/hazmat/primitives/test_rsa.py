# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import copy
import itertools
import os

import pytest

from cryptography.exceptions import (
    InvalidSignature,
    UnsupportedAlgorithm,
    _Reasons,
)
from cryptography.hazmat.bindings._rust import openssl as rust_openssl
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric import utils as asym_utils
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateNumbers,
    RSAPublicNumbers,
)

from ...doubles import (
    DummyAsymmetricPadding,
    DummyHashAlgorithm,
    DummyKeySerializationEncryption,
)
from ...utils import (
    load_nist_vectors,
    load_pkcs1_vectors,
    load_rsa_nist_vectors,
    load_vectors_from_file,
    raises_unsupported_algorithm,
)
from .fixtures_rsa import (
    RSA_KEY_512,
    RSA_KEY_522,
    RSA_KEY_599,
    RSA_KEY_745,
    RSA_KEY_1024,
    RSA_KEY_1025,
    RSA_KEY_1026,
    RSA_KEY_1027,
    RSA_KEY_1028,
    RSA_KEY_1029,
    RSA_KEY_1030,
    RSA_KEY_1031,
    RSA_KEY_1536,
    RSA_KEY_2048,
    RSA_KEY_2048_ALT,
    RSA_KEY_CORRUPTED,
)
from .utils import (
    _check_rsa_private_numbers,
    generate_rsa_verification_test,
    skip_fips_traditional_openssl,
)


@pytest.fixture(scope="session")
def rsa_key_512() -> rsa.RSAPrivateKey:
    return RSA_KEY_512.private_key(unsafe_skip_rsa_key_validation=True)


@pytest.fixture(scope="session")
def rsa_key_2048() -> rsa.RSAPrivateKey:
    return RSA_KEY_2048.private_key(unsafe_skip_rsa_key_validation=True)


class DummyMGF(padding.MGF):
    _salt_length = 0
    _algorithm = hashes.SHA256()


def _check_fips_key_length(backend, private_key):
    if (
        backend._fips_enabled
        and private_key.key_size < backend._fips_rsa_min_key_size
    ):
        pytest.skip(f"Key size not FIPS compliant: {private_key.key_size}")


def _flatten_pkcs1_examples(vectors):
    flattened_vectors = []
    for vector in vectors:
        examples = vector[0].pop("examples")
        for example in examples:
            merged_vector = (vector[0], vector[1], example)
            flattened_vectors.append(merged_vector)

    return flattened_vectors


def _build_oaep_sha2_vectors():
    base_path = os.path.join("asymmetric", "RSA", "oaep-custom")
    vectors = []
    hashalgs = [
        hashes.SHA1(),
        hashes.SHA224(),
        hashes.SHA256(),
        hashes.SHA384(),
        hashes.SHA512(),
    ]
    for mgf1alg, oaepalg in itertools.product(hashalgs, hashalgs):
        if mgf1alg.name == "sha1" and oaepalg.name == "sha1":
            # We need to generate the cartesian product of the permutations
            # of all the SHAs above, but SHA1/SHA1 is something we already
            # tested previously and thus did not generate custom vectors for.
            continue

        examples = _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join(
                    base_path,
                    f"oaep-{mgf1alg.name}-{oaepalg.name}.txt",
                ),
                load_pkcs1_vectors,
            )
        )
        # We've loaded the files, but the loaders don't give us any information
        # about the mgf1 or oaep hash algorithms. We know this info so we'll
        # just add that to the end of the tuple
        for private, public, vector in examples:
            vectors.append((private, public, vector, mgf1alg, oaepalg))
    return vectors


def _skip_pss_hash_algorithm_unsupported(backend, hash_alg):
    if not backend.rsa_padding_supported(
        padding.PSS(
            mgf=padding.MGF1(hash_alg), salt_length=padding.PSS.MAX_LENGTH
        )
    ):
        pytest.skip(f"Does not support {hash_alg.name} in MGF1 using PSS.")


def test_skip_pss_hash_algorithm_unsupported(backend):
    with pytest.raises(pytest.skip.Exception):
        _skip_pss_hash_algorithm_unsupported(backend, DummyHashAlgorithm())


def test_modular_inverse():
    p = int(
        "d1f9f6c09fd3d38987f7970247b85a6da84907753d42ec52bc23b745093f4fff5cff3"
        "617ce43d00121a9accc0051f519c76e08cf02fc18acfe4c9e6aea18da470a2b611d2e"
        "56a7b35caa2c0239bc041a53cc5875ca0b668ae6377d4b23e932d8c995fd1e58ecfd8"
        "c4b73259c0d8a54d691cca3f6fb85c8a5c1baf588e898d481",
        16,
    )
    q = int(
        "d1519255eb8f678c86cfd06802d1fbef8b664441ac46b73d33d13a8404580a33a8e74"
        "cb2ea2e2963125b3d454d7a922cef24dd13e55f989cbabf64255a736671f4629a47b5"
        "b2347cfcd669133088d1c159518531025297c2d67c9da856a12e80222cd03b4c6ec0f"
        "86c957cb7bb8de7a127b645ec9e820aa94581e4762e209f01",
        16,
    )
    assert rsa._modinv(q, p) == int(
        "0275e06afa722999315f8f322275483e15e2fb46d827b17800f99110b269a6732748f"
        "624a382fa2ed1ec68c99f7fc56fb60e76eea51614881f497ba7034c17dde955f92f15"
        "772f8b2b41f3e56d88b1e096cdd293eba4eae1e82db815e0fadea0c4ec971bc6fd875"
        "c20e67e48c31a611e98d32c6213ae4c4d7b53023b2f80c538",
        16,
    )


class TestRSA:
    @pytest.mark.parametrize(
        ("public_exponent", "key_size"),
        itertools.product(
            (3, 65537),
            (1024, 1536, 2048),
        ),
    )
    def test_generate_rsa_keys(self, backend, public_exponent, key_size):
        if backend._fips_enabled:
            if key_size < backend._fips_rsa_min_key_size:
                pytest.skip(f"Key size not FIPS compliant: {key_size}")
            if public_exponent < backend._fips_rsa_min_public_exponent:
                pytest.skip(f"Exponent not FIPS compliant: {public_exponent}")
        skey = rsa.generate_private_key(public_exponent, key_size, backend)
        assert skey.key_size == key_size

        _check_rsa_private_numbers(skey.private_numbers())
        pkey = skey.public_key()
        assert isinstance(pkey.public_numbers(), rsa.RSAPublicNumbers)

    def test_generate_bad_public_exponent(self, backend):
        with pytest.raises(ValueError):
            rsa.generate_private_key(
                public_exponent=1, key_size=2048, backend=backend
            )

        with pytest.raises(ValueError):
            rsa.generate_private_key(
                public_exponent=4, key_size=2048, backend=backend
            )

        with pytest.raises(ValueError):
            rsa.generate_private_key(
                public_exponent=65535, key_size=2048, backend=backend
            )

    def test_cant_generate_insecure_tiny_key(self, backend):
        with pytest.raises(ValueError):
            rsa.generate_private_key(
                public_exponent=65537, key_size=511, backend=backend
            )

        with pytest.raises(ValueError):
            rsa.generate_private_key(
                public_exponent=65537, key_size=256, backend=backend
            )

    @pytest.mark.parametrize(
        "pkcs1_example",
        load_vectors_from_file(
            os.path.join(
                "asymmetric", "RSA", "pkcs-1v2-1d2-vec", "pss-vect.txt"
            ),
            load_pkcs1_vectors,
        ),
    )
    def test_load_pss_vect_example_keys(self, pkcs1_example):
        secret, public = pkcs1_example

        private_num = rsa.RSAPrivateNumbers(
            p=secret["p"],
            q=secret["q"],
            d=secret["private_exponent"],
            dmp1=secret["dmp1"],
            dmq1=secret["dmq1"],
            iqmp=secret["iqmp"],
            public_numbers=rsa.RSAPublicNumbers(
                e=secret["public_exponent"], n=secret["modulus"]
            ),
        )
        _check_rsa_private_numbers(private_num)

        public_num = rsa.RSAPublicNumbers(
            e=public["public_exponent"], n=public["modulus"]
        )
        assert public_num

        public_num2 = private_num.public_numbers
        assert public_num2

        assert public_num.n == public_num2.n
        assert public_num.e == public_num2.e

    @pytest.mark.supported(
        only_if=lambda backend: not rust_openssl.CRYPTOGRAPHY_IS_BORINGSSL,
        skip_message="Does not support RSA PSS loading",
    )
    @pytest.mark.parametrize(
        "path",
        [
            os.path.join("asymmetric", "PKCS8", "rsa_pss_2048.pem"),
            os.path.join("asymmetric", "PKCS8", "rsa_pss_2048_hash.pem"),
            os.path.join("asymmetric", "PKCS8", "rsa_pss_2048_hash_mask.pem"),
            os.path.join(
                "asymmetric", "PKCS8", "rsa_pss_2048_hash_mask_diff.pem"
            ),
            os.path.join(
                "asymmetric", "PKCS8", "rsa_pss_2048_hash_mask_salt.pem"
            ),
        ],
    )
    def test_load_pss_keys_strips_constraints(self, path, backend):
        key = load_vectors_from_file(
            filename=path,
            loader=lambda p: serialization.load_pem_private_key(
                p.read(), password=None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        # These keys have constraints that prohibit PKCS1v15 signing,
        # but for now we load them without the constraint and test that
        # it's truly removed by performing a disallowed signature.
        assert isinstance(key, rsa.RSAPrivateKey)
        signature = key.sign(b"whatever", padding.PKCS1v15(), hashes.SHA224())
        key.public_key().verify(
            signature, b"whatever", padding.PKCS1v15(), hashes.SHA224()
        )

    def test_load_pss_pub_keys_strips_constraints(self, backend):
        key = load_vectors_from_file(
            filename=os.path.join(
                "asymmetric", "PKCS8", "rsa_pss_2048_pub.der"
            ),
            loader=lambda p: serialization.load_der_public_key(
                p.read(),
            ),
            mode="rb",
        )
        assert isinstance(key, rsa.RSAPublicKey)
        with pytest.raises(InvalidSignature):
            key.verify(
                b"badsig", b"whatever", padding.PKCS1v15(), hashes.SHA256()
            )

    @pytest.mark.supported(
        only_if=lambda backend: rust_openssl.CRYPTOGRAPHY_IS_BORINGSSL,
        skip_message="Test requires a backend without RSA-PSS key support",
    )
    def test_load_pss_unsupported(self, backend):
        # Key loading errors unfortunately have multiple paths so
        # we need to allow ValueError and UnsupportedAlgorithm
        with pytest.raises((UnsupportedAlgorithm, ValueError)):
            load_vectors_from_file(
                filename=os.path.join(
                    "asymmetric", "PKCS8", "rsa_pss_2048.pem"
                ),
                loader=lambda p: serialization.load_pem_private_key(
                    p.read(), password=None
                ),
                mode="rb",
            )

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "RSA", "oaep-label.txt"),
            load_nist_vectors,
        ),
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=b"label",
            )
        ),
        skip_message="Does not support RSA OAEP labels",
    )
    def test_oaep_label_decrypt(self, vector, backend):
        private_key = serialization.load_der_private_key(
            binascii.unhexlify(vector["key"]),
            None,
            backend,
            unsafe_skip_rsa_key_validation=True,
        )
        assert isinstance(private_key, rsa.RSAPrivateKey)
        assert vector["oaepdigest"] == b"SHA512"
        decrypted = private_key.decrypt(
            binascii.unhexlify(vector["input"]),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA512()),
                algorithm=hashes.SHA512(),
                label=binascii.unhexlify(vector["oaeplabel"]),
            ),
        )
        assert vector["output"][1:-1] == decrypted

    @pytest.mark.parametrize(
        ("msg", "label"),
        [
            (b"amazing encrypted msg", b"some label"),
            (b"amazing encrypted msg", b""),
        ],
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=b"label",
            )
        ),
        skip_message="Does not support RSA OAEP labels",
    )
    def test_oaep_label_roundtrip(self, rsa_key_2048, msg, label, backend):
        private_key = rsa_key_2048
        ct = private_key.public_key().encrypt(
            msg,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=label,
            ),
        )
        pt = private_key.decrypt(
            ct,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=label,
            ),
        )
        assert pt == msg

    @pytest.mark.parametrize(
        ("enclabel", "declabel"),
        [(b"label1", b"label2"), (b"label3", b""), (b"", b"label4")],
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=b"label",
            )
        ),
        skip_message="Does not support RSA OAEP labels",
    )
    def test_oaep_wrong_label(self, rsa_key_2048, enclabel, declabel, backend):
        private_key = rsa_key_2048
        msg = b"test"
        ct = private_key.public_key().encrypt(
            msg,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=enclabel,
            ),
        )
        with pytest.raises(ValueError):
            private_key.decrypt(
                ct,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=declabel,
                ),
            )


class TestRSASignature:
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.signature_hash_supported(
            hashes.SHA1()
        ),
        skip_message="Does not support SHA1 signature.",
    )
    def test_pkcs1v15_signing(self, backend, subtests):
        vectors = _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join("asymmetric", "RSA", "pkcs1v15sign-vectors.txt"),
                load_pkcs1_vectors,
            )
        )
        for private, public, example in vectors:
            with subtests.test():
                private_key = rsa.RSAPrivateNumbers(
                    p=private["p"],
                    q=private["q"],
                    d=private["private_exponent"],
                    dmp1=private["dmp1"],
                    dmq1=private["dmq1"],
                    iqmp=private["iqmp"],
                    public_numbers=rsa.RSAPublicNumbers(
                        e=private["public_exponent"], n=private["modulus"]
                    ),
                ).private_key(backend, unsafe_skip_rsa_key_validation=True)
                signature = private_key.sign(
                    binascii.unhexlify(example["message"]),
                    padding.PKCS1v15(),
                    hashes.SHA1(),
                )
                assert binascii.hexlify(signature) == example["signature"]

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA1()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.signature_hash_supported(
            hashes.SHA1()
        ),
        skip_message="Does not support SHA1 signature.",
    )
    def test_pss_signing(self, subtests, backend):
        for private, public, example in _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join(
                    "asymmetric", "RSA", "pkcs-1v2-1d2-vec", "pss-vect.txt"
                ),
                load_pkcs1_vectors,
            )
        ):
            with subtests.test():
                private_key = rsa.RSAPrivateNumbers(
                    p=private["p"],
                    q=private["q"],
                    d=private["private_exponent"],
                    dmp1=private["dmp1"],
                    dmq1=private["dmq1"],
                    iqmp=private["iqmp"],
                    public_numbers=rsa.RSAPublicNumbers(
                        e=private["public_exponent"], n=private["modulus"]
                    ),
                ).private_key(backend, unsafe_skip_rsa_key_validation=True)
                public_key = rsa.RSAPublicNumbers(
                    e=public["public_exponent"], n=public["modulus"]
                ).public_key(backend)
                signature = private_key.sign(
                    binascii.unhexlify(example["message"]),
                    padding.PSS(
                        mgf=padding.MGF1(algorithm=hashes.SHA1()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA1(),
                )
                assert len(signature) == (private_key.key_size + 7) // 8
                # PSS signatures contain randomness so we can't do an exact
                # signature check. Instead we'll verify that the signature
                # created successfully verifies.
                public_key.verify(
                    signature,
                    binascii.unhexlify(example["message"]),
                    padding.PSS(
                        mgf=padding.MGF1(algorithm=hashes.SHA1()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA1(),
                )

    @pytest.mark.parametrize(
        "hash_alg",
        [hashes.SHA224(), hashes.SHA256(), hashes.SHA384(), hashes.SHA512()],
    )
    def test_pss_signing_sha2(self, rsa_key_2048, hash_alg, backend):
        _skip_pss_hash_algorithm_unsupported(backend, hash_alg)
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        pss = padding.PSS(
            mgf=padding.MGF1(hash_alg), salt_length=padding.PSS.MAX_LENGTH
        )
        msg = b"testing signature"
        signature = private_key.sign(msg, pss, hash_alg)
        public_key.verify(signature, msg, pss, hash_alg)

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    def test_pss_digest_length(self, rsa_key_2048, backend):
        private_key = rsa_key_2048
        signature = private_key.sign(
            b"some data",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        public = private_key.public_key()
        public.verify(
            signature,
            b"some data",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        public.verify(
            signature,
            b"some data",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=32,
            ),
            hashes.SHA256(),
        )

    @pytest.mark.supported(
        only_if=lambda backend: (
            backend.hash_supported(hashes.SHA512())
            and backend.rsa_padding_supported(
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                )
            )
        ),
        skip_message="Does not support SHA512.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pss_minimum_key_size_for_digest(self, backend):
        private_key = RSA_KEY_522.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )
        private_key.sign(
            b"no failure",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA512(),
        )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.hash_supported(hashes.SHA512()),
        skip_message="Does not support SHA512.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pss_signing_digest_too_large_for_key_size(
        self, rsa_key_512: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_512
        with pytest.raises(ValueError):
            private_key.sign(
                b"msg",
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA512(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    def test_pss_signing_salt_length_too_long(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with pytest.raises(ValueError):
            private_key.sign(
                b"failure coming",
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()), salt_length=1000000
                ),
                hashes.SHA256(),
            )

    def test_unsupported_padding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            private_key.sign(b"msg", DummyAsymmetricPadding(), hashes.SHA256())

    def test_padding_incorrect_type(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with pytest.raises(TypeError):
            private_key.sign(
                b"msg",
                "notpadding",  # type: ignore[arg-type]
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_unsupported_pss_mgf(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_MGF):
            private_key.sign(
                b"msg",
                padding.PSS(
                    mgf=DummyMGF(),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.AUTO,
            )
        ),
        skip_message="Does not support PSS.",
    )
    def test_pss_sign_unsupported_auto(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with pytest.raises(ValueError):
            private_key.sign(
                b"some data",
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.AUTO,
                ),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pkcs1_digest_too_large_for_key_size(self, backend):
        private_key = RSA_KEY_599.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )
        with pytest.raises(ValueError):
            private_key.sign(
                b"failure coming", padding.PKCS1v15(), hashes.SHA512()
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pkcs1_minimum_key_size(self, backend):
        private_key = RSA_KEY_745.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )
        private_key.sign(b"no failure", padding.PKCS1v15(), hashes.SHA512())

    @pytest.mark.parametrize(
        "message",
        [
            b"one little message",
            bytearray(b"one little message"),
        ],
    )
    def test_sign(self, rsa_key_2048: rsa.RSAPrivateKey, message, backend):
        private_key = rsa_key_2048
        pkcs = padding.PKCS1v15()
        algorithm = hashes.SHA256()
        signature = private_key.sign(message, pkcs, algorithm)
        public_key = private_key.public_key()
        public_key.verify(signature, message, pkcs, algorithm)

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_prehashed_sign(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        message = b"one little message"
        h = hashes.Hash(hashes.SHA256(), backend)
        h.update(message)
        digest = h.finalize()
        pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        prehashed_alg = asym_utils.Prehashed(hashes.SHA256())
        signature = private_key.sign(digest, pss, prehashed_alg)
        public_key = private_key.public_key()
        public_key.verify(signature, message, pss, hashes.SHA256())

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    def test_prehashed_digest_length(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        message = b"one little message"
        h = hashes.Hash(hashes.SHA256(), backend)
        h.update(message)
        digest = h.finalize()
        pss = padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        )
        prehashed_alg = asym_utils.Prehashed(hashes.SHA256())
        signature = private_key.sign(digest, pss, prehashed_alg)
        public_key = private_key.public_key()
        public_key.verify(signature, message, pss, hashes.SHA256())

    @pytest.mark.supported(
        only_if=lambda backend: backend.hash_supported(
            hashes.BLAKE2s(digest_size=32)
        ),
        skip_message="Does not support BLAKE2s",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_unsupported_hash(self, rsa_key_512: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_512
        message = b"one little message"
        pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            private_key.sign(message, pss, hashes.BLAKE2s(32))

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_unsupported_hash_pss_mgf1(self, rsa_key_2048: rsa.RSAPrivateKey):
        private_key = rsa_key_2048
        message = b"my message"
        pss = padding.PSS(
            mgf=padding.MGF1(DummyHashAlgorithm()), salt_length=0
        )
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            private_key.sign(message, pss, hashes.SHA256())

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_prehashed_digest_mismatch(
        self, rsa_key_512: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_512
        message = b"one little message"
        h = hashes.Hash(hashes.SHA512(), backend)
        h.update(message)
        digest = h.finalize()
        pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        prehashed_alg = asym_utils.Prehashed(hashes.SHA256())
        with pytest.raises(ValueError):
            private_key.sign(digest, pss, prehashed_alg)

    def test_prehashed_unsupported_in_signature_recover(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        signature = private_key.sign(
            b"sign me", padding.PKCS1v15(), hashes.SHA256()
        )
        prehashed_alg = asym_utils.Prehashed(hashes.SHA256())
        with pytest.raises(TypeError):
            public_key.recover_data_from_signature(
                signature,
                padding.PKCS1v15(),
                prehashed_alg,  # type: ignore[arg-type]
            )

    def test_corrupted_private_key(self, backend):
        with pytest.raises(ValueError):
            serialization.load_pem_private_key(
                RSA_KEY_CORRUPTED, password=None, backend=backend
            )


class TestRSAVerification:
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.signature_hash_supported(
            hashes.SHA1()
        ),
        skip_message="Does not support SHA1 signature.",
    )
    def test_pkcs1v15_verification(self, backend, subtests):
        vectors = _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join("asymmetric", "RSA", "pkcs1v15sign-vectors.txt"),
                load_pkcs1_vectors,
            )
        )
        for private, public, example in vectors:
            with subtests.test():
                public_key = rsa.RSAPublicNumbers(
                    e=public["public_exponent"], n=public["modulus"]
                ).public_key(backend)
                signature = binascii.unhexlify(example["signature"])
                message = binascii.unhexlify(example["message"])
                public_key.verify(
                    signature, message, padding.PKCS1v15(), hashes.SHA1()
                )

                # Test digest recovery by providing hash
                digest = hashes.Hash(hashes.SHA1())
                digest.update(message)
                msg_digest = digest.finalize()
                rec_msg_digest = public_key.recover_data_from_signature(
                    signature, padding.PKCS1v15(), hashes.SHA1()
                )
                assert msg_digest == rec_msg_digest

                # Test recovery of all data (full DigestInfo) with hash alg. as
                # None
                rec_sig_data = public_key.recover_data_from_signature(
                    signature, padding.PKCS1v15(), None
                )
                assert len(rec_sig_data) > len(msg_digest)
                assert msg_digest == rec_sig_data[-len(msg_digest) :]

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_invalid_pkcs1v15_signature_wrong_data(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        signature = private_key.sign(
            b"sign me", padding.PKCS1v15(), hashes.SHA256()
        )
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature,
                b"incorrect data",
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

    def test_invalid_pkcs1v15_signature_recover_wrong_hash_alg(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        signature = private_key.sign(
            b"sign me", padding.PKCS1v15(), hashes.SHA256()
        )
        with pytest.raises(InvalidSignature):
            public_key.recover_data_from_signature(
                signature, padding.PKCS1v15(), hashes.SHA512()
            )

    def test_invalid_signature_sequence_removed(self, backend):
        """
        This test comes from wycheproof
        """
        key_der = binascii.unhexlify(
            b"30820122300d06092a864886f70d01010105000382010f003082010a02820101"
            b"00a2b451a07d0aa5f96e455671513550514a8a5b462ebef717094fa1fee82224"
            b"e637f9746d3f7cafd31878d80325b6ef5a1700f65903b469429e89d6eac88450"
            b"97b5ab393189db92512ed8a7711a1253facd20f79c15e8247f3d3e42e46e48c9"
            b"8e254a2fe9765313a03eff8f17e1a029397a1fa26a8dce26f490ed81299615d9"
            b"814c22da610428e09c7d9658594266f5c021d0fceca08d945a12be82de4d1ece"
            b"6b4c03145b5d3495d4ed5411eb878daf05fd7afc3e09ada0f1126422f590975a"
            b"1969816f48698bcbba1b4d9cae79d460d8f9f85e7975005d9bc22c4e5ac0f7c1"
            b"a45d12569a62807d3b9a02e5a530e773066f453d1f5b4c2e9cf7820283f742b9"
            b"d50203010001"
        )
        sig = binascii.unhexlify(
            b"498209f59a0679a1f926eccf3056da2cba553d7ab3064e7c41ad1d739f038249"
            b"f02f5ad12ee246073d101bc3cdb563e8b6be61562056422b7e6c16ad53deb12a"
            b"f5de744197753a35859833f41bb59c6597f3980132b7478fd0b95fd27dfad64a"
            b"20fd5c25312bbd41a85286cd2a83c8df5efa0779158d01b0747ff165b055eb28"
            b"80ea27095700a295593196d8c5922cf6aa9d7e29b5056db5ded5eb20aeb31b89"
            b"42e26b15a5188a4934cd7e39cfe379a197f49a204343a493452deebca436ee61"
            b"4f4daf989e355544489f7e69ffa8ccc6a1e81cf0ab33c3e6d7591091485a6a31"
            b"bda3b33946490057b9a3003d3fd9daf7c4778b43fd46144d945d815f12628ff4"
        )
        public_key = serialization.load_der_public_key(key_der, backend)
        assert isinstance(public_key, rsa.RSAPublicKey)
        with pytest.raises(InvalidSignature):
            public_key.verify(
                sig,
                binascii.unhexlify(b"313233343030"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_invalid_pkcs1v15_signature_wrong_key(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        private_key2 = RSA_KEY_2048_ALT.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )
        public_key = private_key2.public_key()
        msg = b"sign me"
        signature = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature, msg, padding.PKCS1v15(), hashes.SHA256()
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA1()), salt_length=20)
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.signature_hash_supported(
            hashes.SHA1()
        ),
        skip_message="Does not support SHA1 signature.",
    )
    def test_pss_verification(self, subtests, backend):
        for private, public, example in _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join(
                    "asymmetric", "RSA", "pkcs-1v2-1d2-vec", "pss-vect.txt"
                ),
                load_pkcs1_vectors,
            )
        ):
            with subtests.test():
                public_key = rsa.RSAPublicNumbers(
                    e=public["public_exponent"], n=public["modulus"]
                ).public_key(backend)
                public_key.verify(
                    binascii.unhexlify(example["signature"]),
                    binascii.unhexlify(example["message"]),
                    padding.PSS(
                        mgf=padding.MGF1(algorithm=hashes.SHA1()),
                        salt_length=20,
                    ),
                    hashes.SHA1(),
                )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.AUTO,
            )
        ),
        skip_message="Does not support PSS.",
    )
    def test_pss_verify_auto_salt_length(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        signature = private_key.sign(
            b"some data",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
        private_key.public_key().verify(
            signature,
            b"some data",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.AUTO,
            ),
            hashes.SHA256(),
        )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_invalid_pss_signature_wrong_data(self, backend):
        public_key = rsa.RSAPublicNumbers(
            n=int(
                b"dffc2137d5e810cde9e4b4612f5796447218bab913b3fa98bdf7982e4fa6"
                b"ec4d6653ef2b29fb1642b095befcbea6decc178fb4bed243d3c3592c6854"
                b"6af2d3f3",
                16,
            ),
            e=65537,
        ).public_key(backend)
        signature = binascii.unhexlify(
            b"0e68c3649df91c5bc3665f96e157efa75b71934aaa514d91e94ca8418d100f45"
            b"6f05288e58525f99666bab052adcffdf7186eb40f583bd38d98c97d3d524808b"
        )
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature,
                b"incorrect data",
                padding.PSS(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_invalid_pss_signature_wrong_key(self, backend):
        signature = binascii.unhexlify(
            b"3a1880165014ba6eb53cc1449d13e5132ebcc0cfd9ade6d7a2494a0503bd0826"
            b"f8a46c431e0d7be0ca3e453f8b2b009e2733764da7927cc6dbe7a021437a242e"
        )
        public_key = rsa.RSAPublicNumbers(
            n=int(
                b"381201f4905d67dfeb3dec131a0fbea773489227ec7a1448c3109189ac68"
                b"5a95441be90866a14c4d2e139cd16db540ec6c7abab13ffff91443fd46a8"
                b"960cbb7658ded26a5c95c86f6e40384e1c1239c63e541ba221191c4dd303"
                b"231b42e33c6dbddf5ec9a746f09bf0c25d0f8d27f93ee0ae5c0d723348f4"
                b"030d3581e13522e1",
                16,
            ),
            e=65537,
        ).public_key(backend)
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature,
                b"sign me",
                padding.PSS(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_invalid_pss_signature_data_too_large_for_modulus(self, backend):
        # 2048 bit PSS signature
        signature = binascii.unhexlify(
            b"58750fc3d2f560d1f3e37c8e28bc8da6d3e93f5d58f8becd25b1c931eea30fea"
            b"54cb17d44b90104a0aacb7fe9ffa2a59c5788435911d63de78178d21eb875ccd"
            b"0b07121b641ed4fe6bcb1ca5060322765507b4f24bdba8a698a8e4e07e6bf2c4"
            b"7a736abe5a912e85cd32f648f3e043b4385e8b612dcce342c5fddf18c524deb5"
            b"6295b95f6dfa759b2896b793628a90f133e74c1ff7d3af43e3f7ee792df2e5b6"
            b"a19e996ac3676884354899a437b3ae4e3ac91976c336c332a3b1db0d172b19cb"
            b"40ad3d871296cfffb3c889ce74a179a3e290852c35d59525afe4b39dc907fad2"
            b"ac462c50a488dca486031a3dc8c4cdbbc53e9f71d64732e1533a5d1249b833ce"
        )
        # 1024 bit key
        public_key = RSA_KEY_1024.private_key(
            unsafe_skip_rsa_key_validation=True
        ).public_key()
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature,
                b"sign me",
                padding.PSS(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

    def test_invalid_pss_signature_recover(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        pss_padding = padding.PSS(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        )
        signature = private_key.sign(b"sign me", pss_padding, hashes.SHA256())

        # Hash algorithm cannot be absent for PSS padding
        with pytest.raises(TypeError):
            public_key.recover_data_from_signature(
                signature, pss_padding, None
            )

        # Signature data recovery not supported with PSS
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            public_key.recover_data_from_signature(
                signature, pss_padding, hashes.SHA256()
            )

    def test_unsupported_padding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            public_key.verify(
                b"sig", b"msg", DummyAsymmetricPadding(), hashes.SHA256()
            )

    def test_padding_incorrect_type(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        with pytest.raises(TypeError):
            public_key.verify(
                b"sig",
                b"msg",
                "notpadding",  # type: ignore[arg-type]
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=0)
        ),
        skip_message="Does not support PSS.",
    )
    def test_unsupported_pss_mgf(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_MGF):
            public_key.verify(
                b"sig",
                b"msg",
                padding.PSS(
                    mgf=DummyMGF(), salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA512()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.hash_supported(hashes.SHA512()),
        skip_message="Does not support SHA512.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pss_verify_digest_too_large_for_key_size(
        self, rsa_key_512: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_512
        signature = binascii.unhexlify(
            b"8b9a3ae9fb3b64158f3476dd8d8a1f1425444e98940e0926378baa9944d219d8"
            b"534c050ef6b19b1bdc6eb4da422e89161106a6f5b5cc16135b11eb6439b646bd"
        )
        public_key = private_key.public_key()
        with pytest.raises(ValueError):
            public_key.verify(
                signature,
                b"msg doesn't matter",
                padding.PSS(
                    mgf=padding.MGF1(algorithm=hashes.SHA512()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA512(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS.",
    )
    @pytest.mark.skip_fips(reason="Unsupported key size in FIPS mode.")
    def test_pss_verify_salt_length_too_long(self, backend):
        signature = binascii.unhexlify(
            b"8b9a3ae9fb3b64158f3476dd8d8a1f1425444e98940e0926378baa9944d219d8"
            b"534c050ef6b19b1bdc6eb4da422e89161106a6f5b5cc16135b11eb6439b646bd"
        )
        public_key = rsa.RSAPublicNumbers(
            n=int(
                b"d309e4612809437548b747d7f9eb9cd3340f54fe42bb3f84a36933b0839c"
                b"11b0c8b7f67e11f7252370161e31159c49c784d4bc41c42a78ce0f0b40a3"
                b"ca8ffb91",
                16,
            ),
            e=65537,
        ).public_key(backend)
        with pytest.raises(InvalidSignature):
            public_key.verify(
                signature,
                b"sign me",
                padding.PSS(
                    mgf=padding.MGF1(
                        algorithm=hashes.SHA256(),
                    ),
                    salt_length=1000000,
                ),
                hashes.SHA256(),
            )

    @pytest.mark.parametrize(
        "message",
        [
            b"one little message",
            bytearray(b"one little message"),
        ],
    )
    def test_verify(self, rsa_key_2048: rsa.RSAPrivateKey, message, backend):
        private_key = rsa_key_2048
        pkcs = padding.PKCS1v15()
        algorithm = hashes.SHA256()
        signature = private_key.sign(message, pkcs, algorithm)
        public_key = private_key.public_key()
        public_key.verify(signature, message, pkcs, algorithm)

    def test_prehashed_verify(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        message = b"one little message"
        h = hashes.Hash(hashes.SHA256(), backend)
        h.update(message)
        digest = h.finalize()
        prehashed_alg = asym_utils.Prehashed(hashes.SHA256())
        pkcs = padding.PKCS1v15()
        signature = private_key.sign(message, pkcs, hashes.SHA256())
        public_key = private_key.public_key()
        public_key.verify(signature, digest, pkcs, prehashed_alg)

    def test_prehashed_digest_mismatch(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        public_key = rsa_key_2048.public_key()
        message = b"one little message"
        h = hashes.Hash(hashes.SHA256(), backend)
        h.update(message)
        data = h.finalize()
        prehashed_alg = asym_utils.Prehashed(hashes.SHA512())
        pkcs = padding.PKCS1v15()
        with pytest.raises(ValueError):
            public_key.verify(b"\x00" * 64, data, pkcs, prehashed_alg)


class TestRSAPSSMGF1Verification:
    test_rsa_pss_mgf1_sha1 = pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA1()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        )
        and backend.signature_hash_supported(hashes.SHA1()),
        skip_message=(
            "Does not support PSS using MGF1 with SHA1 or SHA1 signature."
        ),
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGenPSS_186-2.rsp",
                "SigGenPSS_186-3.rsp",
                "SigVerPSS_186-3.rsp",
            ],
            hashes.SHA1(),
            lambda params, hash_alg: padding.PSS(
                mgf=padding.MGF1(
                    algorithm=hash_alg,
                ),
                salt_length=params["salt_length"],
            ),
        )
    )

    test_rsa_pss_mgf1_sha224 = pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA224()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS using MGF1 with SHA224.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGenPSS_186-2.rsp",
                "SigGenPSS_186-3.rsp",
                "SigVerPSS_186-3.rsp",
            ],
            hashes.SHA224(),
            lambda params, hash_alg: padding.PSS(
                mgf=padding.MGF1(
                    algorithm=hash_alg,
                ),
                salt_length=params["salt_length"],
            ),
        )
    )

    test_rsa_pss_mgf1_sha256 = pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS using MGF1 with SHA256.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGenPSS_186-2.rsp",
                "SigGenPSS_186-3.rsp",
                "SigVerPSS_186-3.rsp",
            ],
            hashes.SHA256(),
            lambda params, hash_alg: padding.PSS(
                mgf=padding.MGF1(
                    algorithm=hash_alg,
                ),
                salt_length=params["salt_length"],
            ),
        )
    )

    test_rsa_pss_mgf1_sha384 = pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA384()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS using MGF1 with SHA384.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGenPSS_186-2.rsp",
                "SigGenPSS_186-3.rsp",
                "SigVerPSS_186-3.rsp",
            ],
            hashes.SHA384(),
            lambda params, hash_alg: padding.PSS(
                mgf=padding.MGF1(
                    algorithm=hash_alg,
                ),
                salt_length=params["salt_length"],
            ),
        )
    )

    test_rsa_pss_mgf1_sha512 = pytest.mark.supported(
        only_if=lambda backend: backend.rsa_padding_supported(
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA512()),
                salt_length=padding.PSS.MAX_LENGTH,
            )
        ),
        skip_message="Does not support PSS using MGF1 with SHA512.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGenPSS_186-2.rsp",
                "SigGenPSS_186-3.rsp",
                "SigVerPSS_186-3.rsp",
            ],
            hashes.SHA512(),
            lambda params, hash_alg: padding.PSS(
                mgf=padding.MGF1(
                    algorithm=hash_alg,
                ),
                salt_length=params["salt_length"],
            ),
        )
    )


class TestRSAPKCS1Verification:
    test_rsa_pkcs1v15_verify_sha1 = pytest.mark.supported(
        only_if=lambda backend: (
            backend.signature_hash_supported(hashes.SHA1())
            and backend.rsa_padding_supported(padding.PKCS1v15())
        ),
        skip_message="Does not support SHA1 and PKCS1v1.5.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGen15_186-2.rsp",
                "SigGen15_186-3.rsp",
                "SigVer15_186-3.rsp",
            ],
            hashes.SHA1(),
            lambda params, hash_alg: padding.PKCS1v15(),
        )
    )

    test_rsa_pkcs1v15_verify_sha224 = pytest.mark.supported(
        only_if=lambda backend: (
            backend.signature_hash_supported(hashes.SHA224())
            and backend.rsa_padding_supported(padding.PKCS1v15())
        ),
        skip_message="Does not support SHA224 and PKCS1v1.5.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGen15_186-2.rsp",
                "SigGen15_186-3.rsp",
                "SigVer15_186-3.rsp",
            ],
            hashes.SHA224(),
            lambda params, hash_alg: padding.PKCS1v15(),
        )
    )

    test_rsa_pkcs1v15_verify_sha256 = pytest.mark.supported(
        only_if=lambda backend: (
            backend.signature_hash_supported(hashes.SHA256())
            and backend.rsa_padding_supported(padding.PKCS1v15())
        ),
        skip_message="Does not support SHA256 and PKCS1v1.5.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGen15_186-2.rsp",
                "SigGen15_186-3.rsp",
                "SigVer15_186-3.rsp",
            ],
            hashes.SHA256(),
            lambda params, hash_alg: padding.PKCS1v15(),
        )
    )

    test_rsa_pkcs1v15_verify_sha384 = pytest.mark.supported(
        only_if=lambda backend: (
            backend.signature_hash_supported(hashes.SHA384())
            and backend.rsa_padding_supported(padding.PKCS1v15())
        ),
        skip_message="Does not support SHA384 and PKCS1v1.5.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGen15_186-2.rsp",
                "SigGen15_186-3.rsp",
                "SigVer15_186-3.rsp",
            ],
            hashes.SHA384(),
            lambda params, hash_alg: padding.PKCS1v15(),
        )
    )

    test_rsa_pkcs1v15_verify_sha512 = pytest.mark.supported(
        only_if=lambda backend: (
            backend.signature_hash_supported(hashes.SHA512())
            and backend.rsa_padding_supported(padding.PKCS1v15())
        ),
        skip_message="Does not support SHA512 and PKCS1v1.5.",
    )(
        generate_rsa_verification_test(
            load_rsa_nist_vectors,
            os.path.join("asymmetric", "RSA", "FIPS_186-2"),
            [
                "SigGen15_186-2.rsp",
                "SigGen15_186-3.rsp",
                "SigVer15_186-3.rsp",
            ],
            hashes.SHA512(),
            lambda params, hash_alg: padding.PKCS1v15(),
        )
    )


class TestPSS:
    def test_calculate_max_pss_salt_length(self):
        with pytest.raises(TypeError):
            padding.calculate_max_pss_salt_length(
                object(),  # type:ignore[arg-type]
                hashes.SHA256(),
            )

    def test_invalid_salt_length_not_integer(self):
        with pytest.raises(TypeError):
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=b"not_a_length",  # type:ignore[arg-type]
            )

    def test_invalid_salt_length_negative_integer(self):
        with pytest.raises(ValueError):
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=-1)

    def test_valid_pss_parameters(self):
        algorithm = hashes.SHA256()
        salt_length = algorithm.digest_size
        mgf = padding.MGF1(algorithm)
        pss = padding.PSS(mgf=mgf, salt_length=salt_length)
        assert pss._mgf == mgf
        assert pss._salt_length == salt_length

    def test_valid_pss_parameters_maximum(self):
        algorithm = hashes.SHA256()
        mgf = padding.MGF1(algorithm)
        pss = padding.PSS(mgf=mgf, salt_length=padding.PSS.MAX_LENGTH)
        assert pss._mgf == mgf
        assert pss._salt_length == padding.PSS.MAX_LENGTH

    def test_mgf_property(self):
        algorithm = hashes.SHA256()
        mgf = padding.MGF1(algorithm)
        pss = padding.PSS(mgf=mgf, salt_length=padding.PSS.MAX_LENGTH)
        assert pss.mgf == mgf
        assert pss.mgf == pss._mgf


class TestMGF1:
    def test_invalid_hash_algorithm(self):
        with pytest.raises(TypeError):
            padding.MGF1(b"not_a_hash")  # type:ignore[arg-type]

    def test_valid_mgf1_parameters(self):
        algorithm = hashes.SHA256()
        mgf = padding.MGF1(algorithm)
        assert mgf._algorithm == algorithm


class TestOAEP:
    def test_invalid_algorithm(self):
        mgf = padding.MGF1(hashes.SHA256())
        with pytest.raises(TypeError):
            padding.OAEP(
                mgf=mgf,
                algorithm=b"",  # type:ignore[arg-type]
                label=None,
            )

    def test_algorithm_property(self):
        algorithm = hashes.SHA256()
        mgf = padding.MGF1(algorithm)
        oaep = padding.OAEP(mgf=mgf, algorithm=algorithm, label=None)
        assert oaep.algorithm == algorithm
        assert oaep.algorithm == oaep._algorithm

    def test_mgf_property(self):
        algorithm = hashes.SHA256()
        mgf = padding.MGF1(algorithm)
        oaep = padding.OAEP(mgf=mgf, algorithm=algorithm, label=None)
        assert oaep.mgf == mgf
        assert oaep.mgf == oaep._mgf


class TestRSADecryption:
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_decrypt_pkcs1v15_vectors(self, backend, subtests):
        vectors = _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join("asymmetric", "RSA", "pkcs1v15crypt-vectors.txt"),
                load_pkcs1_vectors,
            )
        )
        for private, public, example in vectors:
            with subtests.test():
                skey = rsa.RSAPrivateNumbers(
                    p=private["p"],
                    q=private["q"],
                    d=private["private_exponent"],
                    dmp1=private["dmp1"],
                    dmq1=private["dmq1"],
                    iqmp=private["iqmp"],
                    public_numbers=rsa.RSAPublicNumbers(
                        e=private["public_exponent"], n=private["modulus"]
                    ),
                ).private_key(backend, unsafe_skip_rsa_key_validation=True)
                ciphertext = binascii.unhexlify(example["encryption"])
                assert len(ciphertext) == (skey.key_size + 7) // 8
                message = skey.decrypt(ciphertext, padding.PKCS1v15())
                assert message == binascii.unhexlify(example["message"])

    def test_unsupported_padding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            private_key.decrypt(b"0" * 256, DummyAsymmetricPadding())

    @pytest.mark.supported(
        only_if=lambda backend: (
            backend.rsa_encryption_supported(padding.PKCS1v15())
            and not backend._lib.Cryptography_HAS_IMPLICIT_RSA_REJECTION
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_decrypt_invalid_decrypt(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with pytest.raises(ValueError):
            private_key.decrypt(b"\x00" * 256, padding.PKCS1v15())

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_decrypt_ciphertext_too_large(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with pytest.raises(ValueError):
            private_key.decrypt(b"\x00" * 257, padding.PKCS1v15())

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    def test_decrypt_ciphertext_too_small(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        ct = binascii.unhexlify(
            b"50b4c14136bd198c2f3c3ed243fce036e168d56517984a263cd66492b80804f1"
            b"69d210f2b9bdfb48b12f9ea05009c77da257cc600ccefe3a6283789d8ea0"
        )
        with pytest.raises(ValueError):
            private_key.decrypt(ct, padding.PKCS1v15())

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            )
        ),
        skip_message="Does not support OAEP.",
    )
    def test_decrypt_oaep_sha1_vectors(self, subtests, backend):
        for private, public, example in _flatten_pkcs1_examples(
            load_vectors_from_file(
                os.path.join(
                    "asymmetric", "RSA", "pkcs-1v2-1d2-vec", "oaep-vect.txt"
                ),
                load_pkcs1_vectors,
            )
        ):
            with subtests.test():
                skey = rsa.RSAPrivateNumbers(
                    p=private["p"],
                    q=private["q"],
                    d=private["private_exponent"],
                    dmp1=private["dmp1"],
                    dmq1=private["dmq1"],
                    iqmp=private["iqmp"],
                    public_numbers=rsa.RSAPublicNumbers(
                        e=private["public_exponent"], n=private["modulus"]
                    ),
                ).private_key(backend, unsafe_skip_rsa_key_validation=True)
                message = skey.decrypt(
                    binascii.unhexlify(example["encryption"]),
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA1()),
                        algorithm=hashes.SHA1(),
                        label=None,
                    ),
                )
                assert message == binascii.unhexlify(example["message"])

    def test_decrypt_oaep_sha2_vectors(self, backend, subtests):
        vectors = _build_oaep_sha2_vectors()
        for private, public, example, mgf1_alg, hash_alg in vectors:
            with subtests.test():
                pad = padding.OAEP(
                    mgf=padding.MGF1(algorithm=mgf1_alg),
                    algorithm=hash_alg,
                    label=None,
                )
                if not backend.rsa_encryption_supported(pad):
                    pytest.skip(
                        f"Does not support OAEP using {mgf1_alg.name} MGF1 "
                        f"or {hash_alg.name} hash."
                    )
                skey = rsa.RSAPrivateNumbers(
                    p=private["p"],
                    q=private["q"],
                    d=private["private_exponent"],
                    dmp1=private["dmp1"],
                    dmq1=private["dmq1"],
                    iqmp=private["iqmp"],
                    public_numbers=rsa.RSAPublicNumbers(
                        e=private["public_exponent"], n=private["modulus"]
                    ),
                ).private_key(backend, unsafe_skip_rsa_key_validation=True)
                message = skey.decrypt(
                    binascii.unhexlify(example["encryption"]),
                    pad,
                )
                assert message == binascii.unhexlify(example["message"])

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            )
        ),
        skip_message="Does not support OAEP.",
    )
    def test_invalid_oaep_decryption(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        # More recent versions of OpenSSL may raise different errors.
        # This test triggers a failure and confirms that we properly handle
        # it.
        private_key = rsa_key_2048

        ciphertext = private_key.public_key().encrypt(
            b"secure data",
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        private_key_alt = RSA_KEY_2048_ALT.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )

        with pytest.raises(ValueError):
            private_key_alt.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA1()),
                algorithm=hashes.SHA1(),
                label=None,
            )
        ),
        skip_message="Does not support OAEP.",
    )
    def test_invalid_oaep_decryption_data_to_large_for_modulus(self, backend):
        key = RSA_KEY_2048_ALT.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )

        ciphertext = (
            b"\xb1ph\xc0\x0b\x1a|\xe6\xda\xea\xb5\xd7%\x94\x07\xf96\xfb\x96"
            b"\x11\x9b\xdc4\xea.-\x91\x80\x13S\x94\x04m\xe9\xc5/F\x1b\x9b:\\"
            b"\x1d\x04\x16ML\xae\xb32J\x01yuA\xbb\x83\x1c\x8f\xf6\xa5\xdbp\xcd"
            b"\nx\xc7\xf6\x15\xb2/\xdcH\xae\xe7\x13\x13by\r4t\x99\x0fc\x1f\xc1"
            b"\x1c\xb1\xdd\xc5\x08\xd1\xee\xa1XQ\xb8H@L5v\xc3\xaf\xf2\r\x97"
            b"\xed\xaa\xe7\xf1\xd4xai\xd3\x83\xd9\xaa9\xbfx\xe1\x87F \x01\xff"
            b"L\xccv}ae\xb3\xfa\xf2B\xb8\xf9\x04H\x94\x85\xcb\x86\xbb\\ghx!W31"
            b"\xc7;t\na_E\xc2\x16\xb0;\xa1\x18\t\x1b\xe1\xdb\x80>)\x15\xc6\x12"
            b"\xcb\xeeg`\x8b\x9b\x1b\x05y4\xb0\x84M6\xcd\xa1\x827o\xfd\x96\xba"
            b"Z#\x8d\xae\x01\xc9\xf2\xb6\xde\x89{8&eQ\x1e8\x03\x01#?\xb66\\"
            b"\xad.\xe9\xfa!\x95 c{\xcaz\xe0*\tP\r\x91\x9a)B\xb5\xadN\xf4$\x83"
            b"\t\xb5u\xab\x19\x99"
        )

        with pytest.raises(ValueError):
            key.decrypt(
                ciphertext,
                padding.OAEP(
                    algorithm=hashes.SHA1(),
                    mgf=padding.MGF1(hashes.SHA1()),
                    label=None,
                ),
            )

    def test_unsupported_oaep_hash(self, rsa_key_2048: rsa.RSAPrivateKey):
        private_key = rsa_key_2048
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            private_key.decrypt(
                b"0" * 256,
                padding.OAEP(
                    mgf=padding.MGF1(DummyHashAlgorithm()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_HASH):
            private_key.decrypt(
                b"0" * 256,
                padding.OAEP(
                    mgf=padding.MGF1(hashes.SHA256()),
                    algorithm=DummyHashAlgorithm(),
                    label=None,
                ),
            )

    def test_unsupported_oaep_mgf(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_MGF):
            private_key.decrypt(
                b"0" * 256,
                padding.OAEP(
                    mgf=DummyMGF(),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )


class TestRSAEncryption:
    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            )
        ),
        skip_message="Does not support OAEP.",
    )
    @pytest.mark.parametrize(
        ("key_data", "pad"),
        itertools.product(
            (
                RSA_KEY_1024,
                RSA_KEY_1025,
                RSA_KEY_1026,
                RSA_KEY_1027,
                RSA_KEY_1028,
                RSA_KEY_1029,
                RSA_KEY_1030,
                RSA_KEY_1031,
                RSA_KEY_1536,
                RSA_KEY_2048,
            ),
            [
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                )
            ],
        ),
    )
    def test_rsa_encrypt_oaep(self, key_data, pad, backend):
        private_key = key_data.private_key(unsafe_skip_rsa_key_validation=True)
        _check_fips_key_length(backend, private_key)
        pt = b"encrypt me!"
        public_key = private_key.public_key()
        ct = public_key.encrypt(pt, pad)
        assert ct != pt
        assert len(ct) == (public_key.key_size + 7) // 8
        recovered_pt = private_key.decrypt(ct, pad)
        assert recovered_pt == pt

    @pytest.mark.parametrize(
        ("mgf1hash", "oaephash"),
        itertools.product(
            [
                hashes.SHA1(),
                hashes.SHA224(),
                hashes.SHA256(),
                hashes.SHA384(),
                hashes.SHA512(),
            ],
            [
                hashes.SHA1(),
                hashes.SHA224(),
                hashes.SHA256(),
                hashes.SHA384(),
                hashes.SHA512(),
            ],
        ),
    )
    def test_rsa_encrypt_oaep_sha2(
        self, rsa_key_2048: rsa.RSAPrivateKey, mgf1hash, oaephash, backend
    ):
        pad = padding.OAEP(
            mgf=padding.MGF1(algorithm=mgf1hash),
            algorithm=oaephash,
            label=None,
        )
        if not backend.rsa_encryption_supported(pad):
            pytest.skip(
                f"Does not support OAEP using {mgf1hash.name} MGF1 "
                f"or {oaephash.name} hash."
            )
        private_key = rsa_key_2048
        pt = b"encrypt me using sha2 hashes!"
        public_key = private_key.public_key()
        ct = public_key.encrypt(pt, pad)
        assert ct != pt
        assert len(ct) == (public_key.key_size + 7) // 8
        recovered_pt = private_key.decrypt(ct, pad)
        assert recovered_pt == pt

    @pytest.mark.supported(
        only_if=lambda backend: backend.rsa_encryption_supported(
            padding.PKCS1v15()
        ),
        skip_message="Does not support PKCS1v1.5.",
    )
    @pytest.mark.parametrize(
        ("key_data", "pad"),
        itertools.product(
            (
                RSA_KEY_1024,
                RSA_KEY_1025,
                RSA_KEY_1026,
                RSA_KEY_1027,
                RSA_KEY_1028,
                RSA_KEY_1029,
                RSA_KEY_1030,
                RSA_KEY_1031,
                RSA_KEY_1536,
                RSA_KEY_2048,
            ),
            [padding.PKCS1v15()],
        ),
    )
    def test_rsa_encrypt_pkcs1v15(self, key_data, pad, backend):
        private_key = key_data.private_key(unsafe_skip_rsa_key_validation=True)
        _check_fips_key_length(backend, private_key)
        pt = b"encrypt me!"
        public_key = private_key.public_key()
        ct = public_key.encrypt(pt, pad)
        assert ct != pt
        assert len(ct) == (public_key.key_size + 7) // 8
        recovered_pt = private_key.decrypt(ct, pad)
        assert recovered_pt == pt

    @pytest.mark.parametrize(
        ("key_data", "pad"),
        itertools.product(
            (
                RSA_KEY_1024,
                RSA_KEY_1025,
                RSA_KEY_1026,
                RSA_KEY_1027,
                RSA_KEY_1028,
                RSA_KEY_1029,
                RSA_KEY_1030,
                RSA_KEY_1031,
                RSA_KEY_1536,
                RSA_KEY_2048,
            ),
            (
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
                padding.PKCS1v15(),
            ),
        ),
    )
    def test_rsa_encrypt_key_too_small(self, key_data, pad, backend):
        private_key = key_data.private_key(unsafe_skip_rsa_key_validation=True)
        if not backend.rsa_encryption_supported(pad):
            pytest.skip("PKCS1v15 padding not allowed in FIPS")
        _check_fips_key_length(backend, private_key)
        public_key = private_key.public_key()
        # Slightly smaller than the key size but not enough for padding.
        with pytest.raises(ValueError):
            public_key.encrypt(b"\x00" * (private_key.key_size // 8 - 1), pad)

        # Larger than the key size.
        with pytest.raises(ValueError):
            public_key.encrypt(b"\x00" * (private_key.key_size // 8 + 5), pad)

    @pytest.mark.supported(
        only_if=lambda backend: backend._fips_enabled,
        skip_message="Requires FIPS",
    )
    def test_rsa_fips_small_key(self, rsa_key_512: rsa.RSAPrivateKey, backend):
        with pytest.raises(ValueError):
            rsa_key_512.sign(b"somedata", padding.PKCS1v15(), hashes.SHA512())

    def test_unsupported_padding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            public_key.encrypt(b"somedata", DummyAsymmetricPadding())
        with pytest.raises(TypeError):
            public_key.encrypt(
                b"somedata",
                padding=object(),  # type: ignore[arg-type]
            )

    def test_unsupported_oaep_mgf(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        public_key = private_key.public_key()

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_MGF):
            public_key.encrypt(
                b"ciphertext",
                padding.OAEP(
                    mgf=DummyMGF(),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )


class TestRSANumbers:
    def test_rsa_public_numbers(self):
        public_numbers = rsa.RSAPublicNumbers(e=1, n=15)
        assert public_numbers.e == 1
        assert public_numbers.n == 15

    def test_rsa_private_numbers(self):
        public_numbers = rsa.RSAPublicNumbers(e=1, n=15)
        private_numbers = rsa.RSAPrivateNumbers(
            p=3,
            q=5,
            d=1,
            dmp1=1,
            dmq1=1,
            iqmp=2,
            public_numbers=public_numbers,
        )

        assert private_numbers.p == 3
        assert private_numbers.q == 5
        assert private_numbers.d == 1
        assert private_numbers.dmp1 == 1
        assert private_numbers.dmq1 == 1
        assert private_numbers.iqmp == 2
        assert private_numbers.public_numbers == public_numbers

    def test_rsa_private_numbers_create_key(self, backend):
        private_key = RSA_KEY_1024.private_key(
            backend, unsafe_skip_rsa_key_validation=True
        )
        assert private_key

    def test_rsa_public_numbers_create_key(self, backend):
        public_key = RSA_KEY_1024.public_numbers.public_key(backend)
        assert public_key

        public_key = rsa.RSAPublicNumbers(n=10, e=3).public_key(backend)
        assert public_key

    def test_public_numbers_invalid_types(self):
        with pytest.raises(TypeError):
            rsa.RSAPublicNumbers(e=None, n=15)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            rsa.RSAPublicNumbers(e=1, n=None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("p", "q", "d", "dmp1", "dmq1", "iqmp", "public_numbers"),
        [
            (None, 5, 1, 1, 1, 2, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, None, 1, 1, 1, 2, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, 5, None, 1, 1, 2, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, 5, 1, None, 1, 2, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, 5, 1, 1, None, 2, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, 5, 1, 1, 1, None, rsa.RSAPublicNumbers(e=1, n=15)),
            (3, 5, 1, 1, 1, 2, None),
        ],
    )
    def test_private_numbers_invalid_types(
        self, p, q, d, dmp1, dmq1, iqmp, public_numbers
    ):
        with pytest.raises(TypeError):
            rsa.RSAPrivateNumbers(
                p=p,
                q=q,
                d=d,
                dmp1=dmp1,
                dmq1=dmq1,
                iqmp=iqmp,
                public_numbers=public_numbers,
            )

    @pytest.mark.parametrize(
        ("e", "n"),
        [
            (7, 2),  # modulus < 3
            (1, 15),  # public_exponent < 3
            (17, 15),  # public_exponent > modulus
            (14, 15),  # public_exponent not odd
        ],
    )
    def test_invalid_public_numbers_argument_values(self, e, n, backend):
        # Start with public_exponent=7, modulus=15. Then change one value at a
        # time to test the bounds.

        with pytest.raises(ValueError):
            rsa.RSAPublicNumbers(e=e, n=n).public_key(backend)

    @pytest.mark.parametrize(
        ("p", "q", "d", "dmp1", "dmq1", "iqmp", "e", "n"),
        [
            (3, 11, 3, 1, 3, 2, 7, 2),  # modulus < 3
            (3, 11, 3, 1, 3, 2, 7, 35),  # modulus != p * q
            (37, 11, 3, 1, 3, 2, 7, 33),  # p > modulus
            (3, 37, 3, 1, 3, 2, 7, 33),  # q > modulus
            (3, 11, 3, 35, 3, 2, 7, 33),  # dmp1 > modulus
            (3, 11, 3, 1, 35, 2, 7, 33),  # dmq1 > modulus
            (3, 11, 3, 1, 3, 35, 7, 33),  # iqmp > modulus
            (3, 11, 37, 1, 3, 2, 7, 33),  # d > modulus
            (3, 11, 3, 1, 3, 2, 1, 33),  # public_exponent < 3
            (3, 11, 3, 1, 3, 35, 65537, 33),  # public_exponent > modulus
            (3, 11, 3, 1, 3, 2, 6, 33),  # public_exponent is not odd
            (3, 11, 3, 2, 3, 2, 7, 33),  # dmp1 is not odd
            (3, 11, 3, 1, 4, 2, 7, 33),  # dmq1 is not odd
        ],
    )
    def test_invalid_private_numbers_argument_values(
        self, p, q, d, dmp1, dmq1, iqmp, e, n, backend
    ):
        # Start with p=3, q=11, private_exponent=3, public_exponent=7,
        # modulus=33, dmp1=1, dmq1=3, iqmp=2. Then change one value at
        # a time to test the bounds.

        with pytest.raises(ValueError):
            rsa.RSAPrivateNumbers(
                p=p,
                q=q,
                d=d,
                dmp1=dmp1,
                dmq1=dmq1,
                iqmp=iqmp,
                public_numbers=rsa.RSAPublicNumbers(e=e, n=n),
            ).private_key(backend)

    def test_public_number_repr(self):
        num = RSAPublicNumbers(1, 1)
        assert repr(num) == "<RSAPublicNumbers(e=1, n=1)>"


class TestRSANumbersEquality:
    def test_public_numbers_eq(self):
        num = RSAPublicNumbers(1, 2)
        num2 = RSAPublicNumbers(1, 2)
        assert num == num2

    def test_public_numbers_ne(self):
        num = RSAPublicNumbers(1, 2)
        assert num != RSAPublicNumbers(2, 2)
        assert num != RSAPublicNumbers(1, 3)
        assert num != object()

    def test_private_numbers_eq(self):
        pub = RSAPublicNumbers(1, 2)
        num = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, pub)
        pub2 = RSAPublicNumbers(1, 2)
        num2 = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, pub2)
        assert num == num2

    def test_private_numbers_ne(self):
        pub = RSAPublicNumbers(1, 2)
        num = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, pub)
        assert num != RSAPrivateNumbers(
            1, 2, 3, 4, 5, 7, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 2, 3, 4, 4, 6, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 2, 3, 5, 5, 6, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 2, 4, 4, 5, 6, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 3, 3, 4, 5, 6, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            2, 2, 3, 4, 5, 6, RSAPublicNumbers(1, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 2, 3, 4, 5, 6, RSAPublicNumbers(2, 2)
        )
        assert num != RSAPrivateNumbers(
            1, 2, 3, 4, 5, 6, RSAPublicNumbers(1, 3)
        )
        assert num != object()

    def test_public_numbers_hash(self):
        pub1 = RSAPublicNumbers(3, 17)
        pub2 = RSAPublicNumbers(3, 17)
        pub3 = RSAPublicNumbers(7, 21)

        assert hash(pub1) == hash(pub2)
        assert hash(pub1) != hash(pub3)

    def test_private_numbers_hash(self):
        priv1 = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, RSAPublicNumbers(1, 2))
        priv2 = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, RSAPublicNumbers(1, 2))
        priv3 = RSAPrivateNumbers(1, 2, 3, 4, 5, 6, RSAPublicNumbers(1, 3))

        assert hash(priv1) == hash(priv2)
        assert hash(priv1) != hash(priv3)


class TestRSAPrimeFactorRecovery:
    def test_recover_prime_factors(self, subtests):
        for key in [
            RSA_KEY_1024,
            RSA_KEY_1025,
            RSA_KEY_1026,
            RSA_KEY_1027,
            RSA_KEY_1028,
            RSA_KEY_1029,
            RSA_KEY_1030,
            RSA_KEY_1031,
            RSA_KEY_1536,
            RSA_KEY_2048,
        ]:
            with subtests.test():
                p, q = rsa.rsa_recover_prime_factors(
                    key.public_numbers.n,
                    key.public_numbers.e,
                    key.d,
                )
                # Unfortunately there is no convention on which prime should be
                # p and which one q. The function we use always makes p > q,
                # but the NIST vectors are not so consistent. Accordingly, we
                # verify we've recovered the proper (p, q) by sorting them and
                # asserting on that.
                assert sorted([p, q]) == sorted([key.p, key.q])
                assert p > q

    def test_invalid_recover_prime_factors(self):
        with pytest.raises(ValueError):
            rsa.rsa_recover_prime_factors(34, 3, 7)


class TestRSAPrivateKeySerialization:
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
    def test_private_bytes_encrypted_pem(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend, fmt, password
    ):
        skip_fips_traditional_openssl(backend, fmt)
        key = rsa_key_2048
        serialized = key.private_bytes(
            serialization.Encoding.PEM,
            fmt,
            serialization.BestAvailableEncryption(password),
        )
        loaded_key = serialization.load_pem_private_key(
            serialized, password, backend, unsafe_skip_rsa_key_validation=True
        )
        assert isinstance(loaded_key, rsa.RSAPrivateKey)
        loaded_priv_num = loaded_key.private_numbers()
        priv_num = key.private_numbers()
        assert loaded_priv_num == priv_num

    @pytest.mark.supported(
        only_if=lambda backend: backend._fips_enabled,
        skip_message="Requires FIPS",
    )
    def test_traditional_serialization_fips(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.BestAvailableEncryption(b"password"),
            )

    @pytest.mark.parametrize(
        ("encoding", "fmt"),
        [
            (serialization.Encoding.Raw, serialization.PrivateFormat.PKCS8),
            (serialization.Encoding.DER, serialization.PrivateFormat.Raw),
            (serialization.Encoding.Raw, serialization.PrivateFormat.Raw),
            (serialization.Encoding.X962, serialization.PrivateFormat.PKCS8),
        ],
    )
    def test_private_bytes_rejects_invalid(
        self, rsa_key_2048: rsa.RSAPrivateKey, encoding, fmt, backend
    ):
        key = rsa_key_2048
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
    def test_private_bytes_encrypted_der(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend, fmt, password
    ):
        key = rsa_key_2048
        serialized = key.private_bytes(
            serialization.Encoding.DER,
            fmt,
            serialization.BestAvailableEncryption(password),
        )
        loaded_key = serialization.load_der_private_key(
            serialized, password, backend, unsafe_skip_rsa_key_validation=True
        )
        assert isinstance(loaded_key, rsa.RSAPrivateKey)
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
        self,
        rsa_key_2048: rsa.RSAPrivateKey,
        backend,
        encoding,
        fmt,
        loader_func,
    ):
        key = rsa_key_2048
        serialized = key.private_bytes(
            encoding, fmt, serialization.NoEncryption()
        )
        loaded_key = loader_func(
            serialized, None, backend, unsafe_skip_rsa_key_validation=True
        )
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
                    "testrsa.pem",
                ),
                serialization.Encoding.PEM,
                serialization.load_pem_private_key,
            ],
            [
                os.path.join("asymmetric", "DER_Serialization", "testrsa.der"),
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
        key = loader_func(
            key_bytes, None, backend, unsafe_skip_rsa_key_validation=True
        )
        serialized = key.private_bytes(
            encoding,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        assert serialized == key_bytes

    def test_private_bytes_traditional_der_encrypted_invalid(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.DER,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.BestAvailableEncryption(b"password"),
            )

    def test_private_bytes_invalid_encoding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(TypeError):
            key.private_bytes(
                "notencoding",  # type: ignore[arg-type]
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_format(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                "invalidformat",  # type: ignore[arg-type]
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_encryption_algorithm(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                "notanencalg",  # type: ignore[arg-type]
            )

    def test_private_bytes_unsupported_encryption_type(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                DummyKeySerializationEncryption(),
            )


class TestRSAPEMPublicKeySerialization:
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "encoding", "format"),
        [
            (
                os.path.join("asymmetric", "public", "PKCS1", "rsa.pub.pem"),
                serialization.load_pem_public_key,
                serialization.Encoding.PEM,
                serialization.PublicFormat.PKCS1,
            ),
            (
                os.path.join("asymmetric", "public", "PKCS1", "rsa.pub.der"),
                serialization.load_der_public_key,
                serialization.Encoding.DER,
                serialization.PublicFormat.PKCS1,
            ),
            (
                os.path.join("asymmetric", "PKCS8", "unenc-rsa-pkcs8.pub.pem"),
                serialization.load_pem_public_key,
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
            (
                os.path.join(
                    "asymmetric",
                    "DER_Serialization",
                    "unenc-rsa-pkcs8.pub.der",
                ),
                serialization.load_der_public_key,
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            ),
        ],
    )
    def test_public_bytes_match(
        self, key_path, loader_func, encoding, format, backend
    ):
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        key = loader_func(key_bytes, backend)
        serialized = key.public_bytes(encoding, format)
        assert serialized == key_bytes

    def test_public_bytes_openssh(self, backend):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "public", "PKCS1", "rsa.pub.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = serialization.load_pem_public_key(key_bytes, backend)

        ssh_bytes = key.public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
        assert ssh_bytes == (
            b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC7JHoJfg6yNzLMOWet8Z49a4KD"
            b"0dCspMAYvo2YAMB7/wdEycocujbhJ2n/seONi+5XqTqqFkM5VBl8rmkkFPZk/7x0"
            b"xmdsTPECSWnHK+HhoaNDFPR3j8jQhVo1laxiqcEhAHegi5cwtFosuJAvSKAFKEvy"
            b"D43si00DQnXWrYHAEQ=="
        )

        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.OpenSSH
            )
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.OpenSSH
            )
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.OpenSSH,
                serialization.PublicFormat.PKCS1,
            )
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.OpenSSH,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )

    def test_public_bytes_invalid_encoding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048.public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                "notencoding",  # type: ignore[arg-type]
                serialization.PublicFormat.PKCS1,
            )

    def test_public_bytes_invalid_format(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        key = rsa_key_2048.public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                serialization.Encoding.PEM,
                "invalidformat",  # type: ignore[arg-type]
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
    def test_public_bytes_rejects_invalid(
        self, rsa_key_2048: rsa.RSAPrivateKey, encoding, fmt, backend
    ):
        key = rsa_key_2048.public_key()
        with pytest.raises(ValueError):
            key.public_bytes(encoding, fmt)

    def test_public_key_equality(self, rsa_key_2048: rsa.RSAPrivateKey):
        key1 = rsa_key_2048.public_key()
        key2 = RSA_KEY_2048.private_key(
            unsafe_skip_rsa_key_validation=True
        ).public_key()
        key3 = RSA_KEY_2048_ALT.private_key(
            unsafe_skip_rsa_key_validation=True
        ).public_key()
        assert key1 == key2
        assert key1 != key3
        assert key1 != object()
        with pytest.raises(TypeError):
            key1 < key2  # type: ignore[operator]

    def test_public_key_copy(self, rsa_key_2048: rsa.RSAPrivateKey):
        key1 = rsa_key_2048.public_key()
        key2 = copy.copy(key1)

        assert key1 == key2
