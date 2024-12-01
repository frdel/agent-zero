# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import base64
import datetime
import os

import pytest

from cryptography import utils
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric import (
    dsa,
    ec,
    ed25519,
    rsa,
)
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    KeySerializationEncryption,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    SSHCertificate,
    SSHCertificateBuilder,
    SSHCertificateType,
    load_pem_private_key,
    load_ssh_private_key,
    load_ssh_public_identity,
    load_ssh_public_key,
    ssh,
)

from ...doubles import DummyKeySerializationEncryption
from ...utils import load_vectors_from_file, raises_unsupported_algorithm
from .fixtures_rsa import RSA_KEY_2048
from .test_ec import _skip_curve_unsupported
from .test_rsa import rsa_key_2048

__all__ = ["rsa_key_2048"]


class TestOpenSSHSerialization:
    @pytest.mark.parametrize(
        ("key_file", "cert_file"),
        [
            ("rsa-psw.key.pub", None),
            ("rsa-nopsw.key.pub", "rsa-nopsw.key-cert.pub"),
            ("dsa-psw.key.pub", None),
            ("dsa-nopsw.key.pub", "dsa-nopsw.key-cert.pub"),
            ("ecdsa-psw.key.pub", None),
            ("ecdsa-nopsw.key.pub", "ecdsa-nopsw.key-cert.pub"),
            ("ed25519-psw.key.pub", None),
            ("ed25519-nopsw.key.pub", "ed25519-nopsw.key-cert.pub"),
            ("sk-ecdsa-psw.key.pub", None),
            ("sk-ecdsa-nopsw.key.pub", None),
            ("sk-ed25519-psw.key.pub", None),
            ("sk-ed25519-nopsw.key.pub", None),
        ],
    )
    def test_load_ssh_public_key(self, key_file, cert_file, backend):
        if "ed25519" in key_file and not backend.ed25519_supported():
            pytest.skip("Requires OpenSSL with Ed25519 support")

        # normal public key
        pub_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", key_file),
            lambda f: f.read(),
            mode="rb",
        )
        nocomment_data = b" ".join(pub_data.split()[:2])
        if key_file.startswith("dsa"):
            with pytest.warns(utils.DeprecatedIn40):
                public_key = load_ssh_public_key(pub_data, backend)
            with pytest.warns(utils.DeprecatedIn40):
                assert (
                    public_key.public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )
        else:
            public_key = load_ssh_public_key(pub_data, backend)
            if not key_file.startswith("sk-"):
                # SK keys do not round-trip
                assert (
                    public_key.public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )

        self.run_partial_pubkey(pub_data, backend)

        # parse public key with ssh certificate
        if cert_file:
            cert_data = load_vectors_from_file(
                os.path.join("asymmetric", "OpenSSH", cert_file),
                lambda f: f.read(),
                mode="rb",
            )
            if cert_file.startswith("dsa"):
                with pytest.warns(utils.DeprecatedIn40):
                    cert_key = load_ssh_public_key(cert_data, backend)
                with pytest.warns(utils.DeprecatedIn40):
                    assert (
                        cert_key.public_bytes(
                            Encoding.OpenSSH, PublicFormat.OpenSSH
                        )
                        == nocomment_data
                    )
            else:
                cert_key = load_ssh_public_key(cert_data, backend)
                assert (
                    cert_key.public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )

            # try with more spaces
            cert_data = b" \t ".join(cert_data.split())
            if cert_file.startswith("dsa"):
                with pytest.warns(utils.DeprecatedIn40):
                    cert_key = load_ssh_public_key(cert_data, backend)
                with pytest.warns(utils.DeprecatedIn40):
                    assert (
                        cert_key.public_bytes(
                            Encoding.OpenSSH, PublicFormat.OpenSSH
                        )
                        == nocomment_data
                    )
            else:
                cert_key = load_ssh_public_key(cert_data, backend)
                assert (
                    cert_key.public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )

            self.run_partial_pubkey(cert_data, backend)

    def run_partial_pubkey(self, pubdata, backend):
        parts = pubdata.split()
        raw = base64.b64decode(parts[1])
        for i in range(1, len(raw)):
            frag = base64.b64encode(raw[:i])
            new_pub = b" ".join([parts[0], frag])
            with pytest.raises(ValueError):
                load_ssh_public_key(new_pub, backend)

    @pytest.mark.parametrize(
        ("key_file",),
        [
            ("rsa-nopsw.key",),
            ("rsa-psw.key",),
            ("dsa-nopsw.key",),
            ("dsa-psw.key",),
            ("ecdsa-nopsw.key",),
            ("ecdsa-psw.key",),
            ("ed25519-nopsw.key",),
            ("ed25519-psw.key",),
            ("ed25519-aesgcm-psw.key",),
        ],
    )
    def test_load_ssh_private_key(self, key_file, backend):
        if "ed25519" in key_file and not backend.ed25519_supported():
            pytest.skip("Requires OpenSSL with Ed25519 support")
        if "-psw" in key_file and not ssh._bcrypt_supported:
            pytest.skip("Requires bcrypt module")

        # read public and private key from ssh-keygen
        priv_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", key_file),
            lambda f: f.read(),
            mode="rb",
        )
        pub_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", key_file + ".pub"),
            lambda f: f.read(),
            mode="rb",
        )
        nocomment_data = b" ".join(pub_data.split()[:2])

        # load and compare
        password = None
        if "-psw" in key_file:
            password = b"password"
        for data in [
            priv_data,
            bytearray(priv_data),
            memoryview(priv_data),
            memoryview(bytearray(priv_data)),
        ]:
            if key_file.startswith("dsa"):
                with pytest.warns(utils.DeprecatedIn40):
                    private_key = load_ssh_private_key(data, password, backend)
                with pytest.warns(utils.DeprecatedIn40):
                    assert (
                        private_key.public_key().public_bytes(
                            Encoding.OpenSSH, PublicFormat.OpenSSH
                        )
                        == nocomment_data
                    )
            else:
                private_key = load_ssh_private_key(data, password, backend)
                assert (
                    private_key.public_key().public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )

        # serialize with own code and reload
        encryption: KeySerializationEncryption = NoEncryption()
        if password:
            encryption = BestAvailableEncryption(password)
        if key_file.startswith("dsa"):
            with pytest.warns(utils.DeprecatedIn40):
                priv_data2 = private_key.private_bytes(
                    Encoding.PEM,
                    PrivateFormat.OpenSSH,
                    encryption,
                )
            with pytest.warns(utils.DeprecatedIn40):
                private_key2 = load_ssh_private_key(
                    priv_data2, password, backend
                )
            with pytest.warns(utils.DeprecatedIn40):
                assert (
                    private_key2.public_key().public_bytes(
                        Encoding.OpenSSH, PublicFormat.OpenSSH
                    )
                    == nocomment_data
                )
        else:
            priv_data2 = private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.OpenSSH,
                encryption,
            )
            private_key2 = load_ssh_private_key(priv_data2, password, backend)
            assert (
                private_key2.public_key().public_bytes(
                    Encoding.OpenSSH, PublicFormat.OpenSSH
                )
                == nocomment_data
            )

        # make sure multi-line base64 is used
        maxline = max(map(len, priv_data2.split(b"\n")))
        assert maxline < 80

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires Ed25519 support",
    )
    @pytest.mark.supported(
        only_if=lambda backend: ssh._bcrypt_supported,
        skip_message="Requires that bcrypt exists",
    )
    def test_load_ssh_private_key_invalid_tag(self, backend):
        priv_data = bytearray(
            load_vectors_from_file(
                os.path.join(
                    "asymmetric", "OpenSSH", "ed25519-aesgcm-psw.key"
                ),
                lambda f: f.read(),
                mode="rb",
            )
        )
        # mutate one byte to break the tag
        priv_data[-38] = 82
        with pytest.raises(InvalidTag):
            load_ssh_private_key(priv_data, b"password")

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires Ed25519 support",
    )
    @pytest.mark.supported(
        only_if=lambda backend: ssh._bcrypt_supported,
        skip_message="Requires that bcrypt exists",
    )
    def test_load_ssh_private_key_tag_incorrect_length(self, backend):
        priv_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "ed25519-aesgcm-psw.key"),
            lambda f: f.read(),
            mode="rb",
        )
        # clip out a byte
        broken_data = priv_data[:-37] + priv_data[-38:]
        with pytest.raises(ValueError):
            load_ssh_private_key(broken_data, b"password")

    @pytest.mark.supported(
        only_if=lambda backend: ssh._bcrypt_supported,
        skip_message="Requires that bcrypt exists",
    )
    def test_bcrypt_encryption(self, backend):
        private_key = ec.generate_private_key(ec.SECP256R1(), backend)
        pub1 = private_key.public_key().public_bytes(
            Encoding.OpenSSH, PublicFormat.OpenSSH
        )

        for psw in (
            b"1",
            b"1234",
            b"1234" * 4,
            b"x" * 72,
        ):
            # BestAvailableEncryption does not handle bytes-like?
            best = BestAvailableEncryption(psw)
            encdata = private_key.private_bytes(
                Encoding.PEM, PrivateFormat.OpenSSH, best
            )
            decoded_key = load_ssh_private_key(encdata, psw, backend)
            pub2 = decoded_key.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
            assert pub1 == pub2

            # bytearray
            decoded_key2 = load_ssh_private_key(
                bytearray(encdata), psw, backend
            )
            pub2 = decoded_key2.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
            assert pub1 == pub2

            # memoryview(bytes)
            decoded_key2 = load_ssh_private_key(
                memoryview(encdata), psw, backend
            )
            pub2 = decoded_key2.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
            assert pub1 == pub2

            # memoryview(bytearray)
            decoded_key2 = load_ssh_private_key(
                memoryview(bytearray(encdata)), psw, backend
            )
            pub2 = decoded_key2.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )
            assert pub1 == pub2

            with pytest.raises(ValueError):
                decoded_key = load_ssh_private_key(encdata, None, backend)
            with pytest.raises(ValueError):
                decoded_key = load_ssh_private_key(encdata, b"wrong", backend)

    @pytest.mark.supported(
        only_if=lambda backend: not ssh._bcrypt_supported,
        skip_message="Requires that bcrypt is missing",
    )
    def test_missing_bcrypt(self, backend):
        priv_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "ecdsa-psw.key"),
            lambda f: f.read(),
            mode="rb",
        )
        with raises_unsupported_algorithm(None):
            load_ssh_private_key(priv_data, b"password", backend)

        private_key = ec.generate_private_key(ec.SECP256R1(), backend)
        with raises_unsupported_algorithm(None):
            private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.OpenSSH,
                BestAvailableEncryption(b"x"),
            )

    def test_fraglist_corners(self):
        f = ssh._FragList()
        with pytest.raises(ValueError):
            f.put_mpint(-1)
        f.put_mpint(0)
        f.put_mpint(0x80)
        assert f.tobytes() == b"\0\0\0\0" + b"\0\0\0\x02" + b"\0\x80"

    def make_file(
        self,
        magic=b"openssh-key-v1\0",
        ciphername=b"none",
        kdfname=b"none",
        kdfoptions=b"",
        nkeys=1,
        pub_type=b"ecdsa-sha2-nistp256",
        pub_fields=(
            b"nistp256",
            b"\x04" * 65,
        ),
        priv_type=None,
        priv_fields=(b"nistp256", b"\x04" * 65, b"\x7f" * 32),
        comment=b"comment",
        checkval1=b"1234",
        checkval2=b"1234",
        pad=None,
        header=b"-----BEGIN OPENSSH PRIVATE KEY-----\n",
        footer=b"-----END OPENSSH PRIVATE KEY-----\n",
        cut=8192,
    ):
        """Create private key file"""
        if not priv_type:
            priv_type = pub_type

        pub = ssh._FragList()
        for elem in (pub_type, *pub_fields):
            pub.put_sshstr(elem)

        secret = ssh._FragList([checkval1, checkval2])
        for i in range(nkeys):
            for elem in (priv_type, *priv_fields, comment):
                secret.put_sshstr(elem)

        if pad is None:
            pad_len = 8 - (secret.size() % 8)
            pad = bytearray(range(1, 1 + pad_len))
        secret.put_raw(pad)

        main = ssh._FragList([magic])
        main.put_sshstr(ciphername)
        main.put_sshstr(kdfname)
        main.put_sshstr(kdfoptions)
        main.put_u32(nkeys)
        for i in range(nkeys):
            main.put_sshstr(pub)
        main.put_sshstr(secret)

        res = main.tobytes()
        return ssh._ssh_pem_encode(res[:cut], header, footer)

    def test_ssh_make_file(self, backend):
        # check if works by default
        data = self.make_file()
        key = load_ssh_private_key(data, None, backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)

    def test_load_ssh_private_key_errors(self, backend):
        # bad kdf
        data = self.make_file(kdfname=b"unknown", ciphername=b"aes256-ctr")
        with raises_unsupported_algorithm(None):
            load_ssh_private_key(data, None, backend)

        # bad cipher
        data = self.make_file(ciphername=b"unknown", kdfname=b"bcrypt")
        with raises_unsupported_algorithm(None):
            load_ssh_private_key(data, None, backend)

        # bad magic
        data = self.make_file(magic=b"unknown")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # too few keys
        data = self.make_file(nkeys=0)
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # too many keys
        data = self.make_file(nkeys=2)
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    def test_ssh_errors_bad_values(self, backend):
        # bad curve
        data = self.make_file(pub_type=b"ecdsa-sha2-nistp444")
        with raises_unsupported_algorithm(None):
            load_ssh_private_key(data, None, backend)

        # curve mismatch
        data = self.make_file(priv_type=b"ecdsa-sha2-nistp384")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # invalid bigint
        data = self.make_file(
            priv_fields=(b"nistp256", b"\x04" * 65, b"\x80" * 32)
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    def test_ssh_errors_pubpriv_mismatch(self, backend):
        # ecdsa public-private mismatch
        data = self.make_file(
            pub_fields=(
                b"nistp256",
                b"\x04" + b"\x05" * 64,
            )
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # rsa public-private mismatch
        data = self.make_file(
            pub_type=b"ssh-rsa",
            pub_fields=(b"x" * 32,) * 2,
            priv_fields=(b"z" * 32,) * 6,
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # dsa public-private mismatch
        data = self.make_file(
            pub_type=b"ssh-dss",
            pub_fields=(b"x" * 32,) * 4,
            priv_fields=(b"z" * 32,) * 5,
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # ed25519 public-private mismatch
        sk = b"x" * 32
        pk1 = b"y" * 32
        pk2 = b"z" * 32
        data = self.make_file(
            pub_type=b"ssh-ed25519",
            pub_fields=(pk1,),
            priv_fields=(
                pk1,
                sk + pk2,
            ),
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)
        data = self.make_file(
            pub_type=b"ssh-ed25519",
            pub_fields=(pk1,),
            priv_fields=(
                pk2,
                sk + pk1,
            ),
        )
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    def test_ssh_errors_bad_wrapper(self, backend):
        # wrong header
        data = self.make_file(header=b"-----BEGIN RSA PRIVATE KEY-----\n")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # wring footer
        data = self.make_file(footer=b"-----END RSA PRIVATE KEY-----\n")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    def test_ssh_no_padding(self, backend):
        # no padding must work, if data is on block boundary
        data = self.make_file(pad=b"", comment=b"")
        key = load_ssh_private_key(data, None, backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)

        # no padding with right last byte
        data = self.make_file(pad=b"", comment=b"\x08" * 8)
        key = load_ssh_private_key(data, None, backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)

        # avoid unexpected padding removal
        data = self.make_file(pad=b"", comment=b"1234\x01\x02\x03\x04")
        key = load_ssh_private_key(data, None, backend)
        assert isinstance(key, ec.EllipticCurvePrivateKey)

        # bad padding with right size
        data = self.make_file(pad=b"\x08" * 8, comment=b"")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    def test_ssh_errors_bad_secrets(self, backend):
        # checkval mismatch
        data = self.make_file(checkval2=b"4321")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

        # bad padding, correct=1
        data = self.make_file(pad=b"\x01\x02")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)
        data = self.make_file(pad=b"")
        with pytest.raises(ValueError):
            load_ssh_private_key(data, None, backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.elliptic_curve_supported(
            ec.SECP192R1()
        ),
        skip_message="Requires backend support for ec.SECP192R1",
    )
    def test_serialize_ssh_private_key_errors_bad_curve(self, backend):
        private_key = ec.generate_private_key(ec.SECP192R1(), backend)
        with pytest.raises(ValueError):
            private_key.private_bytes(
                Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
            )

    def test_serialize_ssh_private_key_errors(
        self, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        # bad encoding
        private_key = ec.generate_private_key(ec.SECP256R1(), backend)
        with pytest.raises(ValueError):
            private_key.private_bytes(
                Encoding.DER, PrivateFormat.OpenSSH, NoEncryption()
            )

        # bad object type
        with pytest.raises(ValueError):
            ssh._serialize_ssh_private_key(
                object(),  # type:ignore[arg-type]
                b"",
                NoEncryption(),
            )

        private_key = ec.generate_private_key(ec.SECP256R1(), backend)

        # unknown encryption class
        with pytest.raises(ValueError):
            private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.OpenSSH,
                DummyKeySerializationEncryption(),
            )

        with pytest.raises(ValueError):
            rsa_key_2048.private_bytes(
                Encoding.DER, PrivateFormat.OpenSSH, NoEncryption()
            )

    @pytest.mark.supported(
        only_if=lambda backend: ssh._bcrypt_supported,
        skip_message="Requires that bcrypt exists",
    )
    @pytest.mark.parametrize(
        "password",
        (
            b"1234",
            b"p@ssw0rd",
            b"x" * 100,
        ),
    )
    @pytest.mark.parametrize(
        "kdf_rounds",
        [
            1,
            10,
            30,
        ],
    )
    def test_serialize_ssh_private_key_with_password(
        self, password, kdf_rounds, rsa_key_2048: rsa.RSAPrivateKey, backend
    ):
        for original_key in [
            ec.generate_private_key(ec.SECP256R1(), backend),
            rsa_key_2048,
        ]:
            assert isinstance(
                original_key, (ec.EllipticCurvePrivateKey, rsa.RSAPrivateKey)
            )
            encoded_key_data = original_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.OpenSSH,
                (
                    PrivateFormat.OpenSSH.encryption_builder()
                    .kdf_rounds(kdf_rounds)
                    .build(password)
                ),
            )

            decoded_key = load_ssh_private_key(
                data=encoded_key_data,
                password=password,
                backend=backend,
            )

            original_public_key = original_key.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )

            decoded_public_key = decoded_key.public_key().public_bytes(
                Encoding.OpenSSH, PublicFormat.OpenSSH
            )

            assert original_public_key == decoded_public_key

    @pytest.mark.supported(
        only_if=lambda backend: backend.dsa_supported(),
        skip_message="Does not support DSA.",
    )
    @pytest.mark.parametrize(
        ("key_path", "supported"),
        [
            (["Traditional_OpenSSL_Serialization", "dsa.1024.pem"], True),
            (["Traditional_OpenSSL_Serialization", "dsa.2048.pem"], False),
            (["Traditional_OpenSSL_Serialization", "dsa.3072.pem"], False),
        ],
    )
    def test_dsa_private_key_sizes(self, key_path, supported, backend):
        key = load_vectors_from_file(
            os.path.join("asymmetric", *key_path),
            lambda pemfile: load_pem_private_key(
                pemfile.read(), None, backend
            ),
            mode="rb",
        )
        assert isinstance(key, dsa.DSAPrivateKey)
        if supported:
            with pytest.warns(utils.DeprecatedIn40):
                res = key.private_bytes(
                    Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
                )
            assert isinstance(res, bytes)
        else:
            with pytest.raises(ValueError):
                with pytest.warns(utils.DeprecatedIn40):
                    key.private_bytes(
                        Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
                    )


class TestRSASSHSerialization:
    def test_load_ssh_public_key_unsupported(self, backend):
        ssh_key = b"ecdsa-sha2-junk AAAAE2VjZHNhLXNoYTItbmlzdHAyNTY="

        with raises_unsupported_algorithm(None):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_bad_format(self, backend):
        ssh_key = b"ssh-rsa not-a-real-key"

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_rsa_too_short(self, backend):
        ssh_key = b"ssh-rsa"

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_truncated_int(self, backend):
        ssh_key = b"ssh-rsa AAAAB3NzaC1yc2EAAAA="

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

        ssh_key = b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAACKr+IHXo"

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_rsa_comment_with_spaces(self, backend):
        ssh_key = (
            b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDu/XRP1kyK6Cgt36gts9XAk"
            b"FiiuJLW6RU0j3KKVZSs1I7Z3UmU9/9aVh/rZV43WQG8jaR6kkcP4stOR0DEtll"
            b"PDA7ZRBnrfiHpSQYQ874AZaAoIjgkv7DBfsE6gcDQLub0PFjWyrYQUJhtOLQEK"
            b"vY/G0vt2iRL3juawWmCFdTK3W3XvwAdgGk71i6lHt+deOPNEPN2H58E4odrZ2f"
            b"sxn/adpDqfb2sM0kPwQs0aWvrrKGvUaustkivQE4XWiSFnB0oJB/lKK/CKVKuy"
            b"///ImSCGHQRvhwariN2tvZ6CBNSLh3iQgeB0AkyJlng7MXB2qYq/Ci2FUOryCX"
            # Extra section appended
            b"2MzHvnbv testkey@localhost extra"
        )

        load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_rsa_extra_data_after_modulo(self, backend):
        ssh_key = (
            b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDu/XRP1kyK6Cgt36gts9XAk"
            b"FiiuJLW6RU0j3KKVZSs1I7Z3UmU9/9aVh/rZV43WQG8jaR6kkcP4stOR0DEtll"
            b"PDA7ZRBnrfiHpSQYQ874AZaAoIjgkv7DBfsE6gcDQLub0PFjWyrYQUJhtOLQEK"
            b"vY/G0vt2iRL3juawWmCFdTK3W3XvwAdgGk71i6lHt+deOPNEPN2H58E4odrZ2f"
            b"sxn/adpDqfb2sM0kPwQs0aWvrrKGvUaustkivQE4XWiSFnB0oJB/lKK/CKVKuy"
            b"///ImSCGHQRvhwariN2tvZ6CBNSLh3iQgeB0AkyJlng7MXB2qYq/Ci2FUOryCX"
            b"2MzHvnbvAQ== testkey@localhost"
        )

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_rsa_different_string(self, backend):
        ssh_key = (
            # "AAAAB3NzA" the final A is capitalized here to cause the string
            # ssh-rsa inside the base64 encoded blob to be incorrect. It should
            # be a lower case 'a'.
            b"ssh-rsa AAAAB3NzAC1yc2EAAAADAQABAAABAQDDu/XRP1kyK6Cgt36gts9XAk"
            b"FiiuJLW6RU0j3KKVZSs1I7Z3UmU9/9aVh/rZV43WQG8jaR6kkcP4stOR0DEtll"
            b"PDA7ZRBnrfiHpSQYQ874AZaAoIjgkv7DBfsE6gcDQLub0PFjWyrYQUJhtOLQEK"
            b"vY/G0vt2iRL3juawWmCFdTK3W3XvwAdgGk71i6lHt+deOPNEPN2H58E4odrZ2f"
            b"sxn/adpDqfb2sM0kPwQs0aWvrrKGvUaustkivQE4XWiSFnB0oJB/lKK/CKVKuy"
            b"///ImSCGHQRvhwariN2tvZ6CBNSLh3iQgeB0AkyJlng7MXB2qYq/Ci2FUOryCX"
            b"2MzHvnbvAQ== testkey@localhost"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_rsa(self, backend):
        ssh_key = (
            b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDDu/XRP1kyK6Cgt36gts9XAk"
            b"FiiuJLW6RU0j3KKVZSs1I7Z3UmU9/9aVh/rZV43WQG8jaR6kkcP4stOR0DEtll"
            b"PDA7ZRBnrfiHpSQYQ874AZaAoIjgkv7DBfsE6gcDQLub0PFjWyrYQUJhtOLQEK"
            b"vY/G0vt2iRL3juawWmCFdTK3W3XvwAdgGk71i6lHt+deOPNEPN2H58E4odrZ2f"
            b"sxn/adpDqfb2sM0kPwQs0aWvrrKGvUaustkivQE4XWiSFnB0oJB/lKK/CKVKuy"
            b"///ImSCGHQRvhwariN2tvZ6CBNSLh3iQgeB0AkyJlng7MXB2qYq/Ci2FUOryCX"
            b"2MzHvnbv testkey@localhost"
        )

        key = load_ssh_public_key(ssh_key, backend)

        assert key is not None
        assert isinstance(key, rsa.RSAPublicKey)

        numbers = key.public_numbers()

        expected_e = 0x10001
        expected_n = int(
            "00C3BBF5D13F59322BA0A0B77EA0B6CF570241628AE24B5BA454D"
            "23DCA295652B3523B67752653DFFD69587FAD9578DD6406F23691"
            "EA491C3F8B2D391D0312D9653C303B651067ADF887A5241843CEF"
            "8019680A088E092FEC305FB04EA070340BB9BD0F1635B2AD84142"
            "61B4E2D010ABD8FC6D2FB768912F78EE6B05A60857532B75B75EF"
            "C007601A4EF58BA947B7E75E38F3443CDD87E7C138A1DAD9D9FB3"
            "19FF69DA43A9F6F6B0CD243F042CD1A5AFAEB286BD46AEB2D922B"
            "D01385D6892167074A0907F94A2BF08A54ABB2FFFFC89920861D0"
            "46F8706AB88DDADBD9E8204D48B87789081E074024C8996783B31"
            "7076A98ABF0A2D8550EAF2097D8CCC7BE76EF",
            16,
        )

        expected = rsa.RSAPublicNumbers(expected_e, expected_n)

        assert numbers == expected


class TestDSSSSHSerialization:
    def test_load_ssh_public_key_dss_too_short(self, backend):
        ssh_key = b"ssh-dss"

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_dss_comment_with_spaces(self, backend):
        ssh_key = (
            b"ssh-dss AAAAB3NzaC1kc3MAAACBALmwUtfwdjAUjU2Dixd5DvT0NDcjjr69UD"
            b"LqSD/Xt5Al7D3GXr1WOrWGpjO0NE9qzRCvMTU7zykRH6XjuNXB6Hvv48Zfm4vm"
            b"nHQHFmmMg2bI75JbnOwdzWnnPZJrVU4rS23dFFPqs5ug+EbhVVrcwzxahjcSjJ"
            b"7WEQSkVQWnSPbbAAAAFQDXmpD3DIkGvLSBf1GdUF4PHKtUrQAAAIB/bJFwss+2"
            b"fngmfG/Li5OyL7A9iVoGdkUaFaxEUROTp7wkm2z49fXFAir+/U31v50Tu98YLf"
            b"WvKlxdHcdgQYV9Ww5LIrhWwwD4UKOwC6w5S3KHVbi3pWUi7vxJFXOWfeu1mC/J"
            b"TWqMKR91j+rmOtdppWIZRyIVIqLcMdGO3m+2VgAAAIANFDz5KQH5NvoljpoRQi"
            b"RgyPjxWXiE7vjLElKj4v8KrpanAywBzdhIW1y/tzpGuwRwj5ihi8iNTHgSsoTa"
            b"j5AG5HPomJf5vJElxpu/2O9pHA52wcNObIQ7j+JA5uWusxNIbl+pF6sSiP8abr"
            b"z53N7tPF/IhHTjBHb1Ol7IFu9p9A== testkey@localhost extra"
        )

        with pytest.warns(utils.DeprecatedIn40):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_dss_extra_data_after_modulo(self, backend):
        ssh_key = (
            b"ssh-dss AAAAB3NzaC1kc3MAAACBALmwUtfwdjAUjU2Dixd5DvT0NDcjjr69UD"
            b"LqSD/Xt5Al7D3GXr1WOrWGpjO0NE9qzRCvMTU7zykRH6XjuNXB6Hvv48Zfm4vm"
            b"nHQHFmmMg2bI75JbnOwdzWnnPZJrVU4rS23dFFPqs5ug+EbhVVrcwzxahjcSjJ"
            b"7WEQSkVQWnSPbbAAAAFQDXmpD3DIkGvLSBf1GdUF4PHKtUrQAAAIB/bJFwss+2"
            b"fngmfG/Li5OyL7A9iVoGdkUaFaxEUROTp7wkm2z49fXFAir+/U31v50Tu98YLf"
            b"WvKlxdHcdgQYV9Ww5LIrhWwwD4UKOwC6w5S3KHVbi3pWUi7vxJFXOWfeu1mC/J"
            b"TWqMKR91j+rmOtdppWIZRyIVIqLcMdGO3m+2VgAAAIANFDz5KQH5NvoljpoRQi"
            b"RgyPjxWXiE7vjLElKj4v8KrpanAywBzdhIW1y/tzpGuwRwj5ihi8iNTHgSsoTa"
            b"j5AG5HPomJf5vJElxpu/2O9pHA52wcNObIQ7j+JA5uWusxNIbl+pF6sSiP8abr"
            b"z53N7tPF/IhHTjBHb1Ol7IFu9p9AAwMD== testkey@localhost"
        )

        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_dss_different_string(self, backend):
        ssh_key = (
            # "AAAAB3NzA" the final A is capitalized here to cause the string
            # ssh-dss inside the base64 encoded blob to be incorrect. It should
            # be a lower case 'a'.
            b"ssh-dss AAAAB3NzAC1kc3MAAACBALmwUtfwdjAUjU2Dixd5DvT0NDcjjr69UD"
            b"LqSD/Xt5Al7D3GXr1WOrWGpjO0NE9qzRCvMTU7zykRH6XjuNXB6Hvv48Zfm4vm"
            b"nHQHFmmMg2bI75JbnOwdzWnnPZJrVU4rS23dFFPqs5ug+EbhVVrcwzxahjcSjJ"
            b"7WEQSkVQWnSPbbAAAAFQDXmpD3DIkGvLSBf1GdUF4PHKtUrQAAAIB/bJFwss+2"
            b"fngmfG/Li5OyL7A9iVoGdkUaFaxEUROTp7wkm2z49fXFAir+/U31v50Tu98YLf"
            b"WvKlxdHcdgQYV9Ww5LIrhWwwD4UKOwC6w5S3KHVbi3pWUi7vxJFXOWfeu1mC/J"
            b"TWqMKR91j+rmOtdppWIZRyIVIqLcMdGO3m+2VgAAAIANFDz5KQH5NvoljpoRQi"
            b"RgyPjxWXiE7vjLElKj4v8KrpanAywBzdhIW1y/tzpGuwRwj5ihi8iNTHgSsoTa"
            b"j5AG5HPomJf5vJElxpu/2O9pHA52wcNObIQ7j+JA5uWusxNIbl+pF6sSiP8abr"
            b"z53N7tPF/IhHTjBHb1Ol7IFu9p9A== testkey@localhost"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_dss(self, backend):
        ssh_key = (
            b"ssh-dss AAAAB3NzaC1kc3MAAACBALmwUtfwdjAUjU2Dixd5DvT0NDcjjr69UD"
            b"LqSD/Xt5Al7D3GXr1WOrWGpjO0NE9qzRCvMTU7zykRH6XjuNXB6Hvv48Zfm4vm"
            b"nHQHFmmMg2bI75JbnOwdzWnnPZJrVU4rS23dFFPqs5ug+EbhVVrcwzxahjcSjJ"
            b"7WEQSkVQWnSPbbAAAAFQDXmpD3DIkGvLSBf1GdUF4PHKtUrQAAAIB/bJFwss+2"
            b"fngmfG/Li5OyL7A9iVoGdkUaFaxEUROTp7wkm2z49fXFAir+/U31v50Tu98YLf"
            b"WvKlxdHcdgQYV9Ww5LIrhWwwD4UKOwC6w5S3KHVbi3pWUi7vxJFXOWfeu1mC/J"
            b"TWqMKR91j+rmOtdppWIZRyIVIqLcMdGO3m+2VgAAAIANFDz5KQH5NvoljpoRQi"
            b"RgyPjxWXiE7vjLElKj4v8KrpanAywBzdhIW1y/tzpGuwRwj5ihi8iNTHgSsoTa"
            b"j5AG5HPomJf5vJElxpu/2O9pHA52wcNObIQ7j+JA5uWusxNIbl+pF6sSiP8abr"
            b"z53N7tPF/IhHTjBHb1Ol7IFu9p9A== testkey@localhost"
        )

        with pytest.warns(utils.DeprecatedIn40):
            key = load_ssh_public_key(ssh_key, backend)

        assert key is not None
        assert isinstance(key, dsa.DSAPublicKey)

        numbers = key.public_numbers()

        expected_y = int(
            "d143cf92901f936fa258e9a11422460c8f8f1597884eef8cb1252a3e2ff0aae"
            "96a7032c01cdd8485b5cbfb73a46bb04708f98a18bc88d4c7812b284da8f900"
            "6e473e89897f9bc9125c69bbfd8ef691c0e76c1c34e6c843b8fe240e6e5aeb3"
            "13486e5fa917ab1288ff1a6ebcf9dcdeed3c5fc88474e30476f53a5ec816ef6"
            "9f4",
            16,
        )
        expected_p = int(
            "b9b052d7f07630148d4d838b17790ef4f43437238ebebd5032ea483fd7b7902"
            "5ec3dc65ebd563ab586a633b4344f6acd10af31353bcf29111fa5e3b8d5c1e8"
            "7befe3c65f9b8be69c740716698c8366c8ef925b9cec1dcd69e73d926b554e2"
            "b4b6ddd1453eab39ba0f846e1555adcc33c5a8637128c9ed61104a45505a748"
            "f6db",
            16,
        )
        expected_q = 1230879958723280233885494314531920096931919647917
        expected_g = int(
            "7f6c9170b2cfb67e78267c6fcb8b93b22fb03d895a0676451a15ac44511393a"
            "7bc249b6cf8f5f5c5022afefd4df5bf9d13bbdf182df5af2a5c5d1dc7604185"
            "7d5b0e4b22b856c300f850a3b00bac394b728755b8b7a56522eefc491573967"
            "debb5982fc94d6a8c291f758feae63ad769a5621947221522a2dc31d18ede6f"
            "b656",
            16,
        )
        expected = dsa.DSAPublicNumbers(
            expected_y,
            dsa.DSAParameterNumbers(expected_p, expected_q, expected_g),
        )

        assert numbers == expected


class TestECDSASSHSerialization:
    def test_load_ssh_public_key_ecdsa_nist_p256(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())

        ssh_key = (
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTYAAABBBGG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCFPls= root@cloud-server-01"
        )
        key = load_ssh_public_key(ssh_key, backend)
        assert isinstance(key, ec.EllipticCurvePublicKey)

        expected_x = int(
            "44196257377740326295529888716212621920056478823906609851236662550"
            "785814128027",
            10,
        )
        expected_y = int(
            "12257763433170736656417248739355923610241609728032203358057767672"
            "925775019611",
            10,
        )

        assert key.public_numbers() == ec.EllipticCurvePublicNumbers(
            expected_x, expected_y, ec.SECP256R1()
        )

    def test_load_ssh_public_key_byteslike(self, backend):
        _skip_curve_unsupported(backend, ec.SECP256R1())

        ssh_key = (
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTYAAABBBGG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCFPls= root@cloud-server-01"
        )
        assert load_ssh_public_key(bytearray(ssh_key), backend)
        assert load_ssh_public_key(memoryview(ssh_key), backend)
        assert load_ssh_public_key(memoryview(bytearray(ssh_key)), backend)

    def test_load_ssh_public_key_ecdsa_nist_p384(self, backend):
        _skip_curve_unsupported(backend, ec.SECP384R1())
        ssh_key = (
            b"ecdsa-sha2-nistp384 AAAAE2VjZHNhLXNoYTItbmlzdHAzODQAAAAIbmlzdHAz"
            b"ODQAAABhBMzucOm9wbwg4iMr5QL0ya0XNQGXpw4wM5f12E3tWhdcrzyGHyel71t1"
            b"4bvF9JZ2/WIuSxUr33XDl8jYo+lMQ5N7Vanc7f7i3AR1YydatL3wQfZStQ1I3rBa"
            b"qQtRSEU8Tg== root@cloud-server-01"
        )
        key = load_ssh_public_key(ssh_key, backend)
        assert isinstance(key, ec.EllipticCurvePublicKey)

        expected_x = int(
            "31541830871345183397582554827482786756220448716666815789487537666"
            "592636882822352575507883817901562613492450642523901",
            10,
        )
        expected_y = int(
            "15111413269431823234030344298767984698884955023183354737123929430"
            "995703524272335782455051101616329050844273733614670",
            10,
        )

        assert key.public_numbers() == ec.EllipticCurvePublicNumbers(
            expected_x, expected_y, ec.SECP384R1()
        )

    def test_load_ssh_public_key_ecdsa_nist_p521(self, backend):
        _skip_curve_unsupported(backend, ec.SECP521R1())
        ssh_key = (
            b"ecdsa-sha2-nistp521 AAAAE2VjZHNhLXNoYTItbmlzdHA1MjEAAAAIbmlzdHA1"
            b"MjEAAACFBAGTrRhMSEgF6Ni+PXNz+5fjS4lw3ypUILVVQ0Av+0hQxOx+MyozELon"
            b"I8NKbrbBjijEs1GuImsmkTmWsMXS1j2A7wB4Kseh7W9KA9IZJ1+TMrzWUEwvOOXi"
            b"wT23pbaWWXG4NaM7vssWfZBnvz3S174TCXnJ+DSccvWBFnKP0KchzLKxbg== "
            b"root@cloud-server-01"
        )
        key = load_ssh_public_key(ssh_key, backend)
        assert isinstance(key, ec.EllipticCurvePublicKey)

        expected_x = int(
            "54124123120178189598842622575230904027376313369742467279346415219"
            "77809037378785192537810367028427387173980786968395921877911964629"
            "142163122798974160187785455",
            10,
        )
        expected_y = int(
            "16111775122845033200938694062381820957441843014849125660011303579"
            "15284560361402515564433711416776946492019498546572162801954089916"
            "006665939539407104638103918",
            10,
        )

        assert key.public_numbers() == ec.EllipticCurvePublicNumbers(
            expected_x, expected_y, ec.SECP521R1()
        )

    def test_load_ssh_public_key_ecdsa_nist_p256_trailing_data(self, backend):
        ssh_key = (
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTYAAABBBGG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCFPltB= root@cloud-server-01"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_ecdsa_nist_p256_missing_data(self, backend):
        ssh_key = (
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTYAAABBBGG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCF= root@cloud-server-01"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_ecdsa_nist_p256_compressed(self, backend):
        # If we ever implement compressed points, note that this is not a valid
        # one, it just has the compressed marker in the right place.
        ssh_key = (
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTYAAABBAWG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCFPls= root@cloud-server-01"
        )
        with pytest.raises(NotImplementedError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_ecdsa_nist_p256_bad_curve_name(self, backend):
        ssh_key = (
            # The curve name in here is changed to be "nistp255".
            b"ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAy"
            b"NTUAAABBBGG2MfkHXp0UkxUyllDzWNBAImsvt5t7pFtTXegZK2WbGxml8zMrgWi5"
            b"teIg1TO03/FD9hbpBFgBeix3NrCFPls= root@cloud-server-01"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)


@pytest.mark.supported(
    only_if=lambda backend: backend.ed25519_supported(),
    skip_message="Requires OpenSSL with Ed25519 support",
)
class TestEd25519SSHSerialization:
    def test_load_ssh_public_key(self, backend):
        ssh_key = (
            b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG2fgpmpYO61qeAxGd0wgRaN/E4"
            b"GR+xWvBmvxjxrB1vG user@chiron.local"
        )
        key = load_ssh_public_key(ssh_key, backend)
        assert isinstance(key, ed25519.Ed25519PublicKey)
        assert key.public_bytes(Encoding.Raw, PublicFormat.Raw) == (
            b"m\x9f\x82\x99\xa9`\xee\xb5\xa9\xe01\x19\xdd0\x81\x16\x8d\xfc"
            b"N\x06G\xecV\xbc\x19\xaf\xc6<k\x07[\xc6"
        )

    def test_public_bytes_openssh(self, backend):
        ssh_key = (
            b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG2fgpmpYO61qeAxGd0wgRaN/E4"
            b"GR+xWvBmvxjxrB1vG"
        )
        key = load_ssh_public_key(ssh_key, backend)
        assert isinstance(key, ed25519.Ed25519PublicKey)
        assert (
            key.public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH) == ssh_key
        )

    def test_load_ssh_public_key_not_32_bytes(self, backend):
        ssh_key = (
            b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI22fgpmpYO61qeAxGd0wgRaN/E4"
            b"GR+xWvBmvxjxrB1vGaGVs user@chiron.local"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)

    def test_load_ssh_public_key_trailing_data(self, backend):
        ssh_key = (
            b"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG2fgpmpYO61qeAxGd0wgRa"
            b"N/E4GR+xWvBmvxjxrB1vGdHJhaWxpbmdkYXRh user@chiron.local"
        )
        with pytest.raises(ValueError):
            load_ssh_public_key(ssh_key, backend)


class TestSSHCertificate:
    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires OpenSSL with Ed25519 support",
    )
    def test_loads_ssh_cert(self, backend):
        # secp256r1 public key, ed25519 signing key
        cert = load_ssh_public_identity(
            b"ecdsa-sha2-nistp256-cert-v01@openssh.com AAAAKGVjZHNhLXNoYTItbm"
            b"lzdHAyNTYtY2VydC12MDFAb3BlbnNzaC5jb20AAAAgLfsFv9Gbc6LZSiJFWdYQl"
            b"IMNI50GExXW0fBpgGVf+Y4AAAAIbmlzdHAyNTYAAABBBIzVyRgVLR4F38bIOLBN"
            b"8CNm8Nf+eBHCVkKDKb9WDyLLD61CEmzjK/ORwFuSE4N60eIGbFidBf0D0xh7G6o"
            b"TNxsAAAAAAAAAAAAAAAEAAAAUdGVzdEBjcnlwdG9ncmFwaHkuaW8AAAAaAAAACm"
            b"NyeXB0b3VzZXIAAAAIdGVzdHVzZXIAAAAAY7KyZAAAAAB2frXAAAAAWAAAAA1mb"
            b"3JjZS1jb21tYW5kAAAALAAAAChlY2hvIGFhYWFhYWFhYWFhYWFhYWFhYWFhYWFh"
            b"YWFhYWFhYWFhYWFhAAAAD3ZlcmlmeS1yZXF1aXJlZAAAAAAAAACCAAAAFXBlcm1"
            b"pdC1YMTEtZm9yd2FyZGluZwAAAAAAAAAXcGVybWl0LWFnZW50LWZvcndhcmRpbm"
            b"cAAAAAAAAAFnBlcm1pdC1wb3J0LWZvcndhcmRpbmcAAAAAAAAACnBlcm1pdC1wd"
            b"HkAAAAAAAAADnBlcm1pdC11c2VyLXJjAAAAAAAAAAAAAAAzAAAAC3NzaC1lZDI1"
            b"NTE5AAAAICH6csEOmGbOfT2B/S/FJg3uyPsaPSZUZk2SVYlfs0KLAAAAUwAAAAt"
            b"zc2gtZWQyNTUxOQAAAEDz2u7X5/TFbN7Ms7DP4yArhz1oWWYKkdAk7FGFkHfjtY"
            b"/YfNQ8Oky3dCZRi7PnSzScEEjos7723dhF8/y99WwH reaperhulk@despoina."
            b"local"
        )
        assert isinstance(cert, SSHCertificate)
        cert.verify_cert_signature()
        signature_key = cert.signature_key()
        assert isinstance(signature_key, ed25519.Ed25519PublicKey)
        assert cert.nonce == (
            b'-\xfb\x05\xbf\xd1\x9bs\xa2\xd9J"EY\xd6\x10\x94\x83\r#\x9d'
            b"\x06\x13\x15\xd6\xd1\xf0i\x80e_\xf9\x8e"
        )
        public_key = cert.public_key()
        assert isinstance(public_key, ec.EllipticCurvePublicKey)
        assert isinstance(public_key.curve, ec.SECP256R1)
        assert cert.serial == 0
        assert cert.type is SSHCertificateType.USER
        assert cert.key_id == b"test@cryptography.io"
        assert cert.valid_principals == [b"cryptouser", b"testuser"]
        assert cert.valid_before == 1988015552
        assert cert.valid_after == 1672655460
        assert cert.critical_options == {
            b"force-command": b"echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            b"verify-required": b"",
        }
        assert cert.extensions == {
            b"permit-X11-forwarding": b"",
            b"permit-agent-forwarding": b"",
            b"permit-port-forwarding": b"",
            b"permit-pty": b"",
            b"permit-user-rc": b"",
        }

    @pytest.mark.parametrize(
        "filename",
        [
            "p256-p384.pub",
            "p256-p521.pub",
            "p256-rsa-sha1.pub",
            "p256-rsa-sha256.pub",
            "p256-rsa-sha512.pub",
        ],
    )
    def test_verify_cert_signature(self, filename, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "certs", filename),
            lambda f: f.read(),
            mode="rb",
        )
        cert = load_ssh_public_identity(data)
        # we have no public API for getting the hash alg of the sig
        assert isinstance(cert, SSHCertificate)
        if backend._fips_enabled and bytes(cert._inner_sig_type) == b"ssh-rsa":
            pytest.skip("FIPS does not support RSA SHA1")
        cert.verify_cert_signature()

    @pytest.mark.parametrize(
        "filename",
        [
            "p256-p256-empty-principals.pub",
            "p256-p384.pub",
            "p256-p521.pub",
            "p256-rsa-sha1.pub",
            "p256-rsa-sha256.pub",
            "p256-rsa-sha512.pub",
        ],
    )
    def test_invalid_signature(self, filename, backend):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "certs", filename),
            lambda f: f.read(),
            mode="rb",
        )
        data = bytearray(data)
        # mutate the signature so it's invalid
        data[-10] = 71
        cert = load_ssh_public_identity(data)
        assert isinstance(cert, SSHCertificate)
        # we have no public API for getting the hash alg of the sig
        if backend._fips_enabled and bytes(cert._inner_sig_type) == b"ssh-rsa":
            pytest.skip("FIPS does not support RSA SHA1")
        with pytest.raises(InvalidSignature):
            cert.verify_cert_signature()

    def test_not_bytes(self):
        with pytest.raises(TypeError):
            load_ssh_public_identity(
                "these aren't bytes"  # type:ignore[arg-type]
            )

    def test_load_ssh_public_key(self, backend):
        # This test will be removed when we implement load_ssh_public_key
        # in terms of load_ssh_public_identity. Needed for coverage now.
        pub_data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "rsa-nopsw.key.pub"),
            lambda f: f.read(),
            mode="rb",
        )
        key = load_ssh_public_identity(pub_data)
        assert isinstance(key, rsa.RSAPublicKey)

    @pytest.mark.parametrize("filename", ["dsa-p256.pub", "p256-dsa.pub"])
    def test_dsa_unsupported(self, filename):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "certs", filename),
            lambda f: f.read(),
            mode="rb",
        )
        with raises_unsupported_algorithm(None):
            load_ssh_public_identity(data)

    def test_mismatched_inner_signature_type_and_sig_type(self):
        data = load_vectors_from_file(
            os.path.join(
                "asymmetric",
                "OpenSSH",
                "certs",
                "p256-p256-broken-signature-key-type.pub",
            ),
            lambda f: f.read(),
            mode="rb",
        )
        with pytest.raises(ValueError):
            load_ssh_public_identity(data)

    def test_invalid_cert_type(self):
        data = load_vectors_from_file(
            os.path.join(
                "asymmetric",
                "OpenSSH",
                "certs",
                "p256-p256-invalid-cert-type.pub",
            ),
            lambda f: f.read(),
            mode="rb",
        )
        with pytest.raises(ValueError):
            load_ssh_public_identity(data)

    @pytest.mark.parametrize(
        "filename",
        [
            "p256-p256-duplicate-extension.pub",
            "p256-p256-non-lexical-extensions.pub",
            "p256-p256-duplicate-crit-opts.pub",
            "p256-p256-non-lexical-crit-opts.pub",
            "p256-ed25519-non-singular-crit-opt-val.pub",
            "p256-ed25519-non-singular-ext-val.pub",
        ],
    )
    def test_invalid_encodings(self, filename):
        data = load_vectors_from_file(
            os.path.join("asymmetric", "OpenSSH", "certs", filename),
            lambda f: f.read(),
            mode="rb",
        )
        with pytest.raises(ValueError):
            load_ssh_public_identity(data)

    def test_invalid_line_format(self, backend):
        with pytest.raises(ValueError):
            load_ssh_public_identity(b"whaaaaaaaaaaat")

    def test_invalid_b64(self, backend):
        with pytest.raises(ValueError):
            load_ssh_public_identity(b"ssh-rsa-cert-v01@openssh.com invalid")

    def test_inner_outer_key_type_mismatch(self):
        with pytest.raises(ValueError):
            load_ssh_public_identity(
                b"ecdsa-sha2-nistp256-cert-v01@openssh.com AAAAK0VjZHNhLXNoYTI"
                b"tbmlzdHAyNTYtY2VydC12MDFAb3BlbnNzaC5jb20AAAAg/9dq+iibMSMdJ0v"
                b"l6D0SrsazwccWptLQs4sEgJBVnQMAAAAIbmlzdHAyNTYAAABBBAsuVFNNj/m"
                b"MyFm2xB99G4xiaUJE1lZNjcp+S2tXYW5KorcHpusSlSqOkUPZ2l0644dgiNP"
                b"DKR/R+BtYENC8aq8AAAAAAAAAAAAAAAEAAAAUdGVzdEBjcnlwdG9ncmFwaHk"
                b"uaW8AAAAaAAAACmNyeXB0b3VzZXIAAAAIdGVzdHVzZXIAAAAAY7ZXNAAAAAB"
                b"2glqqAAAAAAAAAIIAAAAVcGVybWl0LVgxMS1mb3J3YXJkaW5nAAAAAAAAABd"
                b"wZXJtaXQtYWdlbnQtZm9yd2FyZGluZwAAAAAAAAAWcGVybWl0LXBvcnQtZm9"
                b"yd2FyZGluZwAAAAAAAAAKcGVybWl0LXB0eQAAAAAAAAAOcGVybWl0LXVzZXI"
                b"tcmMAAAAAAAAAAAAAAGgAAAATZWNkc2Etc2hhMi1uaXN0cDI1NgAAAAhuaXN"
                b"0cDI1NgAAAEEEzwNcwptXrrgztCug8ZB82f5OsPWJiO4WP0kjdFz1vbBGQOU"
                b"DcCaabh5EbgfMOf1mg58zw35QrqjTXDiBMjyPhwAAAGQAAAATZWNkc2Etc2h"
                b"hMi1uaXN0cDI1NgAAAEkAAAAhAOaNCEtn0JkFfSygACVZMBUMd5/m7avwqxW"
                b"+FxCje1GpAAAAIGf9opl4YoC5XcO92WMFEwUdE3jUQtBg3GRQlXBqFcoL"
            )

    def test_loads_a_cert_empty_principals(self, backend):
        data = load_vectors_from_file(
            os.path.join(
                "asymmetric",
                "OpenSSH",
                "certs",
                "p256-p256-empty-principals.pub",
            ),
            lambda f: f.read(),
            mode="rb",
        )
        cert = load_ssh_public_identity(data)
        assert isinstance(cert, SSHCertificate)
        assert cert.valid_principals == []
        assert cert.extensions == {}
        assert cert.critical_options == {}

    def test_public_bytes(self, backend):
        data = load_vectors_from_file(
            os.path.join(
                "asymmetric",
                "OpenSSH",
                "certs",
                "p256-p256-empty-principals.pub",
            ),
            lambda f: f.read(),
            mode="rb",
        )
        cert = load_ssh_public_identity(data)
        assert isinstance(cert, SSHCertificate)
        assert data == cert.public_bytes()


