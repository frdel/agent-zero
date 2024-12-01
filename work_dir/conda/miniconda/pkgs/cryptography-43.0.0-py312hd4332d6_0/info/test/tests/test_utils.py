# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import inspect
import os
import textwrap

import pretend
import pytest

import cryptography
import cryptography.utils
import cryptography_vectors
from cryptography.exceptions import UnsupportedAlgorithm, _Reasons

from . import deprecated_module
from .utils import (
    check_backend_support,
    load_cryptrec_vectors,
    load_ed25519_vectors,
    load_fips_dsa_key_pair_vectors,
    load_fips_dsa_sig_vectors,
    load_fips_ecdsa_key_pair_vectors,
    load_fips_ecdsa_signing_vectors,
    load_hash_vectors,
    load_kasvs_dh_vectors,
    load_kasvs_ecdh_vectors,
    load_nist_ccm_vectors,
    load_nist_kbkdf_vectors,
    load_nist_vectors,
    load_pkcs1_vectors,
    load_rsa_nist_vectors,
    load_vectors_from_file,
    load_x963_vectors,
    raises_unsupported_algorithm,
)


def test_int_to_bytes_rejects_zero_length():
    with pytest.raises(ValueError):
        cryptography.utils.int_to_bytes(123, 0)
    with pytest.raises(ValueError):
        cryptography.utils.int_to_bytes(0, 0)


def test_check_backend_support_skip():
    supported = pretend.stub(
        kwargs={"only_if": lambda backend: False, "skip_message": "Nope"}
    )
    node = pretend.stub(iter_markers=lambda x: [supported])
    item = pretend.stub(node=node)
    with pytest.raises(pytest.skip.Exception) as exc_info:
        check_backend_support(True, item)
    assert exc_info.value.args[0] == "Nope (True)"


def test_check_backend_support_no_skip():
    supported = pretend.stub(
        kwargs={"only_if": lambda backend: True, "skip_message": "Nope"}
    )
    node = pretend.stub(iter_markers=lambda x: [supported])
    item = pretend.stub(node=node)
    assert check_backend_support(None, item) is None


def test_load_nist_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.1
    # Config info for aes_values
    # AESVS GFSbox test data for CBC
    # State : Encrypt and Decrypt
    # Key Length : 128
    # Generated on Fri Apr 22 15:11:33 2011

    [ENCRYPT]

    COUNT = 0
    KEY = 00000000000000000000000000000000
    IV = 00000000000000000000000000000000
    PLAINTEXT = f34481ec3cc627bacd5dc3fb08f273e6
    CIPHERTEXT = 0336763e966d92595a567cc9ce537f5e

    COUNT = 1
    KEY = 00000000000000000000000000000000
    IV = 00000000000000000000000000000000
    PLAINTEXT = 9798c4640bad75c7c3227db910174e72
    CIPHERTEXT = a9a1631bf4996954ebc093957b234589

    [DECRYPT]

    COUNT = 0
    KEY = 00000000000000000000000000000000
    IV = 00000000000000000000000000000000
    CIPHERTEXT = 0336763e966d92595a567cc9ce537f5e
    PLAINTEXT = f34481ec3cc627bacd5dc3fb08f273e6

    COUNT = 1
    KEY = 00000000000000000000000000000000
    IV = 00000000000000000000000000000000
    CIPHERTEXT = a9a1631bf4996954ebc093957b234589
    PLAINTEXT = 9798c4640bad75c7c3227db910174e72
    """
    ).splitlines()

    assert load_nist_vectors(vector_data) == [
        {
            "key": b"00000000000000000000000000000000",
            "iv": b"00000000000000000000000000000000",
            "plaintext": b"f34481ec3cc627bacd5dc3fb08f273e6",
            "ciphertext": b"0336763e966d92595a567cc9ce537f5e",
        },
        {
            "key": b"00000000000000000000000000000000",
            "iv": b"00000000000000000000000000000000",
            "plaintext": b"9798c4640bad75c7c3227db910174e72",
            "ciphertext": b"a9a1631bf4996954ebc093957b234589",
        },
        {
            "key": b"00000000000000000000000000000000",
            "iv": b"00000000000000000000000000000000",
            "plaintext": b"f34481ec3cc627bacd5dc3fb08f273e6",
            "ciphertext": b"0336763e966d92595a567cc9ce537f5e",
        },
        {
            "key": b"00000000000000000000000000000000",
            "iv": b"00000000000000000000000000000000",
            "plaintext": b"9798c4640bad75c7c3227db910174e72",
            "ciphertext": b"a9a1631bf4996954ebc093957b234589",
        },
    ]


def test_load_nist_vectors_with_null_chars():
    vector_data = textwrap.dedent(
        """
    COUNT = 0
    KEY = thing\\0withnulls

    COUNT = 1
    KEY = 00000000000000000000000000000000
    """
    ).splitlines()

    assert load_nist_vectors(vector_data) == [
        {"key": b"thing\x00withnulls"},
        {"key": b"00000000000000000000000000000000"},
    ]


def test_load_ed25519_vectors():
    vector_data = (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60d75a9"
        "80182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a:d75a98018"
        "2b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a::e5564300c360"
        "ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc"
        "61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b:\n"
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb3d401"
        "7c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c:3d4017c3e"
        "843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c:72:92a009a9f0"
        "d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996"
        "e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c0072:\n"
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7fc51c"
        "d8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025:fc51cd8e6"
        "218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025:af82:6291d657"
        "deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f"
        "290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40aaf82:\n"
        "0d4a05b07352a5436e180356da0ae6efa0345ff7fb1572575772e8005ed978e9e61a1"
        "85bcef2613a6c7cb79763ce945d3b245d76114dd440bcf5f2dc1aa57057:e61a185bc"
        "ef2613a6c7cb79763ce945d3b245d76114dd440bcf5f2dc1aa57057:cbc77b:d9868d"
        "52c2bebce5f3fa5a79891970f309cb6591e3e1702a70276fa97c24b3a8e58606c38c9"
        "758529da50ee31b8219cba45271c689afa60b0ea26c99db19b00ccbc77b:\n"
    ).splitlines()

    assert load_ed25519_vectors(vector_data) == [
        {
            "secret_key": (
                "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7"
                "f60"
            ),
            "public_key": (
                "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f7075"
                "11a"
            ),
            "message": "",
            "signature": (
                "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490"
                "1555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e"
                "7a100b"
            ),
        },
        {
            "secret_key": (
                "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a"
                "6fb"
            ),
            "public_key": (
                "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af46"
                "60c"
            ),
            "message": "72",
            "signature": (
                "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb6"
                "9da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612"
                "bb0c00"
            ),
        },
        {
            "secret_key": (
                "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b445"
                "8f7"
            ),
            "public_key": (
                "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908"
                "025"
            ),
            "message": "af82",
            "signature": (
                "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac"
                "3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea"
                "1ec40a"
            ),
        },
        {
            "secret_key": (
                "0d4a05b07352a5436e180356da0ae6efa0345ff7fb1572575772e8005ed97"
                "8e9"
            ),
            "public_key": (
                "e61a185bcef2613a6c7cb79763ce945d3b245d76114dd440bcf5f2dc1aa57"
                "057"
            ),
            "message": "cbc77b",
            "signature": (
                "d9868d52c2bebce5f3fa5a79891970f309cb6591e3e1702a70276fa97c24b"
                "3a8e58606c38c9758529da50ee31b8219cba45271c689afa60b0ea26c99db"
                "19b00c"
            ),
        },
    ]


def test_load_cryptrec_vectors():
    vector_data = textwrap.dedent(
        """
    # Vectors taken from https://info.isl.ntt.co.jp/crypt/eng/camellia/
    # Download is t_camelia.txt

    # Camellia with 128-bit key

    K No.001 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

    P No.001 : 80 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    C No.001 : 07 92 3A 39 EB 0A 81 7D 1C 4D 87 BD B8 2D 1F 1C

    P No.002 : 40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    C No.002 : 48 CD 64 19 80 96 72 D2 34 92 60 D8 9A 08 D3 D3

    K No.002 : 10 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

    P No.001 : 80 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    C No.001 : 07 92 3A 39 EB 0A 81 7D 1C 4D 87 BD B8 2D 1F 1C
    """
    ).splitlines()

    assert load_cryptrec_vectors(vector_data) == [
        {
            "key": b"00000000000000000000000000000000",
            "plaintext": b"80000000000000000000000000000000",
            "ciphertext": b"07923A39EB0A817D1C4D87BDB82D1F1C",
        },
        {
            "key": b"00000000000000000000000000000000",
            "plaintext": b"40000000000000000000000000000000",
            "ciphertext": b"48CD6419809672D2349260D89A08D3D3",
        },
        {
            "key": b"10000000000000000000000000000000",
            "plaintext": b"80000000000000000000000000000000",
            "ciphertext": b"07923A39EB0A817D1C4D87BDB82D1F1C",
        },
    ]


def test_load_cryptrec_vectors_invalid():
    vector_data = textwrap.dedent(
        """
    # Vectors taken from https://info.isl.ntt.co.jp/crypt/eng/camellia/
    # Download is t_camelia.txt

    # Camellia with 128-bit key

    E No.001 : 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
    """
    ).splitlines()

    with pytest.raises(ValueError):
        load_cryptrec_vectors(vector_data)


def test_load_hash_vectors():
    vector_data = textwrap.dedent(
        """

        # https://tools.ietf.org/html/rfc1321
        [irrelevant]

        Len = 0
        Msg = 00
        MD = d41d8cd98f00b204e9800998ecf8427e

        Len = 8
        Msg = 61
        MD = 0cc175b9c0f1b6a831c399e269772661

        Len = 24
        Msg = 616263
        MD = 900150983cd24fb0d6963f7d28e17f72

        Len = 112
        Msg = 6d65737361676520646967657374
        MD = f96b697d7cb7938d525a2f31aaf161d0
    """
    ).splitlines()
    assert load_hash_vectors(vector_data) == [
        (b"", "d41d8cd98f00b204e9800998ecf8427e"),
        (b"61", "0cc175b9c0f1b6a831c399e269772661"),
        (b"616263", "900150983cd24fb0d6963f7d28e17f72"),
        (b"6d65737361676520646967657374", "f96b697d7cb7938d525a2f31aaf161d0"),
    ]


def test_load_hmac_vectors():
    vector_data = textwrap.dedent(
        """
