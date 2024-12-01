# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.


import binascii
import collections
import json
import os
import re
import typing
from contextlib import contextmanager

import pytest

import cryptography_vectors
from cryptography.exceptions import UnsupportedAlgorithm

HashVector = collections.namedtuple("HashVector", ["message", "digest"])
KeyedHashVector = collections.namedtuple(
    "KeyedHashVector", ["message", "digest", "key"]
)


def check_backend_support(backend, item):
    for mark in item.node.iter_markers("supported"):
        if not mark.kwargs["only_if"](backend):
            pytest.skip("{} ({})".format(mark.kwargs["skip_message"], backend))


@contextmanager
def raises_unsupported_algorithm(reason):
    with pytest.raises(UnsupportedAlgorithm) as exc_info:
        yield exc_info

    assert exc_info.value._reason == reason


T = typing.TypeVar("T")


def load_vectors_from_file(
    filename, loader: typing.Callable[..., T], mode="r"
) -> T:
    with cryptography_vectors.open_vector_file(filename, mode) as vector_file:
        return loader(vector_file)


def load_nist_vectors(vector_data):
    test_data = {}
    data = []

    for line in vector_data:
        line = line.strip()

        # Blank lines, comments, and section headers are ignored
        if (
            not line
            or line.startswith("#")
            or (line.startswith("[") and line.endswith("]"))
        ):
            continue

        if line.strip() == "FAIL":
            test_data["fail"] = True
            continue

        # Build our data using a simple Key = Value format
        name, value = (c.strip() for c in line.split("="))

        # Some tests (PBKDF2) contain \0, which should be interpreted as a
        # null character rather than literal.
        value = value.replace("\\0", "\0")

        # COUNT is a special token that indicates a new block of data
        if name.upper() == "COUNT":
            test_data = {}
            data.append(test_data)
            continue
        # For all other tokens we simply want the name, value stored in
        # the dictionary
        else:
            test_data[name.lower()] = value.encode("ascii")

    return data


def load_cryptrec_vectors(vector_data):
    cryptrec_list = []

    for line in vector_data:
        line = line.strip()

        # Blank lines and comments are ignored
        if not line or line.startswith("#"):
            continue

        if line.startswith("K"):
            key = line.split(" : ")[1].replace(" ", "").encode("ascii")
        elif line.startswith("P"):
            pt = line.split(" : ")[1].replace(" ", "").encode("ascii")
        elif line.startswith("C"):
            ct = line.split(" : ")[1].replace(" ", "").encode("ascii")
            # after a C is found the K+P+C tuple is complete
            # there are many P+C pairs for each K
            cryptrec_list.append(
                {"key": key, "plaintext": pt, "ciphertext": ct}
            )
        else:
            raise ValueError(f"Invalid line in file '{line}'")
    return cryptrec_list


def load_hash_vectors(vector_data):
    vectors: typing.List[typing.Union[KeyedHashVector, HashVector]] = []
    key = None
    msg = None
    md = None

    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#") or line.startswith("["):
            continue

        if line.startswith("Len"):
            length = int(line.split(" = ")[1])
        elif line.startswith("Key"):
            # HMAC vectors contain a key attribute. Hash vectors do not.
            key = line.split(" = ")[1].encode("ascii")
        elif line.startswith("Msg"):
            # In the NIST vectors they have chosen to represent an empty
            # string as hex 00, which is of course not actually an empty
            # string. So we parse the provided length and catch this edge case.
            msg = line.split(" = ")[1].encode("ascii") if length > 0 else b""
        elif line.startswith("MD") or line.startswith("Output"):
            md = line.split(" = ")[1]
            # after MD is found the Msg+MD (+ potential key) tuple is complete
            if key is not None:
                vectors.append(KeyedHashVector(msg, md, key))
                key = None
                msg = None
                md = None
            else:
                vectors.append(HashVector(msg, md))
                msg = None
                md = None
        else:
            raise ValueError("Unknown line in hash vector")
    return vectors


