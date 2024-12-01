# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import email.parser
import os
import typing

import pytest

from cryptography import x509
from cryptography.exceptions import _Reasons
from cryptography.hazmat.bindings._rust import test_support
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7

from ...utils import load_vectors_from_file, raises_unsupported_algorithm


@pytest.mark.supported(
    only_if=lambda backend: backend.pkcs7_supported(),
    skip_message="Requires OpenSSL with PKCS7 support",
)
class TestPKCS7Loading:
    def test_load_invalid_der_pkcs7(self, backend):
        with pytest.raises(ValueError):
            pkcs7.load_der_pkcs7_certificates(b"nonsense")

    def test_load_invalid_pem_pkcs7(self, backend):
        with pytest.raises(ValueError):
            pkcs7.load_pem_pkcs7_certificates(b"nonsense")

    def test_not_bytes_der(self, backend):
        with pytest.raises(TypeError):
            pkcs7.load_der_pkcs7_certificates(38)  # type: ignore[arg-type]

    def test_not_bytes_pem(self, backend):
        with pytest.raises(TypeError):
            pkcs7.load_pem_pkcs7_certificates(38)  # type: ignore[arg-type]

    def test_load_pkcs7_pem(self, backend):
        certs = load_vectors_from_file(
            os.path.join("pkcs7", "isrg.pem"),
            lambda pemfile: pkcs7.load_pem_pkcs7_certificates(pemfile.read()),
            mode="rb",
        )
        assert len(certs) == 1
        assert certs[0].subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        ) == [x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "ISRG Root X1")]

    @pytest.mark.parametrize(
        "filepath",
        [
            os.path.join("pkcs7", "amazon-roots.der"),
            os.path.join("pkcs7", "amazon-roots.p7b"),
        ],
    )
    def test_load_pkcs7_der(self, filepath, backend):
        certs = load_vectors_from_file(
            filepath,
            lambda derfile: pkcs7.load_der_pkcs7_certificates(derfile.read()),
            mode="rb",
        )
        assert len(certs) == 2
        assert certs[0].subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        ) == [
            x509.NameAttribute(
                x509.oid.NameOID.COMMON_NAME, "Amazon Root CA 3"
            )
        ]
        assert certs[1].subject.get_attributes_for_oid(
            x509.oid.NameOID.COMMON_NAME
        ) == [
            x509.NameAttribute(
                x509.oid.NameOID.COMMON_NAME, "Amazon Root CA 2"
            )
        ]

    def test_load_pkcs7_unsupported_type(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_SERIALIZATION):
            load_vectors_from_file(
                os.path.join("pkcs7", "enveloped.pem"),
                lambda pemfile: pkcs7.load_pem_pkcs7_certificates(
                    pemfile.read()
                ),
                mode="rb",
            )

    def test_load_pkcs7_empty_certificates(self):
        der = b"\x30\x0b\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x07\x02"

        with pytest.raises(ValueError):
            pkcs7.load_der_pkcs7_certificates(der)


def _load_cert_key():
    key = load_vectors_from_file(
        os.path.join("x509", "custom", "ca", "ca_key.pem"),
        lambda pemfile: serialization.load_pem_private_key(
            pemfile.read(), None, unsafe_skip_rsa_key_validation=True
        ),
        mode="rb",
    )
    cert = load_vectors_from_file(
        os.path.join("x509", "custom", "ca", "ca.pem"),
        loader=lambda pemfile: x509.load_pem_x509_certificate(pemfile.read()),
        mode="rb",
    )
    return cert, key