class TestSSHCertificateBuilder:
    def test_signs_a_cert(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = ec.generate_private_key(ec.SECP256R1()).public_key()
        valid_after = datetime.datetime(
            2023, 1, 1, 1, tzinfo=datetime.timezone.utc
        ).timestamp()
        valid_before = datetime.datetime(
            2023, 6, 1, 1, tzinfo=datetime.timezone.utc
        ).timestamp()
        key_id = b"test"
        valid_principals = [b"eve", b"alice"]
        builder = (
            SSHCertificateBuilder()
            .public_key(public_key)
            .type(SSHCertificateType.USER)
            .valid_before(valid_before)
            .valid_after(valid_after)
            .key_id(key_id)
            .valid_principals(valid_principals)
            .add_critical_option(b"ordered", b"")
            .add_critical_option(b"maybe", b"test2")
            .add_extension(b"test", b"a value")
            .add_extension(b"allowed", b"")
        )
        cert = builder.sign(private_key)
        cert.verify_cert_signature()
        cert_public_key = cert.public_key()
        assert isinstance(cert_public_key, ec.EllipticCurvePublicKey)
        assert cert_public_key.public_numbers() == public_key.public_numbers()
        assert cert.serial == 0
        assert cert.type is SSHCertificateType.USER
        assert cert.key_id == key_id
        assert cert.valid_principals == valid_principals
        assert cert.valid_before == int(valid_before)
        assert cert.valid_after == int(valid_after)
        assert cert.critical_options == {b"ordered": b"", b"maybe": b"test2"}
        assert list(cert.critical_options) == [b"maybe", b"ordered"]
        assert cert.extensions == {b"test": b"a value", b"allowed": b""}
        assert list(cert.extensions) == [b"allowed", b"test"]
        signature_key = cert.signature_key()
        assert isinstance(signature_key, ec.EllipticCurvePublicKey)
        assert (
            signature_key.public_numbers()
            == private_key.public_key().public_numbers()
        )

    def test_public_key_errors(self):
        public_key = ec.generate_private_key(ec.SECP256R1()).public_key()
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.public_key("not a key")  # type: ignore[arg-type]
        builder = builder.public_key(public_key)
        with pytest.raises(ValueError):
            builder.public_key(public_key)

    def test_serial_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.serial("not a serial")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            builder.serial(-1)
        with pytest.raises(ValueError):
            builder.serial(2**64)
        builder = builder.serial(1)
        with pytest.raises(ValueError):
            builder.serial(1)

    def test_type_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.type("not a type")  # type: ignore[arg-type]
        builder = builder.type(SSHCertificateType.USER)
        with pytest.raises(ValueError):
            builder.type(SSHCertificateType.USER)

    def test_key_id_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.key_id("not bytes")  # type: ignore[arg-type]
        builder = builder.key_id(b"test")
        with pytest.raises(ValueError):
            builder.key_id(b"test")

    def test_valid_principals_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.valid_principals("not a list")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            builder.valid_principals(
                [b"test", "not bytes"]  # type: ignore[list-item]
            )
        with pytest.raises(TypeError):
            builder.valid_principals([])
        with pytest.raises(ValueError):
            builder.valid_principals(
                [b"test"] * (ssh._SSHKEY_CERT_MAX_PRINCIPALS + 1)
            )
        builder = builder.valid_principals([b"test"])
        with pytest.raises(ValueError):
            builder.valid_principals([b"test"])
        with pytest.raises(ValueError):
            builder.valid_for_all_principals()

    def test_valid_for_all_principals_errors(self):
        builder = SSHCertificateBuilder()
        builder = builder.valid_for_all_principals()
        with pytest.raises(ValueError):
            builder.valid_for_all_principals()
        with pytest.raises(ValueError):
            builder.valid_principals([b"test"])

    def test_valid_before_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.valid_before("not an int")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            builder.valid_before(-1)
        with pytest.raises(ValueError):
            builder.valid_after(2**64)
        builder = builder.valid_before(12345)
        with pytest.raises(ValueError):
            builder.valid_before(123456)

    def test_valid_after_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.valid_after("not an int")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            builder.valid_after(-1)
        with pytest.raises(ValueError):
            builder.valid_after(2**64)
        builder = builder.valid_after(1234)
        with pytest.raises(ValueError):
            builder.valid_after(12345)

    def test_add_critical_option_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.add_critical_option(
                "not bytes",  # type: ignore[arg-type]
                b"test",
            )
        with pytest.raises(TypeError):
            builder.add_critical_option(
                b"test",
                object(),  # type: ignore[arg-type]
            )
        builder = builder.add_critical_option(b"test", b"test")
        with pytest.raises(ValueError):
            builder.add_critical_option(b"test", b"test")

    def test_add_extension_errors(self):
        builder = SSHCertificateBuilder()
        with pytest.raises(TypeError):
            builder.add_extension(
                "not bytes",  # type: ignore[arg-type]
                b"test",
            )
        with pytest.raises(TypeError):
            builder.add_extension(b"test", object())  # type: ignore[arg-type]
        builder = builder.add_extension(b"test", b"test")
        with pytest.raises(ValueError):
            builder.add_extension(b"test", b"test")

    def test_sign_unsupported_key(self):
        builder = (
            SSHCertificateBuilder()
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(TypeError):
            builder.sign("not a key")

    def test_sign_no_public_key(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_no_type(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_no_valid_principals(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_no_valid_after(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_no_valid_before(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_principals([b"bob"])
            .valid_after(0)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_valid_after_after_valid_before(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_principals([b"eve"])
            .valid_after(20)
            .valid_before(0)
            .type(SSHCertificateType.USER)
        )
        with pytest.raises(ValueError):
            builder.sign(private_key)

    def test_sign_non_zero_serial(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .serial(123456789)
            .valid_principals([b"alice"])
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        cert = builder.sign(private_key)
        assert cert.serial == 123456789

    def test_crit_opts_exts_lexically_sorted(self):
        private_key = ec.generate_private_key(ec.SECP256R1())
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
            .add_critical_option(b"zebra@cryptography.io", b"")
            .add_critical_option(b"apple@cryptography.io", b"")
            .add_critical_option(b"banana@cryptography.io", b"")
            .add_extension(b"zebra@cryptography.io", b"")
            .add_extension(b"apple@cryptography.io", b"")
            .add_extension(b"banana@cryptography.io", b"")
        )
        cert = builder.sign(private_key)
        # This returns a dict, but dicts are order preserving in
        # all our supported versions of Python so we can use
        # items to confirm the order.
        assert list(cert.extensions.items()) == [
            (b"apple@cryptography.io", b""),
            (b"banana@cryptography.io", b""),
            (b"zebra@cryptography.io", b""),
        ]
        assert list(cert.critical_options.items()) == [
            (b"apple@cryptography.io", b""),
            (b"banana@cryptography.io", b""),
            (b"zebra@cryptography.io", b""),
        ]

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires OpenSSL with Ed25519 support",
    )
    def test_sign_ed25519(self, backend):
        private_key = ed25519.Ed25519PrivateKey.generate()
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        cert = builder.sign(private_key)
        assert isinstance(cert.signature_key(), ed25519.Ed25519PublicKey)
        cert.verify_cert_signature()

    @pytest.mark.parametrize(
        "curve", [ec.SECP256R1(), ec.SECP384R1(), ec.SECP521R1()]
    )
    def test_sign_ec(self, curve):
        private_key = ec.generate_private_key(curve)
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        cert = builder.sign(private_key)
        sig_key = cert.signature_key()
        assert isinstance(sig_key, ec.EllipticCurvePublicKey)
        assert isinstance(sig_key.curve, type(curve))
        cert.verify_cert_signature()

    def test_sign_rsa(self):
        private_key = RSA_KEY_2048.private_key()
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(0)
            .valid_before(2**64 - 1)
            .type(SSHCertificateType.USER)
        )
        cert = builder.sign(private_key)
        sig_key = cert.signature_key()
        assert isinstance(sig_key, rsa.RSAPublicKey)
        cert.verify_cert_signature()

    def test_sign_and_byte_compare_rsa(self, monkeypatch):
        # Monkey patch urandom to return a known value so we
        # get a deterministic signature with RSA.
        monkeypatch.setattr(os, "urandom", lambda _: b"\x00" * 32)
        private_key = RSA_KEY_2048.private_key()
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(1672531200)
            .valid_before(1672617600)
            .type(SSHCertificateType.USER)
            .add_extension(b"permit-pty", b"")
            .add_critical_option(
                b"force-command", b"echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            )
            .add_critical_option(b"verify-required", b"")
        )
        cert = builder.sign(private_key)
        sig_key = cert.signature_key()
        assert isinstance(sig_key, rsa.RSAPublicKey)
        cert.verify_cert_signature()
        assert cert.public_bytes() == (
            b"ssh-rsa-cert-v01@openssh.com AAAAHHNzaC1yc2EtY2VydC12MDFAb3Blbn"
            b"NzaC5jb20AAAAgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADA"
            b"QABAAABAQDBevx+d0dMqlqoMDYVij/797UhaFG6IjDl1qv8wcbP71npI+oTMLxZ"
            b"O3OAKrYIpuSjMGUjoxFrpao5ZhRRdOE7bEnpt4Bi5EnXLvsQ/UnpH6CLltBR54L"
            b"p9avFtab3mEgnrbjnPaAPIrLv3Nt26rRu2tmO1lZidD/cbA4zal0M26p9wp5TY1"
            b"4kyHpbLEIVloBjzetoqXK6u8Hjz/APuagONypNDCySDR6M7jM85HDcLoFFrbBb8"
            b"pruHSTxQejMeEmJxYf8b7rNl58/IWPB1ymbNlvHL/4oSOlnrtHkjcxRWzpQ7U3g"
            b"T9BThGyhCiI7EMyEHMgP3r7kTzEUwT6IavWDAAAAAAAAAAAAAAABAAAAAAAAAAA"
            b"AAAAAY7DNAAAAAABjsh6AAAAAWAAAAA1mb3JjZS1jb21tYW5kAAAALAAAAChlY2"
            b"hvIGFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhAAAAD3Zlcmlme"
            b"S1yZXF1aXJlZAAAAAAAAAASAAAACnBlcm1pdC1wdHkAAAAAAAAAAAAAARcAAAAH"
            b"c3NoLXJzYQAAAAMBAAEAAAEBAMF6/H53R0yqWqgwNhWKP/v3tSFoUboiMOXWq/z"
            b"Bxs/vWekj6hMwvFk7c4Aqtgim5KMwZSOjEWulqjlmFFF04TtsSem3gGLkSdcu+x"
            b"D9SekfoIuW0FHngun1q8W1pveYSCetuOc9oA8isu/c23bqtG7a2Y7WVmJ0P9xsD"
            b"jNqXQzbqn3CnlNjXiTIelssQhWWgGPN62ipcrq7wePP8A+5qA43Kk0MLJINHozu"
            b"MzzkcNwugUWtsFvymu4dJPFB6Mx4SYnFh/xvus2Xnz8hY8HXKZs2W8cv/ihI6We"
            b"u0eSNzFFbOlDtTeBP0FOEbKEKIjsQzIQcyA/evuRPMRTBPohq9YMAAAEUAAAADH"
            b"JzYS1zaGEyLTUxMgAAAQCYbbNzhflDqZAxyBpdLIX0nLAdnTeFNBudMqgo3KGND"
            b"WlU9N17hqBEmcvIOrtNi+JKuKZW89zZrbORHvdjv6NjGSKzJD/XA25YrX1KgMEO"
            b"wt5pzMZX+100drwrjQo+vZqeIN3FJNmT3wssge73v+JsxQrdIAz7YM2OZrFr5HM"
            b"qZEZ5tMvAf/s5YEMDttEU4zMtmjubQyDM5KyYnZdoDT4sKi2rB8gfaigc4IdI/K"
            b"8oXL/3Y7rHuOtejl3lUK4v6DxeRl4aqGYWmhUJc++Rh0cbDgC2S6Cq7gAfG2tND"
            b"zbwL217Q93R08bJn1hDWuiTiaHGauSy2gPUI+cnkvlEocHM"
        )

    @pytest.mark.supported(
        only_if=lambda backend: backend.ed25519_supported(),
        skip_message="Requires OpenSSL with Ed25519 support",
    )
    def test_sign_and_byte_compare_ed25519(self, monkeypatch, backend):
        # Monkey patch urandom to return a known value so we
        # get a deterministic signature with Ed25519.
        monkeypatch.setattr(os, "urandom", lambda _: b"\x00" * 32)
        private_key = load_vectors_from_file(
            os.path.join("asymmetric", "Ed25519", "ed25519-pkcs8.pem"),
            lambda pemfile: load_pem_private_key(
                pemfile.read(), None, backend
            ),
            mode="rb",
        )
        assert isinstance(private_key, ed25519.Ed25519PrivateKey)
        builder = (
            SSHCertificateBuilder()
            .public_key(private_key.public_key())
            .valid_for_all_principals()
            .valid_after(1672531200)
            .valid_before(1672617600)
            .type(SSHCertificateType.USER)
            .add_extension(b"permit-pty", b"")
            .add_critical_option(
                b"force-command", b"echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            )
            .add_critical_option(b"verify-required", b"")
        )
        cert = builder.sign(private_key)
        sig_key = cert.signature_key()
        assert isinstance(sig_key, ed25519.Ed25519PublicKey)
        cert.verify_cert_signature()
        assert cert.public_bytes() == (
            b"ssh-ed25519-cert-v01@openssh.com AAAAIHNzaC1lZDI1NTE5LWNlcnQtdj"
            b"AxQG9wZW5zc2guY29tAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            b"AAAAAAAINdamAGCsQq31Uv+08lkBzoO4XLz2qYjJa8CGmj3B1EaAAAAAAAAAAAA"
            b"AAABAAAAAAAAAAAAAAAAY7DNAAAAAABjsh6AAAAAWAAAAA1mb3JjZS1jb21tYW5"
            b"kAAAALAAAAChlY2hvIGFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYW"
            b"FhAAAAD3ZlcmlmeS1yZXF1aXJlZAAAAAAAAAASAAAACnBlcm1pdC1wdHkAAAAAA"
            b"AAAAAAAADMAAAALc3NoLWVkMjU1MTkAAAAg11qYAYKxCrfVS/7TyWQHOg7hcvPa"
            b"piMlrwIaaPcHURoAAABTAAAAC3NzaC1lZDI1NTE5AAAAQL2aUjeD60C2FrbgHcN"
            b"t8yRa8IRbxvOyA9TZYDGG1dRE3DiR0fuudU20v6vqfTd1gx0S5QyEdECXLl9ZI3"
            b"AwZgc="
        )


class TestSSHSK:
    @staticmethod
    def ssh_str(application):
        data = (
            len(application).to_bytes(length=4, byteorder="big")
            + application.encode()
        )
        return memoryview(data)

    def test_load_application(self):
        ssh.load_application(self.ssh_str("ssh:test"))

    def test_load_application_valueerror(self):
        with pytest.raises(ValueError):
            ssh.load_application(self.ssh_str("hss:test"))