def load_pkcs1_vectors(vector_data):
    """
    Loads data out of RSA PKCS #1 vector files.
    """
    private_key_vector: typing.Optional[typing.Dict[str, typing.Any]] = None
    public_key_vector: typing.Optional[typing.Dict[str, typing.Any]] = None
    attr = None
    key: typing.Any = None
    example_vector: typing.Optional[typing.Dict[str, typing.Any]] = None
    examples = []
    vectors = []
    for line in vector_data:
        if (
            line.startswith("# PSS Example")
            or line.startswith("# OAEP Example")
            or line.startswith("# PKCS#1 v1.5")
        ):
            if example_vector:
                for key, value in example_vector.items():
                    hex_bytes = "".join(value).replace(" ", "").encode("ascii")
                    example_vector[key] = hex_bytes
                examples.append(example_vector)

            attr = None
            example_vector = collections.defaultdict(list)

        if line.startswith("# Message"):
            attr = "message"
            continue
        elif line.startswith("# Salt"):
            attr = "salt"
            continue
        elif line.startswith("# Seed"):
            attr = "seed"
            continue
        elif line.startswith("# Signature"):
            attr = "signature"
            continue
        elif line.startswith("# Encryption"):
            attr = "encryption"
            continue
        elif example_vector and line.startswith(
            "# ============================================="
        ):
            for key, value in example_vector.items():
                hex_bytes = "".join(value).replace(" ", "").encode("ascii")
                example_vector[key] = hex_bytes
            examples.append(example_vector)
            example_vector = None
            attr = None
        elif example_vector and line.startswith("#"):
            continue
        else:
            if attr is not None and example_vector is not None:
                example_vector[attr].append(line.strip())
                continue

        if line.startswith("# Example") or line.startswith(
            "# ============================================="
        ):
            if key:
                assert private_key_vector
                assert public_key_vector

                for key, value in public_key_vector.items():
                    hex_str = "".join(value).replace(" ", "")
                    public_key_vector[key] = int(hex_str, 16)

                for key, value in private_key_vector.items():
                    hex_str = "".join(value).replace(" ", "")
                    private_key_vector[key] = int(hex_str, 16)

                private_key_vector["examples"] = examples
                examples = []

                assert (
                    private_key_vector["public_exponent"]
                    == public_key_vector["public_exponent"]
                )

                assert (
                    private_key_vector["modulus"]
                    == public_key_vector["modulus"]
                )

                vectors.append((private_key_vector, public_key_vector))

            public_key_vector = collections.defaultdict(list)
            private_key_vector = collections.defaultdict(list)
            key = None
            attr = None

        if private_key_vector is None or public_key_vector is None:
            continue

        if line.startswith("# Private key"):
            key = private_key_vector
        elif line.startswith("# Public key"):
            key = public_key_vector
        elif line.startswith("# Modulus:"):
            attr = "modulus"
        elif line.startswith("# Public exponent:"):
            attr = "public_exponent"
        elif line.startswith("# Exponent:"):
            if key is public_key_vector:
                attr = "public_exponent"
            else:
                assert key is private_key_vector
                attr = "private_exponent"
        elif line.startswith("# Prime 1:"):
            attr = "p"
        elif line.startswith("# Prime 2:"):
            attr = "q"
        elif line.startswith("# Prime exponent 1:"):
            attr = "dmp1"
        elif line.startswith("# Prime exponent 2:"):
            attr = "dmq1"
        elif line.startswith("# Coefficient:"):
            attr = "iqmp"
        elif line.startswith("#"):
            attr = None
        else:
            if key is not None and attr is not None:
                key[attr].append(line.strip())
    return vectors