@pytest.mark.supported(
    only_if=lambda backend: backend.pkcs7_supported(),
    skip_message="Requires OpenSSL with PKCS7 support",
)
class TestPKCS7SignatureBuilder:
    def test_invalid_data(self, backend):
        builder = pkcs7.PKCS7SignatureBuilder()
        with pytest.raises(TypeError):
            builder.set_data("not bytes")  # type: ignore[arg-type]

    def test_set_data_twice(self, backend):
        builder = pkcs7.PKCS7SignatureBuilder().set_data(b"test")
        with pytest.raises(ValueError):
            builder.set_data(b"test")

    def test_sign_no_signer(self, backend):
        builder = pkcs7.PKCS7SignatureBuilder().set_data(b"test")
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.SMIME, [])

    def test_sign_no_data(self, backend):
        cert, key = _load_cert_key()
        builder = pkcs7.PKCS7SignatureBuilder().add_signer(
            cert, key, hashes.SHA256()
        )
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.SMIME, [])

    def test_unsupported_hash_alg(self, backend):
        cert, key = _load_cert_key()
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_signer(
                cert,
                key,
                hashes.SHA512_256(),  # type: ignore[arg-type]
            )

    def test_not_a_cert(self, backend):
        _, key = _load_cert_key()
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_signer(
                b"notacert",  # type: ignore[arg-type]
                key,
                hashes.SHA256(),
            )

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Does not support ed25519.",
    )
    def test_unsupported_key_type(self, backend):
        cert, _ = _load_cert_key()
        key = ed25519.Ed25519PrivateKey.generate()
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_signer(
                cert,
                key,  # type: ignore[arg-type]
                hashes.SHA256(),
            )

    def test_sign_invalid_options(self, backend):
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"test")
            .add_signer(cert, key, hashes.SHA256())
        )
        with pytest.raises(ValueError):
            builder.sign(
                serialization.Encoding.SMIME,
                [b"invalid"],  # type: ignore[list-item]
            )

    def test_sign_invalid_encoding(self, backend):
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"test")
            .add_signer(cert, key, hashes.SHA256())
        )
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.Raw, [])

    def test_sign_invalid_options_text_no_detached(self, backend):
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"test")
            .add_signer(cert, key, hashes.SHA256())
        )
        options = [pkcs7.PKCS7Options.Text]
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.SMIME, options)

    def test_sign_invalid_options_text_der_encoding(self, backend):
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"test")
            .add_signer(cert, key, hashes.SHA256())
        )
        options = [
            pkcs7.PKCS7Options.Text,
            pkcs7.PKCS7Options.DetachedSignature,
        ]
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.DER, options)

    def test_sign_invalid_options_no_attrs_and_no_caps(self, backend):
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(b"test")
            .add_signer(cert, key, hashes.SHA256())
        )
        options = [
            pkcs7.PKCS7Options.NoAttributes,
            pkcs7.PKCS7Options.NoCapabilities,
        ]
        with pytest.raises(ValueError):
            builder.sign(serialization.Encoding.SMIME, options)

    def test_smime_sign_detached(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        options = [pkcs7.PKCS7Options.DetachedSignature]
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig = builder.sign(serialization.Encoding.SMIME, options)
        sig_binary = builder.sign(serialization.Encoding.DER, options)
        assert b"text/plain" not in sig
        # We don't have a generic ASN.1 parser available to us so we instead
        # will assert on specific byte sequences being present based on the
        # parameters chosen above.
        assert b"sha-256" in sig
        # Detached signature means that the signed data is *not* embedded into
        # the PKCS7 structure itself, but is present in the SMIME serialization
        # as a separate section before the PKCS7 data. So we should expect to
        # have data in sig but not in sig_binary
        assert data in sig
        # Parse the message to get the signed data, which is the
        # first payload in the message
        message = email.parser.BytesParser().parsebytes(sig)
        payload = message.get_payload()
        assert isinstance(payload, list)
        assert isinstance(payload[0], email.message.Message)
        signed_data = payload[0].get_payload()
        assert isinstance(signed_data, str)
        test_support.pkcs7_verify(
            serialization.Encoding.SMIME,
            sig,
            signed_data.encode(),
            [cert],
            options,
        )
        assert data not in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            data,
            [cert],
            options,
        )

    def test_sign_byteslike(self, backend):
        data = bytearray(b"hello world")
        cert, key = _load_cert_key()
        options = [pkcs7.PKCS7Options.DetachedSignature]
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig = builder.sign(serialization.Encoding.SMIME, options)
        assert bytes(data) in sig
        test_support.pkcs7_verify(
            serialization.Encoding.SMIME,
            sig,
            data,
            [cert],
            options,
        )

        data = bytearray(b"")
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig = builder.sign(serialization.Encoding.SMIME, options)
        test_support.pkcs7_verify(
            serialization.Encoding.SMIME,
            sig,
            data,
            [cert],
            options,
        )

    def test_sign_pem(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        options: typing.List[pkcs7.PKCS7Options] = []
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig = builder.sign(serialization.Encoding.PEM, options)
        test_support.pkcs7_verify(
            serialization.Encoding.PEM,
            sig,
            None,
            [cert],
            options,
        )

    @pytest.mark.parametrize(
        ("hash_alg", "expected_value"),
        [
            (hashes.SHA256(), b"\x06\t`\x86H\x01e\x03\x04\x02\x01"),
            (hashes.SHA384(), b"\x06\t`\x86H\x01e\x03\x04\x02\x02"),
            (hashes.SHA512(), b"\x06\t`\x86H\x01e\x03\x04\x02\x03"),
        ],
    )
    def test_sign_alternate_digests_der(
        self, hash_alg, expected_value, backend
    ):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hash_alg)
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        assert expected_value in sig
        test_support.pkcs7_verify(
            serialization.Encoding.DER, sig, None, [cert], options
        )

    @pytest.mark.parametrize(
        ("hash_alg", "expected_value"),
        [
            (hashes.SHA256(), b"sha-256"),
            (hashes.SHA384(), b"sha-384"),
            (hashes.SHA512(), b"sha-512"),
        ],
    )
    def test_sign_alternate_digests_detached(
        self, hash_alg, expected_value, backend
    ):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hash_alg)
        )
        options = [pkcs7.PKCS7Options.DetachedSignature]
        sig = builder.sign(serialization.Encoding.SMIME, options)
        # When in detached signature mode the hash algorithm is stored as a
        # byte string like "sha-384".
        assert expected_value in sig

    def test_sign_attached(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        options: typing.List[pkcs7.PKCS7Options] = []
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig_binary = builder.sign(serialization.Encoding.DER, options)
        # When not passing detached signature the signed data is embedded into
        # the PKCS7 structure itself
        assert data in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            options,
        )

    def test_sign_binary(self, backend):
        data = b"hello\nworld"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig_no_binary = builder.sign(serialization.Encoding.DER, options)
        sig_binary = builder.sign(
            serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary]
        )
        # Binary prevents translation of LF to CR+LF (SMIME canonical form)
        # so data should not be present in sig_no_binary, but should be present
        # in sig_binary
        assert data not in sig_no_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_no_binary,
            None,
            [cert],
            options,
        )
        assert data in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            options,
        )

    def test_sign_smime_canonicalization(self, backend):
        data = b"hello\nworld"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        options: typing.List[pkcs7.PKCS7Options] = []
        sig_binary = builder.sign(serialization.Encoding.DER, options)
        # LF gets converted to CR+LF (SMIME canonical form)
        # so data should not be present in the sig
        assert data not in sig_binary
        assert b"hello\r\nworld" in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            options,
        )

    def test_sign_text(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        options = [
            pkcs7.PKCS7Options.Text,
            pkcs7.PKCS7Options.DetachedSignature,
        ]
        sig_pem = builder.sign(serialization.Encoding.SMIME, options)
        # The text option adds text/plain headers to the S/MIME message
        # These headers are only relevant in SMIME mode, not binary, which is
        # just the PKCS7 structure itself.
        assert sig_pem.count(b"text/plain") == 1
        assert b"Content-Type: text/plain\r\n\r\nhello world\r\n" in sig_pem
        # Parse the message to get the signed data, which is the
        # first payload in the message
        message = email.parser.BytesParser().parsebytes(sig_pem)
        payload = message.get_payload()
        assert isinstance(payload, list)
        assert isinstance(payload[0], email.message.Message)
        signed_data = payload[0].as_bytes(
            policy=message.policy.clone(linesep="\r\n")
        )
        test_support.pkcs7_verify(
            serialization.Encoding.SMIME,
            sig_pem,
            signed_data,
            [cert],
            options,
        )

    def test_smime_capabilities(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        sig_binary = builder.sign(serialization.Encoding.DER, [])

        # 1.2.840.113549.1.9.15 (SMIMECapabilities) as an ASN.1 DER encoded OID
        assert b"\x06\t*\x86H\x86\xf7\r\x01\t\x0f" in sig_binary

        # 2.16.840.1.101.3.4.1.42 (aes256-CBC-PAD) as an ASN.1 DER encoded OID
        aes256_cbc_pad_oid = b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x2a"
        # 2.16.840.1.101.3.4.1.22 (aes192-CBC-PAD) as an ASN.1 DER encoded OID
        aes192_cbc_pad_oid = b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x16"
        # 2.16.840.1.101.3.4.1.2 (aes128-CBC-PAD) as an ASN.1 DER encoded OID
        aes128_cbc_pad_oid = b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x02"

        # Each algorithm in SMIMECapabilities should be inside its own
        # SEQUENCE.
        # This is encoded as SEQUENCE_IDENTIFIER + LENGTH + ALGORITHM_OID.
        # This tests that each algorithm is indeed encoded inside its own
        # sequence. See RFC 2633, Appendix A for more details.
        sequence_identifier = b"\x30"
        for oid in [
            aes256_cbc_pad_oid,
            aes192_cbc_pad_oid,
            aes128_cbc_pad_oid,
        ]:
            len_oid = len(oid).to_bytes(length=1, byteorder="big")
            assert sequence_identifier + len_oid + oid in sig_binary

        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            [],
        )

    def test_sign_no_capabilities(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        options = [pkcs7.PKCS7Options.NoCapabilities]
        sig_binary = builder.sign(serialization.Encoding.DER, options)
        # NoCapabilities removes the SMIMECapabilities attribute from the
        # PKCS7 structure. This is an ASN.1 sequence with the
        # OID 1.2.840.113549.1.9.15. It does NOT remove all authenticated
        # attributes, so we verify that by looking for the signingTime OID.

        # 1.2.840.113549.1.9.15 SMIMECapabilities as an ASN.1 DER encoded OID
        assert b"\x06\t*\x86H\x86\xf7\r\x01\t\x0f" not in sig_binary
        # 1.2.840.113549.1.9.5 signingTime as an ASN.1 DER encoded OID
        assert b"\x06\t*\x86H\x86\xf7\r\x01\t\x05" in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            options,
        )

    def test_sign_no_attributes(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        options = [pkcs7.PKCS7Options.NoAttributes]
        sig_binary = builder.sign(serialization.Encoding.DER, options)
        # NoAttributes removes all authenticated attributes, so we shouldn't
        # find SMIMECapabilities or signingTime.

        # 1.2.840.113549.1.9.15 SMIMECapabilities as an ASN.1 DER encoded OID
        assert b"\x06\t*\x86H\x86\xf7\r\x01\t\x0f" not in sig_binary
        # 1.2.840.113549.1.9.5 signingTime as an ASN.1 DER encoded OID
        assert b"\x06\t*\x86H\x86\xf7\r\x01\t\x05" not in sig_binary
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig_binary,
            None,
            [cert],
            options,
        )

    def test_sign_no_certs(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA256())
        )

        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        assert sig.count(cert.public_bytes(serialization.Encoding.DER)) == 1

        options = [pkcs7.PKCS7Options.NoCerts]
        sig_no = builder.sign(serialization.Encoding.DER, options)
        assert sig_no.count(cert.public_bytes(serialization.Encoding.DER)) == 0

    @pytest.mark.parametrize(
        "pad",
        [
            padding.PKCS1v15(),
            None,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA512()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
        ],
    )
    def test_rsa_pkcs_padding_options(self, pad, backend):
        data = b"hello world"
        rsa_key = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_key.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read(), None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        assert isinstance(rsa_key, rsa.RSAPrivateKey)
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(rsa_cert, rsa_key, hashes.SHA512(), rsa_padding=pad)
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        # This should be a pkcs1 sha512 signature
        if isinstance(pad, padding.PSS):
            # PKCS7_verify can't verify a PSS sig and we don't bind CMS so
            # we instead just check that a few things are present in the
            # output.
            # There should be four SHA512 OIDs in this structure
            assert sig.count(b"\x06\t`\x86H\x01e\x03\x04\x02\x03") == 4
            # There should be one MGF1 OID in this structure
            assert (
                sig.count(b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x08") == 1
            )
        else:
            # This should be a pkcs1 RSA signature, which uses the
            # `rsaEncryption` OID (1.2.840.113549.1.1.1) no matter which
            # digest algorithm is used.
            # See RFC 3370 section 3.2 for more details.
            # This OID appears twice, once in the certificate itself and
            # another in the SignerInfo data structure in the
            # `digest_encryption_algorithm` field.
            assert (
                sig.count(b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01") == 2
            )
            test_support.pkcs7_verify(
                serialization.Encoding.DER,
                sig,
                None,
                [rsa_cert],
                options,
            )

    def test_not_rsa_key_with_padding(self, backend):
        cert, key = _load_cert_key()
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_signer(
                cert, key, hashes.SHA512(), rsa_padding=padding.PKCS1v15()
            )

    def test_rsa_invalid_padding(self, backend):
        rsa_key = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_key.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read(), None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        assert isinstance(rsa_key, rsa.RSAPrivateKey)
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_signer(
                rsa_cert,
                rsa_key,
                hashes.SHA512(),
                rsa_padding=object(),  # type: ignore[arg-type]
            )

    def test_multiple_signers(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        rsa_key = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_key.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read(), None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        assert isinstance(rsa_key, rsa.RSAPrivateKey)
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA512())
            .add_signer(rsa_cert, rsa_key, hashes.SHA512())
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        # There should be three SHA512 OIDs in this structure
        assert sig.count(b"\x06\t`\x86H\x01e\x03\x04\x02\x03") == 3
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig,
            None,
            [cert, rsa_cert],
            options,
        )

    def test_multiple_signers_different_hash_algs(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        rsa_key = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_key.pem"),
            lambda pemfile: serialization.load_pem_private_key(
                pemfile.read(), None, unsafe_skip_rsa_key_validation=True
            ),
            mode="rb",
        )
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        assert isinstance(rsa_key, rsa.RSAPrivateKey)
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA384())
            .add_signer(rsa_cert, rsa_key, hashes.SHA512())
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        # There should be two SHA384 and two SHA512 OIDs in this structure
        assert sig.count(b"\x06\t`\x86H\x01e\x03\x04\x02\x02") == 2
        assert sig.count(b"\x06\t`\x86H\x01e\x03\x04\x02\x03") == 2
        test_support.pkcs7_verify(
            serialization.Encoding.DER,
            sig,
            None,
            [cert, rsa_cert],
            options,
        )

    def test_add_additional_cert_not_a_cert(self, backend):
        with pytest.raises(TypeError):
            pkcs7.PKCS7SignatureBuilder().add_certificate(
                b"notacert"  # type: ignore[arg-type]
            )

    def test_add_additional_cert(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA384())
            .add_certificate(rsa_cert)
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        assert (
            sig.count(rsa_cert.public_bytes(serialization.Encoding.DER)) == 1
        )

    def test_add_multiple_additional_certs(self, backend):
        data = b"hello world"
        cert, key = _load_cert_key()
        rsa_cert = load_vectors_from_file(
            os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
            loader=lambda pemfile: x509.load_pem_x509_certificate(
                pemfile.read()
            ),
            mode="rb",
        )
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(data)
            .add_signer(cert, key, hashes.SHA384())
            .add_certificate(rsa_cert)
            .add_certificate(rsa_cert)
        )
        options: typing.List[pkcs7.PKCS7Options] = []
        sig = builder.sign(serialization.Encoding.DER, options)
        assert (
            sig.count(rsa_cert.public_bytes(serialization.Encoding.DER)) == 2
        )