Len = 224
# "Jefe"
Key = 4a656665
# "what do ya want for nothing?"
Msg = 7768617420646f2079612077616e7420666f72206e6f7468696e673f
MD = 750c783e6ab0b503eaa86e310a5db738
    """
    ).splitlines()
    assert load_hash_vectors(vector_data) == [
        (
            b"7768617420646f2079612077616e7420666f72206e6f7468696e673f",
            "750c783e6ab0b503eaa86e310a5db738",
            b"4a656665",
        ),
    ]


def test_load_hash_vectors_bad_data():
    vector_data = textwrap.dedent(
        """
        # https://tools.ietf.org/html/rfc1321

        Len = 0
        Msg = 00
        UNKNOWN=Hello World
    """
    ).splitlines()
    with pytest.raises(ValueError):
        load_hash_vectors(vector_data)


def test_load_vectors_from_file():
    vectors = load_vectors_from_file(
        os.path.join("ciphers", "Blowfish", "bf-cfb.txt"),
        load_nist_vectors,
    )
    assert vectors == [
        {
            "key": b"0123456789ABCDEFF0E1D2C3B4A59687",
            "iv": b"FEDCBA9876543210",
            "plaintext": (
                b"37363534333231204E6F77206973207468652074696D6520666F722000"
            ),
            "ciphertext": (
                b"E73214A2822139CAF26ECF6D2EB9E76E3DA3DE04D1517200519D57A6C3"
            ),
        }
    ]


def test_load_nist_gcm_vectors():
    vector_data = textwrap.dedent(
        """
        [Keylen = 128]
        [IVlen = 96]
        [PTlen = 0]
        [AADlen = 0]
        [Taglen = 128]

        Count = 0
        Key = 11754cd72aec309bf52f7687212e8957
        IV = 3c819d9a9bed087615030b65
        PT =
        AAD =
        CT =
        Tag = 250327c674aaf477aef2675748cf6971

        Count = 1
        Key = 272f16edb81a7abbea887357a58c1917
        IV = 794ec588176c703d3d2a7a07
        PT =
        AAD =
        CT =
        Tag = b6e6f197168f5049aeda32dafbdaeb

        Count = 2
        Key = a49a5e26a2f8cb63d05546c2a62f5343
        IV = 907763b19b9b4ab6bd4f0281
        CT =
        AAD =
        Tag = a2be08210d8c470a8df6e8fbd79ec5cf
        FAIL

        Count = 3
        Key = 5c1155084cc0ede76b3bc22e9f7574ef
        IV = 9549e4ba69a61cad7856efc1
        PT = d1448fa852b84408e2dad8381f363de7
        AAD = e98e9d9c618e46fef32660976f854ee3
        CT = f78b60ca125218493bea1c50a2e12ef4
        Tag = d72da7f5c6cf0bca7242c71835809449

        [Keylen = 128]
        [IVlen = 96]
        [PTlen = 0]
        [AADlen = 0]
        [Taglen = 120]

        Count = 0
        Key = eac258e99c55e6ae8ef1da26640613d7
        IV = 4e8df20faaf2c8eebe922902
        CT =
        AAD =
        Tag = e39aeaebe86aa309a4d062d6274339
        PT =

        Count = 1
        Key = 3726cf02fcc6b8639a5497652c94350d
        IV = 55fef82cde693ce76efcc193
        CT =
        AAD =
        Tag = 3d68111a81ed22d2ef5bccac4fc27f
        FAIL

        Count = 2
        Key = f202299d5fd74f03b12d2119a6c4c038
        IV = eec51e7958c3f20a1bb71815
        CT =
        AAD =
        Tag = a81886b3fb26e51fca87b267e1e157
        FAIL

        Count = 3
        Key = fd52925f39546b4c55ffb6b20c59898c
        IV = f5cf3227444afd905a5f6dba
        CT =
        AAD =
        Tag = 1665b0f1a0b456e1664cfd3de08ccd
        PT =

        [Keylen = 128]
        [IVlen = 8]
        [PTlen = 104]
        [AADlen = 0]
        [Taglen = 128]

        Count = 0
        Key = 58fab7632bcf10d2bcee58520bf37414
        IV = 3c
        CT = 15c4db4cbb451211179d57017f
        AAD =
        Tag = eae841d4355feeb3f786bc86625f1e5b
        FAIL
    """
    ).splitlines()
    assert load_nist_vectors(vector_data) == [
        {
            "aad": b"",
            "pt": b"",
            "iv": b"3c819d9a9bed087615030b65",
            "tag": b"250327c674aaf477aef2675748cf6971",
            "key": b"11754cd72aec309bf52f7687212e8957",
            "ct": b"",
        },
        {
            "aad": b"",
            "pt": b"",
            "iv": b"794ec588176c703d3d2a7a07",
            "tag": b"b6e6f197168f5049aeda32dafbdaeb",
            "key": b"272f16edb81a7abbea887357a58c1917",
            "ct": b"",
        },
        {
            "aad": b"",
            "iv": b"907763b19b9b4ab6bd4f0281",
            "tag": b"a2be08210d8c470a8df6e8fbd79ec5cf",
            "key": b"a49a5e26a2f8cb63d05546c2a62f5343",
            "ct": b"",
            "fail": True,
        },
        {
            "aad": b"e98e9d9c618e46fef32660976f854ee3",
            "pt": b"d1448fa852b84408e2dad8381f363de7",
            "iv": b"9549e4ba69a61cad7856efc1",
            "tag": b"d72da7f5c6cf0bca7242c71835809449",
            "key": b"5c1155084cc0ede76b3bc22e9f7574ef",
            "ct": b"f78b60ca125218493bea1c50a2e12ef4",
        },
        {
            "aad": b"",
            "pt": b"",
            "iv": b"4e8df20faaf2c8eebe922902",
            "tag": b"e39aeaebe86aa309a4d062d6274339",
            "key": b"eac258e99c55e6ae8ef1da26640613d7",
            "ct": b"",
        },
        {
            "aad": b"",
            "iv": b"55fef82cde693ce76efcc193",
            "tag": b"3d68111a81ed22d2ef5bccac4fc27f",
            "key": b"3726cf02fcc6b8639a5497652c94350d",
            "ct": b"",
            "fail": True,
        },
        {
            "aad": b"",
            "iv": b"eec51e7958c3f20a1bb71815",
            "tag": b"a81886b3fb26e51fca87b267e1e157",
            "key": b"f202299d5fd74f03b12d2119a6c4c038",
            "ct": b"",
            "fail": True,
        },
        {
            "aad": b"",
            "pt": b"",
            "iv": b"f5cf3227444afd905a5f6dba",
            "tag": b"1665b0f1a0b456e1664cfd3de08ccd",
            "key": b"fd52925f39546b4c55ffb6b20c59898c",
            "ct": b"",
        },
        {
            "aad": b"",
            "iv": b"3c",
            "tag": b"eae841d4355feeb3f786bc86625f1e5b",
            "key": b"58fab7632bcf10d2bcee58520bf37414",
            "ct": b"15c4db4cbb451211179d57017f",
            "fail": True,
        },
    ]


def test_load_pkcs1_vectors():
    vector_data = textwrap.dedent(
        """
    Test vectors for RSA-PSS
    ========================

    This file contains an extract of the original pss-vect.txt

    Key lengths:

    Key  8: 1031 bits
    Key  9: 1536 bits
    ===========================================================================

    <snip>

    # Example 8: A 1031-bit RSA key pair
    # -----------------------------------


    # Public key
    # ----------

    # Modulus:
    49 53 70 a1 fb 18 54 3c 16 d3 63 1e 31 63 25 5d
    f6 2b e6 ee e8 90 d5 f2 55 09 e4 f7 78 a8 ea 6f
    bb bc df 85 df f6 4e 0d 97 20 03 ab 36 81 fb ba
    6d d4 1f d5 41 82 9b 2e 58 2d e9 f2 a4 a4 e0 a2
    d0 90 0b ef 47 53 db 3c ee 0e e0 6c 7d fa e8 b1
    d5 3b 59 53 21 8f 9c ce ea 69 5b 08 66 8e de aa
    dc ed 94 63 b1 d7 90 d5 eb f2 7e 91 15 b4 6c ad
    4d 9a 2b 8e fa b0 56 1b 08 10 34 47 39 ad a0 73
    3f

    # Exponent:
    01 00 01

    # Private key
    # -----------

    # Modulus:
    49 53 70 a1 fb 18 54 3c 16 d3 63 1e 31 63 25 5d
    f6 2b e6 ee e8 90 d5 f2 55 09 e4 f7 78 a8 ea 6f
    bb bc df 85 df f6 4e 0d 97 20 03 ab 36 81 fb ba
    6d d4 1f d5 41 82 9b 2e 58 2d e9 f2 a4 a4 e0 a2
    d0 90 0b ef 47 53 db 3c ee 0e e0 6c 7d fa e8 b1
    d5 3b 59 53 21 8f 9c ce ea 69 5b 08 66 8e de aa
    dc ed 94 63 b1 d7 90 d5 eb f2 7e 91 15 b4 6c ad
    4d 9a 2b 8e fa b0 56 1b 08 10 34 47 39 ad a0 73
    3f

    # Public exponent:
    01 00 01

    # Exponent:
    6c 66 ff e9 89 80 c3 8f cd ea b5 15 98 98 83 61
    65 f4 b4 b8 17 c4 f6 a8 d4 86 ee 4e a9 13 0f e9
    b9 09 2b d1 36 d1 84 f9 5f 50 4a 60 7e ac 56 58
    46 d2 fd d6 59 7a 89 67 c7 39 6e f9 5a 6e ee bb
    45 78 a6 43 96 6d ca 4d 8e e3 de 84 2d e6 32 79
    c6 18 15 9c 1a b5 4a 89 43 7b 6a 61 20 e4 93 0a
    fb 52 a4 ba 6c ed 8a 49 47 ac 64 b3 0a 34 97 cb
    e7 01 c2 d6 26 6d 51 72 19 ad 0e c6 d3 47 db e9

    # Prime 1:
    08 da d7 f1 13 63 fa a6 23 d5 d6 d5 e8 a3 19 32
    8d 82 19 0d 71 27 d2 84 6c 43 9b 0a b7 26 19 b0
    a4 3a 95 32 0e 4e c3 4f c3 a9 ce a8 76 42 23 05
    bd 76 c5 ba 7b e9 e2 f4 10 c8 06 06 45 a1 d2 9e
    db

    # Prime 2:
    08 47 e7 32 37 6f c7 90 0f 89 8e a8 2e b2 b0 fc
    41 85 65 fd ae 62 f7 d9 ec 4c e2 21 7b 97 99 0d
    d2 72 db 15 7f 99 f6 3c 0d cb b9 fb ac db d4 c4
    da db 6d f6 77 56 35 8c a4 17 48 25 b4 8f 49 70
    6d

    # Prime exponent 1:
    05 c2 a8 3c 12 4b 36 21 a2 aa 57 ea 2c 3e fe 03
    5e ff 45 60 f3 3d de bb 7a da b8 1f ce 69 a0 c8
    c2 ed c1 65 20 dd a8 3d 59 a2 3b e8 67 96 3a c6
    5f 2c c7 10 bb cf b9 6e e1 03 de b7 71 d1 05 fd
    85

    # Prime exponent 2:
    04 ca e8 aa 0d 9f aa 16 5c 87 b6 82 ec 14 0b 8e
    d3 b5 0b 24 59 4b 7a 3b 2c 22 0b 36 69 bb 81 9f
    98 4f 55 31 0a 1a e7 82 36 51 d4 a0 2e 99 44 79
    72 59 51 39 36 34 34 e5 e3 0a 7e 7d 24 15 51 e1
    b9

    # Coefficient:
    07 d3 e4 7b f6 86 60 0b 11 ac 28 3c e8 8d bb 3f
    60 51 e8 ef d0 46 80 e4 4c 17 1e f5 31 b8 0b 2b
    7c 39 fc 76 63 20 e2 cf 15 d8 d9 98 20 e9 6f f3
    0d c6 96 91 83 9c 4b 40 d7 b0 6e 45 30 7d c9 1f
    3f

    # RSA-PSS signing of 6 random messages with random salts
    # -------------------------------------------------------
    # PSS Example 8.1

    # -----------------

    # Message to be signed:
    81 33 2f 4b e6 29 48 41 5e a1 d8 99 79 2e ea cf
    6c 6e 1d b1 da 8b e1 3b 5c ea 41 db 2f ed 46 70
    92 e1 ff 39 89 14 c7 14 25 97 75 f5 95 f8 54 7f
    73 56 92 a5 75 e6 92 3a f7 8f 22 c6 99 7d db 90
    fb 6f 72 d7 bb 0d d5 74 4a 31 de cd 3d c3 68 58
    49 83 6e d3 4a ec 59 63 04 ad 11 84 3c 4f 88 48
    9f 20 97 35 f5 fb 7f da f7 ce c8 ad dc 58 18 16
    8f 88 0a cb f4 90 d5 10 05 b7 a8 e8 4e 43 e5 42
    87 97 75 71 dd 99 ee a4 b1 61 eb 2d f1 f5 10 8f
    12 a4 14 2a 83 32 2e db 05 a7 54 87 a3 43 5c 9a
    78 ce 53 ed 93 bc 55 08 57 d7 a9 fb

    # Salt:
    1d 65 49 1d 79 c8 64 b3 73 00 9b e6 f6 f2 46 7b
    ac 4c 78 fa

    # Signature:
    02 62 ac 25 4b fa 77 f3 c1 ac a2 2c 51 79 f8 f0
    40 42 2b 3c 5b af d4 0a 8f 21 cf 0f a5 a6 67 cc
    d5 99 3d 42 db af b4 09 c5 20 e2 5f ce 2b 1e e1
    e7 16 57 7f 1e fa 17 f3 da 28 05 2f 40 f0 41 9b
    23 10 6d 78 45 aa f0 11 25 b6 98 e7 a4 df e9 2d
    39 67 bb 00 c4 d0 d3 5b a3 55 2a b9 a8 b3 ee f0
    7c 7f ec db c5 42 4a c4 db 1e 20 cb 37 d0 b2 74
    47 69 94 0e a9 07 e1 7f bb ca 67 3b 20 52 23 80
    c5

    # PSS Example 8.2

    # -----------------

    # Message to be signed:
    e2 f9 6e af 0e 05 e7 ba 32 6e cc a0 ba 7f d2 f7
    c0 23 56 f3 ce de 9d 0f aa bf 4f cc 8e 60 a9 73
    e5 59 5f d9 ea 08

    # Salt:
    43 5c 09 8a a9 90 9e b2 37 7f 12 48 b0 91 b6 89
    87 ff 18 38

    # Signature:
    27 07 b9 ad 51 15 c5 8c 94 e9 32 e8 ec 0a 28 0f
    56 33 9e 44 a1 b5 8d 4d dc ff 2f 31 2e 5f 34 dc
    fe 39 e8 9c 6a 94 dc ee 86 db bd ae 5b 79 ba 4e
    08 19 a9 e7 bf d9 d9 82 e7 ee 6c 86 ee 68 39 6e
    8b 3a 14 c9 c8 f3 4b 17 8e b7 41 f9 d3 f1 21 10
    9b f5 c8 17 2f ad a2 e7 68 f9 ea 14 33 03 2c 00
    4a 8a a0 7e b9 90 00 0a 48 dc 94 c8 ba c8 aa be
    2b 09 b1 aa 46 c0 a2 aa 0e 12 f6 3f bb a7 75 ba
    7e

    # <snip>

    # =============================================

    # Example 9: A 1536-bit RSA key pair
    # -----------------------------------


    # Public key
    # ----------

    # Modulus:
    e6 bd 69 2a c9 66 45 79 04 03 fd d0 f5 be b8 b9
    bf 92 ed 10 00 7f c3 65 04 64 19 dd 06 c0 5c 5b
    5b 2f 48 ec f9 89 e4 ce 26 91 09 97 9c bb 40 b4
    a0 ad 24 d2 24 83 d1 ee 31 5a d4 cc b1 53 42 68
    35 26 91 c5 24 f6 dd 8e 6c 29 d2 24 cf 24 69 73
    ae c8 6c 5b f6 b1 40 1a 85 0d 1b 9a d1 bb 8c bc
    ec 47 b0 6f 0f 8c 7f 45 d3 fc 8f 31 92 99 c5 43
    3d db c2 b3 05 3b 47 de d2 ec d4 a4 ca ef d6 14
    83 3d c8 bb 62 2f 31 7e d0 76 b8 05 7f e8 de 3f
    84 48 0a d5 e8 3e 4a 61 90 4a 4f 24 8f b3 97 02
    73 57 e1 d3 0e 46 31 39 81 5c 6f d4 fd 5a c5 b8
    17 2a 45 23 0e cb 63 18 a0 4f 14 55 d8 4e 5a 8b

    # Exponent:
    01 00 01

    # Private key
    # -----------

    # Modulus:
    e6 bd 69 2a c9 66 45 79 04 03 fd d0 f5 be b8 b9
    bf 92 ed 10 00 7f c3 65 04 64 19 dd 06 c0 5c 5b
    5b 2f 48 ec f9 89 e4 ce 26 91 09 97 9c bb 40 b4
    a0 ad 24 d2 24 83 d1 ee 31 5a d4 cc b1 53 42 68
    35 26 91 c5 24 f6 dd 8e 6c 29 d2 24 cf 24 69 73
    ae c8 6c 5b f6 b1 40 1a 85 0d 1b 9a d1 bb 8c bc
    ec 47 b0 6f 0f 8c 7f 45 d3 fc 8f 31 92 99 c5 43
    3d db c2 b3 05 3b 47 de d2 ec d4 a4 ca ef d6 14
    83 3d c8 bb 62 2f 31 7e d0 76 b8 05 7f e8 de 3f
    84 48 0a d5 e8 3e 4a 61 90 4a 4f 24 8f b3 97 02
    73 57 e1 d3 0e 46 31 39 81 5c 6f d4 fd 5a c5 b8
    17 2a 45 23 0e cb 63 18 a0 4f 14 55 d8 4e 5a 8b

    # Public exponent:
    01 00 01

    # Exponent:
    6a 7f d8 4f b8 5f ad 07 3b 34 40 6d b7 4f 8d 61
    a6 ab c1 21 96 a9 61 dd 79 56 5e 9d a6 e5 18 7b
    ce 2d 98 02 50 f7 35 95 75 35 92 70 d9 15 90 bb
    0e 42 7c 71 46 0b 55 d5 14 10 b1 91 bc f3 09 fe
    a1 31 a9 2c 8e 70 27 38 fa 71 9f 1e 00 41 f5 2e
    40 e9 1f 22 9f 4d 96 a1 e6 f1 72 e1 55 96 b4 51
    0a 6d ae c2 61 05 f2 be bc 53 31 6b 87 bd f2 13
    11 66 60 70 e8 df ee 69 d5 2c 71 a9 76 ca ae 79
    c7 2b 68 d2 85 80 dc 68 6d 9f 51 29 d2 25 f8 2b
    3d 61 55 13 a8 82 b3 db 91 41 6b 48 ce 08 88 82
    13 e3 7e eb 9a f8 00 d8 1c ab 32 8c e4 20 68 99
    03 c0 0c 7b 5f d3 1b 75 50 3a 6d 41 96 84 d6 29

    # Prime 1:
    f8 eb 97 e9 8d f1 26 64 ee fd b7 61 59 6a 69 dd
    cd 0e 76 da ec e6 ed 4b f5 a1 b5 0a c0 86 f7 92
    8a 4d 2f 87 26 a7 7e 51 5b 74 da 41 98 8f 22 0b
    1c c8 7a a1 fc 81 0c e9 9a 82 f2 d1 ce 82 1e dc
    ed 79 4c 69 41 f4 2c 7a 1a 0b 8c 4d 28 c7 5e c6
    0b 65 22 79 f6 15 4a 76 2a ed 16 5d 47 de e3 67

    # Prime 2:
    ed 4d 71 d0 a6 e2 4b 93 c2 e5 f6 b4 bb e0 5f 5f
    b0 af a0 42 d2 04 fe 33 78 d3 65 c2 f2 88 b6 a8
    da d7 ef e4 5d 15 3e ef 40 ca cc 7b 81 ff 93 40
    02 d1 08 99 4b 94 a5 e4 72 8c d9 c9 63 37 5a e4
    99 65 bd a5 5c bf 0e fe d8 d6 55 3b 40 27 f2 d8
    62 08 a6 e6 b4 89 c1 76 12 80 92 d6 29 e4 9d 3d

    # Prime exponent 1:
    2b b6 8b dd fb 0c 4f 56 c8 55 8b ff af 89 2d 80
    43 03 78 41 e7 fa 81 cf a6 1a 38 c5 e3 9b 90 1c
    8e e7 11 22 a5 da 22 27 bd 6c de eb 48 14 52 c1
    2a d3 d6 1d 5e 4f 77 6a 0a b5 56 59 1b ef e3 e5
    9e 5a 7f dd b8 34 5e 1f 2f 35 b9 f4 ce e5 7c 32
    41 4c 08 6a ec 99 3e 93 53 e4 80 d9 ee c6 28 9f

    # Prime exponent 2:
    4f f8 97 70 9f ad 07 97 46 49 45 78 e7 0f d8 54
    61 30 ee ab 56 27 c4 9b 08 0f 05 ee 4a d9 f3 e4
    b7 cb a9 d6 a5 df f1 13 a4 1c 34 09 33 68 33 f1
    90 81 6d 8a 6b c4 2e 9b ec 56 b7 56 7d 0f 3c 9c
    69 6d b6 19 b2 45 d9 01 dd 85 6d b7 c8 09 2e 77
    e9 a1 cc cd 56 ee 4d ba 42 c5 fd b6 1a ec 26 69

    # Coefficient:
    77 b9 d1 13 7b 50 40 4a 98 27 29 31 6e fa fc 7d
    fe 66 d3 4e 5a 18 26 00 d5 f3 0a 0a 85 12 05 1c
    56 0d 08 1d 4d 0a 18 35 ec 3d 25 a6 0f 4e 4d 6a
    a9 48 b2 bf 3d bb 5b 12 4c bb c3 48 92 55 a3 a9
    48 37 2f 69 78 49 67 45 f9 43 e1 db 4f 18 38 2c
    ea a5 05 df c6 57 57 bb 3f 85 7a 58 dc e5 21 56

    # PKCS#1 v1.5 Signature Example 2.17

    # -----------------

    # Message to be signed:
    06 ad d7 5a b6 89 de 06 77 44 e6 9a 2e bd 4b 90
    fa 93 83 00 3c d0 5f f5 36 cb f2 94 cd 21 5f 09
    23 b7 fc 90 04 f0 aa 18 52 71 a1 d0 06 1f d0 e9
    77 7a d1 ec 0c 71 59 1f 57 8b f7 b8 e5 a1

    # Signature:
    45 14 21 0e 54 1d 5b ad 7d d6 0a e5 49 b9 43 ac
    c4 4f 21 39 0d f5 b6 13 18 45 5a 17 61 0d f5 b7
    4d 84 ae d2 32 f1 7e 59 d9 1d d2 65 99 22 f8 12
    db d4 96 81 69 03 84 b9 54 e9 ad fb 9b 1a 96 8c
    0c bf f7 63 ec ee d6 27 50 c5 91 64 b5 e0 80 a8
    fe f3 d5 5b fe 2a cf ad 27 52 a6 a8 45 9f a1 fa
    b4 9a d3 78 c6 96 4b 23 ee 97 fd 10 34 61 0c 5c
    c1 4c 61 e0 eb fb 17 11 f8 ad e9 6f e6 55 7b 38

    # <snip>

    # =============================================

    # <snip>
    """
    ).splitlines()

    vectors = tuple(load_pkcs1_vectors(vector_data))
    expected = (
        (
            {
                "modulus": int(
                    "495370a1fb18543c16d3631e3163255df62be6eee890d5f25509e4f77"
                    "8a8ea6fbbbcdf85dff64e0d972003ab3681fbba6dd41fd541829b2e58"
                    "2de9f2a4a4e0a2d0900bef4753db3cee0ee06c7dfae8b1d53b5953218"
                    "f9cceea695b08668edeaadced9463b1d790d5ebf27e9115b46cad4d9a"
                    "2b8efab0561b0810344739ada0733f",
                    16,
                ),
                "public_exponent": int("10001", 16),
                "private_exponent": int(
                    "6c66ffe98980c38fcdeab5159898836165f4b4b817c4f6a8d486ee4ea"
                    "9130fe9b9092bd136d184f95f504a607eac565846d2fdd6597a8967c7"
                    "396ef95a6eeebb4578a643966dca4d8ee3de842de63279c618159c1ab"
                    "54a89437b6a6120e4930afb52a4ba6ced8a4947ac64b30a3497cbe701"
                    "c2d6266d517219ad0ec6d347dbe9",
                    16,
                ),
                "p": int(
                    "8dad7f11363faa623d5d6d5e8a319328d82190d7127d2846c439b0ab7"
                    "2619b0a43a95320e4ec34fc3a9cea876422305bd76c5ba7be9e2f410c"
                    "8060645a1d29edb",
                    16,
                ),
                "q": int(
                    "847e732376fc7900f898ea82eb2b0fc418565fdae62f7d9ec4ce2217b"
                    "97990dd272db157f99f63c0dcbb9fbacdbd4c4dadb6df67756358ca41"
                    "74825b48f49706d",
                    16,
                ),
                "dmp1": int(
                    "05c2a83c124b3621a2aa57ea2c3efe035eff4560f33ddebb7adab81fc"
                    "e69a0c8c2edc16520dda83d59a23be867963ac65f2cc710bbcfb96ee1"
                    "03deb771d105fd85",
                    16,
                ),
                "dmq1": int(
                    "04cae8aa0d9faa165c87b682ec140b8ed3b50b24594b7a3b2c220b366"
                    "9bb819f984f55310a1ae7823651d4a02e99447972595139363434e5e3"
                    "0a7e7d241551e1b9",
                    16,
                ),
                "iqmp": int(
                    "07d3e47bf686600b11ac283ce88dbb3f6051e8efd04680e44c171ef53"
                    "1b80b2b7c39fc766320e2cf15d8d99820e96ff30dc69691839c4b40d7"
                    "b06e45307dc91f3f",
                    16,
                ),
                "examples": [
                    {
                        "message": b"81332f4be62948415ea1d899792eeacf6c6e1db1d"
                        b"a8be13b5cea41db2fed467092e1ff398914c71425"
                        b"9775f595f8547f735692a575e6923af78f22c6997"
                        b"ddb90fb6f72d7bb0dd5744a31decd3dc368584983"
                        b"6ed34aec596304ad11843c4f88489f209735f5fb7"
                        b"fdaf7cec8addc5818168f880acbf490d51005b7a8"
                        b"e84e43e54287977571dd99eea4b161eb2df1f5108"
                        b"f12a4142a83322edb05a75487a3435c9a78ce53ed"
                        b"93bc550857d7a9fb",
                        "salt": b"1d65491d79c864b373009be6f6f2467bac4c78fa",
                        "signature": b"0262ac254bfa77f3c1aca22c5179f8f040422b3"
                        b"c5bafd40a8f21cf0fa5a667ccd5993d42dbafb4"
                        b"09c520e25fce2b1ee1e716577f1efa17f3da280"
                        b"52f40f0419b23106d7845aaf01125b698e7a4df"
                        b"e92d3967bb00c4d0d35ba3552ab9a8b3eef07c7"
                        b"fecdbc5424ac4db1e20cb37d0b2744769940ea9"
                        b"07e17fbbca673b20522380c5",
                    },
                    {
                        "message": b"e2f96eaf0e05e7ba326ecca0ba7fd2f7c02356f3c"
                        b"ede9d0faabf4fcc8e60a973e5595fd9ea08",
                        "salt": b"435c098aa9909eb2377f1248b091b68987ff1838",
                        "signature": b"2707b9ad5115c58c94e932e8ec0a280f56339e4"
                        b"4a1b58d4ddcff2f312e5f34dcfe39e89c6a94dc"
                        b"ee86dbbdae5b79ba4e0819a9e7bfd9d982e7ee6"
                        b"c86ee68396e8b3a14c9c8f34b178eb741f9d3f1"
                        b"21109bf5c8172fada2e768f9ea1433032c004a8"
                        b"aa07eb990000a48dc94c8bac8aabe2b09b1aa46"
                        b"c0a2aa0e12f63fbba775ba7e",
                    },
                ],
            },
            {
                "modulus": int(
                    "495370a1fb18543c16d3631e3163255df62be6eee890d5f25509e4f77"
                    "8a8ea6fbbbcdf85dff64e0d972003ab3681fbba6dd41fd541829b2e58"
                    "2de9f2a4a4e0a2d0900bef4753db3cee0ee06c7dfae8b1d53b5953218"
                    "f9cceea695b08668edeaadced9463b1d790d5ebf27e9115b46cad4d9a"
                    "2b8efab0561b0810344739ada0733f",
                    16,
                ),
                "public_exponent": int("10001", 16),
            },
        ),
        (
            {
                "modulus": int(
                    "e6bd692ac96645790403fdd0f5beb8b9bf92ed10007fc365046419dd0"
                    "6c05c5b5b2f48ecf989e4ce269109979cbb40b4a0ad24d22483d1ee31"
                    "5ad4ccb1534268352691c524f6dd8e6c29d224cf246973aec86c5bf6b"
                    "1401a850d1b9ad1bb8cbcec47b06f0f8c7f45d3fc8f319299c5433ddb"
                    "c2b3053b47ded2ecd4a4caefd614833dc8bb622f317ed076b8057fe8d"
                    "e3f84480ad5e83e4a61904a4f248fb397027357e1d30e463139815c6f"
                    "d4fd5ac5b8172a45230ecb6318a04f1455d84e5a8b",
                    16,
                ),
                "public_exponent": int("10001", 16),
                "private_exponent": int(
                    "6a7fd84fb85fad073b34406db74f8d61a6abc12196a961dd79565e9da"
                    "6e5187bce2d980250f7359575359270d91590bb0e427c71460b55d514"
                    "10b191bcf309fea131a92c8e702738fa719f1e0041f52e40e91f229f4"
                    "d96a1e6f172e15596b4510a6daec26105f2bebc53316b87bdf2131166"
                    "6070e8dfee69d52c71a976caae79c72b68d28580dc686d9f5129d225f"
                    "82b3d615513a882b3db91416b48ce08888213e37eeb9af800d81cab32"
                    "8ce420689903c00c7b5fd31b75503a6d419684d629",
                    16,
                ),
                "p": int(
                    "f8eb97e98df12664eefdb761596a69ddcd0e76daece6ed4bf5a1b50ac"
                    "086f7928a4d2f8726a77e515b74da41988f220b1cc87aa1fc810ce99a"
                    "82f2d1ce821edced794c6941f42c7a1a0b8c4d28c75ec60b652279f61"
                    "54a762aed165d47dee367",
                    16,
                ),
                "q": int(
                    "ed4d71d0a6e24b93c2e5f6b4bbe05f5fb0afa042d204fe3378d365c2f"
                    "288b6a8dad7efe45d153eef40cacc7b81ff934002d108994b94a5e472"
                    "8cd9c963375ae49965bda55cbf0efed8d6553b4027f2d86208a6e6b48"
                    "9c176128092d629e49d3d",
                    16,
                ),
                "dmp1": int(
                    "2bb68bddfb0c4f56c8558bffaf892d8043037841e7fa81cfa61a38c5e"
                    "39b901c8ee71122a5da2227bd6cdeeb481452c12ad3d61d5e4f776a0a"
                    "b556591befe3e59e5a7fddb8345e1f2f35b9f4cee57c32414c086aec9"
                    "93e9353e480d9eec6289f",
                    16,
                ),
                "dmq1": int(
                    "4ff897709fad079746494578e70fd8546130eeab5627c49b080f05ee4"
                    "ad9f3e4b7cba9d6a5dff113a41c3409336833f190816d8a6bc42e9bec"
                    "56b7567d0f3c9c696db619b245d901dd856db7c8092e77e9a1cccd56e"
                    "e4dba42c5fdb61aec2669",
                    16,
                ),
                "iqmp": int(
                    "77b9d1137b50404a982729316efafc7dfe66d34e5a182600d5f30a0a8"
                    "512051c560d081d4d0a1835ec3d25a60f4e4d6aa948b2bf3dbb5b124c"
                    "bbc3489255a3a948372f6978496745f943e1db4f18382ceaa505dfc65"
                    "757bb3f857a58dce52156",
                    16,
                ),
                "examples": [
                    {
                        "message": b"06add75ab689de067744e69a2ebd4b90fa9383003"
                        b"cd05ff536cbf294cd215f0923b7fc9004f0aa1852"
                        b"71a1d0061fd0e9777ad1ec0c71591f578bf7b8e5a"
                        b"1",
                        "signature": b"4514210e541d5bad7dd60ae549b943acc44f213"
                        b"90df5b61318455a17610df5b74d84aed232f17e"
                        b"59d91dd2659922f812dbd49681690384b954e9a"
                        b"dfb9b1a968c0cbff763eceed62750c59164b5e0"
                        b"80a8fef3d55bfe2acfad2752a6a8459fa1fab49"
                        b"ad378c6964b23ee97fd1034610c5cc14c61e0eb"
                        b"fb1711f8ade96fe6557b38",
                    }
                ],
            },
            {
                "modulus": int(
                    "e6bd692ac96645790403fdd0f5beb8b9bf92ed10007fc365046419dd0"
                    "6c05c5b5b2f48ecf989e4ce269109979cbb40b4a0ad24d22483d1ee31"
                    "5ad4ccb1534268352691c524f6dd8e6c29d224cf246973aec86c5bf6b"
                    "1401a850d1b9ad1bb8cbcec47b06f0f8c7f45d3fc8f319299c5433ddb"
                    "c2b3053b47ded2ecd4a4caefd614833dc8bb622f317ed076b8057fe8d"
                    "e3f84480ad5e83e4a61904a4f248fb397027357e1d30e463139815c6f"
                    "d4fd5ac5b8172a45230ecb6318a04f1455d84e5a8b",
                    16,
                ),
                "public_exponent": int("10001", 16),
            },
        ),
    )
    assert vectors == expected


def test_load_pkcs1_oaep_vectors():
    vector_data = textwrap.dedent(
        """
    Test vectors for RSA-OAEP
    =========================

    This file contains test vectors for the RSA-OAEP encryption

    Key lengths:

    Key  1: 1024 bits
    # <snip>
    ===========================================================================
    # Example 1: A 1024-bit RSA key pair
    # -----------------------------------


    # Public key
    # ----------

    # Modulus:
    a8 b3 b2 84 af 8e b5 0b 38 70 34 a8 60 f1 46 c4
    91 9f 31 87 63 cd 6c 55 98 c8 ae 48 11 a1 e0 ab
    c4 c7 e0 b0 82 d6 93 a5 e7 fc ed 67 5c f4 66 85
    12 77 2c 0c bc 64 a7 42 c6 c6 30 f5 33 c8 cc 72
    f6 2a e8 33 c4 0b f2 58 42 e9 84 bb 78 bd bf 97
    c0 10 7d 55 bd b6 62 f5 c4 e0 fa b9 84 5c b5 14
    8e f7 39 2d d3 aa ff 93 ae 1e 6b 66 7b b3 d4 24
    76 16 d4 f5 ba 10 d4 cf d2 26 de 88 d3 9f 16 fb

    # Exponent:
    01 00 01

    # Private key
    # -----------

    # Modulus:
    a8 b3 b2 84 af 8e b5 0b 38 70 34 a8 60 f1 46 c4
    91 9f 31 87 63 cd 6c 55 98 c8 ae 48 11 a1 e0 ab
    c4 c7 e0 b0 82 d6 93 a5 e7 fc ed 67 5c f4 66 85
    12 77 2c 0c bc 64 a7 42 c6 c6 30 f5 33 c8 cc 72
    f6 2a e8 33 c4 0b f2 58 42 e9 84 bb 78 bd bf 97
    c0 10 7d 55 bd b6 62 f5 c4 e0 fa b9 84 5c b5 14
    8e f7 39 2d d3 aa ff 93 ae 1e 6b 66 7b b3 d4 24
    76 16 d4 f5 ba 10 d4 cf d2 26 de 88 d3 9f 16 fb

    # Public exponent:
    01 00 01

    # Exponent:
    53 33 9c fd b7 9f c8 46 6a 65 5c 73 16 ac a8 5c
    55 fd 8f 6d d8 98 fd af 11 95 17 ef 4f 52 e8 fd
    8e 25 8d f9 3f ee 18 0f a0 e4 ab 29 69 3c d8 3b
    15 2a 55 3d 4a c4 d1 81 2b 8b 9f a5 af 0e 7f 55
    fe 73 04 df 41 57 09 26 f3 31 1f 15 c4 d6 5a 73
    2c 48 31 16 ee 3d 3d 2d 0a f3 54 9a d9 bf 7c bf
    b7 8a d8 84 f8 4d 5b eb 04 72 4d c7 36 9b 31 de
    f3 7d 0c f5 39 e9 cf cd d3 de 65 37 29 ea d5 d1

    # Prime 1:
    d3 27 37 e7 26 7f fe 13 41 b2 d5 c0 d1 50 a8 1b
    58 6f b3 13 2b ed 2f 8d 52 62 86 4a 9c b9 f3 0a
    f3 8b e4 48 59 8d 41 3a 17 2e fb 80 2c 21 ac f1
    c1 1c 52 0c 2f 26 a4 71 dc ad 21 2e ac 7c a3 9d

    # Prime 2:
    cc 88 53 d1 d5 4d a6 30 fa c0 04 f4 71 f2 81 c7
    b8 98 2d 82 24 a4 90 ed be b3 3d 3e 3d 5c c9 3c
    47 65 70 3d 1d d7 91 64 2f 1f 11 6a 0d d8 52 be
    24 19 b2 af 72 bf e9 a0 30 e8 60 b0 28 8b 5d 77

    # Prime exponent 1:
    0e 12 bf 17 18 e9 ce f5 59 9b a1 c3 88 2f e8 04
    6a 90 87 4e ef ce 8f 2c cc 20 e4 f2 74 1f b0 a3
    3a 38 48 ae c9 c9 30 5f be cb d2 d7 68 19 96 7d
    46 71 ac c6 43 1e 40 37 96 8d b3 78 78 e6 95 c1

    # Prime exponent 2:
    95 29 7b 0f 95 a2 fa 67 d0 07 07 d6 09 df d4 fc
    05 c8 9d af c2 ef 6d 6e a5 5b ec 77 1e a3 33 73
    4d 92 51 e7 90 82 ec da 86 6e fe f1 3c 45 9e 1a
    63 13 86 b7 e3 54 c8 99 f5 f1 12 ca 85 d7 15 83

    # Coefficient:
    4f 45 6c 50 24 93 bd c0 ed 2a b7 56 a3 a6 ed 4d
    67 35 2a 69 7d 42 16 e9 32 12 b1 27 a6 3d 54 11
    ce 6f a9 8d 5d be fd 73 26 3e 37 28 14 27 43 81
    81 66 ed 7d d6 36 87 dd 2a 8c a1 d2 f4 fb d8 e1

    # RSA-OAEP encryption of 6 random messages with random seeds
    # -----------------------------------------------------------

    # OAEP Example 1.1
    # ------------------

    # Message:
    66 28 19 4e 12 07 3d b0 3b a9 4c da 9e f9 53 23
    97 d5 0d ba 79 b9 87 00 4a fe fe 34

    # Seed:
    18 b7 76 ea 21 06 9d 69 77 6a 33 e9 6b ad 48 e1
    dd a0 a5 ef

    # Encryption:
    35 4f e6 7b 4a 12 6d 5d 35 fe 36 c7 77 79 1a 3f
    7b a1 3d ef 48 4e 2d 39 08 af f7 22 fa d4 68 fb
    21 69 6d e9 5d 0b e9 11 c2 d3 17 4f 8a fc c2 01
    03 5f 7b 6d 8e 69 40 2d e5 45 16 18 c2 1a 53 5f
    a9 d7 bf c5 b8 dd 9f c2 43 f8 cf 92 7d b3 13 22
    d6 e8 81 ea a9 1a 99 61 70 e6 57 a0 5a 26 64 26
    d9 8c 88 00 3f 84 77 c1 22 70 94 a0 d9 fa 1e 8c
    40 24 30 9c e1 ec cc b5 21 00 35 d4 7a c7 2e 8a

    # OAEP Example 1.2
    # ------------------

    # Message:
    75 0c 40 47 f5 47 e8 e4 14 11 85 65 23 29 8a c9
    ba e2 45 ef af 13 97 fb e5 6f 9d d5

    # Seed:
    0c c7 42 ce 4a 9b 7f 32 f9 51 bc b2 51 ef d9 25
    fe 4f e3 5f

    # Encryption:
    64 0d b1 ac c5 8e 05 68 fe 54 07 e5 f9 b7 01 df
    f8 c3 c9 1e 71 6c 53 6f c7 fc ec 6c b5 b7 1c 11
    65 98 8d 4a 27 9e 15 77 d7 30 fc 7a 29 93 2e 3f
    00 c8 15 15 23 6d 8d 8e 31 01 7a 7a 09 df 43 52
    d9 04 cd eb 79 aa 58 3a dc c3 1e a6 98 a4 c0 52
    83 da ba 90 89 be 54 91 f6 7c 1a 4e e4 8d c7 4b
    bb e6 64 3a ef 84 66 79 b4 cb 39 5a 35 2d 5e d1
    15 91 2d f6 96 ff e0 70 29 32 94 6d 71 49 2b 44

    # =============================================
    """
    ).splitlines()

    vectors = load_pkcs1_vectors(vector_data)
    expected = [
        (
            {
                "modulus": int(
                    "a8b3b284af8eb50b387034a860f146c4919f318763cd6c5598c8ae481"
                    "1a1e0abc4c7e0b082d693a5e7fced675cf4668512772c0cbc64a742c6"
                    "c630f533c8cc72f62ae833c40bf25842e984bb78bdbf97c0107d55bdb"
                    "662f5c4e0fab9845cb5148ef7392dd3aaff93ae1e6b667bb3d4247616"
                    "d4f5ba10d4cfd226de88d39f16fb",
                    16,
                ),
                "public_exponent": int("10001", 16),
                "private_exponent": int(
                    "53339cfdb79fc8466a655c7316aca85c55fd8f6dd898fdaf119517ef4"
                    "f52e8fd8e258df93fee180fa0e4ab29693cd83b152a553d4ac4d1812b"
                    "8b9fa5af0e7f55fe7304df41570926f3311f15c4d65a732c483116ee3"
                    "d3d2d0af3549ad9bf7cbfb78ad884f84d5beb04724dc7369b31def37d"
                    "0cf539e9cfcdd3de653729ead5d1",
                    16,
                ),
                "p": int(
                    "d32737e7267ffe1341b2d5c0d150a81b586fb3132bed2f8d5262864a9"
                    "cb9f30af38be448598d413a172efb802c21acf1c11c520c2f26a471dc"
                    "ad212eac7ca39d",
                    16,
                ),
                "q": int(
                    "cc8853d1d54da630fac004f471f281c7b8982d8224a490edbeb33d3e3"
                    "d5cc93c4765703d1dd791642f1f116a0dd852be2419b2af72bfe9a030"
                    "e860b0288b5d77",
                    16,
                ),
                "dmp1": int(
                    "0e12bf1718e9cef5599ba1c3882fe8046a90874eefce8f2ccc20e4f27"
                    "41fb0a33a3848aec9c9305fbecbd2d76819967d4671acc6431e403796"
                    "8db37878e695c1",
                    16,
                ),
                "dmq1": int(
                    "95297b0f95a2fa67d00707d609dfd4fc05c89dafc2ef6d6ea55bec771"
                    "ea333734d9251e79082ecda866efef13c459e1a631386b7e354c899f5"
                    "f112ca85d71583",
                    16,
                ),
                "iqmp": int(
                    "4f456c502493bdc0ed2ab756a3a6ed4d67352a697d4216e93212b127a"
                    "63d5411ce6fa98d5dbefd73263e3728142743818166ed7dd63687dd2a"
                    "8ca1d2f4fbd8e1",
                    16,
                ),
                "examples": [
                    {
                        "message": b"6628194e12073db03ba94cda9ef9532397d50dba7"
                        b"9b987004afefe34",
                        "seed": b"18b776ea21069d69776a33e96bad48e1dda0a5ef",
                        "encryption": b"354fe67b4a126d5d35fe36c777791a3f7ba13d"
                        b"ef484e2d3908aff722fad468fb21696de95d0b"
                        b"e911c2d3174f8afcc201035f7b6d8e69402de5"
                        b"451618c21a535fa9d7bfc5b8dd9fc243f8cf92"
                        b"7db31322d6e881eaa91a996170e657a05a2664"
                        b"26d98c88003f8477c1227094a0d9fa1e8c4024"
                        b"309ce1ecccb5210035d47ac72e8a",
                    },
                    {
                        "message": b"750c4047f547e8e41411856523298ac9bae245efa"
                        b"f1397fbe56f9dd5",
                        "seed": b"0cc742ce4a9b7f32f951bcb251efd925fe4fe35f",
                        "encryption": b"640db1acc58e0568fe5407e5f9b701dff8c3c9"
                        b"1e716c536fc7fcec6cb5b71c1165988d4a279e"
                        b"1577d730fc7a29932e3f00c81515236d8d8e31"
                        b"017a7a09df4352d904cdeb79aa583adcc31ea6"
                        b"98a4c05283daba9089be5491f67c1a4ee48dc7"
                        b"4bbbe6643aef846679b4cb395a352d5ed11591"
                        b"2df696ffe0702932946d71492b44",
                    },
                ],
            },
            {
                "modulus": int(
                    "a8b3b284af8eb50b387034a860f146c4919f318763cd6c5598c8ae481"
                    "1a1e0abc4c7e0b082d693a5e7fced675cf4668512772c0cbc64a742c6"
                    "c630f533c8cc72f62ae833c40bf25842e984bb78bdbf97c0107d55bdb"
                    "662f5c4e0fab9845cb5148ef7392dd3aaff93ae1e6b667bb3d4247616"
                    "d4f5ba10d4cfd226de88d39f16fb",
                    16,
                ),
                "public_exponent": int("10001", 16),
            },
        )
    ]
    assert vectors == expected


def test_load_hotp_vectors():
    vector_data = textwrap.dedent(
        """
    # HOTP Test Vectors
    # RFC 4226 Appendix D

    COUNT = 0
    COUNTER = 0
    INTERMEDIATE = cc93cf18508d94934c64b65d8ba7667fb7cde4b0
    TRUNCATED = 4c93cf18
    HOTP = 755224
    SECRET = 12345678901234567890

    COUNT = 1
    COUNTER = 1
    INTERMEDIATE = 75a48a19d4cbe100644e8ac1397eea747a2d33ab
    TRUNCATED = 41397eea
    HOTP = 287082
    SECRET = 12345678901234567890


    COUNT = 2
    COUNTER = 2
    INTERMEDIATE = 0bacb7fa082fef30782211938bc1c5e70416ff44
    TRUNCATED = 82fef30
    HOTP = 359152
    SECRET = 12345678901234567890


    COUNT = 3
    COUNTER = 3
    INTERMEDIATE = 66c28227d03a2d5529262ff016a1e6ef76557ece
    TRUNCATED = 66ef7655
    HOTP = 969429
    SECRET = 12345678901234567890
    """
    ).splitlines()

    assert load_nist_vectors(vector_data) == [
        {
            "counter": b"0",
            "intermediate": b"cc93cf18508d94934c64b65d8ba7667fb7cde4b0",
            "truncated": b"4c93cf18",
            "hotp": b"755224",
            "secret": b"12345678901234567890",
        },
        {
            "counter": b"1",
            "intermediate": b"75a48a19d4cbe100644e8ac1397eea747a2d33ab",
            "truncated": b"41397eea",
            "hotp": b"287082",
            "secret": b"12345678901234567890",
        },
        {
            "counter": b"2",
            "intermediate": b"0bacb7fa082fef30782211938bc1c5e70416ff44",
            "truncated": b"82fef30",
            "hotp": b"359152",
            "secret": b"12345678901234567890",
        },
        {
            "counter": b"3",
            "intermediate": b"66c28227d03a2d5529262ff016a1e6ef76557ece",
            "truncated": b"66ef7655",
            "hotp": b"969429",
            "secret": b"12345678901234567890",
        },
    ]


def test_load_totp_vectors():
    vector_data = textwrap.dedent(
        """
    # TOTP Test Vectors
    # RFC 6238 Appendix B

    COUNT = 0
    TIME = 59
    TOTP = 94287082
    MODE = SHA1
    SECRET = 12345678901234567890

    COUNT = 1
    TIME = 59
    TOTP = 46119246
    MODE = SHA256
    SECRET = 12345678901234567890

    COUNT = 2
    TIME = 59
    TOTP = 90693936
    MODE = SHA512
    SECRET = 12345678901234567890
    """
    ).splitlines()

    assert load_nist_vectors(vector_data) == [
        {
            "time": b"59",
            "totp": b"94287082",
            "mode": b"SHA1",
            "secret": b"12345678901234567890",
        },
        {
            "time": b"59",
            "totp": b"46119246",
            "mode": b"SHA256",
            "secret": b"12345678901234567890",
        },
        {
            "time": b"59",
            "totp": b"90693936",
            "mode": b"SHA512",
            "secret": b"12345678901234567890",
        },
    ]


def test_load_rsa_nist_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.4
    # "SigGen PKCS#1 RSASSA-PSS" information
    # Mod sizes selected: 1024 1536 2048 3072 4096
    # SHA Algorithm selected:SHA1 SHA224 SHA256 SHA384 SHA512
    # Salt len: 20

    [mod = 1024]

    n = bcb47b2e0dafcba81ff2a2b5cb115ca7e757184c9d72bcdcda707a146b3b4e29989d

    e = 00000000000000000000000000000000000000000000000000000000000000000010001
    SHAAlg = SHA1
    Msg = 1248f62a4389f42f7b4bb131053d6c88a994db2075b912ccbe3ea7dc611714f14e
    S = 682cf53c1145d22a50caa9eb1a9ba70670c5915e0fdfde6457a765de2a8fe12de97

    SHAAlg = SHA384
    Msg = e511903c2f1bfba245467295ac95413ac4746c984c3750a728c388aa628b0ebf
    S = 9c748702bbcc1f9468864cd360c8c39d007b2d8aaee833606c70f7593cf0d1519

    [mod = 1024]

    n = 1234567890

    e = 0010001

    SHAAlg = SHA512
    Msg = 3456781293fab829
    S = deadbeef0000
    """
    ).splitlines()

    vectors = load_rsa_nist_vectors(vector_data)
    assert vectors == [
        {
            "modulus": int(
                "bcb47b2e0dafcba81ff2a2b5cb115ca7e757184c9d72bcdcda"
                "707a146b3b4e29989d",
                16,
            ),
            "public_exponent": 65537,
            "algorithm": "SHA1",
            "salt_length": 20,
            "msg": b"1248f62a4389f42f7b4bb131053d6c88a994db2075b912ccbe3ea7dc6"
            b"11714f14e",
            "s": b"682cf53c1145d22a50caa9eb1a9ba70670c5915e0fdfde6457a765de2a8"
            b"fe12de97",
            "fail": False,
        },
        {
            "modulus": int(
                "bcb47b2e0dafcba81ff2a2b5cb115ca7e757184c9d72bcdcda"
                "707a146b3b4e29989d",
                16,
            ),
            "public_exponent": 65537,
            "algorithm": "SHA384",
            "salt_length": 20,
            "msg": b"e511903c2f1bfba245467295ac95413ac4746c984c3750a728c388aa6"
            b"28b0ebf",
            "s": b"9c748702bbcc1f9468864cd360c8c39d007b2d8aaee833606c70f7593cf"
            b"0d1519",
            "fail": False,
        },
        {
            "modulus": 78187493520,
            "public_exponent": 65537,
            "algorithm": "SHA512",
            "salt_length": 20,
            "msg": b"3456781293fab829",
            "s": b"deadbeef0000",
            "fail": False,
        },
    ]