def load_rsa_nist_vectors(vector_data):
    test_data: typing.Dict[str, typing.Any] = {}
    p = None
    salt_length = None
    data = []

    for line in vector_data:
        line = line.strip()

        # Blank lines and section headers are ignored
        if not line or line.startswith("["):
            continue

        if line.startswith("# Salt len:"):
            salt_length = int(line.split(":")[1].strip())
            continue
        elif line.startswith("#"):
            continue

        # Build our data using a simple Key = Value format
        name, value = (c.strip() for c in line.split("="))

        if name == "n":
            n = int(value, 16)
        elif name == "e" and p is None:
            e = int(value, 16)
        elif name == "p":
            p = int(value, 16)
        elif name == "q":
            q = int(value, 16)
        elif name == "SHAAlg":
            if p is None:
                test_data = {
                    "modulus": n,
                    "public_exponent": e,
                    "salt_length": salt_length,
                    "algorithm": value,
                    "fail": False,
                }
            else:
                test_data = {"modulus": n, "p": p, "q": q, "algorithm": value}
                if salt_length is not None:
                    test_data["salt_length"] = salt_length
            data.append(test_data)
        elif name == "e" and p is not None:
            test_data["public_exponent"] = int(value, 16)
        elif name == "d":
            test_data["private_exponent"] = int(value, 16)
        elif name == "Result":
            test_data["fail"] = value.startswith("F")
        # For all other tokens we simply want the name, value stored in
        # the dictionary
        else:
            test_data[name.lower()] = value.encode("ascii")

    return data


def load_fips_dsa_key_pair_vectors(vector_data):
    """
    Loads data out of the FIPS DSA KeyPair vector files.
    """
    vectors = []
    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#") or line.startswith("[mod"):
            continue

        if line.startswith("P"):
            vectors.append({"p": int(line.split("=")[1], 16)})
        elif line.startswith("Q"):
            vectors[-1]["q"] = int(line.split("=")[1], 16)
        elif line.startswith("G"):
            vectors[-1]["g"] = int(line.split("=")[1], 16)
        elif line.startswith("X") and "x" not in vectors[-1]:
            vectors[-1]["x"] = int(line.split("=")[1], 16)
        elif line.startswith("X") and "x" in vectors[-1]:
            vectors.append(
                {
                    "p": vectors[-1]["p"],
                    "q": vectors[-1]["q"],
                    "g": vectors[-1]["g"],
                    "x": int(line.split("=")[1], 16),
                }
            )
        elif line.startswith("Y"):
            vectors[-1]["y"] = int(line.split("=")[1], 16)

    return vectors


FIPS_SHA_REGEX = re.compile(
    r"\[mod = L=...., N=..., SHA-(?P<sha>1|224|256|384|512)\]"
)


def load_fips_dsa_sig_vectors(vector_data):
    """
    Loads data out of the FIPS DSA SigVer vector files.
    """
    vectors = []

    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        sha_match = FIPS_SHA_REGEX.match(line)
        if sha_match:
            digest_algorithm = "SHA-{}".format(sha_match.group("sha"))

        if line.startswith("[mod"):
            continue

        name, value = (c.strip() for c in line.split("="))

        if name == "P":
            vectors.append(
                {"p": int(value, 16), "digest_algorithm": digest_algorithm}
            )
        elif name == "Q":
            vectors[-1]["q"] = int(value, 16)
        elif name == "G":
            vectors[-1]["g"] = int(value, 16)
        elif name == "Msg" and "msg" not in vectors[-1]:
            hexmsg = value.strip().encode("ascii")
            vectors[-1]["msg"] = binascii.unhexlify(hexmsg)
        elif name == "Msg" and "msg" in vectors[-1]:
            hexmsg = value.strip().encode("ascii")
            vectors.append(
                {
                    "p": vectors[-1]["p"],
                    "q": vectors[-1]["q"],
                    "g": vectors[-1]["g"],
                    "digest_algorithm": vectors[-1]["digest_algorithm"],
                    "msg": binascii.unhexlify(hexmsg),
                }
            )
        elif name == "X":
            vectors[-1]["x"] = int(value, 16)
        elif name == "Y":
            vectors[-1]["y"] = int(value, 16)
        elif name == "R":
            vectors[-1]["r"] = int(value, 16)
        elif name == "S":
            vectors[-1]["s"] = int(value, 16)
        elif name == "Result":
            vectors[-1]["result"] = value.split("(")[0].strip()

    return vectors