def _load_rsa_cert_key():
    key = load_vectors_from_file(
        os.path.join("x509", "custom", "ca", "rsa_key.pem"),
        lambda pemfile: serialization.load_pem_private_key(
            pemfile.read(), None, unsafe_skip_rsa_key_validation=True
        ),
        mode="rb",
    )
    cert = load_vectors_from_file(
        os.path.join("x509", "custom", "ca", "rsa_ca.pem"),
        loader=lambda pemfile: x509.load_pem_x509_certificate(pemfile.read()),
        mode="rb",
    )
    return cert, key


@pytest.mark.supported(
    only_if=lambda backend: backend.pkcs7_supported()
    and backend.rsa_encryption_supported(padding.PKCS1v15()),
    skip_message="Requires OpenSSL with PKCS7 support and PKCS1 v1.5 padding "
    "support",
)
class TestPKCS7EnvelopeBuilder:
    def test_invalid_data(self, backend):
        builder = pkcs7.PKCS7EnvelopeBuilder()
        with pytest.raises(TypeError):
            builder.set_data("not bytes")  # type: ignore[arg-type]

    def test_set_data_twice(self, backend):
        builder = pkcs7.PKCS7EnvelopeBuilder().set_data(b"test")
        with pytest.raises(ValueError):
            builder.set_data(b"test")

    def test_encrypt_no_recipient(self, backend):
        builder = pkcs7.PKCS7EnvelopeBuilder().set_data(b"test")
        with pytest.raises(ValueError):
            builder.encrypt(serialization.Encoding.SMIME, [])

    def test_encrypt_no_data(self, backend):
        cert, _ = _load_rsa_cert_key()
        builder = pkcs7.PKCS7EnvelopeBuilder().add_recipient(cert)
        with pytest.raises(ValueError):
            builder.encrypt(serialization.Encoding.SMIME, [])

    def test_unsupported_encryption(self, backend):
        cert_non_rsa, _ = _load_cert_key()
        with pytest.raises(TypeError):
            pkcs7.PKCS7EnvelopeBuilder().add_recipient(cert_non_rsa)

    def test_not_a_cert(self, backend):
        with pytest.raises(TypeError):
            pkcs7.PKCS7EnvelopeBuilder().add_recipient(
                b"notacert",  # type: ignore[arg-type]
            )

    def test_encrypt_invalid_options(self, backend):
        cert, _ = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(b"test").add_recipient(cert)
        )
        with pytest.raises(ValueError):
            builder.encrypt(
                serialization.Encoding.SMIME,
                [b"invalid"],  # type: ignore[list-item]
            )

    def test_encrypt_invalid_encoding(self, backend):
        cert, _ = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(b"test").add_recipient(cert)
        )
        with pytest.raises(ValueError):
            builder.encrypt(serialization.Encoding.Raw, [])

    @pytest.mark.parametrize(
        "invalid_options",
        [
            [pkcs7.PKCS7Options.NoAttributes],
            [pkcs7.PKCS7Options.NoCapabilities],
            [pkcs7.PKCS7Options.NoCerts],
            [pkcs7.PKCS7Options.DetachedSignature],
            [pkcs7.PKCS7Options.Binary, pkcs7.PKCS7Options.Text],
        ],
    )
    def test_encrypt_invalid_encryption_options(
        self, backend, invalid_options
    ):
        cert, _ = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(b"test").add_recipient(cert)
        )
        with pytest.raises(ValueError):
            builder.encrypt(serialization.Encoding.DER, invalid_options)

    @pytest.mark.parametrize(
        "options",
        [
            [pkcs7.PKCS7Options.Text],
            [pkcs7.PKCS7Options.Binary],
        ],
    )
    def test_smime_encrypt_smime_encoding(self, backend, options):
        data = b"hello world\n"
        cert, private_key = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(data).add_recipient(cert)
        )
        enveloped = builder.encrypt(serialization.Encoding.SMIME, options)
        assert b"MIME-Version: 1.0\n" in enveloped
        assert b"Content-Transfer-Encoding: base64\n" in enveloped
        message = email.parser.BytesParser().parsebytes(enveloped)
        assert message.get_content_disposition() == "attachment"
        assert message.get_filename() == "smime.p7m"
        assert message.get_content_type() == "application/pkcs7-mime"
        assert message.get_param("smime-type") == "enveloped-data"
        assert message.get_param("name") == "smime.p7m"

        payload = message.get_payload(decode=True)
        assert isinstance(payload, bytes)

        # We want to know if we've serialized something that has the parameters
        # we expect, so we match on specific byte strings of OIDs & DER values.
        # OID 2.16.840.1.101.3.4.1.2 (aes128-CBC)
        assert b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x02" in payload
        # OID 1.2.840.113549.1.1.1 (rsaEncryption (PKCS #1))
        assert b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01" in payload
        # cryptography CA (the recipient's Common Name)
        assert (
            b"\x0c\x0f\x63\x72\x79\x70\x74\x6f\x67\x72\x61\x70\x68\x79"
            b"\x20\x43\x41"
        ) in payload

        decrypted_bytes = test_support.pkcs7_decrypt(
            serialization.Encoding.SMIME,
            enveloped,
            private_key,
            cert,
            options,
        )
        # New lines are canonicalized to '\r\n' when not using Binary
        expected_data = (
            data
            if pkcs7.PKCS7Options.Binary in options
            else data.replace(b"\n", b"\r\n")
        )
        assert decrypted_bytes == expected_data

    @pytest.mark.parametrize(
        "options",
        [
            [pkcs7.PKCS7Options.Text],
            [pkcs7.PKCS7Options.Binary],
        ],
    )
    def test_smime_encrypt_der_encoding(self, backend, options):
        data = b"hello world\n"
        cert, private_key = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(data).add_recipient(cert)
        )
        enveloped = builder.encrypt(serialization.Encoding.DER, options)

        # We want to know if we've serialized something that has the parameters
        # we expect, so we match on specific byte strings of OIDs & DER values.
        # OID 2.16.840.1.101.3.4.1.2 (aes128-CBC)
        assert b"\x06\x09\x60\x86\x48\x01\x65\x03\x04\x01\x02" in enveloped
        # OID 1.2.840.113549.1.1.1 (rsaEncryption (PKCS #1))
        assert b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01" in enveloped
        # cryptography CA (the recipient's Common Name)
        assert (
            b"\x0c\x0f\x63\x72\x79\x70\x74\x6f\x67\x72\x61\x70\x68\x79"
            b"\x20\x43\x41"
        ) in enveloped

        decrypted_bytes = test_support.pkcs7_decrypt(
            serialization.Encoding.DER,
            enveloped,
            private_key,
            cert,
            options,
        )
        # New lines are canonicalized to '\r\n' when not using Binary
        expected_data = (
            data
            if pkcs7.PKCS7Options.Binary in options
            else data.replace(b"\n", b"\r\n")
        )
        assert decrypted_bytes == expected_data

    @pytest.mark.parametrize(
        "options",
        [
            [pkcs7.PKCS7Options.Text],
            [pkcs7.PKCS7Options.Binary],
        ],
    )
    def test_smime_encrypt_pem_encoding(self, backend, options):
        data = b"hello world\n"
        cert, private_key = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder().set_data(data).add_recipient(cert)
        )
        enveloped = builder.encrypt(serialization.Encoding.PEM, options)
        decrypted_bytes = test_support.pkcs7_decrypt(
            serialization.Encoding.PEM,
            enveloped,
            private_key,
            cert,
            options,
        )
        # New lines are canonicalized to '\r\n' when not using Binary
        expected_data = (
            data
            if pkcs7.PKCS7Options.Binary in options
            else data.replace(b"\n", b"\r\n")
        )
        assert decrypted_bytes == expected_data

    def test_smime_encrypt_multiple_recipients(self, backend):
        data = b"hello world\n"
        cert, _ = _load_rsa_cert_key()
        builder = (
            pkcs7.PKCS7EnvelopeBuilder()
            .set_data(data)
            .add_recipient(cert)
            .add_recipient(cert)
        )
        enveloped = builder.encrypt(serialization.Encoding.DER, [])
        # cryptography CA (the recipient's Common Name)
        common_name_bytes = (
            b"\x0c\x0f\x63\x72\x79\x70\x74\x6f\x67\x72\x61"
            b"\x70\x68\x79\x20\x43\x41"
        )
        assert enveloped.count(common_name_bytes) == 2


