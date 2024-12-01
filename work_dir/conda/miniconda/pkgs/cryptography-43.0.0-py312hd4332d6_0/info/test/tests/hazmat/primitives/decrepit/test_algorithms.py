# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.exceptions import _Reasons
from cryptography.hazmat.decrepit.ciphers.algorithms import (
    ARC4,
    CAST5,
    IDEA,
    SEED,
    Blowfish,
    TripleDES,
)
from cryptography.hazmat.primitives import ciphers
from cryptography.hazmat.primitives.ciphers import modes

from ....utils import load_nist_vectors, raises_unsupported_algorithm
from ..utils import generate_encrypt_test


class TestARC4:
    @pytest.mark.parametrize(
        ("key", "keysize"),
        [
            (b"0" * 10, 40),
            (b"0" * 14, 56),
            (b"0" * 16, 64),
            (b"0" * 20, 80),
            (b"0" * 32, 128),
            (b"0" * 48, 192),
            (b"0" * 64, 256),
        ],
    )
    def test_key_size(self, key, keysize):
        cipher = ARC4(binascii.unhexlify(key))
        assert cipher.key_size == keysize

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            ARC4(binascii.unhexlify(b"0" * 34))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            ARC4("0" * 10)  # type: ignore[arg-type]


def test_invalid_mode_algorithm():
    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        ciphers.Cipher(
            ARC4(b"\x00" * 16),
            modes.GCM(b"\x00" * 12),
        )

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        ciphers.Cipher(
            ARC4(b"\x00" * 16),
            modes.CBC(b"\x00" * 12),
        )

    with raises_unsupported_algorithm(_Reasons.UNSUPPORTED_CIPHER):
        ciphers.Cipher(
            ARC4(b"\x00" * 16),
            modes.CTR(b"\x00" * 12),
        )


class TestTripleDES:
    @pytest.mark.parametrize("key", [b"0" * 16, b"0" * 32, b"0" * 48])
    def test_key_size(self, key):
        cipher = TripleDES(binascii.unhexlify(key))
        assert cipher.key_size == 192

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            TripleDES(binascii.unhexlify(b"0" * 12))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            TripleDES("0" * 16)  # type: ignore[arg-type]


class TestBlowfish:
    @pytest.mark.parametrize(
        ("key", "keysize"),
        [(b"0" * (keysize // 4), keysize) for keysize in range(32, 449, 8)],
    )
    def test_key_size(self, key, keysize):
        cipher = Blowfish(binascii.unhexlify(key))
        assert cipher.key_size == keysize

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            Blowfish(binascii.unhexlify(b"0" * 6))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            Blowfish("0" * 8)  # type: ignore[arg-type]


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        Blowfish(b"\x00" * 56), modes.ECB()
    ),
    skip_message="Does not support Blowfish ECB",
)
class TestBlowfishModeECB:
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "Blowfish"),
        ["bf-ecb.txt"],
        lambda key, **kwargs: Blowfish(binascii.unhexlify(key)),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        Blowfish(b"\x00" * 56), modes.CBC(b"\x00" * 8)
    ),
    skip_message="Does not support Blowfish CBC",
)
class TestBlowfishModeCBC:
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "Blowfish"),
        ["bf-cbc.txt"],
        lambda key, **kwargs: Blowfish(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        Blowfish(b"\x00" * 56), modes.OFB(b"\x00" * 8)
    ),
    skip_message="Does not support Blowfish OFB",
)
class TestBlowfishModeOFB:
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "Blowfish"),
        ["bf-ofb.txt"],
        lambda key, **kwargs: Blowfish(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        Blowfish(b"\x00" * 56), modes.CFB(b"\x00" * 8)
    ),
    skip_message="Does not support Blowfish CFB",
)
class TestBlowfishModeCFB:
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "Blowfish"),
        ["bf-cfb.txt"],
        lambda key, **kwargs: Blowfish(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv)),
    )