# https://tools.ietf.org/html/rfc4492#appendix-A
_ECDSA_CURVE_NAMES = {
    "P-192": "secp192r1",
    "P-224": "secp224r1",
    "P-256": "secp256r1",
    "P-384": "secp384r1",
    "P-521": "secp521r1",
    "K-163": "sect163k1",
    "K-233": "sect233k1",
    "K-256": "secp256k1",
    "K-283": "sect283k1",
    "K-409": "sect409k1",
    "K-571": "sect571k1",
    "B-163": "sect163r2",
    "B-233": "sect233r1",
    "B-283": "sect283r1",
    "B-409": "sect409r1",
    "B-571": "sect571r1",
}


def load_fips_ecdsa_key_pair_vectors(vector_data):
    """
    Loads data out of the FIPS ECDSA KeyPair vector files.
    """
    vectors = []
    key_data = None
    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line[1:-1] in _ECDSA_CURVE_NAMES:
            curve_name = _ECDSA_CURVE_NAMES[line[1:-1]]

        elif line.startswith("d = "):
            if key_data is not None:
                vectors.append(key_data)

            key_data = {"curve": curve_name, "d": int(line.split("=")[1], 16)}

        elif key_data is not None:
            if line.startswith("Qx = "):
                key_data["x"] = int(line.split("=")[1], 16)
            elif line.startswith("Qy = "):
                key_data["y"] = int(line.split("=")[1], 16)

    assert key_data is not None
    vectors.append(key_data)

    return vectors


CURVE_REGEX = re.compile(
    r"\[(?P<curve>[PKB]-[0-9]{3}),SHA-(?P<sha>1|224|256|384|512)\]"
)


def load_fips_ecdsa_signing_vectors(vector_data):
    """
    Loads data out of the FIPS ECDSA SigGen vector files.
    """
    vectors = []

    data: typing.Optional[typing.Dict[str, object]] = None
    for line in vector_data:
        line = line.strip()

        curve_match = CURVE_REGEX.match(line)
        if curve_match:
            curve_name = _ECDSA_CURVE_NAMES[curve_match.group("curve")]
            digest_name = "SHA-{}".format(curve_match.group("sha"))

        elif line.startswith("Msg = "):
            if data is not None:
                vectors.append(data)

            hexmsg = line.split("=")[1].strip().encode("ascii")

            data = {
                "curve": curve_name,
                "digest_algorithm": digest_name,
                "message": binascii.unhexlify(hexmsg),
            }

        elif data is not None:
            if line.startswith("Qx = "):
                data["x"] = int(line.split("=")[1], 16)
            elif line.startswith("Qy = "):
                data["y"] = int(line.split("=")[1], 16)
            elif line.startswith("R = "):
                data["r"] = int(line.split("=")[1], 16)
            elif line.startswith("S = "):
                data["s"] = int(line.split("=")[1], 16)
            elif line.startswith("d = "):
                data["d"] = int(line.split("=")[1], 16)
            elif line.startswith("Result = "):
                data["fail"] = line.split("=")[1].strip()[0] == "F"

    assert data is not None
    vectors.append(data)
    return vectors


KASVS_RESULT_REGEX = re.compile(r"([FP]) \(([0-9]+) -")


