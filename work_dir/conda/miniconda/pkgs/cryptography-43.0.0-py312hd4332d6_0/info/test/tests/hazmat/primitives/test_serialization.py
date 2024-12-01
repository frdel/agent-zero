# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import base64
import itertools
import os
import textwrap

import pytest

from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed448,
    ed25519,
    rsa,
    x448,
    x25519,
)
from cryptography.hazmat.primitives.hashes import SHA1
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_der_parameters,
    load_der_private_key,
    load_der_public_key,
    load_pem_parameters,
    load_pem_private_key,
    load_pem_public_key,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import PBES

from ...utils import load_vectors_from_file
from .test_ec import _skip_curve_unsupported
from .test_rsa import rsa_key_2048
from .utils import _check_dsa_private_numbers, _check_rsa_private_numbers

# Make ruff happy since we're importing fixtures that pytest patches in as
# func args
__all__ = ["rsa_key_2048"]


def _skip_fips_format(key_path, password, backend):
    if backend._fips_enabled:
        if key_path[0] == "Traditional_OpenSSL_Serialization":
            pytest.skip("Traditional OpenSSL format blocked in FIPS mode")
        if (
            key_path[0] in ("PEM_Serialization", "PKCS8")
            and password is not None
        ):
            pytest.skip(
                "The encrypted PEM vectors currently have encryption "
                "that is not FIPS approved in the 3.0 provider"
            )
        if key_path[0] == "DER_Serialization" and password is not None:
            pytest.skip(
                "The encrypted PKCS8 DER vectors currently have encryption "
                "that is not FIPS approved in the 3.0 provider"
            )


class TestBufferProtocolSerialization:
    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["DER_Serialization", "enc-rsa-pkcs8.der"], bytearray(b"foobar")),
            (["DER_Serialization", "enc2-rsa-pkcs8.der"], bytearray(b"baz")),
            (["DER_Serialization", "unenc-rsa-pkcs8.der"], None),
            (["DER_Serialization", "testrsa.der"], None),
        ],
    )
    def test_load_der_rsa_private_key(self, key_path, password, backend):
        _skip_fips_format(key_path, password, backend)
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        key = load_der_private_key(
            bytearray(data), password, unsafe_skip_rsa_key_validation=True
        )
        assert key
        assert isinstance(key, rsa.RSAPrivateKey)
        _check_rsa_private_numbers(key.private_numbers())

    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (
                ["PEM_Serialization", "rsa_private_key.pem"],
                bytearray(b"123456"),
            ),
            (["PKCS8", "unenc-rsa-pkcs8.pem"], None),
            (["PKCS8", "enc-rsa-pkcs8.pem"], bytearray(b"foobar")),
            (["PKCS8", "enc2-rsa-pkcs8.pem"], bytearray(b"baz")),
            (
                ["Traditional_OpenSSL_Serialization", "key1.pem"],
                bytearray(b"123456"),
            ),
        ],
    )
    def test_load_pem_rsa_private_key(self, key_path, password, backend):
        _skip_fips_format(key_path, password, backend)
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = load_pem_private_key(
            bytearray(data), password, unsafe_skip_rsa_key_validation=True
        )
        assert key
        assert isinstance(key, rsa.RSAPrivateKey)
        _check_rsa_private_numbers(key.private_numbers())


