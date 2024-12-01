# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import datetime

import pytest

from cryptography import utils, x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import (
    ec,
    ed448,
    ed25519,
    padding,
    rsa,
)
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    NameOID,
    SignatureAlgorithmOID,
)

from ..hazmat.primitives.fixtures_dsa import DSA_KEY_2048
from ..hazmat.primitives.fixtures_ec import EC_KEY_SECP256R1
from ..hazmat.primitives.test_ec import _skip_curve_unsupported
from ..hazmat.primitives.test_rsa import rsa_key_512, rsa_key_2048
from .test_x509 import DummyExtension

# Make ruff happy since we're importing fixtures that pytest patches in as
# func args
__all__ = ["rsa_key_512", "rsa_key_2048"]


class TestCertificateRevocationListBuilder:
    def test_issuer_name_invalid(self):
        builder = x509.CertificateRevocationListBuilder()
        with pytest.raises(TypeError):
            builder.issuer_name("notanx509name")  # type:ignore[arg-type]

    def test_set_issuer_name_twice(self):
        builder = x509.CertificateRevocationListBuilder().issuer_name(
            x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "US")])
        )
        with pytest.raises(ValueError):
            builder.issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "US")])
            )

    def test_aware_last_update(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        tz = datetime.timezone(datetime.timedelta(hours=-8))
        last_time = datetime.datetime(2012, 1, 16, 22, 43, tzinfo=tz)
        utc_last = datetime.datetime(2012, 1, 17, 6, 43)
        next_time = datetime.datetime(2022, 1, 17, 6, 43)
        private_key = rsa_key_2048
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_time)
            .next_update(next_time)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        with pytest.warns(utils.DeprecatedIn42):
            assert crl.last_update == utc_last
        assert crl.last_update_utc == utc_last.replace(
            tzinfo=datetime.timezone.utc
        )

    def test_last_update_invalid(self):
        builder = x509.CertificateRevocationListBuilder()
        with pytest.raises(TypeError):
            builder.last_update("notadatetime")  # type:ignore[arg-type]

    def test_last_update_before_1950(self):
        builder = x509.CertificateRevocationListBuilder()
        with pytest.raises(ValueError):
            builder.last_update(datetime.datetime(1940, 8, 10))

    def test_set_last_update_twice(self):
        builder = x509.CertificateRevocationListBuilder().last_update(
            datetime.datetime(2002, 1, 1, 12, 1)
        )
        with pytest.raises(ValueError):
            builder.last_update(datetime.datetime(2002, 1, 1, 12, 1))

    def test_aware_next_update(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        tz = datetime.timezone(datetime.timedelta(hours=-8))
        next_time = datetime.datetime(2022, 1, 16, 22, 43, tzinfo=tz)
        utc_next = datetime.datetime(2022, 1, 17, 6, 43)
        last_time = datetime.datetime(2012, 1, 17, 6, 43)
        private_key = rsa_key_2048
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_time)
            .next_update(next_time)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        with pytest.warns(utils.DeprecatedIn42):
            assert crl.next_update == utc_next
        assert crl.next_update_utc == utc_next.replace(
            tzinfo=datetime.timezone.utc
        )

    def test_next_update_invalid(self):
        builder = x509.CertificateRevocationListBuilder()
        with pytest.raises(TypeError):
            builder.next_update("notadatetime")  # type:ignore[arg-type]

    def test_next_update_before_1950(self):
        builder = x509.CertificateRevocationListBuilder()
        with pytest.raises(ValueError):
            builder.next_update(datetime.datetime(1940, 8, 10))

    def test_set_next_update_twice(self):
        builder = x509.CertificateRevocationListBuilder().next_update(
            datetime.datetime(2002, 1, 1, 12, 1)
        )
        with pytest.raises(ValueError):
            builder.next_update(datetime.datetime(2002, 1, 1, 12, 1))

    def test_last_update_after_next_update(self):
        builder = x509.CertificateRevocationListBuilder()

        builder = builder.next_update(datetime.datetime(2002, 1, 1, 12, 1))
        with pytest.raises(ValueError):
            builder.last_update(datetime.datetime(2003, 1, 1, 12, 1))

    def test_next_update_after_last_update(self):
        builder = x509.CertificateRevocationListBuilder()

        builder = builder.last_update(datetime.datetime(2002, 1, 1, 12, 1))
        with pytest.raises(ValueError):
            builder.next_update(datetime.datetime(2001, 1, 1, 12, 1))

    def test_add_extension_checks_for_duplicates(self):
        builder = x509.CertificateRevocationListBuilder().add_extension(
            x509.CRLNumber(1), False
        )

        with pytest.raises(ValueError):
            builder.add_extension(x509.CRLNumber(2), False)

    def test_add_invalid_extension(self):
        builder = x509.CertificateRevocationListBuilder()

        with pytest.raises(TypeError):
            builder.add_extension(object(), False)  # type:ignore[arg-type]

    def test_add_invalid_revoked_certificate(self):
        builder = x509.CertificateRevocationListBuilder()

        with pytest.raises(TypeError):
            builder.add_revoked_certificate(object())  # type:ignore[arg-type]

    def test_no_issuer_name(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        builder = (
            x509.CertificateRevocationListBuilder()
            .last_update(datetime.datetime(2002, 1, 1, 12, 1))
            .next_update(datetime.datetime(2030, 1, 1, 12, 1))
        )

        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA256(), backend)

    def test_no_last_update(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "US")])
            )
            .next_update(datetime.datetime(2030, 1, 1, 12, 1))
        )

        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA256(), backend)

    def test_no_next_update(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name([x509.NameAttribute(NameOID.COUNTRY_NAME, "US")])
            )
            .last_update(datetime.datetime(2030, 1, 1, 12, 1))
        )

        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA256(), backend)

    def test_sign_invalid_padding(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        with pytest.raises(TypeError):
            builder.sign(
                rsa_key_2048,
                hashes.SHA256(),
                rsa_padding=b"notapadding",  # type: ignore[arg-type]
            )
        eckey = ec.generate_private_key(ec.SECP256R1())
        with pytest.raises(TypeError):
            builder.sign(
                eckey, hashes.SHA256(), rsa_padding=padding.PKCS1v15()
            )

    def test_sign_empty_list(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert len(crl) == 0
        with pytest.warns(utils.DeprecatedIn42):
            assert crl.last_update == last_update
            assert crl.next_update == next_update
        assert crl.last_update_utc == last_update.replace(
            tzinfo=datetime.timezone.utc
        )
        assert crl.next_update_utc == next_update.replace(
            tzinfo=datetime.timezone.utc
        )

    def test_sign_pss(self, rsa_key_2048: rsa.RSAPrivateKey, backend):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        pss = padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        )
        crl = builder.sign(private_key, hashes.SHA256(), rsa_padding=pss)
        assert len(crl) == 0
        assert isinstance(crl.signature_algorithm_parameters, padding.PSS)
        assert crl.signature_algorithm_parameters._salt_length == 32
        private_key.public_key().verify(
            crl.signature,
            crl.tbs_certlist_bytes,
            crl.signature_algorithm_parameters,
            hashes.SHA256(),
        )

    @pytest.mark.parametrize(
        "extension",
        [
            x509.CRLNumber(13),
            x509.DeltaCRLIndicator(12345678901234567890),
            x509.AuthorityKeyIdentifier(
                b"\xc3\x9c\xf3\xfc\xd3F\x084\xbb\xceF\x7f\xa0|[\xf3\xe2\x08"
                b"\xcbY",
                None,
                None,
            ),
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.CA_ISSUERS,
                        x509.DNSName("cryptography.io"),
                    )
                ]
            ),
            x509.IssuerAlternativeName(
                [x509.UniformResourceIdentifier("https://cryptography.io")]
            ),
        ],
    )
    def test_sign_extensions(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend, extension
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_extension(extension, False)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert len(crl) == 0
        assert len(crl.extensions) == 1
        ext = crl.extensions.get_extension_for_class(type(extension))
        assert ext.critical is False
        assert ext.value == extension

    def test_sign_multiple_extensions_critical(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        ian = x509.IssuerAlternativeName(
            [x509.UniformResourceIdentifier("https://cryptography.io")]
        )
        crl_number = x509.CRLNumber(13)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_extension(crl_number, False)
            .add_extension(ian, True)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert len(crl) == 0
        assert len(crl.extensions) == 2
        ext1 = crl.extensions.get_extension_for_class(x509.CRLNumber)
        assert ext1.critical is False
        assert ext1.value == crl_number
        ext2 = crl.extensions.get_extension_for_class(
            x509.IssuerAlternativeName
        )
        assert ext2.critical is True
        assert ext2.value == ian

    def test_freshestcrl_extension(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        freshest = x509.FreshestCRL(
            [
                x509.DistributionPoint(
                    [x509.UniformResourceIdentifier("http://d.om/delta")],
                    None,
                    None,
                    None,
                )
            ]
        )
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_extension(freshest, False)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert len(crl) == 0
        assert len(crl.extensions) == 1
        ext1 = crl.extensions.get_extension_for_class(x509.FreshestCRL)
        assert ext1.critical is False
        assert isinstance(ext1.value, x509.FreshestCRL)
        assert isinstance(ext1.value[0], x509.DistributionPoint)
        assert ext1.value[0].full_name is not None
        uri = ext1.value[0].full_name[0]
        assert isinstance(uri, x509.UniformResourceIdentifier)
        assert uri.value == "http://d.om/delta"

    def test_add_unsupported_extension(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_extension(DummyExtension(), False)
        )
        with pytest.raises(NotImplementedError):
            builder.sign(private_key, hashes.SHA256(), backend)

    def test_add_unsupported_entry_extension(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(
                x509.RevokedCertificateBuilder()
                .serial_number(1234)
                .revocation_date(
                    datetime.datetime.now(datetime.timezone.utc).replace(
                        tzinfo=None
                    )
                )
                .add_extension(DummyExtension(), critical=False)
                .build()
            )
        )
        with pytest.raises(NotImplementedError):
            builder.sign(private_key, hashes.SHA256(), backend)

    def test_sign_rsa_key_too_small(
        self, rsa_key_512: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_512
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA512(), backend)

    def test_sign_with_invalid_hash(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        with pytest.raises(TypeError):
            builder.sign(
                private_key,
                object(),  # type: ignore[arg-type]
                backend,
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires OpenSSL with Ed25519 support",
    )
    def test_sign_with_invalid_hash_ed25519(self, backend):
        private_key = ed25519.Ed25519PrivateKey.generate()
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        with pytest.raises(TypeError):
            builder.sign(
                private_key,
                object(),  # type:ignore[arg-type]
                backend,
            )
        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA256(), backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed448_supported(),
        skip_message="Requires OpenSSL with Ed448 support",
    )
    def test_sign_with_invalid_hash_ed448(self, backend):
        private_key = ed448.Ed448PrivateKey.generate()
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
        )

        with pytest.raises(TypeError):
            builder.sign(
                private_key,
                object(),  # type:ignore[arg-type]
                backend,
            )
        with pytest.raises(ValueError):
            builder.sign(private_key, hashes.SHA256(), backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Requires OpenSSL with DSA support",
    )
    def test_sign_dsa_key(self, backend):
        private_key = DSA_KEY_2048.private_key(backend)
        invalidity_date = x509.InvalidityDate(
            datetime.datetime(2002, 1, 1, 0, 0)
        )
        ian = x509.IssuerAlternativeName(
            [x509.UniformResourceIdentifier("https://cryptography.io")]
        )
        revoked_cert0 = (
            x509.RevokedCertificateBuilder()
            .serial_number(2)
            .revocation_date(datetime.datetime(2012, 1, 1, 1, 1))
            .add_extension(invalidity_date, False)
            .build(backend)
        )
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(revoked_cert0)
            .add_extension(ian, False)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert (
            crl.extensions.get_extension_for_class(
                x509.IssuerAlternativeName
            ).value
            == ian
        )
        assert crl[0].serial_number == revoked_cert0.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[0].revocation_date == revoked_cert0.revocation_date
        assert crl[0].revocation_date_utc == revoked_cert0.revocation_date_utc
        assert len(crl[0].extensions) == 1
        ext = crl[0].extensions.get_extension_for_class(x509.InvalidityDate)
        assert ext.critical is False
        assert ext.value == invalidity_date

    def test_sign_ec_key(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        private_key = ec.generate_private_key(ec.SECP256R1(), backend)
        invalidity_date = x509.InvalidityDate(
            datetime.datetime(2002, 1, 1, 0, 0)
        )
        ian = x509.IssuerAlternativeName(
            [x509.UniformResourceIdentifier("https://cryptography.io")]
        )
        revoked_cert0 = (
            x509.RevokedCertificateBuilder()
            .serial_number(2)
            .revocation_date(datetime.datetime(2012, 1, 1, 1, 1))
            .add_extension(invalidity_date, False)
            .build(backend)
        )
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(revoked_cert0)
            .add_extension(ian, False)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert (
            crl.extensions.get_extension_for_class(
                x509.IssuerAlternativeName
            ).value
            == ian
        )
        assert crl[0].serial_number == revoked_cert0.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[0].revocation_date == revoked_cert0.revocation_date
        assert crl[0].revocation_date_utc == revoked_cert0.revocation_date_utc
        assert len(crl[0].extensions) == 1
        ext = crl[0].extensions.get_extension_for_class(x509.InvalidityDate)
        assert ext.critical is False
        assert ext.value == invalidity_date

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires OpenSSL with Ed25519 support",
    )
    def test_sign_ed25519_key(self, backend):
        private_key = ed25519.Ed25519PrivateKey.generate()
        invalidity_date = x509.InvalidityDate(
            datetime.datetime(2002, 1, 1, 0, 0)
        )
        ian = x509.IssuerAlternativeName(
            [x509.UniformResourceIdentifier("https://cryptography.io")]
        )
        revoked_cert0 = (
            x509.RevokedCertificateBuilder()
            .serial_number(2)
            .revocation_date(datetime.datetime(2012, 1, 1, 1, 1))
            .add_extension(invalidity_date, False)
            .build(backend)
        )
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(revoked_cert0)
            .add_extension(ian, False)
        )

        crl = builder.sign(private_key, None, backend)
        assert crl.signature_hash_algorithm is None
        assert crl.signature_algorithm_oid == SignatureAlgorithmOID.ED25519
        assert (
            crl.extensions.get_extension_for_class(
                x509.IssuerAlternativeName
            ).value
            == ian
        )
        assert crl[0].serial_number == revoked_cert0.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[0].revocation_date == revoked_cert0.revocation_date
        assert crl[0].revocation_date_utc == revoked_cert0.revocation_date_utc
        assert len(crl[0].extensions) == 1
        ext = crl[0].extensions.get_extension_for_class(x509.InvalidityDate)
        assert ext.critical is False
        assert ext.value == invalidity_date

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed448_supported(),
        skip_message="Requires OpenSSL with Ed448 support",
    )
    def test_sign_ed448_key(self, backend):
        private_key = ed448.Ed448PrivateKey.generate()
        invalidity_date = x509.InvalidityDate(
            datetime.datetime(2002, 1, 1, 0, 0)
        )
        ian = x509.IssuerAlternativeName(
            [x509.UniformResourceIdentifier("https://cryptography.io")]
        )
        revoked_cert0 = (
            x509.RevokedCertificateBuilder()
            .serial_number(2)
            .revocation_date(datetime.datetime(2012, 1, 1, 1, 1))
            .add_extension(invalidity_date, False)
            .build(backend)
        )
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(revoked_cert0)
            .add_extension(ian, False)
        )

        crl = builder.sign(private_key, None, backend)
        assert crl.signature_hash_algorithm is None
        assert crl.signature_algorithm_oid == SignatureAlgorithmOID.ED448
        assert (
            crl.extensions.get_extension_for_class(
                x509.IssuerAlternativeName
            ).value
            == ian
        )
        assert crl[0].serial_number == revoked_cert0.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[0].revocation_date == revoked_cert0.revocation_date
        assert crl[0].revocation_date_utc == revoked_cert0.revocation_date_utc
        assert len(crl[0].extensions) == 1
        ext = crl[0].extensions.get_extension_for_class(x509.InvalidityDate)
        assert ext.critical is False
        assert ext.value == invalidity_date

    def test_dsa_key_sign_md5(self, backend):
        private_key = DSA_KEY_2048.private_key(backend)
        last_time = datetime.datetime(2012, 1, 16, 22, 43)
        next_time = datetime.datetime(2022, 1, 17, 6, 43)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_time)
            .next_update(next_time)
        )

        with pytest.raises(UnsupportedAlgorithm):
            builder.sign(
                private_key,
                hashes.MD5(),  # type: ignore[arg-type]
                backend,
            )

    def test_ec_key_sign_md5(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())
        private_key = EC_KEY_SECP256R1.private_key(backend)
        last_time = datetime.datetime(2012, 1, 16, 22, 43)
        next_time = datetime.datetime(2022, 1, 17, 6, 43)
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_time)
            .next_update(next_time)
        )

        with pytest.raises(UnsupportedAlgorithm):
            builder.sign(
                private_key,
                hashes.MD5(),  # type: ignore[arg-type]
                backend,
            )

    def test_sign_with_revoked_certificates(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        private_key = rsa_key_2048
        last_update = datetime.datetime(2002, 1, 1, 12, 1)
        next_update = datetime.datetime(2030, 1, 1, 12, 1)
        invalidity_date = x509.InvalidityDate(
            datetime.datetime(2002, 1, 1, 0, 0)
        )
        revoked_cert0 = (
            x509.RevokedCertificateBuilder()
            .serial_number(38)
            .revocation_date(datetime.datetime(2011, 1, 1, 1, 1))
            .build(backend)
        )
        revoked_cert1 = (
            x509.RevokedCertificateBuilder()
            .serial_number(2)
            .revocation_date(datetime.datetime(2012, 1, 1, 1, 1))
            .add_extension(invalidity_date, False)
            .add_extension(
                x509.CRLReason(x509.ReasonFlags.ca_compromise), False
            )
            .build(backend)
        )
        ci = x509.CertificateIssuer([x509.DNSName("cryptography.io")])
        revoked_cert2 = (
            x509.RevokedCertificateBuilder()
            .serial_number(40)
            .revocation_date(datetime.datetime(2011, 1, 1, 1, 1))
            .add_extension(ci, False)
            .build(backend)
        )
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME, "cryptography.io CA"
                        )
                    ]
                )
            )
            .last_update(last_update)
            .next_update(next_update)
            .add_revoked_certificate(revoked_cert0)
            .add_revoked_certificate(revoked_cert1)
            .add_revoked_certificate(revoked_cert2)
        )

        crl = builder.sign(private_key, hashes.SHA256(), backend)
        assert len(crl) == 3
        with pytest.warns(utils.DeprecatedIn42):
            assert crl.last_update == last_update
            assert crl.next_update == next_update
        assert crl.last_update_utc == last_update.replace(
            tzinfo=datetime.timezone.utc
        )
        assert crl.next_update_utc == next_update.replace(
            tzinfo=datetime.timezone.utc
        )
        assert crl[0].serial_number == revoked_cert0.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[0].revocation_date == revoked_cert0.revocation_date
        assert crl[0].revocation_date_utc == revoked_cert0.revocation_date_utc
        assert len(crl[0].extensions) == 0
        assert crl[1].serial_number == revoked_cert1.serial_number
        with pytest.warns(utils.DeprecatedIn42):
            assert crl[1].revocation_date == revoked_cert1.revocation_date
        assert crl[1].revocation_date_utc == revoked_cert1.revocation_date_utc
        assert len(crl[1].extensions) == 2
        ext = crl[1].extensions.get_extension_for_class(x509.InvalidityDate)
        assert ext.critical is False
        assert ext.value == invalidity_date
        assert (
            crl[2]
            .extensions.get_extension_for_class(x509.CertificateIssuer)
            .value
            == ci
        )