def load_kasvs_dh_vectors(vector_data):
    """
    Loads data out of the KASVS key exchange vector data
    """

    vectors = []
    data: typing.Dict[str, typing.Any] = {"fail_z": False, "fail_agree": False}

    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("P = "):
            data["p"] = int(line.split("=")[1], 16)
        elif line.startswith("Q = "):
            data["q"] = int(line.split("=")[1], 16)
        elif line.startswith("G = "):
            data["g"] = int(line.split("=")[1], 16)
        elif line.startswith("Z = "):
            z_hex = line.split("=")[1].strip().encode("ascii")
            data["z"] = binascii.unhexlify(z_hex)
        elif line.startswith("XstatCAVS = "):
            data["x1"] = int(line.split("=")[1], 16)
        elif line.startswith("YstatCAVS = "):
            data["y1"] = int(line.split("=")[1], 16)
        elif line.startswith("XstatIUT = "):
            data["x2"] = int(line.split("=")[1], 16)
        elif line.startswith("YstatIUT = "):
            data["y2"] = int(line.split("=")[1], 16)
        elif line.startswith("Result = "):
            result_str = line.split("=")[1].strip()
            match = KASVS_RESULT_REGEX.match(result_str)
            assert match is not None

            if match.group(1) == "F":
                if int(match.group(2)) in (5, 10):
                    data["fail_z"] = True
                else:
                    data["fail_agree"] = True

            vectors.append(data)

            data = {
                "p": data["p"],
                "q": data["q"],
                "g": data["g"],
                "fail_z": False,
                "fail_agree": False,
            }

    return vectors


def load_kasvs_ecdh_vectors(vector_data):
    """
    Loads data out of the KASVS key exchange vector data
    """

    curve_name_map = {
        "P-192": "secp192r1",
        "P-224": "secp224r1",
        "P-256": "secp256r1",
        "P-384": "secp384r1",
        "P-521": "secp521r1",
    }

    tags = []
    sets = {}
    vectors = []

    # find info in header
    for line in vector_data:
        line = line.strip()

        if line.startswith("#"):
            parm = line.split("Parameter set(s) supported:")
            if len(parm) == 2:
                names = parm[1].strip().split()
                for n in names:
                    tags.append(f"[{n}]")
                break

    # Sets Metadata
    tag = None
    curve = None
    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line in tags:
            tag = line
            curve = None
        elif line.startswith("[Curve selected:"):
            curve = curve_name_map[line.split(":")[1].strip()[:-1]]

        if tag is not None and curve is not None:
            sets[tag.strip("[]")] = curve
            tag = None
        if len(tags) == len(sets):
            break

    # Data
    data: typing.Dict[str, typing.Any] = {
        "CAVS": {},
        "IUT": {},
    }
    tag = None
    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("["):
            tag = line.split()[0][1:]
        elif line.startswith("COUNT = "):
            data["COUNT"] = int(line.split("=")[1])
        elif line.startswith("dsCAVS = "):
            data["CAVS"]["d"] = int(line.split("=")[1], 16)
        elif line.startswith("QsCAVSx = "):
            data["CAVS"]["x"] = int(line.split("=")[1], 16)
        elif line.startswith("QsCAVSy = "):
            data["CAVS"]["y"] = int(line.split("=")[1], 16)
        elif line.startswith("dsIUT = "):
            data["IUT"]["d"] = int(line.split("=")[1], 16)
        elif line.startswith("QsIUTx = "):
            data["IUT"]["x"] = int(line.split("=")[1], 16)
        elif line.startswith("QsIUTy = "):
            data["IUT"]["y"] = int(line.split("=")[1], 16)
        elif line.startswith("OI = "):
            data["OI"] = int(line.split("=")[1], 16)
        elif line.startswith("Z = "):
            data["Z"] = int(line.split("=")[1], 16)
        elif line.startswith("DKM = "):
            data["DKM"] = int(line.split("=")[1], 16)
        elif line.startswith("Result = "):
            result_str = line.split("=")[1].strip()
            match = KASVS_RESULT_REGEX.match(result_str)
            assert match is not None

            if match.group(1) == "F":
                data["fail"] = True
            else:
                data["fail"] = False
            data["errno"] = int(match.group(2))

            data["curve"] = sets[tag]

            vectors.append(data)

            data = {
                "CAVS": {},
                "IUT": {},
            }

    return vectors


