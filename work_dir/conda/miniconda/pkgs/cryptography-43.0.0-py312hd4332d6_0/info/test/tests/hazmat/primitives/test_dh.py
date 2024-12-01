# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import copy
import itertools
import os
import typing

import pytest

from cryptography.hazmat.bindings._rust import openssl as rust_openssl
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dh

from ...doubles import DummyKeySerializationEncryption
from ...utils import load_nist_vectors, load_vectors_from_file
from .fixtures_dh import FFDH3072_P

# RFC 3526
P_1536 = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA237327FFFFFFFFFFFFFFFF",
    16,
)


def _skip_dhx_unsupported(backend, is_dhx):
    if not is_dhx:
        return
    if not backend.dh_x942_serialization_supported():
        pytest.skip("DH x9.42 serialization is not supported")


def test_dh_parameternumbers():
    params = dh.DHParameterNumbers(P_1536, 2)

    assert params.p == P_1536
    assert params.g == 2

    with pytest.raises(TypeError):
        dh.DHParameterNumbers(None, 2)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        dh.DHParameterNumbers(P_1536, None)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        dh.DHParameterNumbers(None, None)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        dh.DHParameterNumbers(P_1536, 1)

    # p too small
    with pytest.raises(ValueError):
        dh.DHParameterNumbers(65537, 2)

    params = dh.DHParameterNumbers(P_1536, 7, 1245)

    assert params.p == P_1536
    assert params.g == 7
    assert params.q == 1245

    with pytest.raises(TypeError):
        dh.DHParameterNumbers(P_1536, 2, "hello")  # type: ignore[arg-type]


def test_dh_numbers():
    params = dh.DHParameterNumbers(P_1536, 2)

    public = dh.DHPublicNumbers(1, params)

    assert public.parameter_numbers is params
    assert public.y == 1

    with pytest.raises(TypeError):
        dh.DHPublicNumbers(1, None)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        dh.DHPublicNumbers(None, params)  # type:ignore[arg-type]

    private = dh.DHPrivateNumbers(1, public)

    assert private.public_numbers is public
    assert private.x == 1

    with pytest.raises(TypeError):
        dh.DHPrivateNumbers(1, None)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        dh.DHPrivateNumbers(None, public)  # type:ignore[arg-type]


def test_dh_parameter_numbers_equality():
    assert dh.DHParameterNumbers(P_1536, 2) == dh.DHParameterNumbers(P_1536, 2)
    assert dh.DHParameterNumbers(P_1536, 7, 12345) == dh.DHParameterNumbers(
        P_1536, 7, 12345
    )
    assert dh.DHParameterNumbers(P_1536 + 2, 2) != dh.DHParameterNumbers(
        P_1536, 2
    )
    assert dh.DHParameterNumbers(P_1536, 2, 123) != dh.DHParameterNumbers(
        P_1536, 2, 456
    )
    assert dh.DHParameterNumbers(P_1536, 2, 123) != dh.DHParameterNumbers(
        P_1536, 2
    )
    assert dh.DHParameterNumbers(P_1536, 5) != dh.DHParameterNumbers(P_1536, 2)
    assert dh.DHParameterNumbers(P_1536, 2) != object()


def test_dh_private_numbers_equality():
    params = dh.DHParameterNumbers(P_1536, 2)
    public = dh.DHPublicNumbers(1, params)
    private = dh.DHPrivateNumbers(2, public)

    assert private == dh.DHPrivateNumbers(2, public)
    assert private != dh.DHPrivateNumbers(0, public)
    assert private != dh.DHPrivateNumbers(2, dh.DHPublicNumbers(0, params))
    assert private != dh.DHPrivateNumbers(
        2, dh.DHPublicNumbers(1, dh.DHParameterNumbers(P_1536, 5))
    )
    assert private != object()