def test_load_rsa_nist_pkcs1v15_verification_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.0
    # "SigVer PKCS#1 Ver 1.5" information
    # Mod sizes selected: 1024 1536 2048 3072 4096
    # SHA Algorithm selected:SHA1 SHA224 SHA256 SHA384 SHA512
    # Generated on Wed Mar 02 00:13:02 2011

    [mod = 1024]

    n = be499b5e7f06c83fa0293e31465c8eb6b58af920bae52a7b5b9bfeb7aa72db126411

    p = e7a80c5d211c06acb900939495f26d365fc2b4825b75e356f89003eaa5931e6be5c3
    q = d248aa248000f720258742da67b711940c8f76e1ecd52b67a6ffe1e49354d66ff84f

    SHAAlg = SHA1
    e = 00000000000000000000000000000000000000000000000000000000000000000011
    d = 0d0f17362bdad181db4e1fe03e8de1a3208989914e14bf269558826bfa20faf4b68d
    Msg = 6b9cfac0ba1c7890b13e381ce752195cc1375237db2afcf6a9dcd1f95ec733a80c
    S = 562d87b5781c01d166fef3972669a0495c145b898a17df4743fbefb0a1582bd6ba9d
    SaltVal = 11223344555432167890
    Result = F (3 - Signature changed )

    SHAAlg = SHA1
    e = 0000000000003
    d = bfa20faf4b68d
    Msg = 2a67c70ff14f9b34ddb42e6f89d5971057a0da980fc9ae70c81a84da0c0ac42737
    S = 2b91c6ae2b3c46ff18d5b7abe239634cb752d0acb53eea0ccd8ea8483036a50e8faf
    SaltVal = 11223344555432167890
    Result = P
    """
    ).splitlines()

    vectors = load_rsa_nist_vectors(vector_data)
    assert vectors == [
        {
            "modulus": int(
                "be499b5e7f06c83fa0293e31465c8eb6b58af920bae52a7b5b"
                "9bfeb7aa72db126411",
                16,
            ),
            "p": int(
                "e7a80c5d211c06acb900939495f26d365fc2b4825b75e356f89003ea"
                "a5931e6be5c3",
                16,
            ),
            "q": int(
                "d248aa248000f720258742da67b711940c8f76e1ecd52b67a6ffe1e4"
                "9354d66ff84f",
                16,
            ),
            "public_exponent": 17,
            "algorithm": "SHA1",
            "private_exponent": int(
                "0d0f17362bdad181db4e1fe03e8de1a3208989914"
                "e14bf269558826bfa20faf4b68d",
                16,
            ),
            "msg": b"6b9cfac0ba1c7890b13e381ce752195cc1375237db2afcf6a9dcd1f95"
            b"ec733a80c",
            "s": b"562d87b5781c01d166fef3972669a0495c145b898a17df4743fbefb0a15"
            b"82bd6ba9d",
            "saltval": b"11223344555432167890",
            "fail": True,
        },
        {
            "modulus": int(
                "be499b5e7f06c83fa0293e31465c8eb6b58af920bae52a7b5b"
                "9bfeb7aa72db126411",
                16,
            ),
            "p": int(
                "e7a80c5d211c06acb900939495f26d365fc2b4825b75e356f89003ea"
                "a5931e6be5c3",
                16,
            ),
            "q": int(
                "d248aa248000f720258742da67b711940c8f76e1ecd52b67a6ffe1e4"
                "9354d66ff84f",
                16,
            ),
            "public_exponent": 3,
            "algorithm": "SHA1",
            "private_exponent": int("bfa20faf4b68d", 16),
            "msg": b"2a67c70ff14f9b34ddb42e6f89d5971057a0da980fc9ae70c81a84da0"
            b"c0ac42737",
            "s": b"2b91c6ae2b3c46ff18d5b7abe239634cb752d0acb53eea0ccd8ea848303"
            b"6a50e8faf",
            "saltval": b"11223344555432167890",
            "fail": False,
        },
    ]


def test_load_rsa_nist_pss_verification_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.0
    # "SigVer PKCS#1 RSASSA-PSS" information
    # Mod sizes selected: 1024 1536 2048 3072 4096
    # SHA Algorithm selected:SHA1 SHA224 SHA256 SHA384 SHA512
    # Salt len: 10
    # Generated on Wed Mar 02 00:25:22 2011

    [mod = 1024]

    n = be499b5e7f06c83fa0293e31465c8eb6b5

    p = e7a80c5d211c06acb900939495f26d365f
    q = d248aa248000f720258742da67b711940c

    SHAAlg = SHA1
    e = 00000000000000011
    d = c8e26a88239672cf49b3422a07c4d834ba
    Msg = 6b9cfac0ba1c7890b13e381ce752195c
    S = 562d87b5781c01d166fef3972669a0495c
    SaltVal = 11223344555432167890
    Result = F (3 - Signature changed )

    SHAAlg = SHA384
    e = 000003
    d = 0d0f17362bdad181db4e1fe03e8de1a320
    Msg = 2a67c70ff14f9b34ddb42e6f89d59710
    S = 2b91c6ae2b3c46ff18d5b7abe239634cb7
    SaltVal = 11223344555432167890
    Result = P
    """
    ).splitlines()

    vectors = load_rsa_nist_vectors(vector_data)
    assert vectors == [
        {
            "modulus": int("be499b5e7f06c83fa0293e31465c8eb6b5", 16),
            "p": int("e7a80c5d211c06acb900939495f26d365f", 16),
            "q": int("d248aa248000f720258742da67b711940c", 16),
            "public_exponent": 17,
            "algorithm": "SHA1",
            "private_exponent": int("c8e26a88239672cf49b3422a07c4d834ba", 16),
            "msg": b"6b9cfac0ba1c7890b13e381ce752195c",
            "s": b"562d87b5781c01d166fef3972669a0495c",
            "saltval": b"11223344555432167890",
            "salt_length": 10,
            "fail": True,
        },
        {
            "modulus": int("be499b5e7f06c83fa0293e31465c8eb6b5", 16),
            "p": int("e7a80c5d211c06acb900939495f26d365f", 16),
            "q": int("d248aa248000f720258742da67b711940c", 16),
            "public_exponent": 3,
            "algorithm": "SHA384",
            "private_exponent": int("0d0f17362bdad181db4e1fe03e8de1a320", 16),
            "msg": b"2a67c70ff14f9b34ddb42e6f89d59710",
            "s": b"2b91c6ae2b3c46ff18d5b7abe239634cb7",
            "saltval": b"11223344555432167890",
            "salt_length": 10,
            "fail": False,
        },
    ]


def test_load_fips_dsa_key_pair_vectors():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.1
    #  "KeyPair" information
    #  Mod sizes selected: L=1024, N=160:: L=2048, N=224 :: L=2048, N=256 :: L
=3072, N=256
    # Generated on Wed May 04 08:50:52 2011


    [mod = L=1024, N=160]

    P = d38311e2cd388c3ed698e82fdf88eb92b5a9a483dc88005d4b725ef341eabb47cf8a7a\
8a41e792a156b7ce97206c4f9c5ce6fc5ae7912102b6b502e59050b5b21ce263dddb2044b65223\
6f4d42ab4b5d6aa73189cef1ace778d7845a5c1c1c7147123188f8dc551054ee162b634d60f097\
f719076640e20980a0093113a8bd73
    Q = 96c5390a8b612c0e422bb2b0ea194a3ec935a281
    G = 06b7861abbd35cc89e79c52f68d20875389b127361ca66822138ce4991d2b862259d6b\
4548a6495b195aa0e0b6137ca37eb23b94074d3c3d300042bdf15762812b6333ef7b07ceba7860\
7610fcc9ee68491dbc1e34cd12615474e52b18bc934fb00c61d39e7da8902291c4434a4e2224c3\
f4fd9f93cd6f4f17fc076341a7e7d9

    X = 8185fee9cc7c0e91fd85503274f1cd5a3fd15a49
    Y = 6f26d98d41de7d871b6381851c9d91fa03942092ab6097e76422070edb71db44ff5682\
80fdb1709f8fc3feab39f1f824adaeb2a298088156ac31af1aa04bf54f475bdcfdcf2f8a2dd973\
e922d83e76f016558617603129b21c70bf7d0e5dc9e68fe332e295b65876eb9a12fe6fca9f1a1c\
e80204646bf99b5771d249a6fea627

    X = 85322d6ea73083064376099ca2f65f56e8522d9b
    Y = 21f8690f717c9f4dcb8f4b6971de2f15b9231fcf41b7eeb997d781f240bfdddfd2090d\
22083c26cca39bf37c9caf1ec89518ea64845a50d747b49131ffff6a2fd11ea7bacbb93c7d0513\
7383a06365af82225dd3713ca5a45006316f53bd12b0e260d5f79795e5a4c9f353f12867a1d320\
2394673ada8563b71555e53f415254

    [mod = L=2048, N=256]

    P = ea1fb1af22881558ef93be8a5f8653c5a559434c49c8c2c12ace5e9c41434c9cf0a8e9\
498acb0f4663c08b4484eace845f6fb17dac62c98e706af0fc74e4da1c6c2b3fbf5a1d58ff82fc\
1a66f3e8b12252c40278fff9dd7f102eed2cb5b7323ebf1908c234d935414dded7f8d244e54561\
b0dca39b301de8c49da9fb23df33c6182e3f983208c560fb5119fbf78ebe3e6564ee235c6a15cb\
b9ac247baba5a423bc6582a1a9d8a2b4f0e9e3d9dbac122f750dd754325135257488b1f6ecabf2\
1bff2947fe0d3b2cb7ffe67f4e7fcdf1214f6053e72a5bb0dd20a0e9fe6db2df0a908c36e95e60\
bf49ca4368b8b892b9c79f61ef91c47567c40e1f80ac5aa66ef7
    Q = 8ec73f3761caf5fdfe6e4e82098bf10f898740dcb808204bf6b18f507192c19d
    G = e4c4eca88415b23ecf811c96e48cd24200fe916631a68a684e6ccb6b1913413d344d1d\
8d84a333839d88eee431521f6e357c16e6a93be111a98076739cd401bab3b9d565bf4fb99e9d18\
5b1e14d61c93700133f908bae03e28764d107dcd2ea7674217622074bb19efff482f5f5c1a86d5\
551b2fc68d1c6e9d8011958ef4b9c2a3a55d0d3c882e6ad7f9f0f3c61568f78d0706b10a26f23b\
4f197c322b825002284a0aca91807bba98ece912b80e10cdf180cf99a35f210c1655fbfdd74f13\
b1b5046591f8403873d12239834dd6c4eceb42bf7482e1794a1601357b629ddfa971f2ed273b14\
6ec1ca06d0adf55dd91d65c37297bda78c6d210c0bc26e558302

    X = 405772da6e90d809e77d5de796562a2dd4dfd10ef00a83a3aba6bd818a0348a1
    Y = 6b32e31ab9031dc4dd0b5039a78d07826687ab087ae6de4736f5b0434e1253092e8a0b\
231f9c87f3fc8a4cb5634eb194bf1b638b7a7889620ce6711567e36aa36cda4604cfaa601a4591\
8371d4ccf68d8b10a50a0460eb1dc0fff62ef5e6ee4d473e18ea4a66c196fb7e677a49b48241a0\
b4a97128eff30fa437050501a584f8771e7280d26d5af30784039159c11ebfea10b692fd0a5821\
5eeb18bff117e13f08db792ed4151a218e4bed8dddfb0793225bd1e9773505166f4bd8cedbb286\
ea28232972da7bae836ba97329ba6b0a36508e50a52a7675e476d4d4137eae13f22a9d2fefde70\
8ba8f34bf336c6e76331761e4b0617633fe7ec3f23672fb19d27

    X = 0e0b95e31fda3f888059c46c3002ef8f2d6be112d0209aeb9e9545da67aeea80
    Y = 778082b77ddba6f56597cc74c3a612abf2ddbd85cc81430c99ab843c1f630b9db01399\
65f563978164f9bf3a8397256be714625cd41cd7fa0067d94ea66d7e073f7125af692ad01371d4\
a17f4550590378f2b074030c20e36911598a1018772f61be3b24de4be5a388ccc09e15a92819c3\
1dec50de9fde105b49eaa097b9d13d9219eeb33b628facfd1c78a7159c8430d0647c506e7e3de7\
4763cb351eada72c00bef3c9641881e6254870c1e6599f8ca2f1bbb74f39a905e3a34e4544168e\
6e50c9e3305fd09cab6ed4aff6fda6e0d5bf375c81ac9054406d9193b003c89272f1bd83d48250\
134b65c77c2b6332d38d34d9016f0e8975536ad6c348a1faedb0

    [mod = L=3072, N=256]

    P = f335666dd1339165af8b9a5e3835adfe15c158e4c3c7bd53132e7d5828c352f593a9a7\
87760ce34b789879941f2f01f02319f6ae0b756f1a842ba54c85612ed632ee2d79ef17f06b77c6\
41b7b080aff52a03fc2462e80abc64d223723c236deeb7d201078ec01ca1fbc1763139e25099a8\
4ec389159c409792080736bd7caa816b92edf23f2c351f90074aa5ea2651b372f8b58a0a65554d\
b2561d706a63685000ac576b7e4562e262a14285a9c6370b290e4eb7757527d80b6c0fd5df831d\
36f3d1d35f12ab060548de1605fd15f7c7aafed688b146a02c945156e284f5b71282045aba9844\
d48b5df2e9e7a5887121eae7d7b01db7cdf6ff917cd8eb50c6bf1d54f90cce1a491a9c74fea88f\
7e7230b047d16b5a6027881d6f154818f06e513faf40c8814630e4e254f17a47bfe9cb519b9828\
9935bf17673ae4c8033504a20a898d0032ee402b72d5986322f3bdfb27400561f7476cd715eaab\
b7338b854e51fc2fa026a5a579b6dcea1b1c0559c13d3c1136f303f4b4d25ad5b692229957
    Q = d3eba6521240694015ef94412e08bf3cf8d635a455a398d6f210f6169041653b
    G = ce84b30ddf290a9f787a7c2f1ce92c1cbf4ef400e3cd7ce4978db2104d7394b493c183\
32c64cec906a71c3778bd93341165dee8e6cd4ca6f13afff531191194ada55ecf01ff94d6cf7c4\
768b82dd29cd131aaf202aefd40e564375285c01f3220af4d70b96f1395420d778228f1461f5d0\
b8e47357e87b1fe3286223b553e3fc9928f16ae3067ded6721bedf1d1a01bfd22b9ae85fce7782\
0d88cdf50a6bde20668ad77a707d1c60fcc5d51c9de488610d0285eb8ff721ff141f93a9fb23c1\
d1f7654c07c46e58836d1652828f71057b8aff0b0778ef2ca934ea9d0f37daddade2d823a4d8e3\
62721082e279d003b575ee59fd050d105dfd71cd63154efe431a0869178d9811f4f231dc5dcf3b\
0ec0f2b0f9896c32ec6c7ee7d60aa97109e09224907328d4e6acd10117e45774406c4c947da802\
0649c3168f690e0bd6e91ac67074d1d436b58ae374523deaf6c93c1e6920db4a080b744804bb07\
3cecfe83fa9398cf150afa286dc7eb7949750cf5001ce104e9187f7e16859afa8fd0d775ae

    X = b2764c46113983777d3e7e97589f1303806d14ad9f2f1ef033097de954b17706
    Y = 814824e435e1e6f38daa239aad6dad21033afce6a3ebd35c1359348a0f2418871968c2\
babfc2baf47742148828f8612183178f126504da73566b6bab33ba1f124c15aa461555c2451d86\
c94ee21c3e3fc24c55527e01b1f03adcdd8ec5cb08082803a7b6a829c3e99eeb332a2cf5c035b0\
ce0078d3d414d31fa47e9726be2989b8d06da2e6cd363f5a7d1515e3f4925e0b32adeae3025cc5\
a996f6fd27494ea408763de48f3bb39f6a06514b019899b312ec570851637b8865cff3a52bf5d5\
4ad5a19e6e400a2d33251055d0a440b50d53f4791391dc754ad02b9eab74c46b4903f9d76f8243\
39914db108057af7cde657d41766a99991ac8787694f4185d6f91d7627048f827b405ec67bf2fe\
56141c4c581d8c317333624e073e5879a82437cb0c7b435c0ce434e15965db1315d64895991e6b\
be7dac040c42052408bbc53423fd31098248a58f8a67da3a39895cd0cc927515d044c1e3cb6a32\
59c3d0da354cce89ea3552c59609db10ee989986527436af21d9485ddf25f90f7dff6d2bae

    X = 52e3e040efb30e1befd909a0bdbcfd140d005b1bff094af97186080262f1904d
    Y = a5ae6e8f9b7a68ab0516dad4d7b7d002126f811d5a52e3d35c6d387fcb43fd19bf7792\