class TestDERSerialization:
    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["DER_Serialization", "enc-rsa-pkcs8.der"], b"foobar"),
            (["DER_Serialization", "enc2-rsa-pkcs8.der"], b"baz"),
            (["DER_Serialization", "unenc-rsa-pkcs8.der"], None),
            (["DER_Serialization", "testrsa.der"], None),
        ],
    )
    def test_load_der_rsa_private_key(self, key_path, password, backend):
        _skip_fips_format(key_path, password, backend)
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda derfile: load_der_private_key(
                derfile.read(), password, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        assert key
        assert isinstance(key, rsa.RSAPrivateKey)
        _check_rsa_private_numbers(key.private_numbers())

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["DER_Serialization", "unenc-dsa-pkcs8.der"], None),
            (["DER_Serialization", "dsa.1024.der"], None),
            (["DER_Serialization", "dsa.2048.der"], None),
            (["DER_Serialization", "dsa.3072.der"], None),
        ],
    )
    def test_load_der_dsa_private_key(self, key_path, password, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda derfile: load_der_private_key(
                derfile.read(), password, backend
            ),
            mode="rb",
        )
        assert key
        assert isinstance(key, dsa.DSAPrivateKey)
        _check_dsa_private_numbers(key.private_numbers())

    @pytest.mark.parametrize(
        "key_path", [["DER_Serialization", "enc-rsa-pkcs8.der"]]
    )
    def test_password_not_bytes(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = "this password is not bytes"

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda derfile: load_der_private_key(
                    derfile.read(),
                    password,  # type:ignore[arg-type]
                    backend,
                ),
                mode="rb",
            )

    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["DER_Serialization", "ec_private_key.der"], None),
            (["DER_Serialization", "ec_private_key_encrypted.der"], b"123456"),
        ],
    )
    def test_load_der_ec_private_key(self, key_path, password, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda derfile: load_der_private_key(
                derfile.read(), password, backend
            ),
            mode="rb",
        )

        assert key
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        assert key.curve.name == "secp256r1"
        assert key.curve.key_size == 256

    @pytest.mark.parametrize(
        "key_path", [["DER_Serialization", "enc-rsa-pkcs8.der"]]
    )
    def test_wrong_password(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = b"this password is wrong"

        with pytest.raises(ValueError):
            load_vectors_from_file(
                key_file,
                lambda derfile: load_der_private_key(
                    derfile.read(), password, backend
                ),
                mode="rb",
            )

    @pytest.mark.parametrize(
        "key_path", [["DER_Serialization", "unenc-rsa-pkcs8.der"]]
    )
    def test_unused_password(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = b"this password will not be used"

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda derfile: load_der_private_key(
                    derfile.read(), password, backend
                ),
                mode="rb",
            )

    @pytest.mark.parametrize(
        ("key_path", "password"),
        itertools.product(
            [["DER_Serialization", "enc-rsa-pkcs8.der"]], [b"", None]
        ),
    )
    def test_missing_password(self, key_path, password, backend):
        key_file = os.path.join("asymmetric", *key_path)

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda derfile: load_der_private_key(
                    derfile.read(), password, backend
                ),
                mode="rb",
            )

    def test_wrong_format(self, backend):
        key_data = b"---- NOT A KEY ----\n"

        with pytest.raises(ValueError):
            load_der_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_der_private_key(
                key_data, b"this password will not be used", backend
            )

    def test_invalid_rsa_even_q(self, backend):
        data = load_vectors_from_file(
            os.path.join(
                "asymmetric", "PEM_Serialization", "rsa-bad-1025-q-is-2.pem"
            ),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        with pytest.raises(ValueError):
            load_pem_private_key(data, None)

    def test_corrupt_der_pkcs8(self, backend):
        # unenc-rsa-pkcs8 with a bunch of data missing.
        key_data = textwrap.dedent(
            """\
        MIICdQIBADALBgkqhkiG9w0BAQEEggJhMIICXQIBAAKBgQC7JHoJfg6yNzLMOWet
        8Z49a4KD0dCspMAYvo2YAMB7/wdEycocujbhJ2n/seONi+5XqTqqFkM5VBl8rmkk
        FPZk/7x0xmdsTPECSWnHK+HhoaNDFPR3j8jQhVo1laxiqcEhAHegi5cwtFosuJAv
        FiRC0Cgz+frQPFQEBsAV9RuasyQxqzxrR0Ow0qncBeGBWbYE6WZhqtcLAI895b+i
        +F4lbB4iD7T9QeIDMU/aIMXA81UO4cns1z4qDAHKeyLLrPQrJ/B4X7XC+egUWm5+
        hr1qmyAMusyXIBECQQDJWZ8piluf4yrYfsJAn6hF5T4RjTztbqvO0GVG2McHY7Uj
        NPSffhzHx/ll0fQEQji+OgydCCX8o3HZrgw5YfSJAkEA7e+rqdU5nO5ZG//PSEQb
        tjLnRiTzBH/elQhtdZ5nF7pcpNTi4k13zutmKcWW4GK75azcRGJUhu1kDM7QYAOd
        SQJAVNkYcifkvna7GmooL5VYEsQsqLbM4v0NF2TIGNfG3z1MGp75KrC5LhL97MNR
        we2p/bd2k0HYyCKUGnf2nMPDiQJBAI75pwittSoE240EobUGIDTSz8CJsXIxuDmL
        z+KOpdpPRR5TQmbEMEspjsFpFymMiuYPgmihQbO2cJl1qScY5OkCQQCJ6m5tcN8l
        Xxg/SNpjEIv+qAyUD96XVlOJlOIeLHQ8kYE0C6ZA+MsqYIzgAreJk88Yn0lU/X0/
        mu/UpE/BRZmR
        """
        ).encode()
        bad_der = base64.b64decode(b"".join(key_data.splitlines()))

        with pytest.raises(ValueError):
            load_der_private_key(bad_der, None, backend)

        with pytest.raises(ValueError):
            load_der_private_key(
                bad_der, b"this password will not be used", backend
            )

    def test_corrupt_traditional_format_der(self, backend):
        # privkey with a bunch of data missing.
        key_data = textwrap.dedent(
            """\
        MIIBPAIBAAJBAKrbeqkuRk8VcRmWFmtP+LviMB3+6dizWW3DwaffznyHGAFwUJ/I
        Tv0XtbsCyl3QoyKGhrOAy3RvPK5M38iuXT0CAwEAAQJAZ3cnzaHXM/bxGaR5CR1R
        rD1qFBAVfoQFiOH9uPJgMaoAuoQEisPHVcZDKcOv4wEg6/TInAIXBnEigtqvRzuy
        mvcpHZwQJdmdHHkGKAs37Dfxi67HbkUCIQCeZGliHXFa071Fp06ZeWlR2ADonTZz
        rJBhdTe0v5pCeQIhAIZfkiGgGBX4cIuuckzEm43g9WMUjxP/0GlK39vIyihxAiEA
        mymehFRT0MvqW5xAKAx7Pgkt8HVKwVhc2LwGKHE0DZM=
        """
        ).encode()
        bad_der = base64.b64decode(b"".join(key_data.splitlines()))

        with pytest.raises(ValueError):
            load_pem_private_key(bad_der, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(
                bad_der, b"this password will not be used", backend
            )

    @pytest.mark.parametrize(
        "key_file",
        [
            os.path.join(
                "asymmetric", "DER_Serialization", "unenc-rsa-pkcs8.pub.der"
            ),
            os.path.join(
                "asymmetric", "DER_Serialization", "rsa_public_key.der"
            ),
            os.path.join("asymmetric", "public", "PKCS1", "rsa.pub.der"),
        ],
    )
    def test_load_der_rsa_public_key(self, key_file, backend):
        key = load_vectors_from_file(
            key_file,
            lambda derfile: load_der_public_key(derfile.read(), backend),
            mode="rb",
        )
        assert key
        assert isinstance(key, rsa.RSAPublicKey)
        numbers = key.public_numbers()
        assert numbers.e == 65537

    def test_load_der_invalid_public_key(self, backend):
        with pytest.raises(ValueError):
            load_der_public_key(b"invalid data", backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    @pytest.mark.parametrize(
        "key_file",
        [
            os.path.join(
                "asymmetric", "DER_Serialization", "unenc-dsa-pkcs8.pub.der"
            ),
            os.path.join(
                "asymmetric", "DER_Serialization", "dsa_public_key.der"
            ),
        ],
    )
    def test_load_der_dsa_public_key(self, key_file, backend):
        key = load_vectors_from_file(
            key_file,
            lambda derfile: load_der_public_key(derfile.read(), backend),
            mode="rb",
        )
        assert key
        assert isinstance(key, dsa.DSAPublicKey)

    def test_load_ec_public_key(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        key = load_vectors_from_file(
            os.path.join(
                "asymmetric", "DER_Serialization", "ec_public_key.der"
            ),
            lambda derfile: load_der_public_key(derfile.read(), backend),
            mode="rb",
        )
        assert key
        assert isinstance(key, ec.EllipticCurvePublicKey)
        assert key.curve.name == "secp256r1"
        assert key.curve.key_size == 256

    @pytest.mark.supported(
        only_if=lambda backend: backend.dh_supported(),
        skip_message="DH not supported",
    )
    def test_wrong_parameters_format(self, backend):
        param_data = b"---- NOT A KEY ----\n"

        with pytest.raises(ValueError):
            load_der_parameters(param_data, backend)


class TestPEMSerialization:
    @pytest.mark.parametrize(
        ("key_file", "password"),
        [
            (["PEM_Serialization", "rsa_private_key.pem"], b"123456"),
            (["PKCS8", "unenc-rsa-pkcs8.pem"], None),
            (["PKCS8", "enc-rsa-pkcs8.pem"], b"foobar"),
            (["PKCS8", "enc2-rsa-pkcs8.pem"], b"baz"),
            (["PKCS8", "pkcs12_s2k_pem-X_9607.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9671.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9925.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9926.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9927.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9928.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9929.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9930.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9931.pem"], b"123456"),
            (["PKCS8", "pkcs12_s2k_pem-X_9932.pem"], b"123456"),
            (["Traditional_OpenSSL_Serialization", "key1.pem"], b"123456"),
            (["Traditional_OpenSSL_Serialization", "key2.pem"], b"a123456"),
            (["Traditional_OpenSSL_Serialization", "testrsa.pem"], None),
            (
                ["Traditional_OpenSSL_Serialization", "testrsa-encrypted.pem"],
                b"password",
            ),
        ],
    )
    def test_load_pem_rsa_private_key(self, key_file, password, backend):
        _skip_fips_format(key_file, password, backend)
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_file),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(),
                password,
                unsafe_skip_rsa_key_validation=True,
            ),
        )

        assert key
        assert isinstance(key, rsa.RSAPrivateKey)
        _check_rsa_private_numbers(key.private_numbers())

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["Traditional_OpenSSL_Serialization", "dsa.1024.pem"], None),
            (["Traditional_OpenSSL_Serialization", "dsa.2048.pem"], None),
            (["Traditional_OpenSSL_Serialization", "dsa.3072.pem"], None),
            (["PKCS8", "unenc-dsa-pkcs8.pem"], None),
            (["PEM_Serialization", "dsa_private_key.pem"], b"123456"),
        ],
    )
    def test_load_dsa_private_key(self, key_path, password, backend):
        _skip_fips_format(key_path, password, backend)
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(), password, backend
            ),
        )
        assert key
        assert isinstance(key, dsa.DSAPrivateKey)
        _check_dsa_private_numbers(key.private_numbers())

    @pytest.mark.parametrize(
        ("key_path", "password"),
        [
            (["PKCS8", "ec_private_key.pem"], None),
            (["PKCS8", "ec_private_key_encrypted.pem"], b"123456"),
            (["PEM_Serialization", "ec_private_key.pem"], None),
            (["PEM_Serialization", "ec_private_key_encrypted.pem"], b"123456"),
        ],
    )
    def test_load_pem_ec_private_key(self, key_path, password, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        _skip_fips_format(key_path, password, backend)
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(), password, backend
            ),
        )

        assert key
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        assert key.curve.name == "secp256r1"
        assert key.curve.key_size == 256

    @pytest.mark.parametrize(
        ("key_file"),
        [
            os.path.join("asymmetric", "PKCS8", "unenc-rsa-pkcs8.pub.pem"),
            os.path.join(
                "asymmetric", "PEM_Serialization", "rsa_public_key.pem"
            ),
            os.path.join("asymmetric", "public", "PKCS1", "rsa.pub.pem"),
            os.path.join(
                "asymmetric",
                "PEM_Serialization",
                "rsa_wrong_delimiter_public_key.pem",
            ),
        ],
    )
    def test_load_pem_rsa_public_key(self, key_file, backend):
        key = load_vectors_from_file(
            key_file,
            lambda pemfile: load_pem_public_key(
                pemfile.read().encode(), backend
            ),
        )
        assert key
        assert isinstance(key, rsa.RSAPublicKey)
        numbers = key.public_numbers()
        assert numbers.e == 65537

    def test_load_pem_public_fails_with_ec_key_with_rsa_delimiter(self):
        with pytest.raises(ValueError):
            load_vectors_from_file(
                os.path.join(
                    "asymmetric",
                    "PEM_Serialization",
                    "ec_public_key_rsa_delimiter.pem",
                ),
                lambda pemfile: load_pem_public_key(pemfile.read().encode()),
            )

    def test_load_priv_key_with_public_key_api_fails(
        self, rsa_key_2048, backend
    ):
        # In OpenSSL 3.0.x the PEM_read_bio_PUBKEY function will invoke
        # the default password callback if you pass an encrypted private
        # key. This is very, very, very bad as the default callback can
        # trigger an interactive console prompt, which will hang the
        # Python process. This test makes sure we don't do that.
        priv_key_serialized = rsa_key_2048.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            BestAvailableEncryption(b"password"),
        )
        with pytest.raises(ValueError):
            load_pem_public_key(priv_key_serialized)

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    @pytest.mark.parametrize(
        ("key_file"),
        [
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pub.pem"),
            os.path.join(
                "asymmetric", "PEM_Serialization", "dsa_public_key.pem"
            ),
        ],
    )
    def test_load_pem_dsa_public_key(self, key_file, backend):
        key = load_vectors_from_file(
            key_file,
            lambda pemfile: load_pem_public_key(
                pemfile.read().encode(), backend
            ),
        )
        assert key
        assert isinstance(key, dsa.DSAPublicKey)

    def test_load_ec_public_key(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        key = load_vectors_from_file(
            os.path.join(
                "asymmetric", "PEM_Serialization", "ec_public_key.pem"
            ),
            lambda pemfile: load_pem_public_key(
                pemfile.read().encode(), backend
            ),
        )
        assert key
        assert isinstance(key, ec.EllipticCurvePublicKey)
        assert key.curve.name == "secp256r1"
        assert key.curve.key_size == 256

    @pytest.mark.skip_fips(
        reason="Traditional OpenSSL format blocked in FIPS mode"
    )
    def test_rsa_traditional_encrypted_values(self, backend):
        pkey = load_vectors_from_file(
            os.path.join(
                "asymmetric", "Traditional_OpenSSL_Serialization", "key1.pem"
            ),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(),
                b"123456",
                unsafe_skip_rsa_key_validation=True,
            ),
        )
        assert isinstance(pkey, rsa.RSAPrivateKey)

        numbers = pkey.private_numbers()
        assert numbers.p == int(
            "fb7d316fc51531b36d93adaefaf52db6ad5beb793d37c4cf9dfc1ddd17cfbafb",
            16,
        )
        assert numbers.q == int(
            "df98264e646de9a0fbeab094e31caad5bc7adceaaae3c800ca0275dd4bb307f5",
            16,
        )
        assert numbers.d == int(
            "db4848c36f478dd5d38f35ae519643b6b810d404bcb76c00e44015e56ca1cab0"
            "7bb7ae91f6b4b43fcfc82a47d7ed55b8c575152116994c2ce5325ec24313b911",
            16,
        )
        assert numbers.dmp1 == int(
            "ce997f967192c2bcc3853186f1559fd355c190c58ddc15cbf5de9b6df954c727",
            16,
        )
        assert numbers.dmq1 == int(
            "b018a57ab20ffaa3862435445d863369b852cf70a67c55058213e3fe10e3848d",
            16,
        )
        assert numbers.iqmp == int(
            "6a8d830616924f5cf2d1bc1973f97fde6b63e052222ac7be06aa2532d10bac76",
            16,
        )
        assert numbers.public_numbers.e == 65537
        assert numbers.public_numbers.n == int(
            "dba786074f2f0350ce1d99f5aed5b520cfe0deb5429ec8f2a88563763f566e77"
            "9814b7c310e5326edae31198eed439b845dd2db99eaa60f5c16a43f4be6bcf37",
            16,
        )

    @pytest.mark.parametrize(
        "key_path",
        [
            ["Traditional_OpenSSL_Serialization", "testrsa.pem"],
            ["PKCS8", "unenc-rsa-pkcs8.pem"],
        ],
    )
    def test_unused_password(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = b"this password will not be used"

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(), password, backend
                ),
            )

    def test_invalid_encoding_with_traditional(self, backend):
        key_file = os.path.join(
            "asymmetric", "Traditional_OpenSSL_Serialization", "testrsa.pem"
        )
        key = load_vectors_from_file(
            key_file,
            lambda pemfile: load_pem_private_key(
                pemfile.read(), None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )

        for enc in (Encoding.OpenSSH, Encoding.Raw, Encoding.X962):
            with pytest.raises(ValueError):
                key.private_bytes(
                    enc, PrivateFormat.TraditionalOpenSSL, NoEncryption()
                )

    @pytest.mark.parametrize(
        "key_path",
        [
            ["Traditional_OpenSSL_Serialization", "testrsa-encrypted.pem"],
            ["PKCS8", "enc-rsa-pkcs8.pem"],
        ],
    )
    def test_password_not_bytes(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = "this password is not bytes"

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(),
                    password,  # type:ignore[arg-type]
                    backend,
                ),
            )

    @pytest.mark.parametrize(
        "key_path",
        [
            ["Traditional_OpenSSL_Serialization", "testrsa-encrypted.pem"],
            ["PKCS8", "enc-rsa-pkcs8.pem"],
        ],
    )
    def test_wrong_password(self, key_path, backend):
        key_file = os.path.join("asymmetric", *key_path)
        password = b"this password is wrong"

        with pytest.raises(ValueError):
            load_vectors_from_file(
                key_file,
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(), password, backend
                ),
            )

    @pytest.mark.parametrize(
        ("key_path", "password"),
        itertools.product(
            [
                ["Traditional_OpenSSL_Serialization", "testrsa-encrypted.pem"],
                ["PKCS8", "enc-rsa-pkcs8.pem"],
            ],
            [b"", None],
        ),
    )
    def test_missing_password(self, key_path, password, backend):
        key_file = os.path.join("asymmetric", *key_path)

        with pytest.raises(TypeError):
            load_vectors_from_file(
                key_file,
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(), password, backend
                ),
            )

    def test_wrong_private_format(self, backend):
        key_data = b"---- NOT A KEY ----\n"

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(
                key_data, b"this password will not be used", backend
            )

    def test_wrong_public_format(self, backend):
        key_data = b"---- NOT A KEY ----\n"

        with pytest.raises(ValueError):
            load_pem_public_key(key_data, backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.dh_supported(),
        skip_message="DH not supported",
    )
    def test_wrong_parameters_format(self, backend):
        param_data = b"---- NOT A KEY ----\n"

        with pytest.raises(ValueError):
            load_pem_parameters(param_data, backend)

    def test_corrupt_traditional_format(self, backend):
        # privkey.pem with a bunch of data missing.
        key_data = textwrap.dedent(
            """\
        -----BEGIN RSA PRIVATE KEY-----
        MIIBPAIBAAJBAKrbeqkuRk8VcRmWFmtP+LviMB3+6dizWW3DwaffznyHGAFwUJ/I
        Tv0XtbsCyl3QoyKGhrOAy3RvPK5M38iuXT0CAwEAAQJAZ3cnzaHXM/bxGaR5CR1R
        rD1qFBAVfoQFiOH9uPJgMaoAuoQEisPHVcZDKcOv4wEg6/TInAIXBnEigtqvRzuy
        mvcpHZwQJdmdHHkGKAs37Dfxi67HbkUCIQCeZGliHXFa071Fp06ZeWlR2ADonTZz
        rJBhdTe0v5pCeQIhAIZfkiGgGBX4cIuuckzEm43g9WMUjxP/0GlK39vIyihxAiEA
        mymehFRT0MvqW5xAKAx7Pgkt8HVKwVhc2LwGKHE0DZM=
        -----END RSA PRIVATE KEY-----
        """
        ).encode()

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(
                key_data, b"this password will not be used", backend
            )

    def test_traditional_encrypted_corrupt_format(self, backend):
        # privkey.pem with a single bit flipped
        key_data = textwrap.dedent(
            """\
        -----BEGIN RSA PRIVATE KEY-----
        Proc-Type: <,ENCRYPTED
        DEK-Info: AES-128-CBC,5E22A2BD85A653FB7A3ED20DE84F54CD

        hAqtb5ZkTMGcs4BBDQ1SKZzdQThWRDzEDxM3qBfjvYa35KxZ54aic013mW/lwj2I
        v5bbpOjrHYHNAiZYZ7RNb+ztbF6F/g5PA5g7mFwEq+LFBY0InIplYBSv9QtE+lot
        Dy4AlZa/+NzJwgdKDb+JVfk5SddyD4ywnyeORnMPy4xXKvjXwmW+iLibZVKsjIgw
        H8hSxcD+FhWyJm9h9uLtmpuqhQo0jTUYpnTezZx2xeVPB53Ev7YCxR9Nsgj5GsVf
        9Z/hqLB7IFgM3pa0z3PQeUIZF/cEf72fISWIOBwwkzVrPUkXWfbuWeJXQXSs3amE
        5A295jD9BQp9CY0nNFSsy+qiXWToq2xT3y5zVNEStmN0SCGNaIlUnJzL9IHW+oMI
        kPmXZMnAYBWeeCF1gf3J3aE5lZInegHNfEI0+J0LazC2aNU5Dg/BNqrmRqKWEIo/
        -----END RSA PRIVATE KEY-----
        """
        ).encode()

        password = b"this password is wrong"

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, password, backend)

    def test_unsupported_key_encryption(self, backend):
        key_data = textwrap.dedent(
            """\
        -----BEGIN RSA PRIVATE KEY-----
        Proc-Type: 4,ENCRYPTED
        DEK-Info: FAKE-123,5E22A2BD85A653FB7A3ED20DE84F54CD

        hAqtb5ZkTMGcs4BBDQ1SKZzdQThWRDzEDxM3qBfjvYa35KxZ54aic013mW/lwj2I
        v5bbpOjrHYHNAiZYZ7RNb+ztbF6F/g5PA5g7mFwEq+LFBY0InIplYBSv9QtE+lot
        Dy4AlZa/+NzJwgdKDb+JVfk5SddyD4ywnyeORnMPy4xXKvjXwmW+iLibZVKsjIgw
        H8hSxcD+FhWyJm9h9uLtmpuqhQo0jTUYpnTezZx2xeVPB53Ev7YCxR9Nsgj5GsVf
        9Z/hqLB7IFgM3pa0z3PQeUIZF/cEf72fISWIOBwwkzVrPUkXWfbuWeJXQXSs3amE
        5A295jD9BQp9CY0nNFSsy+qiXWToq2xT3y5zVNEStmN0SCGNaIlUnJzL9IHW+oMI
        kPmXZMnAYBWeeCF1gf3J3aE5lZInegHNfEI0+J0LazC2aNU5Dg/BNqrmRqKWEIo/
        -----END RSA PRIVATE KEY-----
        """
        ).encode()

        password = b"password"

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, password, backend)

    def test_corrupt_pkcs8_format(self, backend):
        # unenc-rsa-pkcs8.pem with a bunch of data missing.
        key_data = textwrap.dedent(
            """\
        -----BEGIN PRIVATE KEY-----
        MIICdQIBADALBgkqhkiG9w0BAQEEggJhMIICXQIBAAKBgQC7JHoJfg6yNzLMOWet
        8Z49a4KD0dCspMAYvo2YAMB7/wdEycocujbhJ2n/seONi+5XqTqqFkM5VBl8rmkk
        FPZk/7x0xmdsTPECSWnHK+HhoaNDFPR3j8jQhVo1laxiqcEhAHegi5cwtFosuJAv
        FiRC0Cgz+frQPFQEBsAV9RuasyQxqzxrR0Ow0qncBeGBWbYE6WZhqtcLAI895b+i
        +F4lbB4iD7T9QeIDMU/aIMXA81UO4cns1z4qDAHKeyLLrPQrJ/B4X7XC+egUWm5+
        hr1qmyAMusyXIBECQQDJWZ8piluf4yrYfsJAn6hF5T4RjTztbqvO0GVG2McHY7Uj
        NPSffhzHx/ll0fQEQji+OgydCCX8o3HZrgw5YfSJAkEA7e+rqdU5nO5ZG//PSEQb
        tjLnRiTzBH/elQhtdZ5nF7pcpNTi4k13zutmKcWW4GK75azcRGJUhu1kDM7QYAOd
        SQJAVNkYcifkvna7GmooL5VYEsQsqLbM4v0NF2TIGNfG3z1MGp75KrC5LhL97MNR
        we2p/bd2k0HYyCKUGnf2nMPDiQJBAI75pwittSoE240EobUGIDTSz8CJsXIxuDmL
        z+KOpdpPRR5TQmbEMEspjsFpFymMiuYPgmihQbO2cJl1qScY5OkCQQCJ6m5tcN8l
        Xxg/SNpjEIv+qAyUD96XVlOJlOIeLHQ8kYE0C6ZA+MsqYIzgAreJk88Yn0lU/X0/
        mu/UpE/BRZmR
        -----END PRIVATE KEY-----
        """
        ).encode()

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(
                key_data, b"this password will not be used", backend
            )

    def test_pks8_encrypted_corrupt_format(self, backend):
        # enc-rsa-pkcs8.pem with some bits flipped.
        key_data = textwrap.dedent(
            """\
        -----BEGIN ENCRYPTED PRIVATE KEY-----
        MIICojAcBgoqhkiG9w0BDAEDMA4ECHK0M0+QuEL9AgIBIcSCAoDRq+KRY+0XP0tO
        lwBTzViiXSXoyNnKAZKt5r5K/fGNntv22g/1s/ZNCetrqsJDC5eMUPPacz06jFq/
        Ipsep4/OgjQ9UAOzXNrWEoNyrHnWDo7usgD3CW0mKyqER4+wG0adVMbt3N+CJHGB
        85jzRmQTfkdx1rSWeSx+XyswHn8ER4+hQ+omKWMVm7AFkjjmP/KnhUnLT98J8rhU
        ArQoFPHz/6HVkypFccNaPPNg6IA4aS2A+TU9vJYOaXSVfFB2yf99hfYYzC+ukmuU
        5Lun0cysK5s/5uSwDueUmDQKspnaNyiaMGDxvw8hilJc7vg0fGObfnbIpizhxJwq
        gKBfR7Zt0Hv8OYi1He4MehfMGdbHskztF+yQ40LplBGXQrvAqpU4zShga1BoQ98T
        0ekbBmqj7hg47VFsppXR7DKhx7G7rpMmdKbFhAZVCjae7rRGpUtD52cpFdPhMyAX
        huhMkoczwUW8B/rM4272lkHo6Br0yk/TQfTEGkvryflNVu6lniPTV151WV5U1M3o
        3G3a44eDyt7Ln+WSOpWtbPQMTrpKhur6WXgJvrpa/m02oOGdvOlDsoOCgavgQMWg
        7xKKL7620pHl7p7f/8tlE8q6vLXVvyNtAOgt/JAr2rgvrHaZSzDE0DwgCjBXEm+7
        cVMVNkHod7bLQefVanVtWqPzbmr8f7gKeuGwWSG9oew/lN2hxcLEPJHAQlnLgx3P
        0GdGjK9NvwA0EP2gYIeE4+UtSder7xQ7bVh25VB20R4TTIIs4aXXCVOoQPagnzaT
        6JLgl8FrvdfjHwIvmSOO1YMNmILBq000Q8WDqyErBDs4hsvtO6VQ4LeqJj6gClX3
        qeJNaJFu
        -----END ENCRYPTED PRIVATE KEY-----
        """
        ).encode()

        password = b"this password is wrong"

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, None, backend)

        with pytest.raises(ValueError):
            load_pem_private_key(key_data, password, backend)

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    def test_rsa_pkcs8_encrypted_values(self, backend):
        pkey = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "enc-rsa-pkcs8.pem"),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(),
                b"foobar",
                unsafe_skip_rsa_key_validation=True,
            ),
        )
        assert isinstance(pkey, rsa.RSAPrivateKey)

        numbers = pkey.private_numbers()

        assert numbers.public_numbers.n == int(
            "00beec64d6db5760ac2fd4c971145641b9bd7f5c56558ece608795c79807"
            "376a7fe5b19f95b35ca358ea5c8abd7ae051d49cd2f1e45969a1ae945460"
            "3c14b278664a0e414ebc8913acb6203626985525e17a600611b028542dd0"
            "562aad787fb4f1650aa318cdcff751e1b187cbf6785fbe164e9809491b95"
            "dd68480567c99b1a57",
            16,
        )

        assert numbers.public_numbers.e == 65537

        assert numbers.d == int(
            "0cfe316e9dc6b8817f4fcfd5ae38a0886f68f773b8a6db4c9e6d8703c599"
            "f3d9785c3a2c09e4c8090909fb3721e19a3009ec21221523a729265707a5"
            "8f13063671c42a4096cad378ef2510cb59e23071489d8893ac4934dd149f"
            "34f2d094bea57f1c8027c3a77248ac9b91218737d0c3c3dfa7d7829e6977"
            "cf7d995688c86c81",
            16,
        )

        assert numbers.p == int(
            "00db122ac857b2c0437d7616daa98e597bb75ca9ad3a47a70bec10c10036"
            "03328794b225c8e3eee6ffd3fd6d2253d28e071fe27d629ab072faa14377"
            "ce6118cb67",
            16,
        )

        assert numbers.q == int(
            "00df1b8aa8506fcbbbb9d00257f2975e38b33d2698fd0f37e82d7ef38c56"
            "f21b6ced63c825383782a7115cfcc093300987dbd2853b518d1c8f26382a"
            "2d2586d391",
            16,
        )

        assert numbers.dmp1 == int(
            "00be18aca13e60712fdf5daa85421eb10d86d654b269e1255656194fb0c4"
            "2dd01a1070ea12c19f5c39e09587af02f7b1a1030d016a9ffabf3b36d699"
            "ceaf38d9bf",
            16,
        )

        assert numbers.dmq1 == int(
            "71aa8978f90a0c050744b77cf1263725b203ac9f730606d8ae1d289dce4a"
            "28b8d534e9ea347aeb808c73107e583eb80c546d2bddadcdb3c82693a4c1"
            "3d863451",
            16,
        )

        assert numbers.iqmp == int(
            "136b7b1afac6e6279f71b24217b7083485a5e827d156024609dae39d48a6"
            "bdb55af2f062cc4a3b077434e6fffad5faa29a2b5dba2bed3e4621e478c0"
            "97ccfe7f",
            16,
        )

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    def test_load_pem_dsa_private_key(self, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", "PKCS8", "unenc-dsa-pkcs8.pem"),
            lambda pemfile: load_pem_private_key(
                pemfile.read().encode(), None, backend
            ),
        )
        assert key
        assert isinstance(key, dsa.DSAPrivateKey)

        params = key.parameters()
        assert isinstance(params, dsa.DSAParameters)

        num = key.private_numbers()
        pub = num.public_numbers
        parameter_numbers = pub.parameter_numbers
        assert num.x == int("00a535a8e1d0d91beafc8bee1d9b2a3a8de3311203", 16)
        assert pub.y == int(
            "2b260ea97dc6a12ae932c640e7df3d8ff04a8a05a0324f8d5f1b23f15fa1"
            "70ff3f42061124eff2586cb11b49a82dcdc1b90fc6a84fb10109cb67db5d"
            "2da971aeaf17be5e37284563e4c64d9e5fc8480258b319f0de29d54d8350"
            "70d9e287914d77df81491f4423b62da984eb3f45eb2a29fcea5dae525ac6"
            "ab6bcce04bfdf5b6",
            16,
        )

        assert parameter_numbers.p == int(
            "00aa0930cc145825221caffa28ac2894196a27833de5ec21270791689420"
            "7774a2e7b238b0d36f1b2499a2c2585083eb01432924418d867faa212dd1"
            "071d4dceb2782794ad393cc08a4d4ada7f68d6e839a5fcd34b4e402d82cb"
            "8a8cb40fec31911bf9bd360b034caacb4c5e947992573c9e90099c1b0f05"
            "940cabe5d2de49a167",
            16,
        )

        assert parameter_numbers.q == int(
            "00adc0e869b36f0ac013a681fdf4d4899d69820451", 16
        )

        assert parameter_numbers.g == int(
            "008c6b4589afa53a4d1048bfc346d1f386ca75521ccf72ddaa251286880e"
            "e13201ff48890bbfc33d79bacaec71e7a778507bd5f1a66422e39415be03"
            "e71141ba324f5b93131929182c88a9fa4062836066cebe74b5c6690c7d10"
            "1106c240ab7ebd54e4e3301fd086ce6adac922fb2713a2b0887cba13b9bc"
            "68ce5cfff241cd3246",
            16,
        )

    @pytest.mark.parametrize(
        ("key_file", "password"), [("bad-oid-dsa-key.pem", None)]
    )
    def test_load_bad_oid_key(self, key_file, password, backend):
        with pytest.raises(ValueError):
            load_vectors_from_file(
                os.path.join("asymmetric", "PKCS8", key_file),
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(), password, backend
                ),
            )

    @pytest.mark.parametrize(
        ("key_file", "password"), [("bad-encryption-oid.pem", b"password")]
    )
    def test_load_bad_encryption_oid_key(self, key_file, password, backend):
        with pytest.raises(ValueError):
            load_vectors_from_file(
                os.path.join("asymmetric", "PKCS8", key_file),
                lambda pemfile: load_pem_private_key(
                    pemfile.read().encode(), password, backend
                ),
            )