def test_dh_public_numbers_equality():
    params = dh.DHParameterNumbers(P_1536, 2)
    public = dh.DHPublicNumbers(1, params)

    assert public == dh.DHPublicNumbers(1, params)
    assert public != dh.DHPublicNumbers(0, params)
    assert public != dh.DHPublicNumbers(1, dh.DHParameterNumbers(P_1536, 5))
    assert public != object()


@pytest.mark.supported(
    only_if=lambda backend: backend.dh_supported(),
    skip_message="DH not supported",
)
class TestDH:
    def test_small_key_generate_dh(self, backend):
        with pytest.raises(ValueError):
            dh.generate_parameters(2, 511, backend)

    def test_unsupported_generator_generate_dh(self, backend):
        with pytest.raises(ValueError):
            dh.generate_parameters(7, 512, backend)

    def test_large_key_generate_dh(self, backend):
        with pytest.raises(ValueError):
            dh.generate_parameters(2, 1 << 30)

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "DH", "rfc3526.txt"), load_nist_vectors
        ),
    )
    def test_dh_parameters_allows_rfc3526_groups(self, backend, vector):
        p = int.from_bytes(binascii.unhexlify(vector["p"]), "big")
        if backend._fips_enabled and p < backend._fips_dh_min_modulus:
            pytest.skip("modulus too small for FIPS mode")

        params = dh.DHParameterNumbers(p, int(vector["g"]))
        param = params.parameters(backend)
        key = param.generate_private_key()
        # In OpenSSL 3.0.0 OpenSSL maps to known groups. This results in
        # a scenario where loading a known group with p and g returns a
        # re-serialized form that has q as well (the Sophie Germain prime of
        # that group). This makes a naive comparison of the parameter numbers
        # objects fail, so we have to be a bit smarter
        serialized_params = (
            key.private_numbers().public_numbers.parameter_numbers
        )
        if serialized_params.q is None:
            # This is the path OpenSSL < 3.0 takes
            assert serialized_params == params
        else:
            assert serialized_params.p == params.p
            assert serialized_params.g == params.g
            # p = 2q + 1 since it is a Sophie Germain prime, so we can compute
            # what we expect OpenSSL to have done here.
            assert serialized_params.q == (params.p - 1) // 2

    @pytest.mark.skip_fips(reason="modulus too small for FIPS")
    @pytest.mark.parametrize("with_q", [False, True])
    def test_convert_to_numbers(self, backend, with_q):
        if with_q:
            vector = load_vectors_from_file(
                os.path.join("asymmetric", "DH", "RFC5114.txt"),
                load_nist_vectors,
            )[0]
            p = int(vector["p"], 16)
            g = int(vector["g"], 16)
            q: typing.Optional[int] = int(vector["q"], 16)
        else:
            parameters = dh.generate_parameters(2, 512).generate_private_key()

            private = parameters.private_numbers()

            p = private.public_numbers.parameter_numbers.p
            g = private.public_numbers.parameter_numbers.g
            q = None

        params = dh.DHParameterNumbers(p, g, q)
        public = dh.DHPublicNumbers(1, params)
        private = dh.DHPrivateNumbers(2, public)

        deserialized_params = params.parameters(backend)
        deserialized_public = public.public_key(backend)
        deserialized_private = private.private_key(backend)

        assert isinstance(deserialized_params, dh.DHParameters)
        assert isinstance(deserialized_public, dh.DHPublicKey)
        assert isinstance(deserialized_private, dh.DHPrivateKey)

    @pytest.mark.skip_fips(reason="FIPS requires specific parameters")
    def test_numbers_unsupported_parameters(self, backend):
        # p is set to P_1536 + 1 because when calling private_key we want it to
        # fail the DH_check call OpenSSL does, but we specifically want it to
        # fail such that we don't get a DH_NOT_SUITABLE_GENERATOR. We can cause
        # this by making sure p is not prime.
        params = dh.DHParameterNumbers(P_1536 + 1, 2)
        public = dh.DHPublicNumbers(1, params)
        private = dh.DHPrivateNumbers(2, public)

        with pytest.raises(ValueError):
            private.private_key(backend)

    @pytest.mark.skip_fips(reason="FIPS requires key size >= 2048")
    @pytest.mark.parametrize("with_q", [False, True])
    def test_generate_dh(self, backend, with_q):
        if with_q:
            vector = load_vectors_from_file(
                os.path.join("asymmetric", "DH", "RFC5114.txt"),
                load_nist_vectors,
            )[0]
            p = int(vector["p"], 16)
            g = int(vector["g"], 16)
            q = int(vector["q"], 16)
            parameters = dh.DHParameterNumbers(p, g, q).parameters(backend)
            key_size = 1024
        else:
            generator = 2
            key_size = 512

            parameters = dh.generate_parameters(generator, key_size, backend)
        assert isinstance(parameters, dh.DHParameters)

        key = parameters.generate_private_key()
        assert isinstance(key, dh.DHPrivateKey)
        assert key.key_size == key_size

        public = key.public_key()
        assert isinstance(public, dh.DHPublicKey)
        assert public.key_size == key_size

        assert isinstance(parameters, dh.DHParameters)
        parameter_numbers = parameters.parameter_numbers()
        assert isinstance(parameter_numbers, dh.DHParameterNumbers)
        assert parameter_numbers.p.bit_length() == key_size

        assert isinstance(public, dh.DHPublicKey)
        assert isinstance(public.public_numbers(), dh.DHPublicNumbers)
        assert isinstance(public.parameters(), dh.DHParameters)

        assert isinstance(key, dh.DHPrivateKey)
        assert isinstance(key.private_numbers(), dh.DHPrivateNumbers)
        assert isinstance(key.parameters(), dh.DHParameters)

    def test_exchange_wrong_type(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key1 = parameters.generate_private_key()
        with pytest.raises(TypeError):
            key1.exchange(b"invalidtype")  # type: ignore[arg-type]

    def test_exchange(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        assert isinstance(parameters, dh.DHParameters)

        key1 = parameters.generate_private_key()
        key2 = parameters.generate_private_key()

        symkey1 = key1.exchange(key2.public_key())
        assert symkey1
        assert len(symkey1) == 3072 // 8

        symkey2 = key2.exchange(key1.public_key())
        assert symkey1 == symkey2

    def test_exchange_algorithm(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key1 = parameters.generate_private_key()
        key2 = parameters.generate_private_key()

        shared_key_bytes = key2.exchange(key1.public_key())
        symkey = int.from_bytes(shared_key_bytes, "big")

        symkey_manual = pow(
            key1.public_key().public_numbers().y,
            key2.private_numbers().x,
            parameters.parameter_numbers().p,
        )

        assert symkey == symkey_manual

    @pytest.mark.skip_fips(reason="key_size too small for FIPS")
    def test_symmetric_key_padding(self, backend):
        """
        This test has specific parameters that produce a symmetric key
        In length 63 bytes instead 64. We make sure here that we add
        padding to the key.
        """
        p = int(
            "11859949538425015739337467917303613431031019140213666"
            "129025407300654026585086345323066284800963463204246390"
            "256567934582260424238844463330887962689642467123"
        )
        g = 2
        y = int(
            "32155788395534640648739966373159697798396966919821525"
            "72238852825117261342483718574508213761865276905503199"
            "969908098203345481366464874759377454476688391248"
        )
        x = int(
            "409364065449673443397833358558926598469347813468816037"
            "268451847116982490733450463194921405069999008617231539"
            "7147035896687401350877308899732826446337707128"
        )
        parameters = dh.DHParameterNumbers(p, g)
        public = dh.DHPublicNumbers(y, parameters)
        private = dh.DHPrivateNumbers(x, public)
        key = private.private_key(backend)
        symkey = key.exchange(public.public_key(backend))
        assert len(symkey) == 512 // 8
        assert symkey[:1] == b"\x00"

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "DH", "bad_exchange.txt"),
            load_nist_vectors,
        ),
    )
    def test_bad_exchange(self, backend, vector):
        if (
            backend._fips_enabled
            and int(vector["p1"]) < backend._fips_dh_min_modulus
        ):
            pytest.skip("modulus too small for FIPS mode")
        parameters1 = dh.DHParameterNumbers(
            int(vector["p1"]), int(vector["g"])
        )
        public1 = dh.DHPublicNumbers(int(vector["y1"]), parameters1)
        private1 = dh.DHPrivateNumbers(int(vector["x1"]), public1)
        key1 = private1.private_key(backend)
        pub_key1 = key1.public_key()

        parameters2 = dh.DHParameterNumbers(
            int(vector["p2"]), int(vector["g"])
        )
        public2 = dh.DHPublicNumbers(int(vector["y2"]), parameters2)
        private2 = dh.DHPrivateNumbers(int(vector["x2"]), public2)
        key2 = private2.private_key(backend)
        pub_key2 = key2.public_key()

        with pytest.raises(ValueError):
            key1.exchange(pub_key2)

        with pytest.raises(ValueError):
            key2.exchange(pub_key1)

    @pytest.mark.skip_fips(reason="key_size too small for FIPS")
    @pytest.mark.supported(
        only_if=lambda backend: (
            not rust_openssl.CRYPTOGRAPHY_OPENSSL_300_OR_GREATER
        ),
        skip_message="256-bit DH keys are not supported in OpenSSL 3.0.0+",
    )
    def test_load_256bit_key_from_pkcs8(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dh_key_256.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = serialization.load_pem_private_key(data, None, backend)
        assert isinstance(key, dh.DHPrivateKey)
        assert key.key_size == 256

    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "DH", "vec.txt"), load_nist_vectors
        ),
    )
    def test_dh_vectors(self, backend, vector):
        if (
            backend._fips_enabled
            and int(vector["p"]) < backend._fips_dh_min_modulus
        ):
            pytest.skip("modulus too small for FIPS mode")

        if int(vector["p"]).bit_length() < 512:
            pytest.skip("DH keys less than 512 bits are unsupported")

        parameters = dh.DHParameterNumbers(int(vector["p"]), int(vector["g"]))
        public = dh.DHPublicNumbers(int(vector["y"]), parameters)
        private = dh.DHPrivateNumbers(int(vector["x"]), public)
        key = private.private_key(backend)
        symkey = key.exchange(public.public_key(backend))

        assert int.from_bytes(symkey, "big") == int(vector["k"], 16)

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    @pytest.mark.parametrize(
        "vector",
        load_vectors_from_file(
            os.path.join("asymmetric", "DH", "RFC5114.txt"), load_nist_vectors
        ),
    )
    def test_dh_vectors_with_q(self, backend, vector):
        parameters = dh.DHParameterNumbers(
            int(vector["p"], 16), int(vector["g"], 16), int(vector["q"], 16)
        )
        public1 = dh.DHPublicNumbers(int(vector["ystatcavs"], 16), parameters)
        private1 = dh.DHPrivateNumbers(int(vector["xstatcavs"], 16), public1)
        public2 = dh.DHPublicNumbers(int(vector["ystatiut"], 16), parameters)
        private2 = dh.DHPrivateNumbers(int(vector["xstatiut"], 16), public2)
        key1 = private1.private_key(backend)
        key2 = private2.private_key(backend)
        symkey1 = key1.exchange(public2.public_key(backend))
        symkey2 = key2.exchange(public1.public_key(backend))

        assert int.from_bytes(symkey1, "big") == int(vector["z"], 16)
        assert int.from_bytes(symkey2, "big") == int(vector["z"], 16)

    def test_exchange_old_key(self, backend):
        k = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhpub_cryptography_old.pem"),
            lambda f: serialization.load_pem_public_key(f.read()),
            mode="rb",
        )
        assert isinstance(k, dh.DHPublicKey)
        # Ensure this doesn't raise.
        k.parameters().generate_private_key().exchange(k)

    def test_public_key_equality(self, backend):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhpub.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key_bytes_2 = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhpub_rfc5114_2.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key1 = serialization.load_pem_public_key(key_bytes)
        key2 = serialization.load_pem_public_key(key_bytes)
        key3 = serialization.load_pem_public_key(key_bytes_2)
        assert key1 == key2
        assert key1 != key3
        assert key1 != object()

        with pytest.raises(TypeError):
            key1 < key2  # type: ignore[operator]

    def test_public_key_copy(self):
        key_bytes = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhpub.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key1 = serialization.load_pem_public_key(key_bytes)
        key2 = copy.copy(key1)

        assert key1 == key2