362f9c98f8348aa058bb62376685f3d0c366c520d697fcd8416947151d4bbb6f32b53528a01647\
9e99d2cd48d1fc679027c15f0042f207984efe05c1796bca8eba678dfdd00b80418e3ea840557e\
73b09e003882f9a68edba3431d351d1ca07a8150b018fdbdf6c2f1ab475792a3ccaa6594472a45\
f8dc777b60bf67de3e0f65c20d11b7d59faedf83fbce52617f500d9e514947c455274c6e900464\
767fb56599b81344cf6d12c25cb2b7d038d7b166b6cf30534811c15d0e8ab880a2ac06786ae2dd\
de61329a78d526f65245380ce877e979c5b50de66c9c30d66382c8f254653d25a1eb1d3a4897d7\
623399b473ce712a2184cf2da1861706c41466806aefe41b497db82aca6c31c8f4aa68c17d1d9e\
380b57998917655783ec96e5234a131f7299398d36f1f5f84297a55ff292f1f060958c358fed34\
6db2de45127ca728a9417b2c54203e33e53b9a061d924395b09afab8daf3e8dd7eedcec3ac
    """
    ).splitlines()

    expected = [
        {
            "g": int(
                "06b7861abbd35cc89e79c52f68d20875389b127361ca66822138ce499"
                "1d2b862259d6b4548a6495b195aa0e0b6137ca37eb23b94074d3c3d3000"
                "42bdf15762812b6333ef7b07ceba78607610fcc9ee68491dbc1e34cd12"
                "615474e52b18bc934fb00c61d39e7da8902291c4434a4e2224c3f"
                "4fd9f93cd6f4f17fc076341a7e7d9",
                16,
            ),
            "p": int(
                "d38311e2cd388c3ed698e82fdf88eb92b5a9a483dc88005d4b725e"
                "f341eabb47cf8a7a8a41e792a156b7ce97206c4f9c5ce6fc5ae791210"
                "2b6b502e59050b5b21ce263dddb2044b652236f4d42ab4b5d6aa73189c"
                "ef1ace778d7845a5c1c1c7147123188f8dc551054ee162b634d60f097f7"
                "19076640e20980a0093113a8bd73",
                16,
            ),
            "q": int("96c5390a8b612c0e422bb2b0ea194a3ec935a281", 16),
            "x": int("8185fee9cc7c0e91fd85503274f1cd5a3fd15a49", 16),
            "y": int(
                "6f26d98d41de7d871b6381851c9d91fa03942092ab6097e76422"
                "070edb71db44ff568280fdb1709f8fc3feab39f1f824adaeb2a29808815"
                "6ac31af1aa04bf54f475bdcfdcf2f8a2dd973e922d83e76f01655861760"
                "3129b21c70bf7d0e5dc9e68fe332e295b65876eb9a12fe6fca9f1a1ce80"
                "204646bf99b5771d249a6fea627",
                16,
            ),
        },
        {
            "g": int(
                "06b7861abbd35cc89e79c52f68d20875389b127361ca66822138ce4991d"
                "2b862259d6b4548a6495b195aa0e0b6137ca37eb23b94074d3c3d30004"
                "2bdf15762812b6333ef7b07ceba78607610fcc9ee68491dbc1e34cd126"
                "15474e52b18bc934fb00c61d39e7da8902291c4434a4e2224c3f4fd9"
                "f93cd6f4f17fc076341a7e7d9",
                16,
            ),
            "p": int(
                "d38311e2cd388c3ed698e82fdf88eb92b5a9a483dc88005d4b725ef341e"
                "abb47cf8a7a8a41e792a156b7ce97206c4f9c5ce6fc5ae7912102b6b50"
                "2e59050b5b21ce263dddb2044b652236f4d42ab4b5d6aa73189cef1a"
                "ce778d7845a5c1c1c7147123188f8dc551054ee162b634d6"
                "0f097f719076640e20980a0093113a8bd73",
                16,
            ),
            "q": int("96c5390a8b612c0e422bb2b0ea194a3ec935a281", 16),
            "x": int("85322d6ea73083064376099ca2f65f56e8522d9b", 16),
            "y": int(
                "21f8690f717c9f4dcb8f4b6971de2f15b9231fcf41b7eeb997d781f240"
                "bfdddfd2090d22083c26cca39bf37c9caf1ec89518ea64845a50d747b49"
                "131ffff6a2fd11ea7bacbb93c7d05137383a06365af82225dd3713c"
                "a5a45006316f53bd12b0e260d5f79795e5a4c9f353f12867a1d3"
                "202394673ada8563b71555e53f415254",
                16,
            ),
        },
        {
            "g": int(
                "e4c4eca88415b23ecf811c96e48cd24200fe916631a68a684e6ccb6b191"
                "3413d344d1d8d84a333839d88eee431521f6e357c16e6a93be111a9807"
                "6739cd401bab3b9d565bf4fb99e9d185b1e14d61c93700133f908bae0"
                "3e28764d107dcd2ea7674217622074bb19efff482f5f5c1a86d5551b2"
                "fc68d1c6e9d8011958ef4b9c2a3a55d0d3c882e6ad7f9f0f3c61568f78"
                "d0706b10a26f23b4f197c322b825002284a0aca91807bba98ece912"
                "b80e10cdf180cf99a35f210c1655fbfdd74f13b1b5046591f8403873d"
                "12239834dd6c4eceb42bf7482e1794a1601357b629ddfa971f2ed273b1"
                "46ec1ca06d0adf55dd91d65c37297bda78c6d210c0bc26e558302",
                16,
            ),
            "p": int(
                "ea1fb1af22881558ef93be8a5f8653c5a559434c49c8c2c12ace"
                "5e9c41434c9cf0a8e9498acb0f4663c08b4484eace845f6fb17d"
                "ac62c98e706af0fc74e4da1c6c2b3fbf5a1d58ff82fc1a66f3e8b122"
                "52c40278fff9dd7f102eed2cb5b7323ebf1908c234d935414dded7f8d2"
                "44e54561b0dca39b301de8c49da9fb23df33c6182e3f983208c560fb5"
                "119fbf78ebe3e6564ee235c6a15cbb9ac247baba5a423bc6582a1a9d8a"
                "2b4f0e9e3d9dbac122f750dd754325135257488b1f6ecabf21bff2947"
                "fe0d3b2cb7ffe67f4e7fcdf1214f6053e72a5bb0dd20a0e9fe6db2df0a"
                "908c36e95e60bf49ca4368b8b892b9c79f61ef91c47567c40e1f80ac"
                "5aa66ef7",
                16,
            ),
            "q": int(
                "8ec73f3761caf5fdfe6e4e82098bf10f898740dcb808204bf6b1"
                "8f507192c19d",
                16,
            ),
            "x": int(
                "405772da6e90d809e77d5de796562a2dd4dfd10ef00a83a3aba6"
                "bd818a0348a1",
                16,
            ),
            "y": int(
                "6b32e31ab9031dc4dd0b5039a78d07826687ab087ae6de4736f5"
                "b0434e1253092e8a0b231f9c87f3fc8a4cb5634eb194bf1b638"
                "b7a7889620ce6711567e36aa36cda4604cfaa601a45918371d"
                "4ccf68d8b10a50a0460eb1dc0fff62ef5e6ee4d473e18ea4a6"
                "6c196fb7e677a49b48241a0b4a97128eff30fa437050501a584"
                "f8771e7280d26d5af30784039159c11ebfea10b692fd0a58215ee"
                "b18bff117e13f08db792ed4151a218e4bed8dddfb0793225bd1e97"
                "73505166f4bd8cedbb286ea28232972da7bae836ba97329ba6b0a36508"
                "e50a52a7675e476d4d4137eae13f22a9d2fefde708ba8f34bf336c6e7"
                "6331761e4b0617633fe7ec3f23672fb19d27",
                16,
            ),
        },
        {
            "g": int(
                "e4c4eca88415b23ecf811c96e48cd24200fe916631a68a684e6ccb6b191"
                "3413d344d1d8d84a333839d88eee431521f6e357c16e6a93be111a9807"
                "6739cd401bab3b9d565bf4fb99e9d185b1e14d61c93700133f908bae0"
                "3e28764d107dcd2ea7674217622074bb19efff482f5f5c1a86d5551b2"
                "fc68d1c6e9d8011958ef4b9c2a3a55d0d3c882e6ad7f9f0f3c61568f78"
                "d0706b10a26f23b4f197c322b825002284a0aca91807bba98ece912"
                "b80e10cdf180cf99a35f210c1655fbfdd74f13b1b5046591f8403873d"
                "12239834dd6c4eceb42bf7482e1794a1601357b629ddfa971f2ed273b1"
                "46ec1ca06d0adf55dd91d65c37297bda78c6d210c0bc26e558302",
                16,
            ),
            "p": int(
                "ea1fb1af22881558ef93be8a5f8653c5a559434c49c8c2c12ace"
                "5e9c41434c9cf0a8e9498acb0f4663c08b4484eace845f6fb17d"
                "ac62c98e706af0fc74e4da1c6c2b3fbf5a1d58ff82fc1a66f3e8b122"
                "52c40278fff9dd7f102eed2cb5b7323ebf1908c234d935414dded7f8d2"
                "44e54561b0dca39b301de8c49da9fb23df33c6182e3f983208c560fb5"
                "119fbf78ebe3e6564ee235c6a15cbb9ac247baba5a423bc6582a1a9d8a"
                "2b4f0e9e3d9dbac122f750dd754325135257488b1f6ecabf21bff2947"
                "fe0d3b2cb7ffe67f4e7fcdf1214f6053e72a5bb0dd20a0e9fe6db2df0a"
                "908c36e95e60bf49ca4368b8b892b9c79f61ef91c47567c40e1f80ac"
                "5aa66ef7",
                16,
            ),
            "q": int(
                "8ec73f3761caf5fdfe6e4e82098bf10f898740dcb808204bf6b1"
                "8f507192c19d",
                16,
            ),
            "x": int(
                "0e0b95e31fda3f888059c46c3002ef8f2d6be112d0209aeb9e95"
                "45da67aeea80",
                16,
            ),
            "y": int(
                "778082b77ddba6f56597cc74c3a612abf2ddbd85cc81430c99ab"
                "843c1f630b9db0139965f563978164f9bf3a8397256be714625"
                "cd41cd7fa0067d94ea66d7e073f7125af692ad01371d4a17f45"
                "50590378f2b074030c20e36911598a1018772f61be3b24de4be"
                "5a388ccc09e15a92819c31dec50de9fde105b49eaa097b9d13d"
                "9219eeb33b628facfd1c78a7159c8430d0647c506e7e3de74763c"
                "b351eada72c00bef3c9641881e6254870c1e6599f8ca2f1bbb74f"
                "39a905e3a34e4544168e6e50c9e3305fd09cab6ed4aff6fda6e0d"
                "5bf375c81ac9054406d9193b003c89272f1bd83d48250134b65c77"
                "c2b6332d38d34d9016f0e8975536ad6c348a1faedb0",
                16,
            ),
        },
        {
            "g": int(
                "ce84b30ddf290a9f787a7c2f1ce92c1cbf4ef400e3cd7ce4978d"
                "b2104d7394b493c18332c64cec906a71c3778bd93341165dee8"
                "e6cd4ca6f13afff531191194ada55ecf01ff94d6cf7c4768b82"
                "dd29cd131aaf202aefd40e564375285c01f3220af4d70b96f1"
                "395420d778228f1461f5d0b8e47357e87b1fe3286223b553e3"
                "fc9928f16ae3067ded6721bedf1d1a01bfd22b9ae85fce77820d88cdf"
                "50a6bde20668ad77a707d1c60fcc5d51c9de488610d0285eb8ff721f"
                "f141f93a9fb23c1d1f7654c07c46e58836d1652828f71057b8aff0b077"
                "8ef2ca934ea9d0f37daddade2d823a4d8e362721082e279d003b575ee"
                "59fd050d105dfd71cd63154efe431a0869178d9811f4f231dc5dcf3b"
                "0ec0f2b0f9896c32ec6c7ee7d60aa97109e09224907328d4e6acd1011"
                "7e45774406c4c947da8020649c3168f690e0bd6e91ac67074d1d436b"
                "58ae374523deaf6c93c1e6920db4a080b744804bb073cecfe83fa939"
                "8cf150afa286dc7eb7949750cf5001ce104e9187f7e16859afa8fd0d"
                "775ae",
                16,
            ),
            "p": int(
                "f335666dd1339165af8b9a5e3835adfe15c158e4c3c7bd53132e7d5828"
                "c352f593a9a787760ce34b789879941f2f01f02319f6ae0b756f1a842"
                "ba54c85612ed632ee2d79ef17f06b77c641b7b080aff52a03fc2462e8"
                "0abc64d223723c236deeb7d201078ec01ca1fbc1763139e25099a84ec"
                "389159c409792080736bd7caa816b92edf23f2c351f90074aa5ea2651"
                "b372f8b58a0a65554db2561d706a63685000ac576b7e4562e262a1428"
                "5a9c6370b290e4eb7757527d80b6c0fd5df831d36f3d1d35f12ab0605"
                "48de1605fd15f7c7aafed688b146a02c945156e284f5b71282045aba9"
                "844d48b5df2e9e7a5887121eae7d7b01db7cdf6ff917cd8eb50c6bf1d"
                "54f90cce1a491a9c74fea88f7e7230b047d16b5a6027881d6f154818f"
                "06e513faf40c8814630e4e254f17a47bfe9cb519b98289935bf17673a"
                "e4c8033504a20a898d0032ee402b72d5986322f3bdfb27400561f7476"
                "cd715eaabb7338b854e51fc2fa026a5a579b6dcea1b1c0559c13d3c11"
                "36f303f4b4d25ad5b692229957",
                16,
            ),
            "q": int(
                "d3eba6521240694015ef94412e08bf3cf8d635a455a398d6f210"
                "f6169041653b",
                16,
            ),
            "x": int(
                "b2764c46113983777d3e7e97589f1303806d14ad9f2f1ef03309"
                "7de954b17706",
                16,
            ),
            "y": int(
                "814824e435e1e6f38daa239aad6dad21033afce6a3ebd35c1359348a0f2"
                "418871968c2babfc2baf47742148828f8612183178f126504da73566b6"
                "bab33ba1f124c15aa461555c2451d86c94ee21c3e3fc24c55527e"
                "01b1f03adcdd8ec5cb08082803a7b6a829c3e99eeb332a2cf5c035b0c"
                "e0078d3d414d31fa47e9726be2989b8d06da2e6cd363f5a7d1515e3f4"
                "925e0b32adeae3025cc5a996f6fd27494ea408763de48f3bb39f6a06"
                "514b019899b312ec570851637b8865cff3a52bf5d54ad5a19e6e400"
                "a2d33251055d0a440b50d53f4791391dc754ad02b9eab74c46b4903"
                "f9d76f824339914db108057af7cde657d41766a99991ac8787694f"
                "4185d6f91d7627048f827b405ec67bf2fe56141c4c581d8c317333"
                "624e073e5879a82437cb0c7b435c0ce434e15965db1315d648959"
                "91e6bbe7dac040c42052408bbc53423fd31098248a58f8a67da3a"
                "39895cd0cc927515d044c1e3cb6a3259c3d0da354cce89ea3552c"
                "59609db10ee989986527436af21d9485ddf25f90f7dff6d2bae",
                16,
            ),
        },
        {
            "g": int(
                "ce84b30ddf290a9f787a7c2f1ce92c1cbf4ef400e3cd7ce4978d"
                "b2104d7394b493c18332c64cec906a71c3778bd93341165dee8"
                "e6cd4ca6f13afff531191194ada55ecf01ff94d6cf7c4768b82"
                "dd29cd131aaf202aefd40e564375285c01f3220af4d70b96f1"
                "395420d778228f1461f5d0b8e47357e87b1fe3286223b553e3"
                "fc9928f16ae3067ded6721bedf1d1a01bfd22b9ae85fce77820d88cdf"
                "50a6bde20668ad77a707d1c60fcc5d51c9de488610d0285eb8ff721f"
                "f141f93a9fb23c1d1f7654c07c46e58836d1652828f71057b8aff0b077"
                "8ef2ca934ea9d0f37daddade2d823a4d8e362721082e279d003b575ee"
                "59fd050d105dfd71cd63154efe431a0869178d9811f4f231dc5dcf3b"
                "0ec0f2b0f9896c32ec6c7ee7d60aa97109e09224907328d4e6acd1011"
                "7e45774406c4c947da8020649c3168f690e0bd6e91ac67074d1d436b"
                "58ae374523deaf6c93c1e6920db4a080b744804bb073cecfe83fa939"
                "8cf150afa286dc7eb7949750cf5001ce104e9187f7e16859afa8fd0d"
                "775ae",
                16,
            ),
            "p": int(
                "f335666dd1339165af8b9a5e3835adfe15c158e4c3c7bd53132e7d5828"
                "c352f593a9a787760ce34b789879941f2f01f02319f6ae0b756f1a842"
                "ba54c85612ed632ee2d79ef17f06b77c641b7b080aff52a03fc2462e8"
                "0abc64d223723c236deeb7d201078ec01ca1fbc1763139e25099a84ec"
                "389159c409792080736bd7caa816b92edf23f2c351f90074aa5ea2651"
                "b372f8b58a0a65554db2561d706a63685000ac576b7e4562e262a1428"
                "5a9c6370b290e4eb7757527d80b6c0fd5df831d36f3d1d35f12ab0605"
                "48de1605fd15f7c7aafed688b146a02c945156e284f5b71282045aba9"
                "844d48b5df2e9e7a5887121eae7d7b01db7cdf6ff917cd8eb50c6bf1d"
                "54f90cce1a491a9c74fea88f7e7230b047d16b5a6027881d6f154818f"
                "06e513faf40c8814630e4e254f17a47bfe9cb519b98289935bf17673a"
                "e4c8033504a20a898d0032ee402b72d5986322f3bdfb27400561f7476"
                "cd715eaabb7338b854e51fc2fa026a5a579b6dcea1b1c0559c13d3c11"
                "36f303f4b4d25ad5b692229957",
                16,
            ),
            "q": int(
                "d3eba6521240694015ef94412e08bf3cf8d635a455a398d6f210"
                "f6169041653b",
                16,
            ),
            "x": int(
                "52e3e040efb30e1befd909a0bdbcfd140d005b1bff094af97186"
                "080262f1904d",
                16,
            ),
            "y": int(
                "a5ae6e8f9b7a68ab0516dad4d7b7d002126f811d5a52e3d35c6d"
                "387fcb43fd19bf7792362f9c98f8348aa058bb62376685f3d0c3"
                "66c520d697fcd8416947151d4bbb6f32b53528a016479e99d2cd"
                "48d1fc679027c15f0042f207984efe05c1796bca8eba678dfdd0"
                "0b80418e3ea840557e73b09e003882f9a68edba3431d351d1ca0"
                "7a8150b018fdbdf6c2f1ab475792a3ccaa6594472a45f8dc777b"
                "60bf67de3e0f65c20d11b7d59faedf83fbce52617f500d9e5149"
                "47c455274c6e900464767fb56599b81344cf6d12c25cb2b7d038"
                "d7b166b6cf30534811c15d0e8ab880a2ac06786ae2ddde61329a"
                "78d526f65245380ce877e979c5b50de66c9c30d66382c8f25465"
                "3d25a1eb1d3a4897d7623399b473ce712a2184cf2da1861706c4"
                "1466806aefe41b497db82aca6c31c8f4aa68c17d1d9e380b5799"
                "8917655783ec96e5234a131f7299398d36f1f5f84297a55ff292"
                "f1f060958c358fed346db2de45127ca728a9417b2c54203e33e5"
                "3b9a061d924395b09afab8daf3e8dd7eedcec3ac",
                16,
            ),
        },
    ]

    assert expected == load_fips_dsa_key_pair_vectors(vector_data)


def test_load_fips_dsa_sig_ver_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.0
    # "SigVer" information
    # Mod sizes selected: SHA-1 L=1024, N=160,SHA-384 L=2048, N=256
    # Generated on Fri Apr 01 08:37:15 2011

    [mod = L=1024, N=160, SHA-1]

    P = dc5bf3a88b2d99e4c95cdd7a0501cc38630d425cf5c390af3429cff1f35147b795cae\
a923f0d3577158f8a0c89dabd1962c2c453306b5d70cacfb01430aceb54e5a5fa6f93\
40d3bd2da612fceeb76b0ec1ebfae635a56ab141b108e00dc76eefe2edd0c514c21c4\
57457c39065dba9d0ecb7569c247172d8438ad2827b60435b
    Q = e956602b83d195dbe945b3ac702fc61f81571f1d
    G = d7eb9ca20a3c7a079606bafc4c9261ccaba303a5dc9fe9953f197dfe548c234895baa\
77f441ee6a2d97b909cbbd26ff7b869d24cae51b5c6edb127a4b5d75cd8b46608bfa1\
48249dffdb59807c5d7dde3fe3080ca3a2d28312142becb1fa8e24003e21c72871081\
74b95d5bc711e1c8d9b1076784f5dc37a964a5e51390da713

    Msg = 0fe1bfee500bdb76026099b1d37553f6bdfe48c82094ef98cb309dd777330bedfaa\
2f94c823ef74ef4074b50d8706041ac0e371c7c22dcf70263b8d60e17a86c7c379c\
fda8f22469e0df9d49d59439fc99891873628fff25dda5fac5ac794e948babdde96\
8143ba05f1128f34fdad5875edc4cd71c6c24ba2060ffbd439ce2b3
    X = 1d93010c29ecfc432188942f46f19f44f0e1bb5d
    Y = 6240ea0647117c38fe705106d56db578f3e10130928452d4f3587881b8a2bc6873a8b\
efc3237f20914e2a91c7f07a928ee22adeed23d74ab7f82ea11f70497e578f7a9b4cb\
d6f10226222b0b4da2ea1e49813d6bb9882fbf675c0846bb80cc891857b89b0ef1beb\
6cce3378a9aab5d66ad4cb9277cf447dfe1e64434749432fb
    R = b5af307867fb8b54390013cc67020ddf1f2c0b81
    S = 620d3b22ab5031440c3e35eab6f481298f9e9f08
    Result = P

    Msg = 97d50898025d2f9ba633866e968ca75e969d394edba6517204cb3dd537c2ba38778\
a2dc9dbc685a915e5676fcd43bc3726bc59ce3d7a9fae35565082a069c139fa37c9\
0d922b126933db3fa6c5ef6b1edf00d174a51887bb76909c6a94fe994ecc7b7fc8f\
26113b17f30f9d01693df99a125b4f17e184331c6b6e8ca00f54f3a
    X = 350e13534692a7e0c4b7d58836046c436fbb2322
    Y = 69974de550fe6bd3099150faea1623ad3fb6d9bf23a07215093f319725ad0877accff\
d291b6da18eb0cbe51676ceb0977504eb97c27c0b191883f72fb2710a9fbd8bcf13be\
0bf854410b32f42b33ec89d3cc1cf892bcd536c4195ca9ada302ad600c3408739935d\
77dc247529ca47f844cc86f5016a2fe962c6e20ca7c4d4e8f
    R = b5d05faa7005764e8dae0327c5bf1972ff7681b9
    S = 18ea15bd9f00475b25204cbc23f8c23e01588015
    Result = F (3 - R changed )

    [mod = L=2048, N=256, SHA-384]

    P = e7c1c86125db9ef417da1ced7ea0861bdad629216a3f3c745df42a46b989e59f4d984\
25ee3c932fa3c2b6f637bdb6545bec526faa037e11f5578a4363b9fca5eba60d6a9cb\
aa2befd04141d989c7356285132c2eaf74f2d868521cdc0a17ae9a2546ef863027d3f\
8cc7949631fd0e2971417a912c8b8c5c989730db6ea6e8baee0e667850429038093c8\
51ccb6fb173bb081e0efe0bd7450e0946888f89f75e443ab93ef2da293a01622cf43c\
6dd79625d41ba8f9ef7e3086ab39134283d8e96c89249488120fd061e4a87d34af410\
69c0b4fd3934c31b589cbe85b68b912718d5dab859fda7082511fad1d152044905005\
546e19b14aa96585a55269bf2b831
    Q = 8e056ec9d4b7acb580087a6ed9ba3478711bb025d5b8d9c731ef9b38bd43db2f
    G = dc2bfb9776786ad310c8b0cdcbba3062402613c67e6959a8d8d1b05aab636528b7b1f\
e9cd33765f853d6dbe13d09f2681f8c7b1ed7886aaed70c7bd76dbe858ffb8bd86235\
ddf759244678f428c6519af593dc94eeadbd9852ba2b3d61664e8d58c29d2039af3c3\
d6d16f90988f6a8c824569f3d48050e30896a9e17cd0232ef01ab8790008f6973b84c\
763a72f4ae8b485abfb7e8efeb86808fa2b281d3e5d65d28f5992a34c077c5aa8026c\
b2fbc34a45f7e9bd216b10e6f12ecb172e9a6eb8f2e91316905b6add1fd22e83bc2f0\
89f1d5e6a6e6707c18ff55ddcb7954e8bceaf0efc4e8314910c03b0e51175f344faaf\
ee476a373ac95743cec712b72cf2e

    Msg = 6cd6ccfd66bcd832189c5f0c77994210e3bf2c43416f0fe77c4e92f31c5369538dc\
2c003f146c5ac79df43194ccf3c44d470d9f1083bd15b99b5bcf88c32d8a9021f09\
ea2288d7b3bf345a12aef3949c1e121b9fb371a67c2d1377364206ac839dd784835\
61426bda0303f285aa12e9c45d3cdfc6beae3549703b187deeb3296
    X = 56c897b5938ad5b3d437d7e4826da586a6b3be15e893fa1aaa946f20a028b6b3
    Y = 38ad44489e1a5778b9689f4dcf40e2acf23840fb954e987d6e8cb629106328ac64e1f\
3c3eba48b21176ad4afe3b733bead382ee1597e1b83e4b43424f2daaba04e5bd79e14\
36693ac2bddb79a298f026e57e200a252efd1e848a4a2e90be6e78f5242b468b9c0c6\
d2615047a5a40b9ae7e57a519114db55bf3bed65e580f894b094630ca9c217f6accd0\
91e72d2f22da620044ff372d7273f9445017fad492959e59600b7494dbe766a03e401\
25d4e6747c76f68a5b0cdc0e7d7cee12d08c6fb7d0fb049e420a33405075ed4463296\
345ca695fb7feab7c1b5333ae519fcd4bb6a043f4555378969114743d4face96cad31\
c0e0089da4e3f61b6d7dabc088ab7
    R = 3b85b17be240ed658beb3652c9d93e8e9eea160d35ee2459614305802963374e
    S = 726800a5174a53b56dce86064109c0273cd11fcfa3c92c5cd6aa910260c0e3c7
    Result = F (1 - Message changed)

    Msg = 3ad6b0884f358dea09c31a9abc40c45a6000611fc2b907b30eac00413fd2819de70\
15488a411609d46c499b8f7afa1b78b352ac7f8535bd805b8ff2a5eae557098c668\
f7ccd73af886d6823a6d456c29931ee864ed46d767382785728c2a83fcff5271007\
d2a67d06fa205fd7b9d1a42ea5d6dc76e5e18a9eb148cd1e8b262ae
    X = 2faf566a9f057960f1b50c69508f483d9966d6e35743591f3a677a9dc40e1555
    Y = 926425d617babe87c442b03903e32ba5bbf0cd9d602b59c4df791a4d64a6d4333ca0c\
0d370552539197d327dcd1bbf8c454f24b03fc7805f862db34c7b066ddfddbb11dbd0\
10b27123062d028fe041cb56a2e77488348ae0ab6705d87aac4d4e9e6600e9e706326\
d9979982cffa839beb9eacc3963bcca455a507e80c1c37ad4e765b2c9c0477a075e9b\
c584feacdf3a35a9391d4711f14e197c54022282bfed9a191213d64127f17a9c5affe\
c26e0c71f15d3a5b16098fec118c45bf8bb2f3b1560df0949254c1c0aeb0a16d5a95a\
40fab8521fbe8ea77c51169b587cc3360e5733e6a23b9fded8c40724ea1f9e93614b3\
a6c9b4f8dbbe915b794497227ba62
    R = 343ea0a9e66277380f604d5880fca686bffab69ca97bfba015a102a7e23dce0e
    S = 6258488c770e0f5ad7b9da8bade5023fc0d17c6ec517bd08d53e6dc01ac5c2b3
    Result = P
    """
    ).splitlines()

    expected = [
        {
            "p": int(
                "dc5bf3a88b2d99e4c95cdd7a0501cc38630d425cf5c390af3429cff1"
                "f35147b795caea923f0d3577158f8a0c89dabd1962c2c453306b5d70"
                "cacfb01430aceb54e5a5fa6f9340d3bd2da612fceeb76b0ec1ebfae6"
                "35a56ab141b108e00dc76eefe2edd0c514c21c457457c39065dba9d0"
                "ecb7569c247172d8438ad2827b60435b",
                16,
            ),
            "q": int("e956602b83d195dbe945b3ac702fc61f81571f1d", 16),
            "g": int(
                "d7eb9ca20a3c7a079606bafc4c9261ccaba303a5dc9fe9953f197dfe"
                "548c234895baa77f441ee6a2d97b909cbbd26ff7b869d24cae51b5c6"
                "edb127a4b5d75cd8b46608bfa148249dffdb59807c5d7dde3fe3080c"
                "a3a2d28312142becb1fa8e24003e21c7287108174b95d5bc711e1c8d"
                "9b1076784f5dc37a964a5e51390da713",
                16,
            ),
            "digest_algorithm": "SHA-1",
            "msg": binascii.unhexlify(
                b"0fe1bfee500bdb76026099b1d37553f6bdfe48c82094ef98cb309dd77733"
                b"0bedfaa2f94c823ef74ef4074b50d8706041ac0e371c7c22dcf70263b8d6"
                b"0e17a86c7c379cfda8f22469e0df9d49d59439fc99891873628fff25dda5"
                b"fac5ac794e948babdde968143ba05f1128f34fdad5875edc4cd71c6c24ba"
                b"2060ffbd439ce2b3"
            ),
            "x": int("1d93010c29ecfc432188942f46f19f44f0e1bb5d", 16),
            "y": int(
                "6240ea0647117c38fe705106d56db578f3e10130928452d4f3587881"
                "b8a2bc6873a8befc3237f20914e2a91c7f07a928ee22adeed23d74ab"
                "7f82ea11f70497e578f7a9b4cbd6f10226222b0b4da2ea1e49813d6b"
                "b9882fbf675c0846bb80cc891857b89b0ef1beb6cce3378a9aab5d66"
                "ad4cb9277cf447dfe1e64434749432fb",
                16,
            ),
            "r": int("b5af307867fb8b54390013cc67020ddf1f2c0b81", 16),
            "s": int("620d3b22ab5031440c3e35eab6f481298f9e9f08", 16),
            "result": "P",
        },
        {
            "p": int(
                "dc5bf3a88b2d99e4c95cdd7a0501cc38630d425cf5c390af3429cff1"
                "f35147b795caea923f0d3577158f8a0c89dabd1962c2c453306b5d70"
                "cacfb01430aceb54e5a5fa6f9340d3bd2da612fceeb76b0ec1ebfae6"
                "35a56ab141b108e00dc76eefe2edd0c514c21c457457c39065dba9d0"
                "ecb7569c247172d8438ad2827b60435b",
                16,
            ),
            "q": int("e956602b83d195dbe945b3ac702fc61f81571f1d", 16),
            "g": int(
                "d7eb9ca20a3c7a079606bafc4c9261ccaba303a5dc9fe9953f197dfe"
                "548c234895baa77f441ee6a2d97b909cbbd26ff7b869d24cae51b5c6"
                "edb127a4b5d75cd8b46608bfa148249dffdb59807c5d7dde3fe3080c"
                "a3a2d28312142becb1fa8e24003e21c7287108174b95d5bc711e1c8d"
                "9b1076784f5dc37a964a5e51390da713",
                16,
            ),
            "digest_algorithm": "SHA-1",
            "msg": binascii.unhexlify(
                b"97d50898025d2f9ba633866e968ca75e969d394edba6517204cb3dd537c2"
                b"ba38778a2dc9dbc685a915e5676fcd43bc3726bc59ce3d7a9fae35565082"
                b"a069c139fa37c90d922b126933db3fa6c5ef6b1edf00d174a51887bb7690"
                b"9c6a94fe994ecc7b7fc8f26113b17f30f9d01693df99a125b4f17e184331"
                b"c6b6e8ca00f54f3a"
            ),
            "x": int("350e13534692a7e0c4b7d58836046c436fbb2322", 16),
            "y": int(
                "69974de550fe6bd3099150faea1623ad3fb6d9bf23a07215093f3197"
                "25ad0877accffd291b6da18eb0cbe51676ceb0977504eb97c27c0b19"
                "1883f72fb2710a9fbd8bcf13be0bf854410b32f42b33ec89d3cc1cf8"
                "92bcd536c4195ca9ada302ad600c3408739935d77dc247529ca47f84"
                "4cc86f5016a2fe962c6e20ca7c4d4e8f",
                16,
            ),
            "r": int("b5d05faa7005764e8dae0327c5bf1972ff7681b9", 16),
            "s": int("18ea15bd9f00475b25204cbc23f8c23e01588015", 16),
            "result": "F",
        },
        {
            "p": int(
                "e7c1c86125db9ef417da1ced7ea0861bdad629216a3f3c745df42a4"
                "6b989e59f4d98425ee3c932fa3c2b6f637bdb6545bec526faa037e1"
                "1f5578a4363b9fca5eba60d6a9cbaa2befd04141d989c7356285132"
                "c2eaf74f2d868521cdc0a17ae9a2546ef863027d3f8cc7949631fd0"
                "e2971417a912c8b8c5c989730db6ea6e8baee0e667850429038093c"
                "851ccb6fb173bb081e0efe0bd7450e0946888f89f75e443ab93ef2d"
                "a293a01622cf43c6dd79625d41ba8f9ef7e3086ab39134283d8e96c"
                "89249488120fd061e4a87d34af41069c0b4fd3934c31b589cbe85b6"
                "8b912718d5dab859fda7082511fad1d152044905005546e19b14aa9"
                "6585a55269bf2b831",
                16,
            ),
            "q": int(
                "8e056ec9d4b7acb580087a6ed9ba3478711bb025d5b8d9c731ef9b3"
                "8bd43db2f",
                16,
            ),
            "g": int(
                "dc2bfb9776786ad310c8b0cdcbba3062402613c67e6959a8d8d1b05"
                "aab636528b7b1fe9cd33765f853d6dbe13d09f2681f8c7b1ed7886a"
                "aed70c7bd76dbe858ffb8bd86235ddf759244678f428c6519af593d"
                "c94eeadbd9852ba2b3d61664e8d58c29d2039af3c3d6d16f90988f6"
                "a8c824569f3d48050e30896a9e17cd0232ef01ab8790008f6973b84"
                "c763a72f4ae8b485abfb7e8efeb86808fa2b281d3e5d65d28f5992a"
                "34c077c5aa8026cb2fbc34a45f7e9bd216b10e6f12ecb172e9a6eb8"
                "f2e91316905b6add1fd22e83bc2f089f1d5e6a6e6707c18ff55ddcb"
                "7954e8bceaf0efc4e8314910c03b0e51175f344faafee476a373ac9"
                "5743cec712b72cf2e",
                16,
            ),
            "digest_algorithm": "SHA-384",
            "msg": binascii.unhexlify(
                b"6cd6ccfd66bcd832189c5f0c77994210e3bf2c43416f0fe77c4e92f31c5"
                b"369538dc2c003f146c5ac79df43194ccf3c44d470d9f1083bd15b99b5bc"
                b"f88c32d8a9021f09ea2288d7b3bf345a12aef3949c1e121b9fb371a67c2"
                b"d1377364206ac839dd78483561426bda0303f285aa12e9c45d3cdfc6bea"
                b"e3549703b187deeb3296"
            ),
            "x": int(
                "56c897b5938ad5b3d437d7e4826da586a6b3be15e893fa1aaa946f2"
                "0a028b6b3",
                16,
            ),
            "y": int(
                "38ad44489e1a5778b9689f4dcf40e2acf23840fb954e987d6e8cb62"
                "9106328ac64e1f3c3eba48b21176ad4afe3b733bead382ee1597e1b"
                "83e4b43424f2daaba04e5bd79e1436693ac2bddb79a298f026e57e2"
                "00a252efd1e848a4a2e90be6e78f5242b468b9c0c6d2615047a5a40"
                "b9ae7e57a519114db55bf3bed65e580f894b094630ca9c217f6accd"
                "091e72d2f22da620044ff372d7273f9445017fad492959e59600b74"
                "94dbe766a03e40125d4e6747c76f68a5b0cdc0e7d7cee12d08c6fb7"
                "d0fb049e420a33405075ed4463296345ca695fb7feab7c1b5333ae5"
                "19fcd4bb6a043f4555378969114743d4face96cad31c0e0089da4e3"
                "f61b6d7dabc088ab7",
                16,
            ),
            "r": int(
                "3b85b17be240ed658beb3652c9d93e8e9eea160d35ee24596143058"
                "02963374e",
                16,
            ),
            "s": int(
                "726800a5174a53b56dce86064109c0273cd11fcfa3c92c5cd6aa910"
                "260c0e3c7",
                16,
            ),
            "result": "F",
        },
        {
            "p": int(
                "e7c1c86125db9ef417da1ced7ea0861bdad629216a3f3c745df42a4"
                "6b989e59f4d98425ee3c932fa3c2b6f637bdb6545bec526faa037e1"
                "1f5578a4363b9fca5eba60d6a9cbaa2befd04141d989c7356285132"
                "c2eaf74f2d868521cdc0a17ae9a2546ef863027d3f8cc7949631fd0"
                "e2971417a912c8b8c5c989730db6ea6e8baee0e667850429038093c"
                "851ccb6fb173bb081e0efe0bd7450e0946888f89f75e443ab93ef2d"
                "a293a01622cf43c6dd79625d41ba8f9ef7e3086ab39134283d8e96c"
                "89249488120fd061e4a87d34af41069c0b4fd3934c31b589cbe85b6"
                "8b912718d5dab859fda7082511fad1d152044905005546e19b14aa9"
                "6585a55269bf2b831",
                16,
            ),
            "q": int(
                "8e056ec9d4b7acb580087a6ed9ba3478711bb025d5b8d9c731ef9b3"
                "8bd43db2f",
                16,
            ),
            "g": int(
                "dc2bfb9776786ad310c8b0cdcbba3062402613c67e6959a8d8d1b05"
                "aab636528b7b1fe9cd33765f853d6dbe13d09f2681f8c7b1ed7886a"
                "aed70c7bd76dbe858ffb8bd86235ddf759244678f428c6519af593d"
                "c94eeadbd9852ba2b3d61664e8d58c29d2039af3c3d6d16f90988f6"
                "a8c824569f3d48050e30896a9e17cd0232ef01ab8790008f6973b84"
                "c763a72f4ae8b485abfb7e8efeb86808fa2b281d3e5d65d28f5992a"
                "34c077c5aa8026cb2fbc34a45f7e9bd216b10e6f12ecb172e9a6eb8"
                "f2e91316905b6add1fd22e83bc2f089f1d5e6a6e6707c18ff55ddcb"
                "7954e8bceaf0efc4e8314910c03b0e51175f344faafee476a373ac9"
                "5743cec712b72cf2e",
                16,
            ),
            "digest_algorithm": "SHA-384",
            "msg": binascii.unhexlify(
                b"3ad6b0884f358dea09c31a9abc40c45a6000611fc2b907b30eac00413fd"
                b"2819de7015488a411609d46c499b8f7afa1b78b352ac7f8535bd805b8ff"
                b"2a5eae557098c668f7ccd73af886d6823a6d456c29931ee864ed46d7673"
                b"82785728c2a83fcff5271007d2a67d06fa205fd7b9d1a42ea5d6dc76e5e"
                b"18a9eb148cd1e8b262ae"
            ),
            "x": int(
                "2faf566a9f057960f1b50c69508f483d9966d6e35743591f3a677a9"
                "dc40e1555",
                16,
            ),
            "y": int(
                "926425d617babe87c442b03903e32ba5bbf0cd9d602b59c4df791a4d"
                "64a6d4333ca0c0d370552539197d327dcd1bbf8c454f24b03fc7805f"
                "862db34c7b066ddfddbb11dbd010b27123062d028fe041cb56a2e774"
                "88348ae0ab6705d87aac4d4e9e6600e9e706326d9979982cffa839be"
                "b9eacc3963bcca455a507e80c1c37ad4e765b2c9c0477a075e9bc584"
                "feacdf3a35a9391d4711f14e197c54022282bfed9a191213d64127f1"
                "7a9c5affec26e0c71f15d3a5b16098fec118c45bf8bb2f3b1560df09"
                "49254c1c0aeb0a16d5a95a40fab8521fbe8ea77c51169b587cc3360e"
                "5733e6a23b9fded8c40724ea1f9e93614b3a6c9b4f8dbbe915b79449"
                "7227ba62",
                16,
            ),
            "r": int(
                "343ea0a9e66277380f604d5880fca686bffab69ca97bfba015a102a"
                "7e23dce0e",
                16,
            ),
            "s": int(
                "6258488c770e0f5ad7b9da8bade5023fc0d17c6ec517bd08d53e6dc"
                "01ac5c2b3",
                16,
            ),
            "result": "P",
        },
    ]

    assert expected == load_fips_dsa_sig_vectors(vector_data)


