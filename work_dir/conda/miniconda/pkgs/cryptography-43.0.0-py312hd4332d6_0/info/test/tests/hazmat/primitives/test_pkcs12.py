# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import os
from datetime import datetime, timezone

import pytest

from cryptography import x509
from cryptography.hazmat.bindings._rust import openssl as rust_openssl
from cryptography.hazmat.decrepit.ciphers.algorithms import RC2
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed448,
    ed25519,
    rsa,
)
from cryptography.hazmat.primitives.ciphers.modes import CBC
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
    load_pem_private_key,
)
from cryptography.hazmat.primitives.serialization.pkcs12 import (
    PBES,
    PKCS12Certificate,
    PKCS12KeyAndCertificates,
    load_key_and_certificates,
    load_pkcs12,
    serialize_key_and_certificates,
)

from ...doubles import DummyKeySerializationEncryption
from ...utils import load_vectors_from_file


def _skip_curve_unsupported(backend, curve):
    if not backend.elliptic_curve_supported(curve):
        pytest.skip(
            f"Curve {curve.name} is not supported by this backend {backend}"
        )


@pytest.mark.skip_fips(
    reason="PKCS12 unsupported in FIPS mode. So much bad crypto in it."
)
class TestPKCS12Loading:
    def _test_load_pkcs12_ec_keys(self, filename, password, backend):
        cert, key = _load_ca(backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        parsed_key, parsed_cert, parsed_more_certs = load_vectors_from_file(
            os.path.join("pkcs12", filename),
            lambda derfile: load_key_and_certificates(
                derfile.read(), password, backend
            ),
            mode="rb",
        )
        assert isinstance(parsed_key, ec.EllipticCurvePrivateKey)
        assert parsed_cert == cert
        assert parsed_key.private_numbers() == key.private_numbers()
        assert parsed_more_certs == []

    @pytest.mark.parametrize(
        ("filename", "password"),
        [
            ("cert-key-aes256cbc.p12", b"cryptography"),
            ("cert-none-key-none.p12", b"cryptography"),
        ],
    )
    def test_load_pkcs12_ec_keys(self, filename, password, backend):
        self._test_load_pkcs12_ec_keys(filename, password, backend)

    @pytest.mark.parametrize(
        ("filename", "password"),
        [
            ("cert-rc2-key-3des.p12", b"cryptography"),
            ("no-password.p12", None),
        ],
    )
    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            RC2(b"0" * 16), CBC(b"0" * 8)
        ),
        skip_message="Does not support RC2",
    )
    def test_load_pkcs12_ec_keys_rc2(self, filename, password, backend):
        self._test_load_pkcs12_ec_keys(filename, password, backend)

    def test_load_key_and_cert_cert_only(self, backend):
        cert, _ = _load_ca(backend)
        parsed_key, parsed_cert, parsed_more_certs = load_vectors_from_file(
            os.path.join("pkcs12", "cert-aes256cbc-no-key.p12"),
            lambda data: load_key_and_certificates(
                data.read(), b"cryptography", backend
            ),
            mode="rb",
        )
        assert parsed_cert is None
        assert parsed_key is None
        assert parsed_more_certs == [cert]

    def test_load_key_and_certificates_key_only(self, backend):
        _, key = _load_ca(backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        parsed_key, parsed_cert, parsed_more_certs = load_vectors_from_file(
            os.path.join("pkcs12", "no-cert-key-aes256cbc.p12"),
            lambda data: load_key_and_certificates(
                data.read(), b"cryptography", backend
            ),
            mode="rb",
        )
        assert isinstance(parsed_key, ec.EllipticCurvePrivateKey)
        assert parsed_key.private_numbers() == key.private_numbers()
        assert parsed_cert is None
        assert parsed_more_certs == []

    def test_load_pkcs12_key_only(self, backend):
        _, key = _load_ca(backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)
        p12 = load_vectors_from_file(
            os.path.join("pkcs12", "no-cert-key-aes256cbc.p12"),
            lambda data: load_pkcs12(data.read(), b"cryptography", backend),
            mode="rb",
        )
        assert isinstance(p12.key, ec.EllipticCurvePrivateKey)
        assert p12.key.private_numbers() == key.private_numbers()
        assert p12.cert is None
        assert p12.additional_certs == []

    def test_non_bytes(self, backend):
        with pytest.raises(TypeError):
            load_key_and_certificates(
                b"irrelevant",
                object(),  # type: ignore[arg-type]
                backend,
            )

    def test_not_a_pkcs12(self, backend):
        with pytest.raises(ValueError):
            load_key_and_certificates(b"invalid", b"pass", backend)

    def test_invalid_password(self, backend):
        with pytest.raises(ValueError):
            load_vectors_from_file(
                os.path.join("pkcs12", "cert-key-aes256cbc.p12"),
                lambda derfile: load_key_and_certificates(
                    derfile.read(), b"invalid", backend
                ),
                mode="rb",
            )

    def test_buffer_protocol(self, backend):
        p12 = load_vectors_from_file(
            os.path.join("pkcs12", "cert-key-aes256cbc.p12"),
            lambda derfile: derfile.read(),
            mode="rb",
        )
        p12buffer = bytearray(p12)
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12buffer, bytearray(b"cryptography"), backend
        )
        assert parsed_key is not None
        assert parsed_cert is not None
        assert parsed_more_certs == []

    @pytest.mark.parametrize(
        ("name", "name2", "name3", "filename", "password"),
        [
            (None, None, None, "no-name-no-pwd.p12", None),
            (b"name", b"name2", b"name3", "name-all-no-pwd.p12", None),
            (b"name", None, None, "name-1-no-pwd.p12", None),
            (None, b"name2", b"name3", "name-2-3-no-pwd.p12", None),
            (None, b"name2", None, "name-2-no-pwd.p12", None),
            (None, None, b"name3", "name-3-no-pwd.p12", None),
            (
                "☺".encode(),
                "ä".encode(),
                "ç".encode(),
                "name-unicode-no-pwd.p12",
                None,
            ),
            (None, None, None, "no-name-pwd.p12", b"password"),
            (b"name", b"name2", b"name3", "name-all-pwd.p12", b"password"),
            (b"name", None, None, "name-1-pwd.p12", b"password"),
            (None, b"name2", b"name3", "name-2-3-pwd.p12", b"password"),
            (None, b"name2", None, "name-2-pwd.p12", b"password"),
            (None, None, b"name3", "name-3-pwd.p12", b"password"),
            (
                "☺".encode(),
                "ä".encode(),
                "ç".encode(),
                "name-unicode-pwd.p12",
                b"password",
            ),
        ],
    )
    def test_load_object(
        self, filename, name, name2, name3, password, backend
    ):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "cryptography.io.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        pkcs12 = load_vectors_from_file(
            os.path.join("pkcs12", filename),
            lambda derfile: load_pkcs12(derfile.read(), password, backend),
            mode="rb",
        )
        assert pkcs12.cert is not None
        assert pkcs12.cert.certificate == cert
        assert pkcs12.cert.friendly_name == name
        assert isinstance(pkcs12.key, ec.EllipticCurvePrivateKey)
        assert pkcs12.key.private_numbers() == key.private_numbers()
        assert len(pkcs12.additional_certs) == 2
        assert pkcs12.additional_certs[0].certificate == cert2
        assert pkcs12.additional_certs[0].friendly_name == name2
        assert pkcs12.additional_certs[1].certificate == cert3
        assert pkcs12.additional_certs[1].friendly_name == name3

    @pytest.mark.parametrize(
        ("name2", "name3", "filename", "password"),
        [
            (None, None, "no-cert-no-name-no-pwd.p12", None),
            (b"name2", b"name3", "no-cert-name-all-no-pwd.p12", None),
            (b"name2", None, "no-cert-name-2-no-pwd.p12", None),
            (None, b"name3", "no-cert-name-3-no-pwd.p12", None),
            (
                "☹".encode(),
                "ï".encode(),
                "no-cert-name-unicode-no-pwd.p12",
                None,
            ),
            (None, None, "no-cert-no-name-pwd.p12", b"password"),
            (b"name2", b"name3", "no-cert-name-all-pwd.p12", b"password"),
            (b"name2", None, "no-cert-name-2-pwd.p12", b"password"),
            (None, b"name3", "no-cert-name-3-pwd.p12", b"password"),
            (
                "☹".encode(),
                "ï".encode(),
                "no-cert-name-unicode-pwd.p12",
                b"password",
            ),
        ],
    )
    def test_load_object_no_cert_key(
        self, filename, name2, name3, password, backend
    ):
        cert2 = _load_cert(
            backend, os.path.join("x509", "cryptography.io.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        pkcs12 = load_vectors_from_file(
            os.path.join("pkcs12", filename),
            lambda derfile: load_pkcs12(derfile.read(), password, backend),
            mode="rb",
        )
        assert pkcs12.cert is None
        assert pkcs12.key is None
        assert len(pkcs12.additional_certs) == 2
        assert pkcs12.additional_certs[0].certificate == cert2
        assert pkcs12.additional_certs[0].friendly_name == name2
        assert pkcs12.additional_certs[1].certificate == cert3
        assert pkcs12.additional_certs[1].friendly_name == name3


def _load_cert(backend, path):
    return load_vectors_from_file(
        path,
        lambda pemfile: x509.load_pem_x509_certificate(
            pemfile.read(), backend
        ),
        mode="rb",
    )


def _load_ca(backend):
    cert = _load_cert(backend, os.path.join("pkcs12", "ca", "ca.pem"))
    key = load_vectors_from_file(
        os.path.join("pkcs12", "ca", "ca_key.pem"),
        lambda pemfile: load_pem_private_key(pemfile.read(), None, backend),
        mode="rb",
    )
    return cert, key


@pytest.mark.skip_fips(
    reason="PKCS12 unsupported in FIPS mode. So much bad crypto in it."
)
class TestPKCS12Creation:
    @pytest.mark.parametrize(
        (
            "kgenerator",
            "ktype",
            "kparam",
        ),
        [
            pytest.param(
                ed448.Ed448PrivateKey.generate,
                ed448.Ed448PrivateKey,
                [],
                marks=pytest.mark.supported(
                    only_if=lambda backend: backend.ed448_supported(),
                    skip_message="Requires OpenSSL with Ed448 support",
                ),
            ),
            pytest.param(
                ed25519.Ed25519PrivateKey.generate,
                ed25519.Ed25519PrivateKey,
                [],
                marks=pytest.mark.supported(
                    only_if=lambda backend: backend.ed25519_supported(),
                    skip_message="Requires OpenSSL with Ed25519 support",
                ),
            ),
            (rsa.generate_private_key, rsa.RSAPrivateKey, [65537, 1024]),
            (dsa.generate_private_key, dsa.DSAPrivateKey, [1024]),
        ]
        + [
            pytest.param(
                ec.generate_private_key, ec.EllipticCurvePrivateKey, [curve]
            )
            for curve in ec._CURVE_TYPES.values()
        ],
    )
    @pytest.mark.parametrize("name", [None, b"name"])
    @pytest.mark.parametrize(
        ("algorithm", "password"),
        [
            (serialization.BestAvailableEncryption(b"password"), b"password"),
            (serialization.NoEncryption(), None),
        ],
    )
    def test_generate_each_supported_keytype(
        self, backend, kgenerator, ktype, kparam, name, algorithm, password
    ):
        if ktype == ec.EllipticCurvePrivateKey:
            _skip_curve_unsupported(backend, *kparam)

        key = kgenerator(*kparam)

        assert isinstance(key, ktype)
        cacert, cakey = _load_ca(backend)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cert = (
            x509.CertificateBuilder()
            .subject_name(cacert.subject)
            .issuer_name(cacert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now)
            .sign(cakey, hashes.SHA256())
        )
        assert isinstance(cert, x509.Certificate)
        p12 = serialize_key_and_certificates(
            name, key, cert, [cacert], algorithm
        )
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, password, backend
        )
        assert parsed_cert == cert
        assert isinstance(parsed_key, ktype)
        assert parsed_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ) == key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )
        assert parsed_more_certs == [cacert]

    def test_generate_with_cert_key_ca(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))
        encryption = serialization.NoEncryption()
        p12 = serialize_key_and_certificates(
            None, key, cert, [cert2, cert3], encryption
        )

        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, None, backend
        )
        assert parsed_cert == cert
        assert isinstance(parsed_key, ec.EllipticCurvePrivateKey)
        assert parsed_key.private_numbers() == key.private_numbers()
        assert parsed_more_certs == [cert2, cert3]

    def test_generate_cas_friendly_names(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))
        encryption = serialization.NoEncryption()
        p12 = serialize_key_and_certificates(
            b"test",
            key,
            cert,
            [
                PKCS12Certificate(cert2, b"cert2"),
                PKCS12Certificate(cert3, None),
            ],
            encryption,
        )

        p12_cert = load_pkcs12(p12, None, backend)
        cas = p12_cert.additional_certs
        assert cas[0].certificate == cert2
        assert cas[0].friendly_name == b"cert2"
        assert cas[1].certificate == cert3
        assert cas[1].friendly_name is None

    @pytest.mark.parametrize(
        ("encryption_algorithm", "password"),
        [
            (serialization.BestAvailableEncryption(b"password"), b"password"),
            (
                serialization.PrivateFormat.PKCS12.encryption_builder().build(
                    b"not a password"
                ),
                b"not a password",
            ),
            (serialization.NoEncryption(), None),
        ],
    )
    def test_generate_cas_friendly_names_no_key(
        self, backend, encryption_algorithm, password
    ):
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))
        p12 = serialize_key_and_certificates(
            None,
            None,
            None,
            [
                PKCS12Certificate(cert2, b"cert2"),
                PKCS12Certificate(cert3, None),
            ],
            encryption_algorithm,
        )

        p12_cert = load_pkcs12(p12, password, backend)
        cas = p12_cert.additional_certs
        assert cas[0].certificate == cert2
        assert cas[0].friendly_name == b"cert2"
        assert cas[1].certificate == cert3
        assert cas[1].friendly_name is None

    def test_generate_wrong_types(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))
        encryption = serialization.NoEncryption()
        with pytest.raises(TypeError) as exc:
            serialize_key_and_certificates(
                b"name", cert, cert, None, encryption
            )
        assert str(exc.value) == (
            "Key must be RSA, DSA, EllipticCurve, ED25519, or ED448"
            " private key, or None."
        )
        with pytest.raises(TypeError) as exc:
            serialize_key_and_certificates(b"name", key, key, None, encryption)
        assert "object cannot be converted to 'Certificate'" in str(exc.value)

        with pytest.raises(TypeError) as exc:
            serialize_key_and_certificates(b"name", key, cert, None, key)
        assert str(exc.value) == (
            "Key encryption algorithm must be a "
            "KeySerializationEncryption instance"
        )

        with pytest.raises(TypeError) as exc:
            serialize_key_and_certificates(None, key, cert, cert2, encryption)

        with pytest.raises(TypeError) as exc:
            serialize_key_and_certificates(None, key, cert, [key], encryption)
        assert "failed to extract enum CertificateOrPKCS12Certificate" in str(
            exc.value
        )

    def test_generate_no_cert(self, backend):
        _, key = _load_ca(backend)
        p12 = serialize_key_and_certificates(
            None, key, None, None, serialization.NoEncryption()
        )
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, None, backend
        )
        assert parsed_cert is None
        assert isinstance(parsed_key, ec.EllipticCurvePrivateKey)
        assert parsed_key.private_numbers() == key.private_numbers()
        assert parsed_more_certs == []

    @pytest.mark.parametrize(
        ("encryption_algorithm", "password"),
        [
            (serialization.BestAvailableEncryption(b"password"), b"password"),
            (serialization.NoEncryption(), None),
        ],
    )
    def test_generate_cas_only(self, encryption_algorithm, password, backend):
        cert, _ = _load_ca(backend)
        p12 = serialize_key_and_certificates(
            None, None, None, [cert], encryption_algorithm
        )
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, password, backend
        )
        assert parsed_cert is None
        assert parsed_key is None
        assert parsed_more_certs == [cert]

    @pytest.mark.parametrize(
        ("encryption_algorithm", "password"),
        [
            (serialization.BestAvailableEncryption(b"password"), b"password"),
            (serialization.NoEncryption(), None),
        ],
    )
    def test_generate_cert_only(self, encryption_algorithm, password, backend):
        # This test is a bit weird, but when passing *just* a cert
        # with no corresponding key it will be encoded in the cas
        # list. We have external consumers relying on this behavior
        # (and the underlying structure makes no real distinction
        # anyway) so this test ensures we don't break them.
        cert, _ = _load_ca(backend)
        p12 = serialize_key_and_certificates(
            None, None, cert, [], encryption_algorithm
        )
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, password, backend
        )
        assert parsed_cert is None
        assert parsed_key is None
        assert parsed_more_certs == [cert]

    def test_generate_cert_only_none_cas(self, backend):
        # Same as test_generate_cert_only, but passing None instead of an
        # empty list for cas.
        cert, _ = _load_ca(backend)
        p12 = serialize_key_and_certificates(
            None, None, cert, None, serialization.NoEncryption()
        )
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, None
        )
        assert parsed_cert is None
        assert parsed_key is None
        assert parsed_more_certs == [cert]

    def test_invalid_utf8_friendly_name(self, backend):
        cert, _ = _load_ca(backend)
        with pytest.raises(ValueError):
            serialize_key_and_certificates(
                b"\xc9", None, cert, None, serialization.NoEncryption()
            )

    def test_must_supply_something(self):
        with pytest.raises(ValueError) as exc:
            serialize_key_and_certificates(
                None, None, None, None, serialization.NoEncryption()
            )
        assert str(exc.value) == (
            "You must supply at least one of key, cert, or cas"
        )

    def test_generate_unsupported_encryption_type(self, backend):
        cert, key = _load_ca(backend)
        with pytest.raises(ValueError) as exc:
            serialize_key_and_certificates(
                None,
                key,
                cert,
                None,
                DummyKeySerializationEncryption(),
            )
        assert str(exc.value) == "Unsupported key encryption type"

    @pytest.mark.parametrize(
        ("enc_alg", "enc_alg_der"),
        [
            (
                PBES.PBESv2SHA256AndAES256CBC,
                [
                    b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x05\x0d",  # PBESv2
                    b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x2a",  # AES
                ],
            ),
            (
                PBES.PBESv1SHA1And3KeyTripleDESCBC,
                [b"\x06\x0a\x2a\x86\x48\x86\xf7\x0d\x01\x0c\x01\x03"],
            ),
            (
                None,
                [],
            ),
        ],
    )
    @pytest.mark.parametrize(
        ("mac_alg", "mac_alg_der"),
        [
            (hashes.SHA1(), b"\x06\x05\x2b\x0e\x03\x02\x1a"),
            (hashes.SHA256(), b"\x06\t`\x86H\x01e\x03\x04\x02\x01"),
            (None, None),
        ],
    )
    @pytest.mark.parametrize(
        ("iters", "iter_der"),
        [
            (420, b"\x02\x02\x01\xa4"),
            (22222, b"\x02\x02\x56\xce"),
            (None, None),
        ],
    )
    def test_key_serialization_encryption(
        self,
        backend,
        enc_alg,
        enc_alg_der,
        mac_alg,
        mac_alg_der,
        iters,
        iter_der,
    ):
        if (
            enc_alg is PBES.PBESv2SHA256AndAES256CBC
        ) and not rust_openssl.CRYPTOGRAPHY_OPENSSL_300_OR_GREATER:
            pytest.skip("PBESv2 is not supported on OpenSSL < 3.0")

        builder = serialization.PrivateFormat.PKCS12.encryption_builder()
        if enc_alg is not None:
            builder = builder.key_cert_algorithm(enc_alg)
        if mac_alg is not None:
            builder = builder.hmac_hash(mac_alg)
        if iters is not None:
            builder = builder.kdf_rounds(iters)

        encryption = builder.build(b"password")
        key = ec.generate_private_key(ec.SECP256R1())
        cacert, cakey = _load_ca(backend)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cert = (
            x509.CertificateBuilder()
            .subject_name(cacert.subject)
            .issuer_name(cacert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now)
            .sign(cakey, hashes.SHA256())
        )
        assert isinstance(cert, x509.Certificate)
        p12 = serialize_key_and_certificates(
            b"name", key, cert, [cacert], encryption
        )
        # We want to know if we've serialized something that has the parameters
        # we expect, so we match on specific byte strings of OIDs & DER values.
        for der in enc_alg_der:
            assert der in p12
        if mac_alg_der is not None:
            assert mac_alg_der in p12
        if iter_der is not None:
            assert iter_der in p12
        parsed_key, parsed_cert, parsed_more_certs = load_key_and_certificates(
            p12, b"password", backend
        )
        assert parsed_cert == cert
        assert isinstance(parsed_key, ec.EllipticCurvePrivateKey)
        assert parsed_key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ) == key.public_key().public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        )
        assert parsed_more_certs == [cacert]

    def test_set_mac_key_certificate_mismatch(self, backend):
        cacert, _ = _load_ca(backend)
        key = ec.generate_private_key(ec.SECP256R1())
        encryption = (
            serialization.PrivateFormat.PKCS12.encryption_builder()
            .hmac_hash(hashes.SHA256())
            .build(b"password")
        )

        with pytest.raises(ValueError):
            serialize_key_and_certificates(
                b"name", key, cacert, [], encryption
            )