def load_rfc6979_vectors(vector_data):
    """
    Loads data out of the ECDSA and DSA RFC6979 vector files.
    """
    vectors = []
    keys: typing.Dict[str, typing.List[str]] = dict()
    reading_key = False
    current_key_name = None

    data: typing.Dict[str, object] = dict()
    for line in vector_data:
        line = line.strip()

        if reading_key and current_key_name:
            keys[current_key_name].append(line)
            if line.startswith("-----END"):
                reading_key = False
                current_key_name = None

        if line.startswith("PrivateKey=") or line.startswith("PublicKey="):
            reading_key = True
            current_key_name = line.split("=")[1].strip()
            keys[current_key_name] = []
        elif line.startswith("DigestSign = "):
            data["digest_sign"] = line.split("=")[1].strip()
            data["deterministic_nonce"] = False
        elif line.startswith("DigestVerify = "):
            data["digest_verify"] = line.split("=")[1].strip()
            data["verify_error"] = False
        elif line.startswith("Key = "):
            key_name = line.split("=")[1].strip()
            assert key_name in keys
            data["key"] = keys[key_name]
            data["key_name"] = key_name
        elif line.startswith("NonceType = "):
            nonce_type = line.split("=")[1].strip()
            data["deterministic_nonce"] = nonce_type == "deterministic"
        elif line.startswith("Input = "):
            data["input"] = line.split("=")[1].strip(' "')
        elif line.startswith("Output = "):
            data["output"] = line.split("=")[1].strip()
        elif line.startswith("Result = "):
            data["verify_error"] = line.split("=")[1].strip() == "VERIFY_ERROR"

        elif not line:
            if data:
                vectors.append(data)
                data = {}

    return vectors