def test_load_fips_dsa_sig_gen_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 11.2
    # "SigGen" information for "dsa2_values"
    # Mod sizes selected: SHA-1 L=1024, N=160, SHA-256 L=2048, N=256

    [mod = L=1024, N=160, SHA-1]

    P = a8f9cd201e5e35d892f85f80e4db2599a5676a3b1d4f190330ed3256b26d0e80a0e49\
a8fffaaad2a24f472d2573241d4d6d6c7480c80b4c67bb4479c15ada7ea8424d2502fa01472e7\
60241713dab025ae1b02e1703a1435f62ddf4ee4c1b664066eb22f2e3bf28bb70a2a76e4fd5eb\
e2d1229681b5b06439ac9c7e9d8bde283
    Q = f85f0f83ac4df7ea0cdf8f469bfeeaea14156495
    G = 2b3152ff6c62f14622b8f48e59f8af46883b38e79b8c74deeae9df131f8b856e3ad6c\
8455dab87cc0da8ac973417ce4f7878557d6cdf40b35b4a0ca3eb310c6a95d68ce284ad4e25ea\
28591611ee08b8444bd64b25f3f7c572410ddfb39cc728b9c936f85f419129869929cdb909a6a\
3a99bbe089216368171bd0ba81de4fe33

    Msg = 3b46736d559bd4e0c2c1b2553a33ad3c6cf23cac998d3d0c0e8fa4b19bca06f2f38\
6db2dcff9dca4f40ad8f561ffc308b46c5f31a7735b5fa7e0f9e6cb512e63d7eea05538d66a75\
cd0d4234b5ccf6c1715ccaaf9cdc0a2228135f716ee9bdee7fc13ec27a03a6d11c5c5b3685f51\
900b1337153bc6c4e8f52920c33fa37f4e7
    Y = 313fd9ebca91574e1c2eebe1517c57e0c21b0209872140c5328761bbb2450b33f1b18\
b409ce9ab7c4cd8fda3391e8e34868357c199e16a6b2eba06d6749def791d79e95d3a4d09b24c\
392ad89dbf100995ae19c01062056bb14bce005e8731efde175f95b975089bdcdaea562b32786\
d96f5a31aedf75364008ad4fffebb970b
    R = 50ed0e810e3f1c7cb6ac62332058448bd8b284c0
    S = c6aded17216b46b7e4b6f2a97c1ad7cc3da83fde

    Msg = d2bcb53b044b3e2e4b61ba2f91c0995fb83a6a97525e66441a3b489d9594238bc74\
0bdeea0f718a769c977e2de003877b5d7dc25b182ae533db33e78f2c3ff0645f2137abc137d4e\
7d93ccf24f60b18a820bc07c7b4b5fe08b4f9e7d21b256c18f3b9d49acc4f93e2ce6f3754c780\
7757d2e1176042612cb32fc3f4f70700e25
    Y = 29bdd759aaa62d4bf16b4861c81cf42eac2e1637b9ecba512bdbc13ac12a80ae8de25\
26b899ae5e4a231aef884197c944c732693a634d7659abc6975a773f8d3cd5a361fe2492386a3\
c09aaef12e4a7e73ad7dfc3637f7b093f2c40d6223a195c136adf2ea3fbf8704a675aa7817aa7\
ec7f9adfb2854d4e05c3ce7f76560313b
    R = a26c00b5750a2d27fe7435b93476b35438b4d8ab
    S = 61c9bfcb2938755afa7dad1d1e07c6288617bf70

    [mod = L=2048, N=256, SHA-256]

    P = a8adb6c0b4cf9588012e5deff1a871d383e0e2a85b5e8e03d814fe13a059705e66323\
0a377bf7323a8fa117100200bfd5adf857393b0bbd67906c081e585410e38480ead51684dac3a\
38f7b64c9eb109f19739a4517cd7d5d6291e8af20a3fbf17336c7bf80ee718ee087e322ee4104\
7dabefbcc34d10b66b644ddb3160a28c0639563d71993a26543eadb7718f317bf5d9577a61565\
61b082a10029cd44012b18de6844509fe058ba87980792285f2750969fe89c2cd6498db354563\
8d5379d125dccf64e06c1af33a6190841d223da1513333a7c9d78462abaab31b9f96d5f34445c\
eb6309f2f6d2c8dde06441e87980d303ef9a1ff007e8be2f0be06cc15f
    Q = e71f8567447f42e75f5ef85ca20fe557ab0343d37ed09edc3f6e68604d6b9dfb
    G = 5ba24de9607b8998e66ce6c4f812a314c6935842f7ab54cd82b19fa104abfb5d84579\
a623b2574b37d22ccae9b3e415e48f5c0f9bcbdff8071d63b9bb956e547af3a8df99e5d306197\
9652ff96b765cb3ee493643544c75dbe5bb39834531952a0fb4b0378b3fcbb4c8b5800a533039\
2a2a04e700bb6ed7e0b85795ea38b1b962741b3f33b9dde2f4ec1354f09e2eb78e95f037a5804\
b6171659f88715ce1a9b0cc90c27f35ef2f10ff0c7c7a2bb0154d9b8ebe76a3d764aa879af372\
f4240de8347937e5a90cec9f41ff2f26b8da9a94a225d1a913717d73f10397d2183f1ba3b7b45\
a68f1ff1893caf69a827802f7b6a48d51da6fbefb64fd9a6c5b75c4561

    Msg = 4e3a28bcf90d1d2e75f075d9fbe55b36c5529b17bc3a9ccaba6935c9e20548255b3\
dfae0f91db030c12f2c344b3a29c4151c5b209f5e319fdf1c23b190f64f1fe5b330cb7c8fa952\
f9d90f13aff1cb11d63181da9efc6f7e15bfed4862d1a62c7dcf3ba8bf1ff304b102b1ec3f149\
7dddf09712cf323f5610a9d10c3d9132659
    Y = 5a55dceddd1134ee5f11ed85deb4d634a3643f5f36dc3a70689256469a0b651ad2288\
0f14ab85719434f9c0e407e60ea420e2a0cd29422c4899c416359dbb1e592456f2b3cce233259\
c117542fd05f31ea25b015d9121c890b90e0bad033be1368d229985aac7226d1c8c2eab325ef3\
b2cd59d3b9f7de7dbc94af1a9339eb430ca36c26c46ecfa6c5481711496f624e188ad7540ef5d\
f26f8efacb820bd17a1f618acb50c9bc197d4cb7ccac45d824a3bf795c234b556b06aeb929173\
453252084003f69fe98045fe74002ba658f93475622f76791d9b2623d1b5fff2cc16844746efd\
2d30a6a8134bfc4c8cc80a46107901fb973c28fc553130f3286c1489da
    R = 633055e055f237c38999d81c397848c38cce80a55b649d9e7905c298e2a51447
    S = 2bbf68317660ec1e4b154915027b0bc00ee19cfc0bf75d01930504f2ce10a8b0

    Msg = a733b3f588d5ac9b9d4fe2f804df8c256403a9f8eef6f191fc48e1267fb5b4d546b\
a11e77b667844e489bf0d5f72990aeb061d01ccd7949a23def74a803b7d92d51abfadeb4885ff\
d8ffd58ab87548a15c087a39b8993b2fa64c9d31a594eeb7512da16955834336a234435c5a9d0\
dd9b15a94e116154dea63fdc8dd7a512181
    Y = 356ed47537fbf02cb30a8cee0537f300dff1d0c467399ce70b87a8758d5ec9dd25624\
6fccaeb9dfe109f2a984f2ddaa87aad54ce0d31f907e504521baf4207d7073b0a4a9fc67d8ddd\
a99f87aed6e0367cec27f9c608af743bf1ee6e11d55a182d43b024ace534029b866f6422828bb\
81a39aae9601ee81c7f81dd358e69f4e2edfa4654d8a65bc64311dc86aac4abc1fc7a3f651596\
61a0d8e288eb8d665cb0adf5ac3d6ba8e9453facf7542393ae24fd50451d3828086558f7ec528\
e284935a53f67a1aa8e25d8ad5c4ad55d83aef883a4d9eeb6297e6a53f65049ba9e2c6b7953a7\
60bc1dc46f78ceaaa2c02f5375dd82e708744aa40b15799eb81d7e5b1a
    R = bcd490568c0a89ba311bef88ea4f4b03d273e793722722327095a378dd6f3522
    S = 74498fc43091fcdd2d1ef0775f8286945a01cd72b805256b0451f9cbd943cf82
    """
    ).splitlines()

    expected = [
        {
            "p": int(
                "a8f9cd201e5e35d892f85f80e4db2599a5676a3b1d4f190330ed325"
                "6b26d0e80a0e49a8fffaaad2a24f472d2573241d4d6d6c7480c80b4"
                "c67bb4479c15ada7ea8424d2502fa01472e760241713dab025ae1b0"
                "2e1703a1435f62ddf4ee4c1b664066eb22f2e3bf28bb70a2a76e4fd"
                "5ebe2d1229681b5b06439ac9c7e9d8bde283",
                16,
            ),
            "q": int("f85f0f83ac4df7ea0cdf8f469bfeeaea14156495", 16),
            "g": int(
                "2b3152ff6c62f14622b8f48e59f8af46883b38e79b8c74deeae9df1"
                "31f8b856e3ad6c8455dab87cc0da8ac973417ce4f7878557d6cdf40"
                "b35b4a0ca3eb310c6a95d68ce284ad4e25ea28591611ee08b8444bd"
                "64b25f3f7c572410ddfb39cc728b9c936f85f419129869929cdb909"
                "a6a3a99bbe089216368171bd0ba81de4fe33",
                16,
            ),
            "digest_algorithm": "SHA-1",
            "msg": binascii.unhexlify(
                b"3b46736d559bd4e0c2c1b2553a33ad3c6cf23cac998d3d0c0e8fa4b19bc"
                b"a06f2f386db2dcff9dca4f40ad8f561ffc308b46c5f31a7735b5fa7e0f9"
                b"e6cb512e63d7eea05538d66a75cd0d4234b5ccf6c1715ccaaf9cdc0a222"
                b"8135f716ee9bdee7fc13ec27a03a6d11c5c5b3685f51900b1337153bc6c"
                b"4e8f52920c33fa37f4e7"
            ),
            "y": int(
                "313fd9ebca91574e1c2eebe1517c57e0c21b0209872140c5328761b"
                "bb2450b33f1b18b409ce9ab7c4cd8fda3391e8e34868357c199e16a"
                "6b2eba06d6749def791d79e95d3a4d09b24c392ad89dbf100995ae1"
                "9c01062056bb14bce005e8731efde175f95b975089bdcdaea562b32"
                "786d96f5a31aedf75364008ad4fffebb970b",
                16,
            ),
            "r": int("50ed0e810e3f1c7cb6ac62332058448bd8b284c0", 16),
            "s": int("c6aded17216b46b7e4b6f2a97c1ad7cc3da83fde", 16),
        },
        {
            "p": int(
                "a8f9cd201e5e35d892f85f80e4db2599a5676a3b1d4f190330ed325"
                "6b26d0e80a0e49a8fffaaad2a24f472d2573241d4d6d6c7480c80b4"
                "c67bb4479c15ada7ea8424d2502fa01472e760241713dab025ae1b0"
                "2e1703a1435f62ddf4ee4c1b664066eb22f2e3bf28bb70a2a76e4fd"
                "5ebe2d1229681b5b06439ac9c7e9d8bde283",
                16,
            ),
            "q": int("f85f0f83ac4df7ea0cdf8f469bfeeaea14156495", 16),
            "g": int(
                "2b3152ff6c62f14622b8f48e59f8af46883b38e79b8c74deeae9df1"
                "31f8b856e3ad6c8455dab87cc0da8ac973417ce4f7878557d6cdf40"
                "b35b4a0ca3eb310c6a95d68ce284ad4e25ea28591611ee08b8444bd"
                "64b25f3f7c572410ddfb39cc728b9c936f85f419129869929cdb909"
                "a6a3a99bbe089216368171bd0ba81de4fe33",
                16,
            ),
            "digest_algorithm": "SHA-1",
            "msg": binascii.unhexlify(
                b"d2bcb53b044b3e2e4b61ba2f91c0995fb83a6a97525e66441a3b489d959"
                b"4238bc740bdeea0f718a769c977e2de003877b5d7dc25b182ae533db33e"
                b"78f2c3ff0645f2137abc137d4e7d93ccf24f60b18a820bc07c7b4b5fe08"
                b"b4f9e7d21b256c18f3b9d49acc4f93e2ce6f3754c7807757d2e11760426"
                b"12cb32fc3f4f70700e25"
            ),
            "y": int(
                "29bdd759aaa62d4bf16b4861c81cf42eac2e1637b9ecba512bdbc13"
                "ac12a80ae8de2526b899ae5e4a231aef884197c944c732693a634d7"
                "659abc6975a773f8d3cd5a361fe2492386a3c09aaef12e4a7e73ad7"
                "dfc3637f7b093f2c40d6223a195c136adf2ea3fbf8704a675aa7817"
                "aa7ec7f9adfb2854d4e05c3ce7f76560313b",
                16,
            ),
            "r": int("a26c00b5750a2d27fe7435b93476b35438b4d8ab", 16),
            "s": int("61c9bfcb2938755afa7dad1d1e07c6288617bf70", 16),
        },
        {
            "p": int(
                "a8adb6c0b4cf9588012e5deff1a871d383e0e2a85b5e8e03d814fe1"
                "3a059705e663230a377bf7323a8fa117100200bfd5adf857393b0bb"
                "d67906c081e585410e38480ead51684dac3a38f7b64c9eb109f1973"
                "9a4517cd7d5d6291e8af20a3fbf17336c7bf80ee718ee087e322ee4"
                "1047dabefbcc34d10b66b644ddb3160a28c0639563d71993a26543e"
                "adb7718f317bf5d9577a6156561b082a10029cd44012b18de684450"
                "9fe058ba87980792285f2750969fe89c2cd6498db3545638d5379d1"
                "25dccf64e06c1af33a6190841d223da1513333a7c9d78462abaab31"
                "b9f96d5f34445ceb6309f2f6d2c8dde06441e87980d303ef9a1ff00"
                "7e8be2f0be06cc15f",
                16,
            ),
            "q": int(
                "e71f8567447f42e75f5ef85ca20fe557ab0343d37ed09edc3f6e686"
                "04d6b9dfb",
                16,
            ),
            "g": int(
                "5ba24de9607b8998e66ce6c4f812a314c6935842f7ab54cd82b19fa"
                "104abfb5d84579a623b2574b37d22ccae9b3e415e48f5c0f9bcbdff"
                "8071d63b9bb956e547af3a8df99e5d3061979652ff96b765cb3ee49"
                "3643544c75dbe5bb39834531952a0fb4b0378b3fcbb4c8b5800a533"
                "0392a2a04e700bb6ed7e0b85795ea38b1b962741b3f33b9dde2f4ec"
                "1354f09e2eb78e95f037a5804b6171659f88715ce1a9b0cc90c27f3"
                "5ef2f10ff0c7c7a2bb0154d9b8ebe76a3d764aa879af372f4240de8"
                "347937e5a90cec9f41ff2f26b8da9a94a225d1a913717d73f10397d"
                "2183f1ba3b7b45a68f1ff1893caf69a827802f7b6a48d51da6fbefb"
                "64fd9a6c5b75c4561",
                16,
            ),
            "digest_algorithm": "SHA-256",
            "msg": binascii.unhexlify(
                b"4e3a28bcf90d1d2e75f075d9fbe55b36c5529b17bc3a9ccaba6935c9e20"
                b"548255b3dfae0f91db030c12f2c344b3a29c4151c5b209f5e319fdf1c23"
                b"b190f64f1fe5b330cb7c8fa952f9d90f13aff1cb11d63181da9efc6f7e1"
                b"5bfed4862d1a62c7dcf3ba8bf1ff304b102b1ec3f1497dddf09712cf323"
                b"f5610a9d10c3d9132659"
            ),
            "y": int(
                "5a55dceddd1134ee5f11ed85deb4d634a3643f5f36dc3a706892564"
                "69a0b651ad22880f14ab85719434f9c0e407e60ea420e2a0cd29422"
                "c4899c416359dbb1e592456f2b3cce233259c117542fd05f31ea25b"
                "015d9121c890b90e0bad033be1368d229985aac7226d1c8c2eab325"
                "ef3b2cd59d3b9f7de7dbc94af1a9339eb430ca36c26c46ecfa6c548"
                "1711496f624e188ad7540ef5df26f8efacb820bd17a1f618acb50c9"
                "bc197d4cb7ccac45d824a3bf795c234b556b06aeb92917345325208"
                "4003f69fe98045fe74002ba658f93475622f76791d9b2623d1b5fff"
                "2cc16844746efd2d30a6a8134bfc4c8cc80a46107901fb973c28fc5"
                "53130f3286c1489da",
                16,
            ),
            "r": int(
                "633055e055f237c38999d81c397848c38cce80a55b649d9e7905c29"
                "8e2a51447",
                16,
            ),
            "s": int(
                "2bbf68317660ec1e4b154915027b0bc00ee19cfc0bf75d01930504f"
                "2ce10a8b0",
                16,
            ),
        },
        {
            "p": int(
                "a8adb6c0b4cf9588012e5deff1a871d383e0e2a85b5e8e03d814fe1"
                "3a059705e663230a377bf7323a8fa117100200bfd5adf857393b0bb"
                "d67906c081e585410e38480ead51684dac3a38f7b64c9eb109f1973"
                "9a4517cd7d5d6291e8af20a3fbf17336c7bf80ee718ee087e322ee4"
                "1047dabefbcc34d10b66b644ddb3160a28c0639563d71993a26543e"
                "adb7718f317bf5d9577a6156561b082a10029cd44012b18de684450"
                "9fe058ba87980792285f2750969fe89c2cd6498db3545638d5379d1"
                "25dccf64e06c1af33a6190841d223da1513333a7c9d78462abaab31"
                "b9f96d5f34445ceb6309f2f6d2c8dde06441e87980d303ef9a1ff00"
                "7e8be2f0be06cc15f",
                16,
            ),
            "q": int(
                "e71f8567447f42e75f5ef85ca20fe557ab0343d37ed09edc3f6e686"
                "04d6b9dfb",
                16,
            ),
            "g": int(
                "5ba24de9607b8998e66ce6c4f812a314c6935842f7ab54cd82b19fa"
                "104abfb5d84579a623b2574b37d22ccae9b3e415e48f5c0f9bcbdff"
                "8071d63b9bb956e547af3a8df99e5d3061979652ff96b765cb3ee49"
                "3643544c75dbe5bb39834531952a0fb4b0378b3fcbb4c8b5800a533"
                "0392a2a04e700bb6ed7e0b85795ea38b1b962741b3f33b9dde2f4ec"
                "1354f09e2eb78e95f037a5804b6171659f88715ce1a9b0cc90c27f3"
                "5ef2f10ff0c7c7a2bb0154d9b8ebe76a3d764aa879af372f4240de8"
                "347937e5a90cec9f41ff2f26b8da9a94a225d1a913717d73f10397d"
                "2183f1ba3b7b45a68f1ff1893caf69a827802f7b6a48d51da6fbefb"
                "64fd9a6c5b75c4561",
                16,
            ),
            "digest_algorithm": "SHA-256",
            "msg": binascii.unhexlify(
                b"a733b3f588d5ac9b9d4fe2f804df8c256403a9f8eef6f191fc48e1267fb"
                b"5b4d546ba11e77b667844e489bf0d5f72990aeb061d01ccd7949a23def7"
                b"4a803b7d92d51abfadeb4885ffd8ffd58ab87548a15c087a39b8993b2fa"
                b"64c9d31a594eeb7512da16955834336a234435c5a9d0dd9b15a94e11615"
                b"4dea63fdc8dd7a512181"
            ),
            "y": int(
                "356ed47537fbf02cb30a8cee0537f300dff1d0c467399ce70b87a87"
                "58d5ec9dd256246fccaeb9dfe109f2a984f2ddaa87aad54ce0d31f9"
                "07e504521baf4207d7073b0a4a9fc67d8ddda99f87aed6e0367cec2"
                "7f9c608af743bf1ee6e11d55a182d43b024ace534029b866f642282"
                "8bb81a39aae9601ee81c7f81dd358e69f4e2edfa4654d8a65bc6431"
                "1dc86aac4abc1fc7a3f65159661a0d8e288eb8d665cb0adf5ac3d6b"
                "a8e9453facf7542393ae24fd50451d3828086558f7ec528e284935a"
                "53f67a1aa8e25d8ad5c4ad55d83aef883a4d9eeb6297e6a53f65049"
                "ba9e2c6b7953a760bc1dc46f78ceaaa2c02f5375dd82e708744aa40"
                "b15799eb81d7e5b1a",
                16,
            ),
            "r": int(
                "bcd490568c0a89ba311bef88ea4f4b03d273e793722722327095a37"
                "8dd6f3522",
                16,
            ),
            "s": int(
                "74498fc43091fcdd2d1ef0775f8286945a01cd72b805256b0451f9c"
                "bd943cf82",
                16,
            ),
        },
    ]
    assert expected == load_fips_dsa_sig_vectors(vector_data)


def test_load_fips_ecdsa_key_pair_vectors():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.0
    #  "Key Pair" information
    #  Curves selected: P-192 K-233 B-571
    #  Generated on Wed Mar 16 16:16:42 2011


    [P-192]

    [B.4.2 Key Pair Generation by Testing Candidates]
    N = 2

    d = e5ce89a34adddf25ff3bf1ffe6803f57d0220de3118798ea
    Qx = 8abf7b3ceb2b02438af19543d3e5b1d573fa9ac60085840f
    Qy = a87f80182dcd56a6a061f81f7da393e7cffd5e0738c6b245

    d = 7d14435714ad13ff23341cb567cc91198ff8617cc39751b2
    Qx = 39dc723b19527daa1e80425209c56463481b9b47c51f8cbd
    Qy = 432a3e84f2a16418834fabaf6b7d2341669512951f1672ad


    [K-233]

    [B.4.2 Key Pair Generation by Testing Candidates]
    N = 2

    d = 01da7422b50e3ff051f2aaaed10acea6cbf6110c517da2f4eaca8b5b87
    Qx = 01c7475da9a161e4b3f7d6b086494063543a979e34b8d7ac44204d47bf9f
    Qy = 0131cbd433f112871cc175943991b6a1350bf0cdd57ed8c831a2a7710c92

    d = 530951158f7b1586978c196603c12d25607d2cb0557efadb23cd0ce8
    Qx = d37500a0391d98d3070d493e2b392a2c79dc736c097ed24b7dd5ddec44
    Qy = 01d996cc79f37d8dba143d4a8ad9a8a60ed7ea760aae1ddba34d883f65d9


    [B-571]

    [B.4.2 Key Pair Generation by Testing Candidates]
    N = 2

    d = 01443e93c7ef6802655f641ecbe95e75f1f15b02d2e172f49a32e22047d5c00ebe1b3f\
f0456374461360667dbf07bc67f7d6135ee0d1d46a226a530fefe8ebf3b926e9fbad8d57a6
    Qx = 053e3710d8e7d4138db0a369c97e5332c1be38a20a4a84c36f5e55ea9fd6f34545b86\
4ea64f319e74b5ee9e4e1fa1b7c5b2db0e52467518f8c45b658824871d5d4025a6320ca06f8
    Qy = 03a22cfd370c4a449b936ae97ab97aab11c57686cca99d14ef184f9417fad8bedae4d\
f8357e3710bcda1833b30e297d4bf637938b995d231e557d13f062e81e830af5ab052208ead

    d = 03d2bd44ca9eeee8c860a4873ed55a54bdfdf5dab4060df7292877960b85d1fd496aa3\
3c587347213d7f6bf208a6ab4b430546e7b6ffbc3135bd12f44a28517867ca3c83a821d6f8
    Qx = 07a7af10f6617090bade18b2e092d0dfdc87cd616db7f2db133477a82bfe3ea421ebb\
7d6289980819292a719eb247195529ea60ad62862de0a26c72bfc49ecc81c2f9ed704e3168f
    Qy = 0721496cf16f988b1aabef3368450441df8439a0ca794170f270ead56203d675b57f5\
a4090a3a2f602a77ff3bac1417f7e25a683f667b3b91f105016a47afad46a0367b18e2bdf0c
    """
    ).splitlines()

    expected = [
        {
            "curve": "secp192r1",
            "d": int("e5ce89a34adddf25ff3bf1ffe6803f57d0220de3118798ea", 16),
            "x": int("8abf7b3ceb2b02438af19543d3e5b1d573fa9ac60085840f", 16),
            "y": int("a87f80182dcd56a6a061f81f7da393e7cffd5e0738c6b245", 16),
        },
        {
            "curve": "secp192r1",
            "d": int("7d14435714ad13ff23341cb567cc91198ff8617cc39751b2", 16),
            "x": int("39dc723b19527daa1e80425209c56463481b9b47c51f8cbd", 16),
            "y": int("432a3e84f2a16418834fabaf6b7d2341669512951f1672ad", 16),
        },
        {
            "curve": "sect233k1",
            "d": int(
                "1da7422b50e3ff051f2aaaed10acea6cbf6110c517da2f4eaca8b5b87",
                16,
            ),
            "x": int(
                "1c7475da9a161e4b3f7d6b086494063543a979e34b8d7ac4"
                "4204d47bf9f",
                16,
            ),
            "y": int(
                "131cbd433f112871cc175943991b6a1350bf0cdd57ed8c83"
                "1a2a7710c92",
                16,
            ),
        },
        {
            "curve": "sect233k1",
            "d": int(
                "530951158f7b1586978c196603c12d25607d2cb0557efadb23cd0ce8",
                16,
            ),
            "x": int(
                "d37500a0391d98d3070d493e2b392a2c79dc736c097ed24b"
                "7dd5ddec44",
                16,
            ),
            "y": int(
                "1d996cc79f37d8dba143d4a8ad9a8a60ed7ea760aae1ddba"
                "34d883f65d9",
                16,
            ),
        },
        {
            "curve": "sect571r1",
            "d": int(
                "1443e93c7ef6802655f641ecbe95e75f1f15b02d2e172f49"
                "a32e22047d5c00ebe1b3ff0456374461360667dbf07bc67f"
                "7d6135ee0d1d46a226a530fefe8ebf3b926e9fbad8d57a6",
                16,
            ),
            "x": int(
                "53e3710d8e7d4138db0a369c97e5332c1be38a20a4a84c36"
                "f5e55ea9fd6f34545b864ea64f319e74b5ee9e4e1fa1b7c5"
                "b2db0e52467518f8c45b658824871d5d4025a6320ca06f8",
                16,
            ),
            "y": int(
                "3a22cfd370c4a449b936ae97ab97aab11c57686cca99d14e"
                "f184f9417fad8bedae4df8357e3710bcda1833b30e297d4b"
                "f637938b995d231e557d13f062e81e830af5ab052208ead",
                16,
            ),
        },
        {
            "curve": "sect571r1",
            "d": int(
                "3d2bd44ca9eeee8c860a4873ed55a54bdfdf5dab4060df72"
                "92877960b85d1fd496aa33c587347213d7f6bf208a6ab4b4"
                "30546e7b6ffbc3135bd12f44a28517867ca3c83a821d6f8",
                16,
            ),
            "x": int(
                "7a7af10f6617090bade18b2e092d0dfdc87cd616db7f2db1"
                "33477a82bfe3ea421ebb7d6289980819292a719eb2471955"
                "29ea60ad62862de0a26c72bfc49ecc81c2f9ed704e3168f",
                16,
            ),
            "y": int(
                "721496cf16f988b1aabef3368450441df8439a0ca794170f"
                "270ead56203d675b57f5a4090a3a2f602a77ff3bac1417f7"
                "e25a683f667b3b91f105016a47afad46a0367b18e2bdf0c",
                16,
            ),
        },
    ]

    assert expected == load_fips_ecdsa_key_pair_vectors(vector_data)


def test_load_fips_ecdsa_signing_vectors():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.2
    #  "SigVer" information for "ecdsa_values"
    #  Curves/SHAs selected: P-192, B-571,SHA-512
    #  Generated on Tue Aug 16 15:27:42 2011

    [P-192,SHA-1]

    Msg = ebf748d748ebbca7d29fb473698a6e6b4fb10c865d4af024cc39ae3df3464ba4f1d6\
d40f32bf9618a91bb5986fa1a2af048a0e14dc51e5267eb05e127d689d0ac6f1a7f156ce066316\
b971cc7a11d0fd7a2093e27cf2d08727a4e6748cc32fd59c7810c5b9019df21cdcc0bca432c0a3\
eed0785387508877114359cee4a071cf
    d = e14f37b3d1374ff8b03f41b9b3fdd2f0ebccf275d660d7f3
    Qx = 07008ea40b08dbe76432096e80a2494c94982d2d5bcf98e6
    Qy = 76fab681d00b414ea636ba215de26d98c41bd7f2e4d65477
    k = cb0abc7043a10783684556fb12c4154d57bc31a289685f25
    R = 6994d962bdd0d793ffddf855ec5bf2f91a9698b46258a63e
    S = 02ba6465a234903744ab02bc8521405b73cf5fc00e1a9f41
    Result = F (3 - S changed)

    Msg = 0dcb3e96d77ee64e9d0a350d31563d525755fc675f0c833504e83fc69c030181b42f\