@pytest.mark.skip_fips(
    reason="PKCS12 unsupported in FIPS mode. So much bad crypto in it."
)
def test_pkcs12_ordering():
    """
    In OpenSSL < 3.0.0 PKCS12 parsing reverses the order. However, we
    accidentally thought it was **encoding** that did it, leading to bug
    https://github.com/pyca/cryptography/issues/5872
    This test ensures our ordering is correct going forward.
    """

    def make_cert(name):
        key = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name(
            [
                x509.NameAttribute(x509.NameOID.COMMON_NAME, name),
            ]
        )
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now)
            .sign(key, hashes.SHA256())
        )
        return (key, cert)

    # Make some certificates with distinct names.
    a_name = "A" * 20
    b_name = "B" * 20
    c_name = "C" * 20
    a_key, a_cert = make_cert(a_name)
    _, b_cert = make_cert(b_name)
    _, c_cert = make_cert(c_name)

    # Bundle them in a PKCS#12 file in order A, B, C.
    p12 = serialize_key_and_certificates(
        b"p12", a_key, a_cert, [b_cert, c_cert], serialization.NoEncryption()
    )

    # Parse them out. The API should report them in the same order.
    (_, cert, certs) = load_key_and_certificates(p12, None)
    assert cert == a_cert
    assert certs == [b_cert, c_cert]

    # The ordering in the PKCS#12 file itself should also match.
    a_idx = p12.index(a_name.encode("utf-8"))
    b_idx = p12.index(b_name.encode("utf-8"))
    c_idx = p12.index(c_name.encode("utf-8"))

    assert a_idx < b_idx < c_idx