class TestCAST5:
    @pytest.mark.parametrize(
        ("key", "keysize"),
        [(b"0" * (keysize // 4), keysize) for keysize in range(40, 129, 8)],
    )
    def test_key_size(self, key, keysize):
        cipher = CAST5(binascii.unhexlify(key))
        assert cipher.key_size == keysize

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            CAST5(binascii.unhexlify(b"0" * 34))

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            CAST5("0" * 10)  # type: ignore[arg-type]


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        CAST5(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support CAST5 ECB",
)
class TestCAST5ModeECB:
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "CAST5"),
        ["cast5-ecb.txt"],
        lambda key, **kwargs: CAST5(binascii.unhexlify(key)),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        CAST5(b"\x00" * 16), modes.CBC(b"\x00" * 8)
    ),
    skip_message="Does not support CAST5 CBC",
)
class TestCAST5ModeCBC:
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "CAST5"),
        ["cast5-cbc.txt"],
        lambda key, **kwargs: CAST5(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        CAST5(b"\x00" * 16), modes.OFB(b"\x00" * 8)
    ),
    skip_message="Does not support CAST5 OFB",
)
class TestCAST5ModeOFB:
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "CAST5"),
        ["cast5-ofb.txt"],
        lambda key, **kwargs: CAST5(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        CAST5(b"\x00" * 16), modes.CFB(b"\x00" * 8)
    ),
    skip_message="Does not support CAST5 CFB",
)
class TestCAST5ModeCFB:
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "CAST5"),
        ["cast5-cfb.txt"],
        lambda key, **kwargs: CAST5(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv)),
    )


class TestIDEA:
    def test_key_size(self):
        cipher = IDEA(b"\x00" * 16)
        assert cipher.key_size == 128

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            IDEA(b"\x00" * 17)

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            IDEA("0" * 16)  # type: ignore[arg-type]


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        IDEA(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support IDEA ECB",
)
class TestIDEAModeECB:
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "IDEA"),
        ["idea-ecb.txt"],
        lambda key, **kwargs: IDEA(binascii.unhexlify(key)),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        IDEA(b"\x00" * 16), modes.CBC(b"\x00" * 8)
    ),
    skip_message="Does not support IDEA CBC",
)
class TestIDEAModeCBC:
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "IDEA"),
        ["idea-cbc.txt"],
        lambda key, **kwargs: IDEA(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        IDEA(b"\x00" * 16), modes.OFB(b"\x00" * 8)
    ),
    skip_message="Does not support IDEA OFB",
)
class TestIDEAModeOFB:
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "IDEA"),
        ["idea-ofb.txt"],
        lambda key, **kwargs: IDEA(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        IDEA(b"\x00" * 16), modes.CFB(b"\x00" * 8)
    ),
    skip_message="Does not support IDEA CFB",
)
class TestIDEAModeCFB:
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "IDEA"),
        ["idea-cfb.txt"],
        lambda key, **kwargs: IDEA(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv)),
    )


class TestSEED:
    def test_key_size(self):
        cipher = SEED(b"\x00" * 16)
        assert cipher.key_size == 128

    def test_invalid_key_size(self):
        with pytest.raises(ValueError):
            SEED(b"\x00" * 17)

    def test_invalid_key_type(self):
        with pytest.raises(TypeError, match="key must be bytes"):
            SEED("0" * 16)  # type: ignore[arg-type]


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        SEED(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support SEED ECB",
)
class TestSEEDModeECB:
    test_ecb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["rfc-4269.txt"],
        lambda key, **kwargs: SEED(binascii.unhexlify(key)),
        lambda **kwargs: modes.ECB(),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        SEED(b"\x00" * 16), modes.CBC(b"\x00" * 16)
    ),
    skip_message="Does not support SEED CBC",
)
class TestSEEDModeCBC:
    test_cbc = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["rfc-4196.txt"],
        lambda key, **kwargs: SEED(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CBC(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        SEED(b"\x00" * 16), modes.OFB(b"\x00" * 16)
    ),
    skip_message="Does not support SEED OFB",
)
class TestSEEDModeOFB:
    test_ofb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["seed-ofb.txt"],
        lambda key, **kwargs: SEED(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.OFB(binascii.unhexlify(iv)),
    )


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        SEED(b"\x00" * 16), modes.CFB(b"\x00" * 16)
    ),
    skip_message="Does not support SEED CFB",
)
class TestSEEDModeCFB:
    test_cfb = generate_encrypt_test(
        load_nist_vectors,
        os.path.join("ciphers", "SEED"),
        ["seed-cfb.txt"],
        lambda key, **kwargs: SEED(binascii.unhexlify(key)),
        lambda iv, **kwargs: modes.CFB(binascii.unhexlify(iv)),
    )