@pytest.mark.supported(
    only_if=lambda backend: backend.dh_supported(),
    skip_message="DH not supported",
)
class TestDHPrivateKeySerialization:
    @pytest.mark.parametrize(
        ("encoding", "loader_func"),
        [
            [serialization.Encoding.PEM, serialization.load_pem_private_key],
            [serialization.Encoding.DER, serialization.load_der_private_key],
        ],
    )
    def test_private_bytes_unencrypted(self, backend, encoding, loader_func):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        serialized = key.private_bytes(
            encoding,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        loaded_key = loader_func(serialized, None, backend)
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
        ],
    )
    def test_private_bytes_rejects_invalid(self, encoding, fmt, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(ValueError):
            key.private_bytes(encoding, fmt, serialization.NoEncryption())

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "encoding", "is_dhx"),
        [
            (
                os.path.join("asymmetric", "DH", "dhkey.pem"),
                serialization.load_pem_private_key,
                serialization.Encoding.PEM,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey.der"),
                serialization.load_der_private_key,
                serialization.Encoding.DER,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.pem"),
                serialization.load_pem_private_key,
                serialization.Encoding.PEM,
                True,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.der"),
                serialization.load_der_private_key,
                serialization.Encoding.DER,
                True,
            ),
        ],
    )
    def test_private_bytes_match(
        self, key_path, loader_func, encoding, is_dhx, backend
    ):
        _skip_dhx_unsupported(backend, is_dhx)
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        key = loader_func(key_bytes, None, backend)
        serialized = key.private_bytes(
            encoding,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        assert serialized == key_bytes

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "vec_path", "is_dhx"),
        [
            (
                os.path.join("asymmetric", "DH", "dhkey.pem"),
                serialization.load_pem_private_key,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey.der"),
                serialization.load_der_private_key,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.pem"),
                serialization.load_pem_private_key,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
                True,
            ),
            (
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.der"),
                serialization.load_der_private_key,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
                True,
            ),
        ],
    )
    def test_private_bytes_values(
        self, key_path, loader_func, vec_path, is_dhx, backend
    ):
        _skip_dhx_unsupported(backend, is_dhx)
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        vec = load_vectors_from_file(vec_path, load_nist_vectors)[0]
        key = loader_func(key_bytes, None, backend)
        private_numbers = key.private_numbers()
        assert private_numbers.x == int(vec["x"], 16)
        assert private_numbers.public_numbers.y == int(vec["y"], 16)
        assert private_numbers.public_numbers.parameter_numbers.g == int(
            vec["g"], 16
        )
        assert private_numbers.public_numbers.parameter_numbers.p == int(
            vec["p"], 16
        )
        if "q" in vec:
            assert private_numbers.public_numbers.parameter_numbers.q == int(
                vec["q"], 16
            )
        else:
            assert private_numbers.public_numbers.parameter_numbers.q is None

    def test_private_bytes_traditional_openssl_invalid(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_encoding(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(TypeError):
            key.private_bytes(
                "notencoding",  # type:ignore[arg-type]
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_format(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                "invalidformat",  # type:ignore[arg-type]
                serialization.NoEncryption(),
            )

    def test_private_bytes_invalid_encryption_algorithm(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(TypeError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                "notanencalg",  # type:ignore[arg-type]
            )

    def test_private_bytes_unsupported_encryption_type(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key()
        with pytest.raises(ValueError):
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                DummyKeySerializationEncryption(),
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.dh_supported(),
    skip_message="DH not supported",
)
class TestDHPublicKeySerialization:
    @pytest.mark.parametrize(
        ("encoding", "loader_func"),
        [
            [serialization.Encoding.PEM, serialization.load_pem_public_key],
            [serialization.Encoding.DER, serialization.load_der_public_key],
        ],
    )
    def test_public_bytes(self, backend, encoding, loader_func):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key().public_key()
        serialized = key.public_bytes(
            encoding, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        loaded_key = loader_func(serialized, backend)
        loaded_pub_num = loaded_key.public_numbers()
        pub_num = key.public_numbers()

        assert loaded_pub_num.y == pub_num.y
        assert (
            loaded_pub_num.parameter_numbers.p == pub_num.parameter_numbers.p
        )
        assert (
            loaded_pub_num.parameter_numbers.g == pub_num.parameter_numbers.g
        )
        if pub_num.parameter_numbers.q and loaded_pub_num.parameter_numbers.q:
            assert (
                loaded_pub_num.parameter_numbers.q
                == pub_num.parameter_numbers.q
            )
        else:
            # When this branch becomes unreachable by coverage (when support
            # for RHEL8 is dropped), all this code can be replaced with:
            #   assert loaded_pub_num == pub_num
            assert True

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "encoding", "is_dhx"),
        [
            (
                os.path.join("asymmetric", "DH", "dhpub.pem"),
                serialization.load_pem_public_key,
                serialization.Encoding.PEM,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub.der"),
                serialization.load_der_public_key,
                serialization.Encoding.DER,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub_rfc5114_2.pem"),
                serialization.load_pem_public_key,
                serialization.Encoding.PEM,
                True,
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub_rfc5114_2.der"),
                serialization.load_der_public_key,
                serialization.Encoding.DER,
                True,
            ),
        ],
    )
    def test_public_bytes_match(
        self, key_path, loader_func, encoding, is_dhx, backend
    ):
        _skip_dhx_unsupported(backend, is_dhx)
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        pub_key = loader_func(key_bytes, backend)
        serialized = pub_key.public_bytes(
            encoding,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        assert serialized == key_bytes

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    @pytest.mark.parametrize(
        ("key_path", "loader_func", "vec_path"),
        [
            (
                os.path.join("asymmetric", "DH", "dhpub.pem"),
                serialization.load_pem_public_key,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub.der"),
                serialization.load_der_public_key,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub_rfc5114_2.pem"),
                serialization.load_pem_public_key,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhpub_rfc5114_2.der"),
                serialization.load_der_public_key,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
            ),
        ],
    )
    def test_public_bytes_values(
        self, key_path, loader_func, vec_path, backend
    ):
        key_bytes = load_vectors_from_file(
            key_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        vec = load_vectors_from_file(vec_path, load_nist_vectors)[0]
        pub_key = loader_func(key_bytes, backend)
        public_numbers = pub_key.public_numbers()
        assert public_numbers.y == int(vec["y"], 16)
        assert public_numbers.parameter_numbers.g == int(vec["g"], 16)
        assert public_numbers.parameter_numbers.p == int(vec["p"], 16)
        if "q" in vec:
            assert public_numbers.parameter_numbers.q == int(vec["q"], 16)
        else:
            assert public_numbers.parameter_numbers.q is None

    def test_public_bytes_invalid_encoding(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key().public_key()
        with pytest.raises(TypeError):
            key.public_bytes(
                "notencoding",  # type:ignore[arg-type]
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )

    def test_public_bytes_pkcs1_unsupported(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key().public_key()
        with pytest.raises(ValueError):
            key.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.PKCS1
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.dh_supported(),
    skip_message="DH not supported",
)
class TestDHParameterSerialization:
    @pytest.mark.parametrize(
        ("encoding", "loader_func"),
        [
            [serialization.Encoding.PEM, serialization.load_pem_parameters],
            [serialization.Encoding.DER, serialization.load_der_parameters],
        ],
    )
    def test_parameter_bytes(self, backend, encoding, loader_func):
        parameters = FFDH3072_P.parameters(backend)
        serialized = parameters.parameter_bytes(
            encoding, serialization.ParameterFormat.PKCS3
        )
        loaded_key = loader_func(serialized, backend)
        loaded_param_num = loaded_key.parameter_numbers()
        assert loaded_param_num == parameters.parameter_numbers()

    @pytest.mark.parametrize(
        ("param_path", "loader_func", "encoding", "is_dhx"),
        [
            (
                os.path.join("asymmetric", "DH", "dhp.pem"),
                serialization.load_pem_parameters,
                serialization.Encoding.PEM,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhp.der"),
                serialization.load_der_parameters,
                serialization.Encoding.DER,
                False,
            ),
            (
                os.path.join("asymmetric", "DH", "dhp_rfc5114_2.pem"),
                serialization.load_pem_parameters,
                serialization.Encoding.PEM,
                True,
            ),
            (
                os.path.join("asymmetric", "DH", "dhp_rfc5114_2.der"),
                serialization.load_der_parameters,
                serialization.Encoding.DER,
                True,
            ),
        ],
    )
    def test_parameter_bytes_match(
        self, param_path, loader_func, encoding, backend, is_dhx
    ):
        _skip_dhx_unsupported(backend, is_dhx)
        param_bytes = load_vectors_from_file(
            param_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        parameters = loader_func(param_bytes, backend)
        serialized = parameters.parameter_bytes(
            encoding,
            serialization.ParameterFormat.PKCS3,
        )
        assert serialized == param_bytes

    @pytest.mark.parametrize(
        ("param_path", "loader_func", "vec_path"),
        [
            (
                os.path.join("asymmetric", "DH", "dhp.pem"),
                serialization.load_pem_parameters,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhp.der"),
                serialization.load_der_parameters,
                os.path.join("asymmetric", "DH", "dhkey.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhp_rfc5114_2.pem"),
                serialization.load_pem_parameters,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
            ),
            (
                os.path.join("asymmetric", "DH", "dhp_rfc5114_2.der"),
                serialization.load_der_parameters,
                os.path.join("asymmetric", "DH", "dhkey_rfc5114_2.txt"),
            ),
        ],
    )
    def test_public_bytes_values(
        self, param_path, loader_func, vec_path, backend
    ):
        key_bytes = load_vectors_from_file(
            param_path, lambda pemfile: pemfile.read(), mode="rb"
        )
        vec = load_vectors_from_file(vec_path, load_nist_vectors)[0]
        parameters = loader_func(key_bytes, backend)
        parameter_numbers = parameters.parameter_numbers()
        assert parameter_numbers.g == int(vec["g"], 16)
        assert parameter_numbers.p == int(vec["p"], 16)
        if "q" in vec:
            assert parameter_numbers.q == int(vec["q"], 16)
        else:
            assert parameter_numbers.q is None

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
        parameters = FFDH3072_P.parameters(backend)
        key = parameters.generate_private_key().public_key()
        with pytest.raises(ValueError):
            key.public_bytes(encoding, fmt)

    def test_parameter_bytes_invalid_encoding(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        with pytest.raises(TypeError):
            parameters.parameter_bytes(
                "notencoding",  # type:ignore[arg-type]
                serialization.ParameterFormat.PKCS3,
            )

    def test_parameter_bytes_invalid_format(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        with pytest.raises(ValueError):
            parameters.parameter_bytes(
                serialization.Encoding.PEM,
                "notformat",  # type: ignore[arg-type]
            )

    def test_parameter_bytes_openssh_unsupported(self, backend):
        parameters = FFDH3072_P.parameters(backend)
        with pytest.raises(TypeError):
            parameters.parameter_bytes(
                serialization.Encoding.OpenSSH,
                serialization.ParameterFormat.PKCS3,
            )