class TestKeySerializationEncryptionTypes:
    def test_non_bytes_password(self):
        with pytest.raises(ValueError):
            BestAvailableEncryption(object())  # type:ignore[arg-type]

    def test_encryption_with_zero_length_password(self):
        with pytest.raises(ValueError):
            BestAvailableEncryption(b"")


@pytest.mark.supported(
    only_if=lambda backend: backend.ed25519_supported(),
    skip_message="Requires OpenSSL with Ed25519 support",
)
class TestEd25519Serialization:
    def test_load_der_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "Ed25519", "ed25519-pkcs8-enc.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "Ed25519", "ed25519-pkcs8.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        key = load_der_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    def test_load_pem_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "Ed25519", "ed25519-pkcs8-enc.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "Ed25519", "ed25519-pkcs8.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = load_pem_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    @pytest.mark.parametrize(
        ("key_path", "encoding", "loader"),
        [
            (
                ["Ed25519", "ed25519-pub.pem"],
                Encoding.PEM,
                load_pem_public_key,
            ),
            (
                ["Ed25519", "ed25519-pub.der"],
                Encoding.DER,
                load_der_public_key,
            ),
        ],
    )
    def test_load_public_key(self, key_path, encoding, loader, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        public_key = loader(data, backend)
        assert (
            public_key.public_bytes(
                encoding, PublicFormat.SubjectPublicKeyInfo
            )
            == data
        )

    def test_openssl_serialization_unsupported(self, backend):
        key = ed25519.Ed25519PrivateKey.generate()
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.DER,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.x448_supported(),
    skip_message="Requires OpenSSL with X448 support",
)
class TestX448Serialization:
    def test_load_der_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "X448", "x448-pkcs8-enc.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "X448", "x448-pkcs8.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        key = load_der_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    def test_load_pem_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "X448", "x448-pkcs8-enc.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "X448", "x448-pkcs8.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = load_pem_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    @pytest.mark.parametrize(
        ("key_path", "encoding", "loader"),
        [
            (["X448", "x448-pub.pem"], Encoding.PEM, load_pem_public_key),
            (["X448", "x448-pub.der"], Encoding.DER, load_der_public_key),
        ],
    )
    def test_load_public_key(self, key_path, encoding, loader, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        public_key = loader(data, backend)
        assert (
            public_key.public_bytes(
                encoding, PublicFormat.SubjectPublicKeyInfo
            )
            == data
        )

    def test_openssl_serialization_unsupported(self, backend):
        key = x448.X448PrivateKey.generate()
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.DER,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )

    def test_openssh_serialization_unsupported(self, backend):
        key = x448.X448PrivateKey.generate()
        with pytest.raises(ValueError):
            key.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.x25519_supported(),
    skip_message="Requires OpenSSL with X25519 support",
)
class TestX25519Serialization:
    def test_load_der_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "X25519", "x25519-pkcs8-enc.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "X25519", "x25519-pkcs8.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        key = load_der_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    def test_load_pem_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "X25519", "x25519-pkcs8-enc.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "X25519", "x25519-pkcs8.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = load_pem_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    @pytest.mark.parametrize(
        ("key_path", "encoding", "loader"),
        [
            (["X25519", "x25519-pub.pem"], Encoding.PEM, load_pem_public_key),
            (["X25519", "x25519-pub.der"], Encoding.DER, load_der_public_key),
        ],
    )
    def test_load_public_key(self, key_path, encoding, loader, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        public_key = loader(data, backend)
        assert (
            public_key.public_bytes(
                encoding, PublicFormat.SubjectPublicKeyInfo
            )
            == data
        )

    def test_openssl_serialization_unsupported(self, backend):
        key = x25519.X25519PrivateKey.generate()
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.DER,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )

    def test_openssh_serialization_unsupported(self, backend):
        key = x25519.X25519PrivateKey.generate()
        with pytest.raises(ValueError):
            key.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.ed448_supported(),
    skip_message="Requires OpenSSL with Ed448 support",
)
class TestEd448Serialization:
    def test_load_der_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "ed448-pkcs8-enc.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "ed448-pkcs8.der"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        key = load_der_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    def test_load_pem_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "ed448-pkcs8-enc.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        unencrypted = load_vectors_from_file(
            os.path.join("asymmetric", "Ed448", "ed448-pkcs8.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        key = load_pem_private_key(data, b"password", backend)
        assert (
            key.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
            )
            == unencrypted
        )

    @pytest.mark.parametrize(
        ("key_path", "encoding", "loader"),
        [
            (["Ed448", "ed448-pub.pem"], Encoding.PEM, load_pem_public_key),
            (["Ed448", "ed448-pub.der"], Encoding.DER, load_der_public_key),
        ],
    )
    def test_load_public_key(self, key_path, encoding, loader, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        public_key = loader(data, backend)
        assert (
            public_key.public_bytes(
                encoding, PublicFormat.SubjectPublicKeyInfo
            )
            == data
        )

    def test_openssl_serialization_unsupported(self, backend):
        key = ed448.Ed448PrivateKey.generate()
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.DER,
                PrivateFormat.TraditionalOpenSSL,
                NoEncryption(),
            )

    def test_openssh_serialization_unsupported(self, backend):
        key = ed448.Ed448PrivateKey.generate()
        with pytest.raises(ValueError):
            key.public_key().public_bytes(
                Encoding.OpenSSH,
                PublicFormat.OpenSSH,
            )
        with pytest.raises(ValueError):
            key.private_bytes(
                Encoding.PEM,
                PrivateFormat.OpenSSH,
                NoEncryption(),
            )


@pytest.mark.supported(
    only_if=lambda backend: backend.dh_supported(),
    skip_message="DH not supported",
)
class TestDHSerialization:
    """Test all options with least-supported key type."""

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    def test_dh_public_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhkey.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        public_key = load_pem_private_key(data, None, backend).public_key()
        for enc in (
            Encoding.PEM,
            Encoding.DER,
            Encoding.OpenSSH,
            Encoding.Raw,
            Encoding.X962,
        ):
            for fmt in (
                PublicFormat.SubjectPublicKeyInfo,
                PublicFormat.PKCS1,
                PublicFormat.OpenSSH,
                PublicFormat.Raw,
                PublicFormat.CompressedPoint,
                PublicFormat.UncompressedPoint,
            ):
                if (
                    enc in (Encoding.PEM, Encoding.DER)
                    and fmt == PublicFormat.SubjectPublicKeyInfo
                ):
                    # tested elsewhere
                    continue
                with pytest.raises(ValueError):
                    public_key.public_bytes(enc, fmt)

    @pytest.mark.skip_fips(reason="non-FIPS parameters")
    def test_dh_private_key(self, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "DH", "dhkey.pem"),
            lambda pemfile: pemfile.read(),
            mode="rb",
        )
        private_key = load_pem_private_key(data, None, backend)
        for enc in (
            Encoding.PEM,
            Encoding.DER,
            Encoding.OpenSSH,
            Encoding.Raw,
            Encoding.X962,
        ):
            for fmt in (
                PrivateFormat.PKCS8,
                PrivateFormat.TraditionalOpenSSL,
                PrivateFormat.Raw,
            ):
                if (
                    enc in (Encoding.PEM, Encoding.DER)
                    and fmt is PrivateFormat.PKCS8
                ):
                    # tested elsewhere
                    continue
                with pytest.raises(ValueError):
                    private_key.private_bytes(enc, fmt, NoEncryption())