@pytest.mark.supported(
    only_if=lambda backend: backend.pkcs7_supported(),
    skip_message="Requires OpenSSL with PKCS7 support",
)
class TestPKCS7SerializeCerts:
    @pytest.mark.parametrize(
        ("encoding", "loader"),
        [
            (serialization.Encoding.PEM, pkcs7.load_pem_pkcs7_certificates),
            (serialization.Encoding.DER, pkcs7.load_der_pkcs7_certificates),
        ],
    )
    def test_roundtrip(self, encoding, loader, backend):
        certs = load_vectors_from_file(
            os.path.join("pkcs7", "amazon-roots.der"),
            lambda derfile: pkcs7.load_der_pkcs7_certificates(derfile.read()),
            mode="rb",
        )
        p7 = pkcs7.serialize_certificates(certs, encoding)
        certs2 = loader(p7)
        assert certs == certs2

    def test_ordering(self, backend):
        certs = load_vectors_from_file(
            os.path.join("pkcs7", "amazon-roots.der"),
            lambda derfile: pkcs7.load_der_pkcs7_certificates(derfile.read()),
            mode="rb",
        )
        p7 = pkcs7.serialize_certificates(
            list(reversed(certs)), serialization.Encoding.DER
        )
        certs2 = pkcs7.load_der_pkcs7_certificates(p7)
        assert certs == certs2

    def test_pem_matches_vector(self, backend):
        p7_pem = load_vectors_from_file(
            os.path.join("pkcs7", "isrg.pem"),
            lambda p: p.read(),
            mode="rb",
        )
        certs = pkcs7.load_pem_pkcs7_certificates(p7_pem)
        p7 = pkcs7.serialize_certificates(certs, serialization.Encoding.PEM)
        assert p7 == p7_pem

    def test_der_matches_vector(self, backend):
        p7_der = load_vectors_from_file(
            os.path.join("pkcs7", "amazon-roots.der"),
            lambda p: p.read(),
            mode="rb",
        )
        certs = pkcs7.load_der_pkcs7_certificates(p7_der)
        p7 = pkcs7.serialize_certificates(certs, serialization.Encoding.DER)
        assert p7 == p7_der

    def test_invalid_types(self):
        certs = load_vectors_from_file(
            os.path.join("pkcs7", "amazon-roots.der"),
            lambda derfile: pkcs7.load_der_pkcs7_certificates(derfile.read()),
            mode="rb",
        )
        with pytest.raises(TypeError):
            pkcs7.serialize_certificates(
                object(),  # type: ignore[arg-type]
                serialization.Encoding.PEM,
            )

        with pytest.raises(TypeError):
            pkcs7.serialize_certificates([], serialization.Encoding.PEM)

        with pytest.raises(TypeError):
            pkcs7.serialize_certificates(
                certs,
                "not an encoding",  # type: ignore[arg-type]
            )


@pytest.mark.supported(
    only_if=lambda backend: not backend.pkcs7_supported(),
    skip_message="Requires OpenSSL without PKCS7 support (BoringSSL)",
)
class TestPKCS7Unsupported:
    def test_pkcs7_functions_unsupported(self):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_SERIALIZATION):
            pkcs7.load_der_pkcs7_certificates(b"nonsense")

        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_SERIALIZATION):
            pkcs7.load_pem_pkcs7_certificates(b"nonsense")


@pytest.mark.supported(
    only_if=lambda backend: backend.pkcs7_supported()
    and not backend.rsa_encryption_supported(padding.PKCS1v15()),
    skip_message="Requires OpenSSL with no PKCS1 v1.5 padding support",
)
class TestPKCS7EnvelopeBuilderUnsupported:
    def test_envelope_builder_unsupported(self, backend):
        with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_PADDING):
            pkcs7.PKCS7EnvelopeBuilder()