class TestPKCS12Objects:
    def test_certificate_constructor(self, backend):
        with pytest.raises(TypeError):
            PKCS12Certificate(None, None)  # type:ignore[arg-type]
        with pytest.raises(TypeError):
            PKCS12Certificate("hello", None)  # type:ignore[arg-type]
        cert = _load_cert(backend, os.path.join("x509", "cryptography.io.pem"))
        with pytest.raises(TypeError):
            PKCS12Certificate(cert, "hello")  # type:ignore[arg-type]
        with pytest.raises(TypeError):
            PKCS12Certificate(cert, 42)  # type:ignore[arg-type]

    def test_certificate_equality(self, backend):
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        c2n = PKCS12Certificate(cert2, None)
        c2a = PKCS12Certificate(cert2, b"a")
        c2b = PKCS12Certificate(cert2, b"b")
        c3n = PKCS12Certificate(cert3, None)
        c3a = PKCS12Certificate(cert3, b"a")

        assert c2n == c2n
        assert c2a == c2a
        assert c2n != c2a
        assert c2n != c3n
        assert c2a != c2b
        assert c2a != c3a

        assert c2n != "test"  # type: ignore[comparison-overlap]

    def test_certificate_hash(self, backend):
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        c2n = PKCS12Certificate(cert2, None)
        c2a = PKCS12Certificate(cert2, b"a")
        c2b = PKCS12Certificate(cert2, b"b")
        c3n = PKCS12Certificate(cert3, None)
        c3a = PKCS12Certificate(cert3, b"a")

        assert hash(c2n) == hash(c2n)
        assert hash(c2a) == hash(c2a)
        assert hash(c2n) != hash(c2a)
        assert hash(c2n) != hash(c3n)
        assert hash(c2a) != hash(c2b)
        assert hash(c2a) != hash(c3a)

    def test_certificate_repr(self, backend):
        cert = _load_cert(backend, os.path.join("x509", "cryptography.io.pem"))
        assert (
            repr(PKCS12Certificate(cert, None))
            == f"<PKCS12Certificate({cert!r}, friendly_name=None)>"
        )
        assert (
            repr(PKCS12Certificate(cert, b"a"))
            == f"<PKCS12Certificate({cert!r}, friendly_name=b'a')>"
        )

    def test_key_and_certificates_constructor(self, backend):
        with pytest.raises(TypeError):
            PKCS12KeyAndCertificates(
                "hello",  # type:ignore[arg-type]
                None,
                [],
            )
        with pytest.raises(TypeError):
            PKCS12KeyAndCertificates(
                None,
                "hello",  # type:ignore[arg-type]
                [],
            )
        with pytest.raises(TypeError):
            PKCS12KeyAndCertificates(
                None,
                None,
                ["hello"],  # type:ignore[list-item]
            )

    def test_key_and_certificates_equality(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        p12a = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12b = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, b"name"),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12c = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert2, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12d = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert3, None), PKCS12Certificate(cert2, None)],
        )
        p12e = PKCS12KeyAndCertificates(
            None,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12f = PKCS12KeyAndCertificates(
            None,
            PKCS12Certificate(cert2, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12g = PKCS12KeyAndCertificates(
            key,
            None,
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12h = PKCS12KeyAndCertificates(None, None, [])

        assert p12a == p12a
        assert p12h == p12h

        assert p12a != p12b
        assert p12a != p12c
        assert p12a != p12d
        assert p12a != p12e
        assert p12a != p12g
        assert p12a != p12h
        assert p12e != p12f
        assert p12e != p12g
        assert p12e != p12h

        assert p12e != "test"

    def test_key_and_certificates_hash(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "custom", "dsa_selfsigned_ca.pem")
        )
        cert3 = _load_cert(backend, os.path.join("x509", "letsencryptx3.pem"))

        p12a = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12b = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, b"name"),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12c = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert2, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12d = PKCS12KeyAndCertificates(
            key,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert3, None), PKCS12Certificate(cert2, None)],
        )
        p12e = PKCS12KeyAndCertificates(
            None,
            PKCS12Certificate(cert, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12f = PKCS12KeyAndCertificates(
            None,
            PKCS12Certificate(cert2, None),
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12g = PKCS12KeyAndCertificates(
            key,
            None,
            [PKCS12Certificate(cert2, None), PKCS12Certificate(cert3, None)],
        )
        p12h = PKCS12KeyAndCertificates(None, None, [])

        assert hash(p12a) == hash(p12a)
        assert hash(p12h) == hash(p12h)

        assert hash(p12a) != hash(p12b)
        assert hash(p12a) != hash(p12c)
        assert hash(p12a) != hash(p12d)
        assert hash(p12a) != hash(p12e)
        assert hash(p12a) != hash(p12g)
        assert hash(p12a) != hash(p12h)
        assert hash(p12e) != hash(p12f)
        assert hash(p12e) != hash(p12g)
        assert hash(p12e) != hash(p12h)

    def test_key_and_certificates_repr(self, backend):
        cert, key = _load_ca(backend)
        cert2 = _load_cert(
            backend, os.path.join("x509", "cryptography.io.pem")
        )
        assert repr(
            PKCS12KeyAndCertificates(
                key,
                PKCS12Certificate(cert, None),
                [PKCS12Certificate(cert2, b"name2")],
            )
        ) == (
            f"<PKCS12KeyAndCertificates(key={key}, "
            f"cert=<PKCS12Certificate({cert}, friendly_name=None)>, "
            f"additional_certs=["
            f"<PKCS12Certificate({cert2}, friendly_name=b'name2')>])>"
        )