e80c378e86274a93922c570d54a7a358c05755ec3ae91928e02236e81b43e596e4ccbf6a910488\
9c388072bec4e1faeae11fe4eb24fa4f9573560dcf2e3abc703c526d46d502c7a7222583431cc8\
178354ae7dbb84e3479917707bce0968
    d = 7a0235bea3d70445f14d56f9b7fb80ec8ff4eb2f76865244
    Qx = 0ea3c1fa1f124f26530cbfddeb831eecc67df31e08889d1d
    Qy = 7215a0cce0501b47903bd8fe1179c2dfe07bd076f89f5225
    k = 3c646b0f03f5575e5fd463d4319817ce8bd3022eaf551cef
    R = a3ba51c39c43991d87dff0f34d0bec7c883299e04f60f95e
    S = 8a7f9c59c6d65ad390e4c19636ba92b53be5d0f848b4e1f7

    [B-571,SHA-512]

    Msg = 10d2e00ae57176c79cdfc746c0c887abe799ee445b151b008e3d9f81eb69be40298d\
df37b5c45a9b6e5ff83785d8c140cf11e6a4c3879a2845796872363da24b10f1f8d9cc48f8af20\
681dceb60dd62095d6d3b1779a4a805de3d74e38983b24c0748618e2f92ef7cac257ff4bd1f411\
13f2891eb13c47930e69ddbe91f270fb
    d = 03e1b03ffca4399d5b439fac8f87a5cb06930f00d304193d7daf83d5947d0c1e293f74\
aef8e56849f16147133c37a6b3d1b1883e5d61d6b871ea036c5291d9a74541f28878cb986
    Qx = 3b236fc135d849d50140fdaae1045e6ae35ef61091e98f5059b30eb16acdd0deb2bc0\
d3544bc3a666e0014e50030134fe5466a9e4d3911ed580e28851f3747c0010888e819d3d1f
    Qy = 3a8b6627a587d289032bd76374d16771188d7ff281c39542c8977f6872fa932e5daa1\
4e13792dea9ffe8e9f68d6b525ec99b81a5a60cfb0590cc6f297cfff8d7ba1a8bb81fe2e16
    k = 2e56a94cfbbcd293e242f0c2a2e9df289a9480e6ba52e0f00fa19bcf2a7769bd155e6b\
79ddbd6a8646b0e69c8baea27f8034a18796e8eb4fe6e0e2358c383521d9375d2b6b437f9
    R = 2eb1c5c1fc93cf3c8babed12c031cf1504e094174fd335104cbe4a2abd210b5a14b1c3\
a455579f1ed0517c31822340e4dd3c1f967e1b4b9d071a1072afc1a199f8c548cd449a634
    S = 22f97bb48641235826cf4e597fa8de849402d6bd6114ad2d7fbcf53a08247e5ee921f1\
bd5994dffee36eedff5592bb93b8bb148214da3b7baebffbd96b4f86c55b3f6bbac142442
    Result = P (0 )

    Msg = b61a0849a28672cb536fcf61ea2eb389d02ff7a09aa391744cae6597bd56703c40c5\
0ca2dee5f7ee796acfd47322f03d8dbe4d99dc8eec588b4e5467f123075b2d74b2a0b0bbfd3ac5\
487a905fad6d6ac1421c2e564c0cf15e1f0f10bc31c249b7b46edd2462a55f85560d99bde9d5b0\
6b97817d1dbe0a67c701d6e6e7878272
    d = 2e09ffd8b434bb7f67d1d3ccf482164f1653c6e4ec64dec2517aa21b7a93b2b21ea1ee\
bb54734882f29303e489f02e3b741a87287e2dcdf3858eb6d2ec668f8b5b26f442ce513a2
    Qx = 36f1be8738dd7dae4486b86a08fe90424f3673e76b10e739442e15f3bfafaf841842a\
c98e490521b7e7bb94c127529f6ec6a42cc6f06fc80606f1210fe020ff508148f93301c9d3
    Qy = 4d39666ebe99fe214336ad440d776c88eb916f2f4a3433548b87d2aebed840b424d15\
c8341b4a0a657bf6a234d4fe78631c8e07ac1f4dc7474cd6b4545d536b7b17c160db4562d9
    k = 378e7801566d7b77db7a474717ab2195b02957cc264a9449d4126a7cc574728ed5a476\
9abd5dde987ca66cfe3d45b5fc52ffd266acb8a8bb3fcb4b60f7febbf48aebe33bd3efbdd
    R = 3d8105f87fe3166046c08e80a28acc98a80b8b7a729623053c2a9e80afd06756edfe09\
bdcf3035f6829ede041b745955d219dc5d30ddd8b37f6ba0f6d2857504cdc68a1ed812a10
    S = 34db9998dc53527114518a7ce3783d674ca8cced823fa05e2942e7a0a20b3cc583dcd9\
30c43f9b93079c5ee18a1f5a66e7c3527c18610f9b47a4da7e245ef803e0662e4d2ad721c
    """
    ).splitlines()

    expected = [
        {
            "curve": "secp192r1",
            "digest_algorithm": "SHA-1",
            "message": binascii.unhexlify(
                b"ebf748d748ebbca7d29fb473698a6e6b4fb10c865d4af024cc39ae3df346"
                b"4ba4f1d6d40f32bf9618a91bb5986fa1a2af048a0e14dc51e5267eb05e12"
                b"7d689d0ac6f1a7f156ce066316b971cc7a11d0fd7a2093e27cf2d08727a4"
                b"e6748cc32fd59c7810c5b9019df21cdcc0bca432c0a3eed0785387508877"
                b"114359cee4a071cf"
            ),
            "d": int("e14f37b3d1374ff8b03f41b9b3fdd2f0ebccf275d660d7f3", 16),
            "x": int("7008ea40b08dbe76432096e80a2494c94982d2d5bcf98e6", 16),
            "y": int("76fab681d00b414ea636ba215de26d98c41bd7f2e4d65477", 16),
            "r": int("6994d962bdd0d793ffddf855ec5bf2f91a9698b46258a63e", 16),
            "s": int("02ba6465a234903744ab02bc8521405b73cf5fc00e1a9f41", 16),
            "fail": True,
        },
        {
            "curve": "secp192r1",
            "digest_algorithm": "SHA-1",
            "message": binascii.unhexlify(
                b"0dcb3e96d77ee64e9d0a350d31563d525755fc675f0c833504e83fc69c03"
                b"0181b42fe80c378e86274a93922c570d54a7a358c05755ec3ae91928e022"
                b"36e81b43e596e4ccbf6a9104889c388072bec4e1faeae11fe4eb24fa4f95"
                b"73560dcf2e3abc703c526d46d502c7a7222583431cc8178354ae7dbb84e3"
                b"479917707bce0968"
            ),
            "d": int("7a0235bea3d70445f14d56f9b7fb80ec8ff4eb2f76865244", 16),
            "x": int("ea3c1fa1f124f26530cbfddeb831eecc67df31e08889d1d", 16),
            "y": int("7215a0cce0501b47903bd8fe1179c2dfe07bd076f89f5225", 16),
            "r": int("a3ba51c39c43991d87dff0f34d0bec7c883299e04f60f95e", 16),
            "s": int("8a7f9c59c6d65ad390e4c19636ba92b53be5d0f848b4e1f7", 16),
        },
        {
            "curve": "sect571r1",
            "digest_algorithm": "SHA-512",
            "message": binascii.unhexlify(
                b"10d2e00ae57176c79cdfc746c0c887abe799ee445b151b008e3d9f81eb69"
                b"be40298ddf37b5c45a9b6e5ff83785d8c140cf11e6a4c3879a2845796872"
                b"363da24b10f1f8d9cc48f8af20681dceb60dd62095d6d3b1779a4a805de3"
                b"d74e38983b24c0748618e2f92ef7cac257ff4bd1f41113f2891eb13c4793"
                b"0e69ddbe91f270fb"
            ),
            "d": int(
                "3e1b03ffca4399d5b439fac8f87a5cb06930f00d304193d7daf83d59"
                "47d0c1e293f74aef8e56849f16147133c37a6b3d1b1883e5d61d6b87"
                "1ea036c5291d9a74541f28878cb986",
                16,
            ),
            "x": int(
                "3b236fc135d849d50140fdaae1045e6ae35ef61091e98f5059b30eb1"
                "6acdd0deb2bc0d3544bc3a666e0014e50030134fe5466a9e4d3911ed"
                "580e28851f3747c0010888e819d3d1f",
                16,
            ),
            "y": int(
                "3a8b6627a587d289032bd76374d16771188d7ff281c39542c8977f68"
                "72fa932e5daa14e13792dea9ffe8e9f68d6b525ec99b81a5a60cfb05"
                "90cc6f297cfff8d7ba1a8bb81fe2e16",
                16,
            ),
            "r": int(
                "2eb1c5c1fc93cf3c8babed12c031cf1504e094174fd335104cbe4a2a"
                "bd210b5a14b1c3a455579f1ed0517c31822340e4dd3c1f967e1b4b9d"
                "071a1072afc1a199f8c548cd449a634",
                16,
            ),
            "s": int(
                "22f97bb48641235826cf4e597fa8de849402d6bd6114ad2d7fbcf53a"
                "08247e5ee921f1bd5994dffee36eedff5592bb93b8bb148214da3b7b"
                "aebffbd96b4f86c55b3f6bbac142442",
                16,
            ),
            "fail": False,
        },
        {
            "curve": "sect571r1",
            "digest_algorithm": "SHA-512",
            "message": binascii.unhexlify(
                b"b61a0849a28672cb536fcf61ea2eb389d02ff7a09aa391744cae6597bd56"
                b"703c40c50ca2dee5f7ee796acfd47322f03d8dbe4d99dc8eec588b4e5467"
                b"f123075b2d74b2a0b0bbfd3ac5487a905fad6d6ac1421c2e564c0cf15e1f"
                b"0f10bc31c249b7b46edd2462a55f85560d99bde9d5b06b97817d1dbe0a67"
                b"c701d6e6e7878272"
            ),
            "d": int(
                "2e09ffd8b434bb7f67d1d3ccf482164f1653c6e4ec64dec2517aa21b"
                "7a93b2b21ea1eebb54734882f29303e489f02e3b741a87287e2dcdf3"
                "858eb6d2ec668f8b5b26f442ce513a2",
                16,
            ),
            "x": int(
                "36f1be8738dd7dae4486b86a08fe90424f3673e76b10e739442e15f3"
                "bfafaf841842ac98e490521b7e7bb94c127529f6ec6a42cc6f06fc80"
                "606f1210fe020ff508148f93301c9d3",
                16,
            ),
            "y": int(
                "4d39666ebe99fe214336ad440d776c88eb916f2f4a3433548b87d2ae"
                "bed840b424d15c8341b4a0a657bf6a234d4fe78631c8e07ac1f4dc74"
                "74cd6b4545d536b7b17c160db4562d9",
                16,
            ),
            "r": int(
                "3d8105f87fe3166046c08e80a28acc98a80b8b7a729623053c2a9e80"
                "afd06756edfe09bdcf3035f6829ede041b745955d219dc5d30ddd8b3"
                "7f6ba0f6d2857504cdc68a1ed812a10",
                16,
            ),
            "s": int(
                "34db9998dc53527114518a7ce3783d674ca8cced823fa05e2942e7a0"
                "a20b3cc583dcd930c43f9b93079c5ee18a1f5a66e7c3527c18610f9b"
                "47a4da7e245ef803e0662e4d2ad721c",
                16,
            ),
        },
    ]
    assert expected == load_fips_ecdsa_signing_vectors(vector_data)


def test_load_kasvs_dh_vectors():
    vector_data = textwrap.dedent(
        """
    [SHA(s) supported (Used for hashing Z): SHA256 ]
    #  Generated on Thu Mar 17 20:44:26 2011



    [FA - SHA1]
    P = da3a8085d372437805de95b88b675122f575df976610c6a844de99f1df82a06848bf7a\
42f18895c97402e81118e01a00d0855d51922f434c022350861d58ddf60d65bc6941fc6064b147\
071a4c30426d82fc90d888f94990267c64beef8c304a4b2b26fb93724d6a9472fa16bc50c5b9b8\
b59afb62cfe9ea3ba042c73a6ade35
    Q = f2ca7621eb250aa5f22cef1907011295defc50a7
    G = a51883e9ac0539859df3d25c716437008bb4bd8ec4786eb4bc643299daef5e3e5af586\
3a6ac40a597b83a27583f6a658d408825105b16d31b6ed088fc623f648fd6d95e9cefcb0745763\
cddf564c87bcf4ba7928e74fd6a3080481f588d535e4c026b58a21e1e5ec412ff241b436043e29\
173f1dc6cb943c09742de989547288



    COUNT = 0
    XstatCAVS = 42c6ee70beb7465928a1efe692d2281b8f7b53d6
    YstatCAVS = 5a7890f6d20ee9c7162cd84222cb0c7cb5b4f29244a58fc95327fc41045f47\
6fb3da42fca76a1dd59222a7a7c3872d5af7d8dc254e003eccdb38f291619c51911df2b6ed67d0\
b459f4bc25819c0078777b9a1a24c72e7c037a3720a1edad5863ef5ac75ce816869c820859558d\
5721089ddbe331f55bef741396a3bbf85c6c1a
    XstatIUT = 54081a8fef2127a1f22ed90440b1b09c331d0614
    YstatIUT = 0b92af0468b841ea5de4ca91d895b5e922245421de57ed7a88d2de41610b208\
e8e233705f17b2e9eb91914bad2fa87f0a58519a7da2980bc06e7411c925a6050526bd86e62150\
5e6f610b63fdcd9afcfaa96bd087afca44d9197cc35b559f731357a5b979250c0f3a254bb8165f\
5072156e3fd6f9a6e69bcf4b4578f78b3bde7
    Z = 8d8f4175e16e15a42eb9099b11528af88741cc206a088971d3064bb291eda608d1600b\
ff829624db258fd15e95d96d3e74c6be3232afe5c855b9c59681ce13b7aea9ff2b16707e4c02f0\
e82bf6dadf2149ac62630f6c62dea0e505e3279404da5ffd5a088e8474ae0c8726b8189cb3d2f0\
4baffe700be849df9f91567fc2ebb8
    CAVSHashZZ = eb99e77ac2272c7a2ee70c59375ac4d167312c20
    Result = P (0 - Correct)



    COUNT = 2
    XstatCAVS = 32e642683d745a23dccf4f12f989d8dfd1fd9894c422930950cb4c71
    YstatCAVS = 8cd371363b32fcc2e936e345f2278b77001f2efdf78512c3ee75c12f88507e\
2d5c0e5cdded3bb78435506c8028a3f4d6f028c0f49a0d61f1285795197e56deac80279e723f2b\
3746e213ac8ec60f1cefc2308ff17a7e9e2efab537e17406d2829fd85e0c54dda2d9f0b4fcda3d\
2776110e096a817588e19588b77be8b41bafdd41ad91b0edf629333bd6ac1e461208ead124c31b\
8a7935c723e1c450c5798dc05f8265ad9e35095ff112af9e889f00315fa337a76a450670866eca\
12cc6ad0778576962eb9cdc12721d3c15e4d87b67488a145d400240670eb26695a42879cd3940a\
55087f6527667277e1212a202dbe455c45c64b9be4a38153557bbb8fd755
    XstatIUT = 7d8ae93df3bc09d399a4157ec562126acf51092c3269ab27f60a3a2b
    YstatIUT = 22127e9728e906ea4b1512c8b1e80474b58446210c23ccfc800f83c2c15da81\
59940e494b235266f6a9d5f80529067794f1a9edd566755d23d0a3060fe074c5a10122df3e4729\
73bba39ea3a988e8387f5f0491e590b6b5edc299b4598ab1e79b72681a0be8cd8735a5adb85fa3\
1310f29ec407c9654f1bb83bcdf7f771b68d176817f662e8d798b53ebb4e5dd407b7b1d8fdb62e\
a9e1b60d6c3d75d9bcf83f4b8d1ed39408bd8d973b4ea81e8e832eac361dcd530713388a60971e\
a9f8b1e69c1e99df1cca12bdaf293dacfa1419c5692ceffa91988aef3321ac8cbc2efae6c4337c\
8808310fb5a240395a98e6004fe613c39e84f4177341746d9e388dcb2e8
    Z = 0efeaa399a182e0a603baf0dd95aa0fae5289ebd47d5f0f60c86bc936839c31c9f7f37\
bf04f76ab02f4094a8ab10ed907ec7291585cc085c3e8981df2bd46a01c19ec9a2f66709df1d4f\
efbeb48c8263554e46890f59eb642bf95ff7f0de70138621c22c4cc32be6c3d5c82c0c9a76a9f5\
a65bffe0c096a350f96a9da945d7e5095b15b566ce3cb8b0377cd9375b6c046afa9ea0bc084677\
3445f16566b2c84cae4f6d212e89ee539a1ce7ea325273fd228053efce2a585eb9e8f308b48cf4\
e29593b6f7a02e8625e1e8bff1ea1405f8c8c34b8339a9a99c7c9de4eb9895df7719ccda9394f5\
3080eff1226f6b9c7ae0a38941e18b1a137aabbb62308eb35ba2
    CAVSHashZZ = 76dedc997d5113573bbeeaf991f62b257511b7d9aa83270dfc4fec40
    Result = P (10 - Z value should have leading 0 nibble )



    COUNT = 3
    XstatCAVS = 66502429aba271e2f2ee2197a2b336e5f0467f192aa28b60dcbf1194
    YstatCAVS = dfb001294215423d7146a2453cdb8598ccef01e1d931a913c3e4ed4a3cf38a\
912066c28e4eaf77dd80ff07183a6160bd95932f513402f864dcf7a70cbedc9b60bbfbc67f72a8\
3d5f6463a2b5a4fc906d3e921f5e1069126113265b440e15ccf2d7164bad7131f1613fec35df7f\
470d45888e0c91be091f3f9552d670b8b7f479853193cb3c39f35fc7bd547ccb1bc579a67302b4\
ba948e6db51043d351bb74a952e6a694e6e7456f714c47d7c8eeeb4fd83ad93c86b78445f9393f\
dfd65c7dbd7fd6eba9794ddf183901b1d213321fd0ab3f7588ab0f6b3692f365a87131eda0e062\
505861988f6ce63150207545ecf9678e0971330253dfb7cfd546c5346fec
    XstatIUT = 106b358be4f068348ac240ecbb454e5c39ca80b078cb0fafd856e9c5
    YstatIUT = 715d0781975b7b03162f4401c1eda343fd9bf1140006034573b31828a618c35\
6163554cd27da956f7179a69e860fb6efeaa2e2aa9f1261506a8344c4929953621381b13d6426e\
152c0f2f94bfcd2b758eca24923596d427ed8f957e8bc9b1c7d21a87ef02222a1477cf3bfaadc6\
8106456ab9706026006eccd290b21543de6bb97d5b8cf4ccee1c081a6d1dd27aaef060fa93888a\
47a4a416ad5c5bd490ea600e04379232fb1077fbf394f4579accdbe352714e25b88916dca8d8f7\
e0c4ed9594f7693f656a235a2e88ebda48b0d557e32da9f12d2a4c3180f05b16b4fba9bec79278\
a3971b77f9223b5ab78b857e0376c5008211592c8c72d521373ee3b22b8
    Z = cf879ebd107bb877457809c3fc410218b7acba3c5967495a8f1c3370d57f038a48dd69\
f9f69b9f4dd855e7c58a1e4ec32646a978266eb314db468ea1dfcee8a85a1644a5732498c4fbcd\
f85098c6ed0ce12e431e99142fd2335369b3f56620ada21aa69d883e82a0b5e35484dde32d17c2\
dc873f2cc5518eb7fc19695dff9fc94c9d9432bb4b09d8180323cfc561ebc2d6eff8dd5f8496f2\
b22377700a22bbfe61a6969c198129397454843e4fc3540026986039665095490056287e4fc49e\
6cb3181cb2bf06444fd0040150271c9ce1f61c13ecd5dd022194a2dbf3e1c7fbc6bd19497c7b88\
8b4da613d28fa6f378a43369cb8795a1c823f7d6cf4d84bba578
    CAVSHashZZ = ebac4fb70699224f85d9e3c799b1f3a56dab268b882aba49525df02d
    Result = F (5 - Z changed )



    [FB - SHA224]
    P = f3722b9b911c6aede9eaeeaa406283de66a097f39a7225df6c3c916e57920d356e5047\
8d307dbfd146bfb91b6f68ecbbcf54b3d19c33a4b17293fea3e3d6bff8ac4cca93a805386f062a\
8a27ae906ef5da94d279fd7b3d7289e00956f76bae9c0d2b8d11742ca5809630632aae58f9c6dc\
e00c7380581deffde2187b022f83c6ceaeaadb0844a17fcbb04039ca6843c91f0c9058b22434b2\
63c3dfda8de8429e087c5be97fc5c9db9526031ad3a218bd9916fb4a3c27966d208b1e360014c0\
1e95530c148fb3cd27e6a7250d3c3b81dcd220ca14548dbccf99ebb9e334db6bcd14e632c98dd3\
f9860af7ae450f1b7809b45f0ec10e6f27672beebc9963befc73
    Q = a9a17de95a29091bf8e07dab53ea1aba9403be3c61027c6c8f48bac5
    G = 035513ec441402b78353ab1bba550b21c76c89973885a627170262ef52497d5d137b89\
27a212aaab2f051198c90bb81dffd9eb10b36b7ca3b63565b4c1025aea3b5e9c4a348c9cfa17f3\
907a1e4469701c0dedb8a4b9e96c5965b1fb8c229b0c34baac774bf9dda4fc5ee8764358b3c848\
12878aab7464bc09e97aecab7d7e3fbb4870e2a3b89667a4158bf1ed1a90dfaf47019fbb52b1b9\
6365bb4e1e9474993fe382fd23480dc875861be152997a621fdb7aef977ea5b4d3d74486b162dc\
28f95a64cf65587a919a57eef92934fc9410df7f09fa82f975328ed82ff29cc3e15a971f56f4ac\
2dcb289252575e02a6cdb7fcc6cddd7b0dca9c422e63eb2b8f05



    COUNT = 0
    XstatCAVS = 1610eaa4e0ccc8857e2b53149e008492b1fbd9025a6e8d95aaee9c0f
    YstatCAVS = 51ee21cd9f97015180f258fad5c94ff5a458806b1412087236bf77fe87aae1\
a36735816ed6e2160a731159814b6ae1f3f52c478dd9207094adfb62f7667d5c366327e66d2309\
6395e938504db330953a708015f861fe9d9487611093b9fe7327518a7cc15994ab573313e15411\
7c1a3ae88b8bdd1e316748249e4a9cbd1947f159836d13613d1f9449fc3442171d1970bc28958c\
1cafa2776a6f14ccdb29db02f64911bd83bfdcdfc843dd14a4cab9acb0bda8b293d2f5f7050768\
e57533cbc415a29e6f31cc365e107f91ae3722484e2c7329a85af69055a5a104da37e810878896\
d1b247b02b75234ecff82b1958f42d7b031622e9394c98b5229112f7f620
    XstatIUT = 0c4c83d75b27864b052cadc556e500e25aabf0c9d1bc01f0e1fe3862
    YstatIUT = 467a857337a82472a1307a64dccc8e9994c5c63ec4312936885d17be419051a\
5f037fbb052d7010ebe01634d9e8b8b522d9ab4749fdc274f465369b89e360df8f70b7865a3c71\
d2dbcd2df19e9293dab1153d3d63fcb7deb559b684dde6c6eed63214444807041c9a0ce3f52ca4\
39ec16dd231995b5dc6f18e6801b6bd6454babccf9abbfacffb49c71e6494a4779cbfa550c5d71\
44114e6fc193f460dcd0be7e6e06e546da7653770dc5859df87029e722dbe81361030569148d16\
36988926bf0dcfe47c9d8a54698c08b3b5c70afe86b5c6f643463f8f34889d27d6cfd2d478c2d7\
b3d008a985c7380f0b43f10024b59c3543880883c42d0e7e0a07326ba3a
    Z = 10a30bacab82e652415376baffdbc008c7eb2e5a3aa68bc10ce486ca84983fd89b1b02\
