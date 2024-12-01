# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import os

import pytest

from cryptography.hazmat.primitives import keywrap
from cryptography.hazmat.primitives.ciphers import algorithms, modes

from ...utils import load_nist_vectors
from .utils import _load_all_params


class TestAESKeyWrap:
    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            algorithms.AES(b"\x00" * 16), modes.ECB()
        ),
        skip_message="Does not support AES key wrap (RFC 3394) because AES-ECB"
        " is unsupported",
    )
    def test_wrap(self, backend, subtests):
        params = _load_all_params(
            os.path.join("keywrap", "kwtestvectors"),
            ["KW_AE_128.txt", "KW_AE_192.txt", "KW_AE_256.txt"],
            load_nist_vectors,
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["k"])
                key_to_wrap = binascii.unhexlify(param["p"])
                wrapped_key = keywrap.aes_key_wrap(
                    wrapping_key, key_to_wrap, backend
                )
                assert param["c"] == binascii.hexlify(wrapped_key)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            algorithms.AES(b"\x00" * 16), modes.ECB()
        ),
        skip_message="Does not support AES key wrap (RFC 3394) because AES-ECB"
        " is unsupported",
    )
    def test_unwrap(self, backend, subtests):
        params = _load_all_params(
            os.path.join("keywrap", "kwtestvectors"),
            ["KW_AD_128.txt", "KW_AD_192.txt", "KW_AD_256.txt"],
            load_nist_vectors,
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["k"])
                wrapped_key = binascii.unhexlify(param["c"])
                if param.get("fail") is True:
                    with pytest.raises(keywrap.InvalidUnwrap):
                        keywrap.aes_key_unwrap(
                            wrapping_key, wrapped_key, backend
                        )
                else:
                    unwrapped_key = keywrap.aes_key_unwrap(
                        wrapping_key, wrapped_key, backend
                    )
                    assert param["p"] == binascii.hexlify(unwrapped_key)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            algorithms.AES(b"\x00" * 16), modes.ECB()
        ),
        skip_message="Does not support AES key wrap (RFC 3394) because AES-ECB"
        " is unsupported",
    )
    def test_wrap_invalid_key_length(self, backend):
        # The wrapping key must be of length [16, 24, 32]
        with pytest.raises(ValueError):
            keywrap.aes_key_wrap(b"badkey", b"sixteen_byte_key", backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            algorithms.AES(b"\x00" * 16), modes.ECB()
        ),
        skip_message="Does not support AES key wrap (RFC 3394) because AES-ECB"
        " is unsupported",
    )
    def test_unwrap_invalid_key_length(self, backend):
        with pytest.raises(ValueError):
            keywrap.aes_key_unwrap(b"badkey", b"\x00" * 24, backend)

    @pytest.mark.supported(
        only_if=lambda backend: backend.cipher_supported(
            algorithms.AES(b"\x00" * 16), modes.ECB()
        ),
        skip_message="Does not support AES key wrap (RFC 3394) because AES-ECB"
        " is unsupported",
    )
    def test_wrap_invalid_key_to_wrap_length(self, backend):
        # Keys to wrap must be at least 16 bytes long
        with pytest.raises(ValueError):
            keywrap.aes_key_wrap(b"sixteen_byte_key", b"\x00" * 15, backend)

        # Keys to wrap must be a multiple of 8 bytes
        with pytest.raises(ValueError):
            keywrap.aes_key_wrap(b"sixteen_byte_key", b"\x00" * 23, backend)

    def test_unwrap_invalid_wrapped_key_length(self, backend):
        # Keys to unwrap must be at least 24 bytes
        with pytest.raises(keywrap.InvalidUnwrap):
            keywrap.aes_key_unwrap(b"sixteen_byte_key", b"\x00" * 16, backend)

        # Keys to unwrap must be a multiple of 8 bytes
        with pytest.raises(keywrap.InvalidUnwrap):
            keywrap.aes_key_unwrap(b"sixteen_byte_key", b"\x00" * 27, backend)


@pytest.mark.supported(
    only_if=lambda backend: backend.cipher_supported(
        algorithms.AES(b"\x00" * 16), modes.ECB()
    ),
    skip_message="Does not support AES key wrap (RFC 5649) because AES-ECB"
    " is unsupported",
)
class TestAESKeyWrapWithPadding:
    def test_wrap(self, backend, subtests):
        params = _load_all_params(
            os.path.join("keywrap", "kwtestvectors"),
            ["KWP_AE_128.txt", "KWP_AE_192.txt", "KWP_AE_256.txt"],
            load_nist_vectors,
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["k"])
                key_to_wrap = binascii.unhexlify(param["p"])
                wrapped_key = keywrap.aes_key_wrap_with_padding(
                    wrapping_key, key_to_wrap, backend
                )
                assert param["c"] == binascii.hexlify(wrapped_key)

    def test_wrap_additional_vectors(self, backend, subtests):
        params = _load_all_params(
            "keywrap", ["kwp_botan.txt"], load_nist_vectors
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["key"])
                key_to_wrap = binascii.unhexlify(param["input"])
                wrapped_key = keywrap.aes_key_wrap_with_padding(
                    wrapping_key, key_to_wrap, backend
                )
                assert wrapped_key == binascii.unhexlify(param["output"])

    def test_unwrap(self, backend, subtests):
        params = _load_all_params(
            os.path.join("keywrap", "kwtestvectors"),
            ["KWP_AD_128.txt", "KWP_AD_192.txt", "KWP_AD_256.txt"],
            load_nist_vectors,
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["k"])
                wrapped_key = binascii.unhexlify(param["c"])
                if param.get("fail") is True:
                    with pytest.raises(keywrap.InvalidUnwrap):
                        keywrap.aes_key_unwrap_with_padding(
                            wrapping_key, wrapped_key, backend
                        )
                else:
                    unwrapped_key = keywrap.aes_key_unwrap_with_padding(
                        wrapping_key, wrapped_key, backend
                    )
                    assert param["p"] == binascii.hexlify(unwrapped_key)

    def test_unwrap_additional_vectors(self, backend, subtests):
        params = _load_all_params(
            "keywrap", ["kwp_botan.txt"], load_nist_vectors
        )
        for param in params:
            with subtests.test():
                wrapping_key = binascii.unhexlify(param["key"])
                wrapped_key = binascii.unhexlify(param["output"])
                unwrapped_key = keywrap.aes_key_unwrap_with_padding(
                    wrapping_key, wrapped_key, backend
                )
                assert unwrapped_key == binascii.unhexlify(param["input"])

    def test_unwrap_invalid_wrapped_key_length(self, backend):
        # Keys to unwrap must be at least 16 bytes
        with pytest.raises(
            keywrap.InvalidUnwrap, match="Must be at least 16 bytes"
        ):
            keywrap.aes_key_unwrap_with_padding(
                b"sixteen_byte_key", b"\x00" * 15, backend
            )

    def test_wrap_invalid_key_length(self, backend):
        with pytest.raises(ValueError, match="must be a valid AES key length"):
            keywrap.aes_key_wrap_with_padding(b"badkey", b"\x00", backend)

    def test_unwrap_invalid_key_length(self, backend):
        with pytest.raises(ValueError, match="must be a valid AES key length"):
            keywrap.aes_key_unwrap_with_padding(
                b"badkey", b"\x00" * 16, backend
            )