class TestEncryptionBuilder:
    def test_unsupported_format(self):
        f = PrivateFormat.PKCS8
        with pytest.raises(ValueError):
            f.encryption_builder()

    def test_duplicate_kdf_rounds(self):
        b = PrivateFormat.OpenSSH.encryption_builder().kdf_rounds(12)
        with pytest.raises(ValueError):
            b.kdf_rounds(12)

    def test_invalid_kdf_rounds(self):
        b = PrivateFormat.OpenSSH.encryption_builder()
        with pytest.raises(ValueError):
            b.kdf_rounds(0)
        with pytest.raises(ValueError):
            b.kdf_rounds(-1)
        with pytest.raises(TypeError):
            b.kdf_rounds("string")  # type: ignore[arg-type]

    def test_invalid_password(self):
        b = PrivateFormat.OpenSSH.encryption_builder()
        with pytest.raises(ValueError):
            b.build(12)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            b.build(b"")

    def test_unsupported_type_for_methods(self):
        b = PrivateFormat.OpenSSH.encryption_builder()
        with pytest.raises(TypeError):
            b.key_cert_algorithm(PBES.PBESv1SHA1And3KeyTripleDESCBC)
        with pytest.raises(TypeError):
            b.hmac_hash(SHA1())

    def test_duplicate_hmac_hash(self):
        b = PrivateFormat.PKCS12.encryption_builder().hmac_hash(SHA1())
        with pytest.raises(ValueError):
            b.hmac_hash(SHA1())

    def test_duplicate_key_cert_algorithm(self):
        b = PrivateFormat.PKCS12.encryption_builder().key_cert_algorithm(
            PBES.PBESv1SHA1And3KeyTripleDESCBC
        )
        with pytest.raises(ValueError):
            b.key_cert_algorithm(PBES.PBESv1SHA1And3KeyTripleDESCBC)