7bb40e75333406361005f5e756526a95fe01202df9217d81b1713d5187c368fdd4c9c2433d9e6c\
18844769479b725c4140c92a304ee1bc5726d8f5321b5b1c54a1a6b67c527e6817c0ed613a0d4e\
60db55de898788b7e8d4aa9a81ab5ed7f6282962c433d246ed640555bdd76d29c2874551264d74\
c76373f8a88871b41b041c98041b16f94f983ddf00f5bc7d2416d19168c90178974a0602436cd1\
86748bcc63a629edc3a0db59415cccd37a65130ea477c89da92d41371f5972891cf41f9c7f0e75\
ccbff9893225384db30daa5e310f08e3e0fad98bcdf8ecf35fe5
    CAVSHashZZ = 014f5daea733d0e9e100f852e74d64a319f741cfbdb47975ab9dd3d0
    Result = F (3 - IUT's Static public key fails PKV 5.6.2.4)


    COUNT = 1
    XstatCAVS = 9ee22ac51664e40e0a24dbb94142dba40605e2b6eeaaa0268a0f6847
    YstatCAVS = c2630c9d38ed5c825d1c6a3eba7143f3fc8a049c8bcd1efc212d2af64eca99\
4308208691d330aa8f27fc4a1e55de4e512113996d21375a667f8c26d76dee2f6809b15432a33f\
b735aca5c2263940f58712bded08f55443dee300b9489589e0462bd6bce19deaec4adc12fa61a6\
94c8c5c999b28211d7835bac0ffd2b316850823e2dc1d1f58e05cbf75c673036d116b3f03b9687\
c89f9c2a0d43c4ffc9a605addbdcce0cb3790c6db846156bb857a7b3df40dc6ed04d19cc9eaebb\
6bbc034e77c3d882a1a62317cce25b6130f0803e3bc49b5e36768260073a617034872be0b50bed\
32740224beaf582d67fbcfef3b3ecc18f9c71c782e9a68495ef31dc7986e
    XstatIUT = 438093a468236658821bf64eb08456139963d4fb27121c3ed6c55876
    YstatIUT = e192da8e1244e27221c1765344a5bb379dce741d427a734b4bdb6c4d16b2490\
bd37564d745008e63ae46ef332331d79887ac63298ce143e125f8b320c0f859b7f5f2c1e0053e4\
a7a16997e6143ff702300c9863ae7caef5c1dfca0ecf5197c557745b793f0790a4fe678aeb93fd\
b52490d4f273a5553944dda3ac8b9b792c9b67f8d7b9496398e432a423ae87ebeba688be3ed67e\
ddd7575fa56431cd48579bf53c903bbe066dd78b23c0996ef3a880f0d91315104366a82f01abde\
cce96fd371f94e8420f8bc5b896c801df573554f749b03d0d28b1e1a990bc61c7e9659342ac7e2\
68e9c0b7c40fdaab394f29cf0a54f780022f9a03b0bd28eb7db8b0b1b47
    Z = 56f8f40fa4b8f3580f9014b30d60a42933a53a62182a690142f458dc275c3b2f0e721b\
c5ee6e890b14516419110f5252ff1cceea8e274b2987aa78e3bae90c1935b276b7a1f1c944f79d\
4774b7a85b3355bdf25cb02bddfbda4ee7918bc93a5c9ca6d7e8fdedbda8e6c8a6ca794bad055a\
52b19c148958227344cbddd70271d4610316cfea1e559b0bc3a12d15023b30d9f2db602053a056\
9c3bd2ce1faf59280ecd339f845dbcaaf2e883c5cc6263996f866b18b75d049d4c82097af8a5ce\
353e14416b3eeb31ba9bc4f6f3dbd846c5299fb5c0043a1b95b9149b39d14df9e6a69547abf8a4\
d518475576730ed528779366568e46b7dd4ed787cb72d0733c93
    CAVSHashZZ = 17dbbaa7a20c1390cd8cb3d31ee947bf9dde87739e067b9861ffeea9
    Result = P (0 - Correct)
    """
    ).splitlines()

    expected = [
        {
            "fail_agree": False,
            "fail_z": False,
            "g": int(
                "a51883e9ac0539859df3d25c716437008bb4bd8ec4786eb4bc643299daef5"
                "e3e5af5863a6ac40a597b83a27583f6a658d408825105b16d31b6ed088fc6"
                "23f648fd6d95e9cefcb0745763cddf564c87bcf4ba7928e74fd6a3080481f"
                "588d535e4c026b58a21e1e5ec412ff241b436043e29173f1dc6cb943c0974"
                "2de989547288",
                16,
            ),
            "p": int(
                "da3a8085d372437805de95b88b675122f575df976610c6a844de99f1df82a"
                "06848bf7a42f18895c97402e81118e01a00d0855d51922f434c022350861d"
                "58ddf60d65bc6941fc6064b147071a4c30426d82fc90d888f94990267c64b"
                "eef8c304a4b2b26fb93724d6a9472fa16bc50c5b9b8b59afb62cfe9ea3ba0"
                "42c73a6ade35",
                16,
            ),
            "q": 1386090807861091316803998193774751098153687863463,
            "x1": 381229709512864262422021151581620734547375903702,
            "x2": 479735944608461101114916716909067001453470352916,
            "y1": int(
                "5a7890f6d20ee9c7162cd84222cb0c7cb5b4f29244a58fc95327fc41045f4"
                "76fb3da42fca76a1dd59222a7a7c3872d5af7d8dc254e003eccdb38f29161"
                "9c51911df2b6ed67d0b459f4bc25819c0078777b9a1a24c72e7c037a3720a"
                "1edad5863ef5ac75ce816869c820859558d5721089ddbe331f55bef741396"
                "a3bbf85c6c1a",
                16,
            ),
            "y2": int(
                "b92af0468b841ea5de4ca91d895b5e922245421de57ed7a88d2de41610b20"
                "8e8e233705f17b2e9eb91914bad2fa87f0a58519a7da2980bc06e7411c925"
                "a6050526bd86e621505e6f610b63fdcd9afcfaa96bd087afca44d9197cc35"
                "b559f731357a5b979250c0f3a254bb8165f5072156e3fd6f9a6e69bcf4b45"
                "78f78b3bde7",
                16,
            ),
            "z": binascii.unhexlify(
                b"8d8f4175e16e15a42eb9099b11528af88741cc206a088971d3064bb291ed"
                b"a608d1600bff829624db258fd15e95d96d3e74c6be3232afe5c855b9c596"
                b"81ce13b7aea9ff2b16707e4c02f0e82bf6dadf2149ac62630f6c62dea0e5"
                b"05e3279404da5ffd5a088e8474ae0c8726b8189cb3d2f04baffe700be849"
                b"df9f91567fc2ebb8"
            ),
        },
        {
            "fail_agree": False,
            "fail_z": False,
            "g": int(
                "a51883e9ac0539859df3d25c716437008bb4bd8ec4786eb4bc643299daef5"
                "e3e5af5863a6ac40a597b83a27583f6a658d408825105b16d31b6ed088fc6"
                "23f648fd6d95e9cefcb0745763cddf564c87bcf4ba7928e74fd6a3080481f"
                "588d535e4c026b58a21e1e5ec412ff241b436043e29173f1dc6cb943c0974"
                "2de989547288",
                16,
            ),
            "p": int(
                "da3a8085d372437805de95b88b675122f575df976610c6a844de99f1df82a"
                "06848bf7a42f18895c97402e81118e01a00d0855d51922f434c022350861d"
                "58ddf60d65bc6941fc6064b147071a4c30426d82fc90d888f94990267c64b"
                "eef8c304a4b2b26fb93724d6a9472fa16bc50c5b9b8b59afb62cfe9ea3ba0"
                "42c73a6ade35",
                16,
            ),
            "q": 1386090807861091316803998193774751098153687863463,
            "x1": int(
                "32e642683d745a23dccf4f12f989d8dfd1fd9894c422930950cb4c71", 16
            ),
            "x2": int(
                "7d8ae93df3bc09d399a4157ec562126acf51092c3269ab27f60a3a2b", 16
            ),
            "y1": int(
                "8cd371363b32fcc2e936e345f2278b77001f2efdf78512c3ee75c12f88507"
                "e2d5c0e5cdded3bb78435506c8028a3f4d6f028c0f49a0d61f1285795197e"
                "56deac80279e723f2b3746e213ac8ec60f1cefc2308ff17a7e9e2efab537e"
                "17406d2829fd85e0c54dda2d9f0b4fcda3d2776110e096a817588e19588b7"
                "7be8b41bafdd41ad91b0edf629333bd6ac1e461208ead124c31b8a7935c72"
                "3e1c450c5798dc05f8265ad9e35095ff112af9e889f00315fa337a76a4506"
                "70866eca12cc6ad0778576962eb9cdc12721d3c15e4d87b67488a145d4002"
                "40670eb26695a42879cd3940a55087f6527667277e1212a202dbe455c45c6"
                "4b9be4a38153557bbb8fd755",
                16,
            ),
            "y2": int(
                "22127e9728e906ea4b1512c8b1e80474b58446210c23ccfc800f83c2c15da"
                "8159940e494b235266f6a9d5f80529067794f1a9edd566755d23d0a3060fe"
                "074c5a10122df3e472973bba39ea3a988e8387f5f0491e590b6b5edc299b4"
                "598ab1e79b72681a0be8cd8735a5adb85fa31310f29ec407c9654f1bb83bc"
                "df7f771b68d176817f662e8d798b53ebb4e5dd407b7b1d8fdb62ea9e1b60d"
                "6c3d75d9bcf83f4b8d1ed39408bd8d973b4ea81e8e832eac361dcd5307133"
                "88a60971ea9f8b1e69c1e99df1cca12bdaf293dacfa1419c5692ceffa9198"
                "8aef3321ac8cbc2efae6c4337c8808310fb5a240395a98e6004fe613c39e8"
                "4f4177341746d9e388dcb2e8",
                16,
            ),
            "z": binascii.unhexlify(
                b"0efeaa399a182e0a603baf0dd95aa0fae5289ebd47d5f0f60c86bc936839"
                b"c31c9f7f37bf04f76ab02f4094a8ab10ed907ec7291585cc085c3e8981df"
                b"2bd46a01c19ec9a2f66709df1d4fefbeb48c8263554e46890f59eb642bf9"
                b"5ff7f0de70138621c22c4cc32be6c3d5c82c0c9a76a9f5a65bffe0c096a3"
                b"50f96a9da945d7e5095b15b566ce3cb8b0377cd9375b6c046afa9ea0bc08"
                b"46773445f16566b2c84cae4f6d212e89ee539a1ce7ea325273fd228053ef"
                b"ce2a585eb9e8f308b48cf4e29593b6f7a02e8625e1e8bff1ea1405f8c8c3"
                b"4b8339a9a99c7c9de4eb9895df7719ccda9394f53080eff1226f6b9c7ae0"
                b"a38941e18b1a137aabbb62308eb35ba2"
            ),
        },
        {
            "fail_agree": False,
            "fail_z": True,
            "g": int(
                "a51883e9ac0539859df3d25c716437008bb4bd8ec4786eb4bc643299daef5"
                "e3e5af5863a6ac40a597b83a27583f6a658d408825105b16d31b6ed088fc6"
                "23f648fd6d95e9cefcb0745763cddf564c87bcf4ba7928e74fd6a3080481f"
                "588d535e4c026b58a21e1e5ec412ff241b436043e29173f1dc6cb943c0974"
                "2de989547288",
                16,
            ),
            "p": int(
                "da3a8085d372437805de95b88b675122f575df976610c6a844de99f1df82a"
                "06848bf7a42f18895c97402e81118e01a00d0855d51922f434c022350861d"
                "58ddf60d65bc6941fc6064b147071a4c30426d82fc90d888f94990267c64b"
                "eef8c304a4b2b26fb93724d6a9472fa16bc50c5b9b8b59afb62cfe9ea3ba0"
                "42c73a6ade35",
                16,
            ),
            "q": 1386090807861091316803998193774751098153687863463,
            "x1": int(
                "66502429aba271e2f2ee2197a2b336e5f0467f192aa28b60dcbf1194", 16
            ),
            "x2": int(
                "106b358be4f068348ac240ecbb454e5c39ca80b078cb0fafd856e9c5", 16
            ),
            "y1": int(
                "dfb001294215423d7146a2453cdb8598ccef01e1d931a913c3e4ed4a3cf38"
                "a912066c28e4eaf77dd80ff07183a6160bd95932f513402f864dcf7a70cbe"
                "dc9b60bbfbc67f72a83d5f6463a2b5a4fc906d3e921f5e1069126113265b4"
                "40e15ccf2d7164bad7131f1613fec35df7f470d45888e0c91be091f3f9552"
                "d670b8b7f479853193cb3c39f35fc7bd547ccb1bc579a67302b4ba948e6db"
                "51043d351bb74a952e6a694e6e7456f714c47d7c8eeeb4fd83ad93c86b784"
                "45f9393fdfd65c7dbd7fd6eba9794ddf183901b1d213321fd0ab3f7588ab0"
                "f6b3692f365a87131eda0e062505861988f6ce63150207545ecf9678e0971"
                "330253dfb7cfd546c5346fec",
                16,
            ),
            "y2": int(
                "715d0781975b7b03162f4401c1eda343fd9bf1140006034573b31828a618c"
                "356163554cd27da956f7179a69e860fb6efeaa2e2aa9f1261506a8344c492"
                "9953621381b13d6426e152c0f2f94bfcd2b758eca24923596d427ed8f957e"
                "8bc9b1c7d21a87ef02222a1477cf3bfaadc68106456ab9706026006eccd29"
                "0b21543de6bb97d5b8cf4ccee1c081a6d1dd27aaef060fa93888a47a4a416"
                "ad5c5bd490ea600e04379232fb1077fbf394f4579accdbe352714e25b8891"
                "6dca8d8f7e0c4ed9594f7693f656a235a2e88ebda48b0d557e32da9f12d2a"
                "4c3180f05b16b4fba9bec79278a3971b77f9223b5ab78b857e0376c500821"
                "1592c8c72d521373ee3b22b8",
                16,
            ),
            "z": binascii.unhexlify(
                b"cf879ebd107bb877457809c3fc410218b7acba3c5967495a8f1c3370d57f"
                b"038a48dd69f9f69b9f4dd855e7c58a1e4ec32646a978266eb314db468ea1"
                b"dfcee8a85a1644a5732498c4fbcdf85098c6ed0ce12e431e99142fd23353"
                b"69b3f56620ada21aa69d883e82a0b5e35484dde32d17c2dc873f2cc5518e"
                b"b7fc19695dff9fc94c9d9432bb4b09d8180323cfc561ebc2d6eff8dd5f84"
                b"96f2b22377700a22bbfe61a6969c198129397454843e4fc3540026986039"
                b"665095490056287e4fc49e6cb3181cb2bf06444fd0040150271c9ce1f61c"
                b"13ecd5dd022194a2dbf3e1c7fbc6bd19497c7b888b4da613d28fa6f378a4"
                b"3369cb8795a1c823f7d6cf4d84bba578"
            ),
        },
        {
            "fail_agree": True,
            "fail_z": False,
            "g": int(
                "35513ec441402b78353ab1bba550b21c76c89973885a627170262ef52497d"
                "5d137b8927a212aaab2f051198c90bb81dffd9eb10b36b7ca3b63565b4c10"
                "25aea3b5e9c4a348c9cfa17f3907a1e4469701c0dedb8a4b9e96c5965b1fb"
                "8c229b0c34baac774bf9dda4fc5ee8764358b3c84812878aab7464bc09e97"
                "aecab7d7e3fbb4870e2a3b89667a4158bf1ed1a90dfaf47019fbb52b1b963"
                "65bb4e1e9474993fe382fd23480dc875861be152997a621fdb7aef977ea5b"
                "4d3d74486b162dc28f95a64cf65587a919a57eef92934fc9410df7f09fa82"
                "f975328ed82ff29cc3e15a971f56f4ac2dcb289252575e02a6cdb7fcc6cdd"
                "d7b0dca9c422e63eb2b8f05",
                16,
            ),
            "p": int(
                "f3722b9b911c6aede9eaeeaa406283de66a097f39a7225df6c3c916e57920"
                "d356e50478d307dbfd146bfb91b6f68ecbbcf54b3d19c33a4b17293fea3e3"
                "d6bff8ac4cca93a805386f062a8a27ae906ef5da94d279fd7b3d7289e0095"
                "6f76bae9c0d2b8d11742ca5809630632aae58f9c6dce00c7380581deffde2"
                "187b022f83c6ceaeaadb0844a17fcbb04039ca6843c91f0c9058b22434b26"
                "3c3dfda8de8429e087c5be97fc5c9db9526031ad3a218bd9916fb4a3c2796"
                "6d208b1e360014c01e95530c148fb3cd27e6a7250d3c3b81dcd220ca14548"
                "dbccf99ebb9e334db6bcd14e632c98dd3f9860af7ae450f1b7809b45f0ec1"
                "0e6f27672beebc9963befc73",
                16,
            ),
            "q": int(
                "a9a17de95a29091bf8e07dab53ea1aba9403be3c61027c6c8f48bac5", 16
            ),
            "x1": int(
                "1610eaa4e0ccc8857e2b53149e008492b1fbd9025a6e8d95aaee9c0f", 16
            ),
            "x2": int(
                "c4c83d75b27864b052cadc556e500e25aabf0c9d1bc01f0e1fe3862", 16
            ),
            "y1": int(
                "51ee21cd9f97015180f258fad5c94ff5a458806b1412087236bf77fe87aae"
                "1a36735816ed6e2160a731159814b6ae1f3f52c478dd9207094adfb62f766"
                "7d5c366327e66d23096395e938504db330953a708015f861fe9d948761109"
                "3b9fe7327518a7cc15994ab573313e154117c1a3ae88b8bdd1e316748249e"
                "4a9cbd1947f159836d13613d1f9449fc3442171d1970bc28958c1cafa2776"
                "a6f14ccdb29db02f64911bd83bfdcdfc843dd14a4cab9acb0bda8b293d2f5"
                "f7050768e57533cbc415a29e6f31cc365e107f91ae3722484e2c7329a85af"
                "69055a5a104da37e810878896d1b247b02b75234ecff82b1958f42d7b0316"
                "22e9394c98b5229112f7f620",
                16,
            ),
            "y2": int(
                "467a857337a82472a1307a64dccc8e9994c5c63ec4312936885d17be41905"
                "1a5f037fbb052d7010ebe01634d9e8b8b522d9ab4749fdc274f465369b89e"
                "360df8f70b7865a3c71d2dbcd2df19e9293dab1153d3d63fcb7deb559b684"
                "dde6c6eed63214444807041c9a0ce3f52ca439ec16dd231995b5dc6f18e68"
                "01b6bd6454babccf9abbfacffb49c71e6494a4779cbfa550c5d7144114e6f"
                "c193f460dcd0be7e6e06e546da7653770dc5859df87029e722dbe81361030"
                "569148d1636988926bf0dcfe47c9d8a54698c08b3b5c70afe86b5c6f64346"
                "3f8f34889d27d6cfd2d478c2d7b3d008a985c7380f0b43f10024b59c35438"
                "80883c42d0e7e0a07326ba3a",
                16,
            ),
            "z": binascii.unhexlify(
                b"10a30bacab82e652415376baffdbc008c7eb2e5a3aa68bc10ce486ca8498"
                b"3fd89b1b027bb40e75333406361005f5e756526a95fe01202df9217d81b1"
                b"713d5187c368fdd4c9c2433d9e6c18844769479b725c4140c92a304ee1bc"
                b"5726d8f5321b5b1c54a1a6b67c527e6817c0ed613a0d4e60db55de898788"
                b"b7e8d4aa9a81ab5ed7f6282962c433d246ed640555bdd76d29c287455126"
                b"4d74c76373f8a88871b41b041c98041b16f94f983ddf00f5bc7d2416d191"
                b"68c90178974a0602436cd186748bcc63a629edc3a0db59415cccd37a6513"
                b"0ea477c89da92d41371f5972891cf41f9c7f0e75ccbff9893225384db30d"
                b"aa5e310f08e3e0fad98bcdf8ecf35fe5"
            ),
        },
        {
            "fail_agree": False,
            "fail_z": False,
            "g": int(
                "35513ec441402b78353ab1bba550b21c76c89973885a627170262ef5"
                "2497d5d137b8927a212aaab2f051198c90bb81dffd9eb10b36b7ca3b"
                "63565b4c1025aea3b5e9c4a348c9cfa17f3907a1e4469701c0dedb8a"
                "4b9e96c5965b1fb8c229b0c34baac774bf9dda4fc5ee8764358b3c84"
                "812878aab7464bc09e97aecab7d7e3fbb4870e2a3b89667a4158bf1e"
                "d1a90dfaf47019fbb52b1b96365bb4e1e9474993fe382fd23480dc87"
                "5861be152997a621fdb7aef977ea5b4d3d74486b162dc28f95a64cf6"
                "5587a919a57eef92934fc9410df7f09fa82f975328ed82ff29cc3e15"
                "a971f56f4ac2dcb289252575e02a6cdb7fcc6cddd7b0dca9c422e63e"
                "b2b8f05",
                16,
            ),
            "p": int(
                "f3722b9b911c6aede9eaeeaa406283de66a097f39a7225df6c3c916e"
                "57920d356e50478d307dbfd146bfb91b6f68ecbbcf54b3d19c33a4b1"
                "7293fea3e3d6bff8ac4cca93a805386f062a8a27ae906ef5da94d279"
                "fd7b3d7289e00956f76bae9c0d2b8d11742ca5809630632aae58f9c6"
                "dce00c7380581deffde2187b022f83c6ceaeaadb0844a17fcbb04039"
                "ca6843c91f0c9058b22434b263c3dfda8de8429e087c5be97fc5c9db"
                "9526031ad3a218bd9916fb4a3c27966d208b1e360014c01e95530c14"
                "8fb3cd27e6a7250d3c3b81dcd220ca14548dbccf99ebb9e334db6bcd"
                "14e632c98dd3f9860af7ae450f1b7809b45f0ec10e6f27672beebc99"
                "63befc73",
                16,
            ),
            "q": int(
                "a9a17de95a29091bf8e07dab53ea1aba9403be3c61027c6c8f48bac5", 16
            ),
            "x1": int(
                "9ee22ac51664e40e0a24dbb94142dba40605e2b6eeaaa0268a0f6847", 16
            ),
            "x2": int(
                "438093a468236658821bf64eb08456139963d4fb27121c3ed6c55876", 16
            ),
            "y1": int(
                "c2630c9d38ed5c825d1c6a3eba7143f3fc8a049c8bcd1efc212d2af64eca9"
                "94308208691d330aa8f27fc4a1e55de4e512113996d21375a667f8c26d76d"
                "ee2f6809b15432a33fb735aca5c2263940f58712bded08f55443dee300b94"
                "89589e0462bd6bce19deaec4adc12fa61a694c8c5c999b28211d7835bac0f"
                "fd2b316850823e2dc1d1f58e05cbf75c673036d116b3f03b9687c89f9c2a0"
                "d43c4ffc9a605addbdcce0cb3790c6db846156bb857a7b3df40dc6ed04d19"
                "cc9eaebb6bbc034e77c3d882a1a62317cce25b6130f0803e3bc49b5e36768"
                "260073a617034872be0b50bed32740224beaf582d67fbcfef3b3ecc18f9c7"
                "1c782e9a68495ef31dc7986e",
                16,
            ),
            "y2": int(
                "e192da8e1244e27221c1765344a5bb379dce741d427a734b4bdb6c4d16b24"
                "90bd37564d745008e63ae46ef332331d79887ac63298ce143e125f8b320c0"
                "f859b7f5f2c1e0053e4a7a16997e6143ff702300c9863ae7caef5c1dfca0e"
                "cf5197c557745b793f0790a4fe678aeb93fdb52490d4f273a5553944dda3a"
                "c8b9b792c9b67f8d7b9496398e432a423ae87ebeba688be3ed67eddd7575f"
                "a56431cd48579bf53c903bbe066dd78b23c0996ef3a880f0d91315104366a"
                "82f01abdecce96fd371f94e8420f8bc5b896c801df573554f749b03d0d28b"
                "1e1a990bc61c7e9659342ac7e268e9c0b7c40fdaab394f29cf0a54f780022"
                "f9a03b0bd28eb7db8b0b1b47",
                16,
            ),
            "z": binascii.unhexlify(
                b"56f8f40fa4b8f3580f9014b30d60a42933a53a62182a690142f458dc275c"
                b"3b2f0e721bc5ee6e890b14516419110f5252ff1cceea8e274b2987aa78e3"
                b"bae90c1935b276b7a1f1c944f79d4774b7a85b3355bdf25cb02bddfbda4e"
                b"e7918bc93a5c9ca6d7e8fdedbda8e6c8a6ca794bad055a52b19c14895822"
                b"7344cbddd70271d4610316cfea1e559b0bc3a12d15023b30d9f2db602053"
                b"a0569c3bd2ce1faf59280ecd339f845dbcaaf2e883c5cc6263996f866b18"
                b"b75d049d4c82097af8a5ce353e14416b3eeb31ba9bc4f6f3dbd846c5299f"
                b"b5c0043a1b95b9149b39d14df9e6a69547abf8a4d518475576730ed52877"
                b"9366568e46b7dd4ed787cb72d0733c93"
            ),
        },
    ]

    assert expected == load_kasvs_dh_vectors(vector_data)


def test_load_kasvs_ecdh_vectors_empty_vector_data():
    assert [] == load_kasvs_ecdh_vectors([])


def test_load_kasvs_ecdh_vectors():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.0
    #  Parameter set(s) supported: EA EB EC ED EE
    #  CAVSid: CAVSid (in hex: 434156536964)
    #  IUTid: In hex: a1b2c3d4e5
    [EA]

    [Curve selected:  P-192]
    [SHA(s) supported (Used for hashing Z):  SHA1]
    [EB]

    [Curve selected:  P-224]
    [SHA(s) supported (Used for hashing Z):  SHA224]
    [EC]

    [Curve selected:  P-256]
    [SHA(s) supported (Used for hashing Z):  SHA256]
    [ED]

    [Curve selected:  P-384]
    [SHA(s) supported (Used for hashing Z):  SHA384]
    [EE]

    [Curve selected:  P-521]
    [SHA(s) supported (Used for hashing Z):  SHA512]
    #  Generated on Thu Mar 17 19:46:10 2011



    [EA - SHA1]


    COUNT = 0
    dsCAVS = f70c297a683d6b7ef82b5af7349606c4447c8b4fc6fa5e80
    QsCAVSx = f7b5061fb557e516c50abf541d97dbfd76ca7172b22cf590
    QsCAVSy = 135e15e21f9e85c76205fd148a92ac19f9e6243ddab322d1
    dsIUT = a5b4bbad57f101ca48021cb7440cd681a9d40cd51b99d917
    QsIUTx = 79a77fcb18a32cdb59ed5d87740f29e8565d649dbf01ce86
    QsIUTy = f7187efaa0b1573f1fb00905d46810b880bf738b4c720bb7
    Z = 26382468d721761e14a87dc3bee67340095c6455962d1ba3
    CAVSHashZZ = af52ba700d3bbba7ce2916d6b729422c26c32364
    Result = P (0 - Correct)



    COUNT = 2
    dsCAVS = 5f909dcb0ccce58c82fada748c47297579e6a981b5518a96
    QsCAVSx = 537f1ecfda0e366de393a9bc8188fcc280311bffefe21ecf
    QsCAVSy = a1fa1f98498d65f2754caff4e5303a4066a5ff89fde95381
    dsIUT = 3357aa7f47f3e09421602cc12cdce4434c68e330d44de05e
    QsIUTx = 6a33d43d9c72173eabc7a771a5687748c4774c62762e96ec
    QsIUTy = 8033f238b3abc69470aad4be8dbe4f60a2fd50207626c56a
    Z = 3153034f6617326f19c35be8c99a0585431adf09d2f8e0fd
    CAVSHashZZ = f8414e30c2d382e28d2a57a2447fdc203baa416b
    Result = F (8 - Z changed )



    COUNT = 8
    dsCAVS = 8fcfaf0524cc868fad20e50410a2205319f1327308d98dc8
    QsCAVSx = 9b0243d80a9e328738080fb4d46bc450243d0efb7ead0c92
    QsCAVSy = ad5bebad7f03849693071537f60ef858cad214123beee7c7
    dsIUT = bba95dac90289cb68ca2b006f9757219b70579c299ad7a7d
    QsIUTx = 7733dc0cb365cd6312724196b9b4eb491fd4d2e31b9afdb1
    QsIUTy = 92ffa3722acc5b94d772258ba2d471b06c0f53f56fcd8662
    Z = 0f3c6e4a29a08296ae730f56a1ebf819ea2edfa6f0434e40
    CAVSHashZZ = c124545eed4b83a799e7e90371d806b5684a1bd2
    Result = P (13 - Z value should have leading 0 nibble )


    [EB - SHA224]


    COUNT = 0
    dsCAVS = e53a88af7cf8ce6bf13c8b9ad191494e37a6acc1368c71f4306e39e5
    QsCAVSx = 3a24217c4b957fea922eec9d9ac52d5cb4b3fcd95efde1e4fa0dd6e2
    QsCAVSy = 775b94025a808eb6f4af14ea4b57dca576c35373c6dc198b15b981df
    dsIUT = 09f51e302c6a0fe6ff48f34c208c6af91e70f65f88102e6fcab9af4a
    QsIUTx = c5d5706ccd7424c74fd616e699865af96e56f39adea6aa059e5092b5
    QsIUTy = f0729077bb602404d56d2f7e2ba5bb2f383df4a5425567881ff0165d
    Z = b1259ceedfb663d9515089cf727e7024fb3d86cbcec611b4ba0b4ab6
    CAVSHashZZ = 8b21fd05a4b50e401908cd8f26757f5c57f22b69f170aa7381f8596d
    Result = P (0 - Correct)



    [EC - SHA256]


    COUNT = 0
    dsCAVS = 305dfb4a8850cc59280891147baf457bfe5e2bae984571634a77dc8d3472fa9b
    QsCAVSx = 202cb5a224e6c2a84e624094486edf04116c8d68ec1f4a0e0ed9ee090e1a900b
    QsCAVSy = cacf3a5789bb33954be600425d62d9eae5371f90f88167258814213e4a4f4b1a
    dsIUT = 72cc52808f294b64b6f7233c3d2f5d96cc1d29287320e39e1c151deef0bc14eb
    QsIUTx = 49a768c9a4ca56e374f685dd76a461b1016c59dcded2c8d8cbd9f23ca453831f
    QsIUTy = b1e3bb9b5f12a3b5ae788535d4554bd8c46e0e6130075e4e437d3854cf8f1c34
    Z = c0147c3c2691b450b5edc08b51aea224d9f4359ff67aab6da3146f396dbceaea
    CAVSHashZZ = ea9ffd54511979ab8c4b387784972cbd05fc5fd4ff78e048b0026557b56a5\
1dd
    Result = F (2 - CAVS's Static public key Y fails PKV 5.6.2.5)



    [ED - SHA384]


    COUNT = 0
    dsCAVS = 0e5c98ff2d2a3aab14ad0067b60dbe64e4f541ab5bed11c5a0c55ae1e60b51ff5\
faaf377837977d80cbfdc33c2ff542b
    QsCAVSx = d1bf2ac21637d66d6398aac01dcd56ac6f065fb45d1f6f16747bab9e9b01b463\
0b59b20927aea147355bf41838acb482
    QsCAVSy = 4c9e23f1c5a41647d094086bf4ed31708651f21d996c47780688ac10f77deee2\
e43b5241b6caecd2fd5444bc50472e0e
    dsIUT = f865418473e5bf7d2e1bbcd9bd5a9270c003a9dd35e778133ca59fcab4bb64fe24\
d6800e7047bdd033abc8bfa8db35b5
    QsIUTx = 32b72ab9b558249dcbc6cbade234f58e4f7aa5d3f6420ea99a5f997e8c2a91fb7\
fd83779d0d2169428683771c745fd1a
    QsIUTy = c749e02a3719bb56bf1dfc4ba3820309c01ab6e84cb29db7cdd80f127233f5295\
687f8178f3a8704c1063b84c2ee472f
    Z = a781430e6078a179df3f9ee27cd8fdc6188f161b6c4ccc4053ef6c6ca6fc222946883a\
53c06db08f0a020023ced055aa
    CAVSHashZZ = ccb70d0adbabe4d8956519db0d536605cbb366aed58fc55718f56ae3648fa\
5c9ee7bae56cc463587cb74e2f9c6ace1cb
    Result = P (0 - Correct)



    [EE - SHA512]


    COUNT = 0
    dsCAVS = 0000002fef62381162942889a6094a6bb9ac1f4ddf66d9cda9f618232d31b90c5\
0d7da78a47ed91d40cae946898571db972dc294b109815f38feee9eaac0d5f7c3250728
    QsCAVSx = 0000004b05ffa025113390797f2736174aa1c784f4dd34e764ee40d40e4d2442\
677ebea3498086c9473e5c92789cbdb02bb327bbd61d58690f6a83d9ca73bccbde37dec4
    QsCAVSy = 0000004da67cffc98070b82af61feba78787efefb13bd810d80ff92304788e49\
a4e5b634b3565474a8ecb1615d7b1b77a7a27875adb73a8a5d8f3f84e5e8b744cda250b0
    dsIUT = 00000311a5e520e238141527671a38cb6f776d96a9f82ef70dffa11dc0895f4060\
f1abbb9ad6fd259e4a7beaf5f7266ea1bb45bcbfebfda2705e5c551e710fb1d745f57e
    QsIUTx = 0000010ba3778cb2cc965834c0a9593adc6a222692656d657fb0d15293edf0ab3\
3762384a96a16fddea7540b7ccbcca46ec4ac9bcf95fdb5aa18e158aab4d91981bd733e
    QsIUTy = 0000018522df93ddd636e5bc94daecdc600fa241686ec18634fd30b7cbdfdc9ff\
ba1166ac08df34a31896f6fad191414929261ebd7187afb72919f8a0c926be37f99c1e5
    Z = 01a5e4b31be4b1346e53906b6767b1fe94ec1a8a5abc28fb6f01518c056959af3bc933\
5dddab178b52318cc5512559931b8dc18de0ce810c2c7f15769d7ce70e719c
    CAVSHashZZ = d2d6538feb65d609f377b81a027dc800eed07b69c0e9eedb243369202ed47\
f47021022a6c9b45ed791d09d9540eb81ea065fc1959eca365001ee39928c343d75
    Result = F (7 - IUT's Static private key d changed-prikey validity)



    """
    ).splitlines()

    expected = [
        {
            "errno": 0,
            "fail": False,
            "COUNT": 0,
            "CAVS": {
                "d": int(
                    "f70c297a683d6b7ef82b5af7349606c4447c8b4fc6fa5e80", 16
                ),
                "x": int(
                    "f7b5061fb557e516c50abf541d97dbfd76ca7172b22cf590", 16
                ),
                "y": int(
                    "135e15e21f9e85c76205fd148a92ac19f9e6243ddab322d1", 16
                ),
            },
            "IUT": {
                "d": int(
                    "a5b4bbad57f101ca48021cb7440cd681a9d40cd51b99d917", 16
                ),
                "x": int(
                    "79a77fcb18a32cdb59ed5d87740f29e8565d649dbf01ce86", 16
                ),
                "y": int(
                    "f7187efaa0b1573f1fb00905d46810b880bf738b4c720bb7", 16
                ),
            },
            "Z": int("26382468d721761e14a87dc3bee67340095c6455962d1ba3", 16),
            "curve": "secp192r1",
        },
        {
            "errno": 8,
            "fail": True,
            "COUNT": 2,
            "CAVS": {
                "d": int(
                    "5f909dcb0ccce58c82fada748c47297579e6a981b5518a96", 16
                ),
                "x": int(
                    "537f1ecfda0e366de393a9bc8188fcc280311bffefe21ecf", 16
                ),
                "y": int(
                    "a1fa1f98498d65f2754caff4e5303a4066a5ff89fde95381", 16
                ),
            },
            "IUT": {
                "d": int(
                    "3357aa7f47f3e09421602cc12cdce4434c68e330d44de05e", 16
                ),
                "x": int(
                    "6a33d43d9c72173eabc7a771a5687748c4774c62762e96ec", 16
                ),
                "y": int(
                    "8033f238b3abc69470aad4be8dbe4f60a2fd50207626c56a", 16
                ),
            },
            "Z": int("3153034f6617326f19c35be8c99a0585431adf09d2f8e0fd", 16),
            "curve": "secp192r1",
        },
        {
            "errno": 13,
            "fail": False,
            "COUNT": 8,
            "CAVS": {
                "d": int(
                    "8fcfaf0524cc868fad20e50410a2205319f1327308d98dc8", 16
                ),
                "x": int(
                    "9b0243d80a9e328738080fb4d46bc450243d0efb7ead0c92", 16
                ),
                "y": int(
                    "ad5bebad7f03849693071537f60ef858cad214123beee7c7", 16
                ),
            },
            "IUT": {
                "d": int(
                    "bba95dac90289cb68ca2b006f9757219b70579c299ad7a7d", 16
                ),
                "x": int(
                    "7733dc0cb365cd6312724196b9b4eb491fd4d2e31b9afdb1", 16
                ),
                "y": int(
                    "92ffa3722acc5b94d772258ba2d471b06c0f53f56fcd8662", 16
                ),
            },
            "Z": int("0f3c6e4a29a08296ae730f56a1ebf819ea2edfa6f0434e40", 16),
            "curve": "secp192r1",
        },
        {
            "errno": 0,
            "fail": False,
            "COUNT": 0,
            "CAVS": {
                "d": int(
                    "e53a88af7cf8ce6bf13c8b9ad191494e37a6acc1368c71f4"
                    "306e39e5",
                    16,
                ),
                "x": int(
                    "3a24217c4b957fea922eec9d9ac52d5cb4b3fcd95efde1e4"
                    "fa0dd6e2",
                    16,
                ),
                "y": int(
                    "775b94025a808eb6f4af14ea4b57dca576c35373c6dc198b"
                    "15b981df",
                    16,
                ),
            },
            "IUT": {
                "d": int(
                    "09f51e302c6a0fe6ff48f34c208c6af91e70f65f88102e6f"
                    "cab9af4a",
                    16,
                ),
                "x": int(
                    "c5d5706ccd7424c74fd616e699865af96e56f39adea6aa05"
                    "9e5092b5",
                    16,
                ),
                "y": int(
                    "f0729077bb602404d56d2f7e2ba5bb2f383df4a542556788"
                    "1ff0165d",
                    16,
                ),
            },
            "Z": int(
                "b1259ceedfb663d9515089cf727e7024fb3d86cbcec611b4ba0b4ab6",
                16,
            ),
            "curve": "secp224r1",
        },
        {
            "errno": 2,
            "fail": True,
            "COUNT": 0,
            "CAVS": {
                "d": int(
                    "305dfb4a8850cc59280891147baf457bfe5e2bae98457163"
                    "4a77dc8d3472fa9b",
                    16,
                ),
                "x": int(
                    "202cb5a224e6c2a84e624094486edf04116c8d68ec1f4a0e"
                    "0ed9ee090e1a900b",
                    16,
                ),
                "y": int(
                    "cacf3a5789bb33954be600425d62d9eae5371f90f8816725"
                    "8814213e4a4f4b1a",
                    16,
                ),
            },
            "IUT": {
                "d": int(
                    "72cc52808f294b64b6f7233c3d2f5d96cc1d29287320e39e"
                    "1c151deef0bc14eb",
                    16,
                ),
                "x": int(
                    "49a768c9a4ca56e374f685dd76a461b1016c59dcded2c8d8"
                    "cbd9f23ca453831f",
                    16,
                ),
                "y": int(
                    "b1e3bb9b5f12a3b5ae788535d4554bd8c46e0e6130075e4e"
                    "437d3854cf8f1c34",
                    16,
                ),
            },
            "Z": int(
                "c0147c3c2691b450b5edc08b51aea224d9f4359ff67aab6d"
                "a3146f396dbceaea",
                16,
            ),
            "curve": "secp256r1",
        },
        {
            "errno": 0,
            "fail": False,
            "COUNT": 0,
            "CAVS": {
                "d": int(
                    "0e5c98ff2d2a3aab14ad0067b60dbe64e4f541ab5bed11c5"
                    "a0c55ae1e60b51ff5faaf377837977d80cbfdc33c2ff542b",
                    16,
                ),
                "x": int(
                    "d1bf2ac21637d66d6398aac01dcd56ac6f065fb45d1f6f16"
                    "747bab9e9b01b4630b59b20927aea147355bf41838acb482",
                    16,
                ),
                "y": int(
                    "4c9e23f1c5a41647d094086bf4ed31708651f21d996c4778"
                    "0688ac10f77deee2e43b5241b6caecd2fd5444bc50472e0e",
                    16,
                ),
            },
            "IUT": {
                "d": int(
                    "f865418473e5bf7d2e1bbcd9bd5a9270c003a9dd35e77813"
                    "3ca59fcab4bb64fe24d6800e7047bdd033abc8bfa8db35b5",
                    16,
                ),
                "x": int(
                    "32b72ab9b558249dcbc6cbade234f58e4f7aa5d3f6420ea9"
                    "9a5f997e8c2a91fb7fd83779d0d2169428683771c745fd1a",
                    16,
                ),
                "y": int(
                    "c749e02a3719bb56bf1dfc4ba3820309c01ab6e84cb29db7"
                    "cdd80f127233f5295687f8178f3a8704c1063b84c2ee472f",
                    16,
                ),
            },
            "Z": int(
                "a781430e6078a179df3f9ee27cd8fdc6188f161b6c4ccc40"
                "53ef6c6ca6fc222946883a53c06db08f0a020023ced055aa",
                16,
            ),
            "curve": "secp384r1",
        },
        {
            "errno": 7,
            "fail": True,
            "COUNT": 0,
            "CAVS": {
                "d": int(
                    "0000002fef62381162942889a6094a6bb9ac1f4ddf66d9cd"
                    "a9f618232d31b90c50d7da78a47ed91d40cae946898571db"
                    "972dc294b109815f38feee9eaac0d5f7c3250728",
                    16,
                ),
                "x": int(
                    "0000004b05ffa025113390797f2736174aa1c784f4dd34e7"
                    "64ee40d40e4d2442677ebea3498086c9473e5c92789cbdb0"
                    "2bb327bbd61d58690f6a83d9ca73bccbde37dec4",
                    16,
                ),
                "y": int(
                    "0000004da67cffc98070b82af61feba78787efefb13bd810"
                    "d80ff92304788e49a4e5b634b3565474a8ecb1615d7b1b77"
                    "a7a27875adb73a8a5d8f3f84e5e8b744cda250b0",
                    16,
                ),
            },
            "IUT": {
                "d": int(
                    "00000311a5e520e238141527671a38cb6f776d96a9f82ef7"
                    "0dffa11dc0895f4060f1abbb9ad6fd259e4a7beaf5f7266e"
                    "a1bb45bcbfebfda2705e5c551e710fb1d745f57e",
                    16,
                ),
                "x": int(
                    "0000010ba3778cb2cc965834c0a9593adc6a222692656d65"
                    "7fb0d15293edf0ab33762384a96a16fddea7540b7ccbcca4"
                    "6ec4ac9bcf95fdb5aa18e158aab4d91981bd733e",
                    16,
                ),
                "y": int(
                    "0000018522df93ddd636e5bc94daecdc600fa241686ec186"
                    "34fd30b7cbdfdc9ffba1166ac08df34a31896f6fad191414"
                    "929261ebd7187afb72919f8a0c926be37f99c1e5",
                    16,
                ),
            },
            "Z": int(
                "01a5e4b31be4b1346e53906b6767b1fe94ec1a8a5abc28fb"
                "6f01518c056959af3bc9335dddab178b52318cc551255993"
                "1b8dc18de0ce810c2c7f15769d7ce70e719c",
                16,
            ),
            "curve": "secp521r1",
        },
    ]

    assert expected == load_kasvs_ecdh_vectors(vector_data)