def load_x963_vectors(vector_data):
    """
    Loads data out of the X9.63 vector data
    """

    vectors = []

    # Sets Metadata
    hashname = None
    vector = {}
    for line in vector_data:
        line = line.strip()

        if line.startswith("[SHA"):
            hashname = line[1:-1]
            shared_secret_len = 0
            shared_info_len = 0
            key_data_len = 0
        elif line.startswith("[shared secret length"):
            shared_secret_len = int(line[1:-1].split("=")[1].strip())
        elif line.startswith("[SharedInfo length"):
            shared_info_len = int(line[1:-1].split("=")[1].strip())
        elif line.startswith("[key data length"):
            key_data_len = int(line[1:-1].split("=")[1].strip())
        elif line.startswith("COUNT"):
            count = int(line.split("=")[1].strip())
            vector["hash"] = hashname
            vector["count"] = count
            vector["shared_secret_length"] = shared_secret_len
            vector["sharedinfo_length"] = shared_info_len
            vector["key_data_length"] = key_data_len
        elif line.startswith("Z"):
            vector["Z"] = line.split("=")[1].strip()
            assert vector["Z"] is not None
            assert ((shared_secret_len + 7) // 8) * 2 == len(vector["Z"])
        elif line.startswith("SharedInfo"):
            if shared_info_len != 0:
                vector["sharedinfo"] = line.split("=")[1].strip()
                assert vector["sharedinfo"] is not None
                silen = len(vector["sharedinfo"])
                assert ((shared_info_len + 7) // 8) * 2 == silen
        elif line.startswith("key_data"):
            vector["key_data"] = line.split("=")[1].strip()
            assert vector["key_data"] is not None
            assert ((key_data_len + 7) // 8) * 2 == len(vector["key_data"])
            vectors.append(vector)
            vector = {}

    return vectors


def load_nist_kbkdf_vectors(vector_data):
    """
    Load NIST SP 800-108 KDF Vectors
    """
    vectors = []
    test_data = None
    tag = {}

    for line in vector_data:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):
            tag_data = line[1:-1]
            name, value = (c.strip() for c in tag_data.split("="))
            if value.endswith("_BITS"):
                value = int(value.split("_")[0])
                tag.update({name.lower(): value})
                continue

            tag.update({name.lower(): value.lower()})
        elif line.startswith("COUNT="):
            test_data = {}
            test_data.update(tag)
            vectors.append(test_data)
        elif line.startswith(("L", "DataBeforeCtrLen", "DataAfterCtrLen")):
            name, value = (c.strip() for c in line.split("="))
            test_data[name.lower()] = int(value)
        else:
            name, value = (c.strip() for c in line.split("="))
            test_data[name.lower()] = value.encode("ascii")

    return vectors


def load_ed25519_vectors(vector_data):
    data = []
    for line in vector_data:
        secret_key, public_key, message, signature, _ = line.split(":")
        # In the vectors the first element is secret key + public key
        secret_key = secret_key[0:64]
        # In the vectors the signature section is signature + message
        signature = signature[0:128]
        data.append(
            {
                "secret_key": secret_key,
                "public_key": public_key,
                "message": message,
                "signature": signature,
            }
        )
    return data


def load_nist_ccm_vectors(vector_data):
    test_data = {}
    section_data = None
    global_data = {}
    new_section = False
    data = []

    for line in vector_data:
        line = line.strip()

        # Blank lines and comments should be ignored
        if not line or line.startswith("#"):
            continue

        # Some of the CCM vectors have global values for this. They are always
        # at the top before the first section header (see: VADT, VNT, VPT)
        if line.startswith(("Alen", "Plen", "Nlen", "Tlen")):
            name, value = (c.strip() for c in line.split("="))
            global_data[name.lower()] = int(value)
            continue

        # section headers contain length data we might care about
        if line.startswith("["):
            new_section = True
            section_data = {}
            section = line[1:-1]
            items = [c.strip() for c in section.split(",")]
            for item in items:
                name, value = (c.strip() for c in item.split("="))
                section_data[name.lower()] = int(value)
            continue

        name, value = (c.strip() for c in line.split("="))

        if name.lower() in ("key", "nonce") and new_section:
            section_data[name.lower()] = value.encode("ascii")
            continue

        new_section = False

        # Payload is sometimes special because these vectors are absurd. Each
        # example may or may not have a payload. If it does not then the
        # previous example's payload should be used. We accomplish this by
        # writing it into the section_data. Because we update each example
        # with the section data it will be overwritten if a new payload value
        # is present. NIST should be ashamed of their vector creation.
        if name.lower() == "payload":
            section_data[name.lower()] = value.encode("ascii")

        # Result is a special token telling us if the test should pass/fail.
        # This is only present in the DVPT CCM tests
        if name.lower() == "result":
            if value.lower() == "pass":
                test_data["fail"] = False
            else:
                test_data["fail"] = True
            continue

        # COUNT is a special token that indicates a new block of data
        if name.lower() == "count":
            test_data = {}
            test_data.update(global_data)
            test_data.update(section_data)
            data.append(test_data)
            continue
        # For all other tokens we simply want the name, value stored in
        # the dictionary
        else:
            test_data[name.lower()] = value.encode("ascii")

    return data


class WycheproofTest:
    def __init__(self, testfiledata, testgroup, testcase):
        self.testfiledata = testfiledata
        self.testgroup = testgroup
        self.testcase = testcase

    def __repr__(self):
        return "<WycheproofTest({!r}, {!r}, {!r}, tcId={})>".format(
            self.testfiledata,
            self.testgroup,
            self.testcase,
            self.testcase["tcId"],
        )

    @property
    def valid(self) -> bool:
        return self.testcase["result"] == "valid"

    @property
    def acceptable(self) -> bool:
        return self.testcase["result"] == "acceptable"

    @property
    def invalid(self) -> bool:
        return self.testcase["result"] == "invalid"

    def has_flag(self, flag: str) -> bool:
        return flag in self.testcase["flags"]

    def cache_value_to_group(self, cache_key: str, func):
        cache_val = self.testgroup.get(cache_key)
        if cache_val is not None:
            return cache_val
        self.testgroup[cache_key] = cache_val = func()
        return cache_val


def load_wycheproof_tests(wycheproof, test_file, subdir):
    path = os.path.join(wycheproof, subdir, test_file)
    with open(path) as f:
        data = json.load(f)
        for group in data.pop("testGroups"):
            cases = group.pop("tests")
            for c in cases:
                yield WycheproofTest(data, group, c)