def test_load_kasvs_ecdh_kdf_vectors():
    vector_data = textwrap.dedent(
        """
    #  Parameter set(s) supported: EB EC ED EE
    #  CAVSid: CAVSid (in hex: 434156536964)
    #  IUTid: In hex: a1b2c3d4e5
    [EB]

    [Curve selected:  P-224]
    [SHA(s) supported (Used in the KDF function):  SHA224 SHA256 SHA384 SHA512]
    [MAC algorithm supported:  HMAC]
    [HMAC SHAs supported:  SHA512]
    [HMACKeySize(in bits):  112]
    [HMAC Tag length(in bits):  64]

    #  Generated on Mon Dec 22 11:45:18 2014



    [EB - SHA224]


    COUNT = 50
    dsCAVS = 540904b67b3716823dd621ed72ad3dbc615887b4f56f910b78a57199
    QsCAVSx = 28e5f3a72d8f6b8499dd1bcdfceafcecec68a0d715789bcf4b55fe15
    QsCAVSy = 8c8006a7da7c1a19f5328d7e865522b0c0dfb9a29b2c46dc96590d2a
    Nonce = 4eefb2a29a0e89c3898a7affdfa60dd7
    dsIUT = 5e717ae889fc8d67be11c2ebe1a7d3550051448d68a040b2dee8e327
    QsIUTx = ae7f3db340b647d61713f5374c019f1be2b28573cb6219bb7b747223
    QsIUTy = 800e6bffcf97c15864ec6e5673fb83359b45f89b8a26a27f6f3dfbff
    NonceDKMIUT = bb7f1b40d14ebd70443393990b57
    OI = a1b2c3d4e5bb7f1b40d14ebd70443393990b574341565369645b1582daab9cc6c30d6\
1fdcf1cdfc7e9a304651e0fdb
    CAVSTag = 84de198c3a958c62
    Z = 43f23b2c760d686fc99cc008b63aea92f866e224265af60d2d8ae540
    MacData = 5374616e646172642054657374204d6573736167654eefb2a29a0e89c3898a7a\
ffdfa60dd7
    DKM = ad65fa2d12541c3a21f3cd223efb
    Result = F (12 - Tag changed )
    """
    ).splitlines()

    expected = [
        {
            "errno": 12,
            "fail": True,
            "COUNT": 50,
            "CAVS": {
                "d": int(
                    "540904b67b3716823dd621ed72ad3dbc615887b4f56f910b"
                    "78a57199",
                    16,
                ),
                "x": int(
                    "28e5f3a72d8f6b8499dd1bcdfceafcecec68a0d715789bcf"
                    "4b55fe15",
                    16,
                ),
                "y": int(
                    "8c8006a7da7c1a19f5328d7e865522b0c0dfb9a29b2c46dc"
                    "96590d2a",
                    16,
                ),
            },
            "IUT": {
                "d": int(
                    "5e717ae889fc8d67be11c2ebe1a7d3550051448d68a040b2"
                    "dee8e327",
                    16,
                ),
                "x": int(
                    "ae7f3db340b647d61713f5374c019f1be2b28573cb6219bb"
                    "7b747223",
                    16,
                ),
                "y": int(
                    "800e6bffcf97c15864ec6e5673fb83359b45f89b8a26a27f"
                    "6f3dfbff",
                    16,
                ),
            },
            "OI": int(
                "a1b2c3d4e5bb7f1b40d14ebd70443393990b574341565369"
                "645b1582daab9cc6c30d61fdcf1cdfc7e9a304651e0fdb",
                16,
            ),
            "Z": int(
                "43f23b2c760d686fc99cc008b63aea92f866e224265af60d2d8ae540",
                16,
            ),
            "DKM": int("ad65fa2d12541c3a21f3cd223efb", 16),
            "curve": "secp224r1",
        }
    ]

    assert expected == load_kasvs_ecdh_vectors(vector_data)


def test_load_x963_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 12.0
    # 'ANS X9.63-2001' information for sample

    [SHA-1]
    [shared secret length = 192]
    [SharedInfo length = 0]
    [key data length = 128]

    COUNT = 0
    Z = 1c7d7b5f0597b03d06a018466ed1a93e30ed4b04dc64ccdd
    SharedInfo =
        Counter = 00000001
        Hash input 1 = 1c7d7b5f0597b03d06a018466ed1a93e30ed4b04dc64ccdd00000001
        K1 = bf71dffd8f4d99223936beb46fee8ccc60439b7e
    key_data = bf71dffd8f4d99223936beb46fee8ccc

    COUNT = 1
    Z = 5ed096510e3fcf782ceea98e9737993e2b21370f6cda2ab1
    SharedInfo =
        Counter = 00000001
        Hash input 1 = 5ed096510e3fcf782ceea98e9737993e2b21370f6cda2ab100000001
        K1 = ec3e224446bfd7b3be1df404104af953c1b2d0f5
    key_data = ec3e224446bfd7b3be1df404104af953

    [SHA-512]
    [shared secret length = 521]
    [SharedInfo length = 128]
    [key data length = 1024]

    COUNT = 0
    Z = 00aa5bb79b33e389fa58ceadc047197f14e73712f452caa9fc4c9adb369348b8150739\
2f1a86ddfdb7c4ff8231c4bd0f44e44a1b55b1404747a9e2e753f55ef05a2d
    SharedInfo = e3b5b4c1b0d5cf1d2b3a2f9937895d31
        Counter = 00000001
        Hash input 1 = 00aa5bb79b33e389fa58ceadc047197f14e73712f452caa9fc4c9ad\
b369348b81507392f1a86ddfdb7c4ff8231c4bd0f44e44a1b55b1404747a9e2e753f55ef05a2d0\
0000001e3b5b4c1b0d5cf1d2b3a2f9937895d31
        K1 = 4463f869f3cc18769b52264b0112b5858f7ad32a5a2d96d8cffabf7fa733633d6\
e4dd2a599acceb3ea54a6217ce0b50eef4f6b40a5c30250a5a8eeee20800226
        Counter = 00000002
        Hash input 2 = 00aa5bb79b33e389fa58ceadc047197f14e73712f452caa9fc4c9ad\
b369348b81507392f1a86ddfdb7c4ff8231c4bd0f44e44a1b55b1404747a9e2e753f55ef05a2d0\
0000002e3b5b4c1b0d5cf1d2b3a2f9937895d31
        K2 = 7089dbf351f3f5022aa9638bf1ee419dea9c4ff745a25ac27bda33ca08bd56dd1\
a59b4106cf2dbbc0ab2aa8e2efa7b17902d34276951ceccab87f9661c3e8816
    key_data = 4463f869f3cc18769b52264b0112b5858f7ad32a5a2d96d8cffabf7fa733633\
d6e4dd2a599acceb3ea54a6217ce0b50eef4f6b40a5c30250a5a8eeee208002267089dbf351f3f\
5022aa9638bf1ee419dea9c4ff745a25ac27bda33ca08bd56dd1a59b4106cf2dbbc0ab2aa8e2ef\
a7b17902d34276951ceccab87f9661c3e8816
    """
    ).splitlines()

    assert load_x963_vectors(vector_data) == [
        {
            "hash": "SHA-1",
            "count": 0,
            "shared_secret_length": 192,
            "Z": "1c7d7b5f0597b03d06a018466ed1a93e30ed4b04dc64ccdd",
            "sharedinfo_length": 0,
            "key_data_length": 128,
            "key_data": "bf71dffd8f4d99223936beb46fee8ccc",
        },
        {
            "hash": "SHA-1",
            "count": 1,
            "shared_secret_length": 192,
            "Z": "5ed096510e3fcf782ceea98e9737993e2b21370f6cda2ab1",
            "sharedinfo_length": 0,
            "key_data_length": 128,
            "key_data": "ec3e224446bfd7b3be1df404104af953",
        },
        {
            "hash": "SHA-512",
            "count": 0,
            "shared_secret_length": 521,
            "Z": (
                "00aa5bb79b33e389fa58ceadc047197f14e73712f452caa9fc4c9adb3693"
                "48b81507392f1a86ddfdb7c4ff8231c4bd0f44e44a1b55b1404747a9e2e7"
                "53f55ef05a2d"
            ),
            "sharedinfo_length": 128,
            "sharedinfo": "e3b5b4c1b0d5cf1d2b3a2f9937895d31",
            "key_data_length": 1024,
            "key_data": (
                "4463f869f3cc18769b52264b0112b5858f7ad32a5a2d96d8cffabf7fa733"
                "633d6e4dd2a599acceb3ea54a6217ce0b50eef4f6b40a5c30250a5a8eeee"
                "208002267089dbf351f3f5022aa9638bf1ee419dea9c4ff745a25ac27bda"
                "33ca08bd56dd1a59b4106cf2dbbc0ab2aa8e2efa7b17902d34276951cecc"
                "ab87f9661c3e8816"
            ),
        },
    ]


def test_load_kbkdf_vectors():
    vector_data = textwrap.dedent(
        """
    # CAVS 14.4
    # "SP800-108 - KDF" information for "test1"
    # KDF Mode Supported: Counter Mode
    # Location of counter tested: (Before Fixed Input Data)\
( After Fixed Input Data)(In Middle of Fixed Input Data before Context)
    # PRFs tested: CMAC with key sizes:	AES128  AES192  AES256  TDES2  TDES3\
HMAC with key sizes:	SHA1  SHA224  SHA256  SHA384  SHA512
    # Generated on Tue Apr 23 12:20:16 2013

    [PRF=HMAC_SHA1]
    [CTRLOCATION=BEFORE_FIXED]
    [RLEN=8_BITS]

    COUNT=0
    L = 128
    KI = 00a39bd547fb88b2d98727cf64c195c61e1cad6c
    FixedInputDataByteLen = 60
    FixedInputData = 98132c1ffaf59ae5cbc0a3133d84c551bb97e0c75ecaddfc30056f68\
76f59803009bffc7d75c4ed46f40b8f80426750d15bc1ddb14ac5dcb69a68242
        Binary rep of i = 01
        instring = 0198132c1ffaf59ae5cbc0a3133d84c551bb97e0c75ecaddfc30056f68\
76f59803009bffc7d75c4ed46f40b8f80426750d15bc1ddb14ac5dcb69a68242
    KO = 0611e1903609b47ad7a5fc2c82e47702

    COUNT=1
    L = 128
    KI = a39bdf744ed7e33fdec060c8736e9725179885a8
    FixedInputDataByteLen = 60
    FixedInputData = af71b44940acff98949ad17f1ca20e8fdb3957cacdcd41e9c591e182\
35019f90b9f8ee6e75700bcab2f8407525a104799b3e9725e27d738a9045e832
        Binary rep of i = 01
        instring = 01af71b44940acff98949ad17f1ca20e8fdb3957cacdcd41e9c591e182\
35019f90b9f8ee6e75700bcab2f8407525a104799b3e9725e27d738a9045e832
    KO = 51dc4668947e3685099bc3b5f8527468

    [PRF=HMAC_SHA224]
    [CTRLOCATION=AFTER_FIXED]
    [RLEN=8_BITS]

    COUNT=0
    L = 128
    KI = ab56556b107a3a79fe084df0f1bb3ad049a6cc1490f20da4b3df282c
    FixedInputDataByteLen = 60
    FixedInputData = 7f50fc1f77c3ac752443154c1577d3c47b86fccffe82ff43aa1b91ee\
b5730d7e9e6aab78374d854aecb7143faba6b1eb90d3d9e7a2f6d78dd9a6c4a7
        Binary rep of i = 01
        instring = 7f50fc1f77c3ac752443154c1577d3c47b86fccffe82ff43aa1b91eeb5\
730d7e9e6aab78374d854aecb7143faba6b1eb90d3d9e7a2f6d78dd9a6c4a701
    KO = b8894c6133a46701909b5c8a84322dec
    """
    ).splitlines()

    assert load_nist_kbkdf_vectors(vector_data) == [
        {
            "prf": "hmac_sha1",
            "ctrlocation": "before_fixed",
            "rlen": 8,
            "l": 128,
            "ki": b"00a39bd547fb88b2d98727cf64c195c61e1cad6c",
            "fixedinputdatabytelen": b"60",
            "fixedinputdata": (
                b"98132c1ffaf59ae5cbc0a3133d84c551bb97e0c75ecaddfc30056f6876f"
                b"59803009bffc7d75c4ed46f40b8f80426750d15bc1ddb14ac5dcb69a682"
                b"42"
            ),
            "binary rep of i": b"01",
            "instring": (
                b"0198132c1ffaf59ae5cbc0a3133d84c551bb97e0c75ecaddfc30056f687"
                b"6f59803009bffc7d75c4ed46f40b8f80426750d15bc1ddb14ac5dcb69a6"
                b"8242"
            ),
            "ko": b"0611e1903609b47ad7a5fc2c82e47702",
        },
        {
            "prf": "hmac_sha1",
            "ctrlocation": "before_fixed",
            "rlen": 8,
            "l": 128,
            "ki": b"a39bdf744ed7e33fdec060c8736e9725179885a8",
            "fixedinputdatabytelen": b"60",
            "fixedinputdata": (
                b"af71b44940acff98949ad17f1ca20e8fdb3957cacdcd41e9c591e182350"
                b"19f90b9f8ee6e75700bcab2f8407525a104799b3e9725e27d738a9045e8"
                b"32"
            ),
            "binary rep of i": b"01",
            "instring": (
                b"01af71b44940acff98949ad17f1ca20e8fdb3957cacdcd41e9c591e1823"
                b"5019f90b9f8ee6e75700bcab2f8407525a104799b3e9725e27d738a9045"
                b"e832"
            ),
            "ko": b"51dc4668947e3685099bc3b5f8527468",
        },
        {
            "prf": "hmac_sha224",
            "ctrlocation": "after_fixed",
            "rlen": 8,
            "l": 128,
            "ki": b"ab56556b107a3a79fe084df0f1bb3ad049a6cc1490f20da4b3df282c",
            "fixedinputdatabytelen": b"60",
            "fixedinputdata": (
                b"7f50fc1f77c3ac752443154c1577d3c47b86fccffe82ff43aa1b91eeb57"
                b"30d7e9e6aab78374d854aecb7143faba6b1eb90d3d9e7a2f6d78dd9a6c4"
                b"a7"
            ),
            "binary rep of i": b"01",
            "instring": (
                b"7f50fc1f77c3ac752443154c1577d3c47b86fccffe82ff43aa1b91eeb57"
                b"30d7e9e6aab78374d854aecb7143faba6b1eb90d3d9e7a2f6d78dd9a6c4"
                b"a701"
            ),
            "ko": b"b8894c6133a46701909b5c8a84322dec",
        },
    ]


def test_load_nist_ccm_vectors_dvpt():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.0
    #  "CCM-DVPT" information
    #  AES Keylen: 128
    #  Generated on Tue Mar 15 08:09:25 2011


    [Alen = 0, Plen = 0, Nlen = 7, Tlen = 4]

    Key = 4ae701103c63deca5b5a3939d7d05992

    Count = 0
    Nonce = 5a8aa485c316e9
    Adata = 00
    CT = 02209f55
    Result = Pass
    Payload = 00

    Count = 1
    Nonce = 3796cf51b87266
    Adata = 00
    CT = 9a04c241
    Result = Fail

    [Alen = 0, Plen = 0, Nlen = 7, Tlen = 16]

    Key = 4bb3c4a4f893ad8c9bdc833c325d62b3

    Count = 15
    Nonce = 5a8aa485c316e9
    Adata = 00
    CT = 75d582db43ce9b13ab4b6f7f14341330
    Result = Pass
    Payload = 00

    Count = 16
    Nonce = 3796cf51b87266
    Adata = 00
    CT = 3a65e03af37b81d05acc7ec1bc39deb0
    Result = Fail
    """
    ).splitlines()
    assert load_nist_ccm_vectors(vector_data) == [
        {
            "key": b"4ae701103c63deca5b5a3939d7d05992",
            "alen": 0,
            "plen": 0,
            "nlen": 7,
            "tlen": 4,
            "nonce": b"5a8aa485c316e9",
            "adata": b"00",
            "ct": b"02209f55",
            "fail": False,
            "payload": b"00",
        },
        {
            "key": b"4ae701103c63deca5b5a3939d7d05992",
            "alen": 0,
            "plen": 0,
            "nlen": 7,
            "tlen": 4,
            "nonce": b"3796cf51b87266",
            "adata": b"00",
            "ct": b"9a04c241",
            "fail": True,
            "payload": b"00",
        },
        {
            "key": b"4bb3c4a4f893ad8c9bdc833c325d62b3",
            "alen": 0,
            "plen": 0,
            "nlen": 7,
            "tlen": 16,
            "nonce": b"5a8aa485c316e9",
            "adata": b"00",
            "ct": b"75d582db43ce9b13ab4b6f7f14341330",
            "fail": False,
            "payload": b"00",
        },
        {
            "key": b"4bb3c4a4f893ad8c9bdc833c325d62b3",
            "alen": 0,
            "plen": 0,
            "nlen": 7,
            "tlen": 16,
            "nonce": b"3796cf51b87266",
            "adata": b"00",
            "ct": b"3a65e03af37b81d05acc7ec1bc39deb0",
            "fail": True,
            "payload": b"00",
        },
    ]


def test_load_nist_ccm_vectors_vadt():
    vector_data = textwrap.dedent(
        """
    #  CAVS 11.0
    #  "CCM-VADT" information
    #  AES Keylen: 128
    #  Generated on Tue Mar 15 08:09:24 2011

    Plen = 24
    Nlen = 13
    Tlen = 16

    [Alen = 0]

    Key = d24a3d3dde8c84830280cb87abad0bb3
    Nonce = f1100035bb24a8d26004e0e24b

    Count = 0
    Adata = 00
    Payload = 7c86135ed9c2a515aaae0e9a208133897269220f30870006
    CT = 1faeb0ee2ca2cd52f0aa3966578344f24e69b742c4ab37ab11233

    Count = 1
    Adata = 00
    Payload = 48df73208cdc63d716752df7794807b1b2a80794a2433455
    CT = 2bf7d09079bc0b904c711a0b0e4a70ca8ea892d9566f03f8b77a1
    CT = 642145210f947bc4a0b1e678fd8c990c2c1d89d4110a95c954d61

    [Alen = 1]

    Key = 08b0da255d2083808a1b4d367090bacc
    Nonce = 777828b13679a9e2ca89568233

    Count = 10
    Adata = dd
    Payload = 1b156d7e2bf7c9a25ad91cff7b0b02161cb78ff9162286b0
    CT = e8b80af4960d5417c15726406e345c5c46831192b03432eed16b6

    Count = 11
    Adata = c5
    Payload = 032fee9dbffccc751e6a1ee6d07bb218b3a7ec6bf5740ead
    CT = f0828917020651c085e42459c544ec52e99372005362baf308ebe
    """
    ).splitlines()
    assert load_nist_ccm_vectors(vector_data) == [
        {
            "plen": 24,
            "nlen": 13,
            "tlen": 16,
            "alen": 0,
            "key": b"d24a3d3dde8c84830280cb87abad0bb3",
            "nonce": b"f1100035bb24a8d26004e0e24b",
            "adata": b"00",
            "payload": b"7c86135ed9c2a515aaae0e9a208133897269220f30870006",
            "ct": b"1faeb0ee2ca2cd52f0aa3966578344f24e69b742c4ab37ab11233",
        },
        {
            "plen": 24,
            "nlen": 13,
            "tlen": 16,
            "alen": 0,
            "key": b"d24a3d3dde8c84830280cb87abad0bb3",
            "nonce": b"f1100035bb24a8d26004e0e24b",
            "adata": b"00",
            "payload": b"48df73208cdc63d716752df7794807b1b2a80794a2433455",
            "ct": b"642145210f947bc4a0b1e678fd8c990c2c1d89d4110a95c954d61",
        },
        {
            "plen": 24,
            "nlen": 13,
            "tlen": 16,
            "alen": 1,
            "key": b"08b0da255d2083808a1b4d367090bacc",
            "nonce": b"777828b13679a9e2ca89568233",
            "adata": b"dd",
            "payload": b"1b156d7e2bf7c9a25ad91cff7b0b02161cb78ff9162286b0",
            "ct": b"e8b80af4960d5417c15726406e345c5c46831192b03432eed16b6",
        },
        {
            "plen": 24,
            "nlen": 13,
            "tlen": 16,
            "alen": 1,
            "key": b"08b0da255d2083808a1b4d367090bacc",
            "nonce": b"777828b13679a9e2ca89568233",
            "adata": b"c5",
            "payload": b"032fee9dbffccc751e6a1ee6d07bb218b3a7ec6bf5740ead",
            "ct": b"f0828917020651c085e42459c544ec52e99372005362baf308ebe",
        },
    ]


def test_vector_version():
    assert cryptography.__version__ == cryptography_vectors.__version__


def test_raises_unsupported_algorithm_wrong_type():
    # Check that it raises if the wrong type of exception is raised.
    class TestException(Exception):
        pass

    with pytest.raises(TestException):
        with raises_unsupported_algorithm(None):
            raise TestException


def test_raises_unsupported_algorithm_wrong_reason():
    # Check that it fails if the wrong reason code is raised.
    with pytest.raises(AssertionError):
        with raises_unsupported_algorithm(None):
            raise UnsupportedAlgorithm(
                "An error.", _Reasons.BACKEND_MISSING_INTERFACE
            )


def test_raises_unsupported_no_exc():
    # Check that it fails if no exception is raised.
    with pytest.raises(pytest.fail.Exception):
        with raises_unsupported_algorithm(_Reasons.BACKEND_MISSING_INTERFACE):
            pass


def test_raises_unsupported_algorithm():
    # Check that it doesn't assert if the right things are raised.
    with raises_unsupported_algorithm(
        _Reasons.BACKEND_MISSING_INTERFACE
    ) as exc_info:
        raise UnsupportedAlgorithm(
            "An error.", _Reasons.BACKEND_MISSING_INTERFACE
        )
    assert exc_info.type is UnsupportedAlgorithm


class TestDeprecated:
    def test_getattr(self):
        with pytest.warns(DeprecationWarning):
            assert deprecated_module.DEPRECATED == 3

        assert deprecated_module.NOT_DEPRECATED == 12

    def test_inspect_deprecated_module(self):
        # Check if inspection is supported by _ModuleWithDeprecations.
        assert isinstance(
            deprecated_module, cryptography.utils._ModuleWithDeprecations
        )
        source_file = inspect.getsourcefile(deprecated_module)
        assert isinstance(source_file, str)
        assert source_file.endswith("deprecated_module.py")
