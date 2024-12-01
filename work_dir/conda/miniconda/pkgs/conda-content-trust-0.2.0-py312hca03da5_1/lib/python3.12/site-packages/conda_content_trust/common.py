# Copyright (C) 2019 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
This module contains functions that provide format validation, serialization,
and some key transformations for the pyca/cryptography library.  These are used
across conda_content_trust modules.

Function Manifest for this Module, by Category

Encoding:
  x  canonserialize

Formats and Validation:
     PrivateKey  -- extends cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey
     PublicKey   -- extends cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey
     checkformat_string
  x  is_hex_string
  x  is_hex_signature
  r  is_hex_key
  r  checkformat_hex_key
  r  checkformat_list_of_hex_keys
  x  is_signable
  x  checkformat_byteslike
  x  checkformat_natural_int
  x  checkformat_expiration_distance
  x  checkformat_utc_isoformat
  x  checkformat_gpg_fingerprint
     is_gpg_fingerprint
  x  checkformat_gpg_signature
     is_gpg_signature
     checkformat_any_signature
     checkformat_delegation
     checkformat_delegations
     checkformat_delegating_metadata
  x  iso8601_time_plus_delta

Crypto Utility:
   x sha512256
   x keyfiles_to_keys
   x keyfiles_to_bytes

Exceptions:
    CCT_Error
        SignatureError
        MetadataVerificationError
        UnknownRoleError
"""
from __future__ import annotations

from binascii import hexlify, unhexlify
from datetime import datetime, timedelta
from json import dumps, load
from typing import Any, Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

# specification version for the metadata produced by conda-content-trust
# Details in the Conda Security Metadata Specification.  Note that this
# version string is parsed via setuptools's packaging.version library, and so
# supports PEP 440; however, we should use a limited subset that is numerical
# only, and according to SemVer principles.
# PEP 440 compatibility:
#   > None is not re.match(r'^([1-9]\d*!)?(0|[1-9]\d*)(\.(0|[1-9]\d*))*((a|b|rc)(0|[1-9]\d*))?(\.post(0|[1-9]\d*))?(\.dev(0|[1-9]\d*))?$', version_string)
# SemVer compatibility:
#   > None is not re.match(r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$', version_string)
# Try, however, to keep to three simple numeric elements separated by periods,
# i.e., things that match this subset of SemVer:
#   > None is not re.match(r'^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$', version_string)
SECURITY_METADATA_SPEC_VERSION = "0.6.0"

# The only types we're allowed to wrap as "signables" and sign are
# the JSON-serializable types.  (There are further constraints to what is
# JSON-serializable in addition to these type constraints.)
SUPPORTED_SERIALIZABLE_TYPES = [dict, list, tuple, str, int, float, bool, type(None)]

# These are the permissible strings in the "type" field of delegating metadata.
SUPPORTED_DELEGATING_METADATA_TYPES = ["root", "key_mgr"]  # May be loosened later.


class CCT_Error(Exception):
    """
    All errors we raise that are not ValueErrors, TypeErrors, or
    certain errors from securesystemslib should be instances of this class or
    of subclasses of this class.
    """


class SignatureError(CCT_Error):
    """
    Indicates that a signable cannot be verified due to issues with the
    signature(s) inside it.
    """


class MetadataVerificationError(CCT_Error):
    """
    Indicates that a chain of authority metadata cannot be verified (e.g.
    a metadata update is found on the repository, but could not be
    authenticated).
    """


class UnknownRoleError(CCT_Error):
    """
    Indicates that a piece of role metadata (like root.json, or key_mgr.json)
    was expected but not found.
    """


def canonserialize(obj):
    """
    Given a JSON-compatible object, does the following:
     - serializes the dictionary as utf-8-encoded JSON, lazy-canonicalized
       such that any dictionary keys in any dictionaries inside <dictionary>
       are sorted and indentation is used and set to 2 spaces (using json lib)

    TODO: ✅ Implement the serialization checks from serialization document.

    Note that if the provided object includes a dictionary that is *indexed*
    by both strings and integers, a TypeError will be raised complaining about
    comparing strings and integers during the sort.  (Each dictionary in an
    object must be indexed only by strings or only by integers.)
    """

    # Try converting to a JSON string.
    try:
        # TODO: In the future, assess whether or not to employ more typical
        #       practice of using no whitespace (instead of NLs and 2-indent).
        json_string = dumps(obj, indent=2, sort_keys=True)
    except TypeError:
        # TODO: ✅ Log or craft/use an appropriate exception class.
        raise

    return json_string.encode("utf-8")


def load_metadata_from_file(fname):
    # TODO ✅: Argument validation for fname.  Consider adding "pathvalidate"
    #          as a dependency, and calling its sanitize_filename() here.

    with open(fname, "rb") as fobj:
        metadata = load(fobj)

    # TODO ✅: Consider validating what is read here, for everywhere.

    return metadata


def write_metadata_to_file(metadata, filename):
    """
    Canonicalizes and serializes JSON-friendly metadata, and writes that to the
    given filename.
    """

    # TODO ✅: Argument validation for filename.  Consider adding
    #          "pathvalidate" as a dependency, and calling its
    #          sanitize_filename() here.

    metadata = canonserialize(metadata)

    with open(filename, "wb") as fobj:
        fobj.write(metadata)


class MixinKey:
    """
    This is a mix-in (https://www.ianlewis.org/en/mixins-and-python) for the
    PrivateKey and PublicKey classes, specifically.  It provides some
    convenience functions.
    """

    @classmethod
    def to_hex(cls, key):
        return hexlify(cls.to_bytes(key)).decode("utf-8")

    @classmethod
    def is_equivalent_to(cls, k1, k2):
        """
        Given Ed25519PrivateKey or Ed25519PublicKey objects, determines if the
        underlying key data is identical.
        """
        checkformat_key(k2)
        if type(k1) is not type(k2):
            return False
        return cls.to_bytes(k1) == cls.to_bytes(k2)

    @classmethod  # a class method for inheritors of this mix-in
    def from_hex(cls, key_value_in_hex):
        # from_private_bytes() and from_public_bytes() both check length (32),
        # but do not produce helpful errors if the argument provided it is not
        # the right type, so we'll do that here before calling them.
        checkformat_hex_key(key_value_in_hex)
        key_value_in_bytes = unhexlify(key_value_in_hex)
        new_object = cls.from_bytes(key_value_in_bytes)
        checkformat_key(new_object)
        return new_object


class PrivateKey(MixinKey, ed25519.Ed25519PrivateKey):
    """
    This class expands the class
    cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey
    very slightly, adding some functionality from MixinKey.

    Note on the sign() method:
        We preserve Ed25519PrivateKey's sign method unchanged.  The sign()
        method is deterministic and does not depend at any point on the ability
        to generate random data (unlike the key generation).  The returned
        value for sign() is a length 64 bytes() object, a raw ed25519
        signature.
    """

    @classmethod
    def to_bytes(cls, key):
        return key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

    @classmethod
    def from_bytes(cls, key_value_in_bytes):
        """
        Constructs an object of the class based on the given key value.
        The "cryptography" library provides from_public_bytes() and
        from_private_bytes() class methods for Ed25519PublicKey and
        Ed25519PrivateKey classes in place of constructors.  We extend provide
        a single API for those, and make the created objects objects of the
        subclass using this mix-in.
        """
        # from_private_bytes() and from_public_bytes() both check length (32),
        # but do not produce helpful errors if the argument provided it is not
        # the right type, so we'll do that here before calling them.
        checkformat_byteslike(key_value_in_bytes)
        return super().from_private_bytes(key_value_in_bytes)


class PublicKey(MixinKey, ed25519.Ed25519PublicKey):
    """
    This class expands the class
    cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey
    very slightly, adding some functionality from MixinKey.

    We preserve Ed25519PublicKey's verify() method unchanged.
    """

    @classmethod
    def to_bytes(cls, key):
        """
        Pops out the nice, tidy bytes of a given ed25519 key object, public or
        private.
        """
        return key.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    @classmethod
    def from_bytes(cls, key_value_in_bytes):
        """
        Constructs an object of the class based on the given key value.
        The "cryptography" library provides from_public_bytes() and
        from_private_bytes() class methods for Ed25519PublicKey and
        Ed25519PrivateKey classes in place of constructors.  We extend provide
        a single API for those, and make the created objects objects of the
        subclass using this mix-in.
        """
        # from_private_bytes() and from_public_bytes() both check length (32),
        # but do not produce helpful errors if the argument provided it is not
        # the right type, so we'll do that here before calling them.
        checkformat_byteslike(key_value_in_bytes)
        return super().from_public_bytes(key_value_in_bytes)


# No....  For now, I'll stick with the raw dictionary representations.
# If function profusion makes it inconvenient for folks to use this library,
# it MAY then be time to make signatures into class objects... but it's
# probably best to avoid that potential complexity and confusion.
# class Signature():
#     def __init__(self, ):
#         self.is_gpg_sig = False


# ✅ TODO: Consider a schema definitions module, e.g. PyPI project "schema"
def is_hex_string(hex_string: Any) -> bool:
    """
    Returns True if hex is a hex string with no uppercase characters, no spaces,
    etc.  Else, False.
    """
    try:
        checkformat_hex_string(hex_string)
        return True
    except (ValueError, TypeError):
        return False


HexString = str


def checkformat_hex_string(hex_string: Any) -> HexString:
    """
    Throws TypeError if s is not a string.
    Throws ValueError if the given string is not a string of hexadecimal
    characters (upper-case not allowed to prevent redundancy).
    """
    bytes.fromhex(hex_string)
    # isalnum() checks for no whitespace which bytes.fromhex() would allow.
    if not hex_string.isalnum() or hex_string.lower() != hex_string:
        raise ValueError(
            "Expected a hex string; non-hexadecimal or upper-case character found."
        )

    return hex_string


def is_hex_signature(hex_signature: Any) -> bool:
    """
    Returns True if key is a hex string with no uppercase characters, no
    spaces, no '0x' prefix(es), etc., and is 128 hexadecimal characters (the
    correct length for an ed25519 signature, 64 bytes of raw data represented
    as 128 hexadecimal characters).
    Else, returns False.
    """
    if is_hex_string(hex_signature) and len(hex_signature) == 128:
        return True

    return False


def is_hex_key(hex_key: Any) -> bool:
    """
    Returns True if key is a hex string with no uppercase characters, no
    spaces, no '0x' prefix(es), etc., and is 64 hexadecimal characters (the
    correct length for an ed25519 key, 32 bytes of raw data represented as 64
    hexadecimal characters).
    Else, returns False.
    """
    try:
        checkformat_hex_key(hex_key)
        return True
    except (TypeError, ValueError):
        return False


def is_signable(signable: Any) -> bool:
    """
    Returns True if the given dictionary is a signable dictionary as produced
    by wrap_as_signable.  Note that there MUST be no additional elements beyond
    'signed' and 'signable' in the dictionary.  (The only data in the envelope
    outside the signed portion of the data should be the signatures; what's
    outside of 'signed' is under attacker control.)
    """
    return (
        isinstance(signable, dict)
        and set(signable) == {"signatures", "signed"}
        and isinstance(signable["signatures"], dict)
        and type(signable["signed"]) in SUPPORTED_SERIALIZABLE_TYPES
    )


Signable = dict


# TODO: ✅ Consolidate: switch to use of this wherever is_a_signable is called
#          and then an error is raised if the result is False.
def checkformat_signable(signable: Any) -> Signable:
    if not is_signable(signable):
        raise TypeError(
            "Expected a signable dictionary, but the given argument "
            "does not match expectations for a signable dictionary "
            '(must be a dictionary containing only keys "signatures" and '
            '"signed", where the value for key "signatures" is a dict '
            'and the value for key "signed" is a supported serializable '
            "type (" + str(SUPPORTED_SERIALIZABLE_TYPES) + ")"
        )

    return signable


class BytesLike(Protocol):
    def decode(self, *args, **kwargs) -> str:
        ...


def checkformat_byteslike(byteslike: Any) -> BytesLike:
    if not hasattr(byteslike, "decode"):
        raise TypeError("Expected a bytes-like object with a decode method.")

    return byteslike


def checkformat_natural_int(natural_int: Any) -> int:  # Annotated[int, ">= 1"]
    # Technically a TypeError or ValueError, depending, but meh.
    if int(natural_int) != natural_int or natural_int < 1:
        raise ValueError("Expected an integer >= 1.")

    return natural_int


# This is not yet widely used.
# TODO: ✅ See to it that anywhere we're checking for a string, we use this.
def checkformat_string(string: Any) -> str:
    if not isinstance(string, str):
        raise TypeError("Expecting a string")

    return string


def checkformat_expiration_distance(expiration_distance: Any) -> timedelta:
    if not isinstance(expiration_distance, timedelta):
        raise TypeError(
            "Expiration distance must be a datetime.timedelta object. "
            "Instead received a " + str(type(expiration_distance))
        )

    return expiration_distance


HexKey = HexString  # Annotated[HexString, "len() == 64"]


def checkformat_hex_key(hex_key: Any) -> HexKey:
    checkformat_hex_string(hex_key)

    if 64 != len(hex_key):
        raise ValueError("Expected a 64-character hex string representing a key value.")

    return hex_key


def checkformat_list_of_hex_keys(list_of_hex_keys: Any) -> list[HexKey]:
    """
    Note that this rejects any list of keys that includes any exact duplicates.
    """
    if not isinstance(list_of_hex_keys, list):
        raise TypeError(
            "Expected a list of 64-character hex strings representing keys."
        )

    for hex_key in list_of_hex_keys:
        checkformat_hex_key(hex_key)

    if len(set(list_of_hex_keys)) != len(list_of_hex_keys):
        raise ValueError(
            "The given list of keys in hex string form contains duplicates.  "
            "Duplicates are not permitted."
        )

    return list_of_hex_keys


def checkformat_utc_isoformat(date_string: Any) -> str:
    try:
        datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        # ValueError: date_string does not match format '%Y-%m-%dT%H:%M:%SZ'
        raise TypeError(
            "The provided string appears not to be a datetime string "
            "formatted as an ISO8601 UTC-specific datetime (e.g. "
            '"1999-12-31T23:59:59Z").'
        ) from None

    return date_string


def is_gpg_fingerprint(gpg_fingerprint: Any) -> bool:
    """
    True if the given value is a hex string of length 40 (representing a
    20-byte SHA-1 value, which is what OpenPGP/GPG uses as a key fingerprint).
    """
    try:
        checkformat_gpg_fingerprint(gpg_fingerprint)
        return True
    except (TypeError, ValueError):
        return False


GPGFingerprint = HexKey  # Annotated[HexKey, "len()==40"]


def checkformat_gpg_fingerprint(gpg_fingerprint: Any) -> GPGFingerprint:
    """
    See is_gpg_fingerprint.  Raises a TypeError if is_gpg_fingerprint is not
    True.
    """
    if len(gpg_fingerprint) != 40:
        raise ValueError(
            'The given value, "' + str(gpg_fingerprint) + '", is not a full '
            "GPG fingerprint (40 hex characters)."
        )

    # ⚠️ Yes, the following is a redundant test.  Please leave it here in case
    #    code changes elsewhere.
    # Prevent multiple possible representations of keys.  There are security
    # implications.  For example, we cannot permit two signatures from the
    # same key -- with the key represented differently -- to count as two
    # signatures from distinct keys.
    # local hex test. isalnum() checks for no whitespace.
    bytes.fromhex(gpg_fingerprint)
    if not gpg_fingerprint.isalnum() or gpg_fingerprint.lower() != gpg_fingerprint:
        raise ValueError(
            "Expected a hex string; non-hexadecimal or upper-case character found."
        )

    return gpg_fingerprint


def is_gpg_signature(gpg_signature: Any) -> bool:
    # TODO: ✅ docstring based on docstring from checkformat_gpg_signature

    try:
        checkformat_gpg_signature(gpg_signature)
        return True
    except (ValueError, TypeError):
        return False


GPGSignature = dict


def checkformat_gpg_signature(gpg_signature: Any) -> GPGSignature:
    """
    Raises a TypeError if the given object is not a dictionary representing a
    signature in a format that we expect.

    This is similar to BUT NOT THE SAME AS that produced by
    securesystemslib.gpg.functions.create_signature(), conforming to
    securesystemslib.formats.GPG_SIGNATURE_SCHEMA.

    We use a slightly different format in order to include the raw ed25519
    public key value. This is the format we expect for Root signatures.

    If the given object matches the format, returns silently.
    """
    if not isinstance(gpg_signature, dict):
        raise TypeError(
            "OpenPGP signatures objects must be dictionaries.  Received "
            "type " + str(type(gpg_signature)) + " instead."
        )

    if sorted(list(gpg_signature.keys())) not in [
        ["other_headers", "signature"],
        ["other_headers", "see_also", "signature"],
    ]:
        raise ValueError(
            'OpenPGP signature objects must include a "signature" and an '
            '"other_headers" entry, and may include a "see_also" entry.  No '
            "other entries are permitted."
        )

    if not is_hex_string(gpg_signature["other_headers"]):
        raise ValueError(
            '"other_headers" entry in OpenPGP signature object must be a ' "hex string."
        )
        # TODO ✅: Determine if we can constrain "other_headers" beyond
        #          limiting it to a hex string.  (No length constraint is
        #          provided here, for example.)

    if not is_hex_signature(gpg_signature["signature"]):
        raise ValueError(
            '"signature" entry in OpenPGP signature obj must be a hex '
            "string representing an ed25519 signature, 128 hex characters "
            "representing 64 bytes of data."
        )

    if "see_also" in gpg_signature:
        checkformat_gpg_fingerprint(gpg_signature["see_also"])

    return gpg_signature


def is_signature(signature: Any) -> bool:
    """
    Returns True if signature_obj is a dictionary representing an ed25519
    signature, either in the conda-content-trust normal format, or
    the format for a GPG signature.

    See conda_content_trust.common.checkformat_signature() docstring for more details.
    """
    try:
        checkformat_signature(signature)
        return True
    except (TypeError, ValueError):
        return False


Signature = dict


def checkformat_signature(signature: Any) -> Signature:
    """
    Raises a TypeError if the given object is not a dictionary.
    Raises a ValueError if the given object is a dictionary, but is not in
    our generalized signature format (supports both raw ed25519 signatures
    OpenPGP/GPG signatures).

    If the given object matches the format, returns silently.

    The generalized signature format is:
    {
     (REQUIRED)      'signature': <64-byte value ed25519 signature, as 128 hex chars>,
     (GPG SIGS ONLY) 'other_headers': <hex string of irrelevant OpenPGP data hashed in the signature digest>,
     (OPTIONAL)      'see_also': <40-hex-character SHA1 OpenPGP/GPG key identifier, for diagnostic purposes>
    }
    Examples:
        { 'signature': 'deadbeef'*32}      # normal ed25519 signature (no OpenPGP)

        { 'signature': 'deadbeef'*32,      # OpenPGP ed25519 signature
          'other_headers': 'deadbeef'*??}  # extra info OpenPGP insists on signing over

        { 'signature': 'deadbeef'*32,      # OpenPGP ed25519 signature
          'other_headers': 'deadbeef'*??,
          'see_also': 'deadbeef'*10}}      # listing an OpenPGP key fingerprint
    """
    if not isinstance(signature, dict):
        raise TypeError("Expected a signature object, of type dict.")
    elif not ("signature" in signature and is_hex_signature(signature["signature"])):
        # Even the minimal required element is not correct, so...
        raise ValueError(
            "Expected a dictionary representing an ed25519 signature as a "
            "128-character hex string.  This requires at least key "
            '"signature", with value a 128-character hexadecimal string '
            "representing a (64-byte) ed25519 signature."
        )

    # simple ed25519 signature, not an OpenPGP signature
    elif len(signature) == 1:
        # If this is a simple ed25519 signature, and not an OpenPGP/GPG
        # signature, then we're all set, since 'signature' is included and
        # has a reasonable value.
        return signature

    # Permit an OpenPGP (GPG / RFC 4880) signature noted as defined in
    # function is_gpg_signature.
    elif is_gpg_signature(signature):
        return signature

    else:
        raise ValueError(
            "Provided signature does not have the correct format for a "
            "signature object (neither simple ed25519 sig nor OpenPGP "
            "ed25519 sig)."
        )


Delegation = dict


def checkformat_delegation(delegation: Any) -> Delegation:
    """
    A dictionary specifying public key values and threshold of keys
    e.g.
        {   'pubkeys': ['ff'*32, '1e'*32],
            'threshold': 1}
    threshold must be an integer >= 1. pubkeys must be a list of hexadecimal
    representations of ed25519 public keys.

    Note that because drafts are allowed, we do not demand here that the list
    of pubkeys include enough keys to meet threshold.  Not listing pubkeys yet
    is okay during writing, but when verifying metadata, one should not accept
    delegations with impossible-to-meet requirements (len(pubkeys) < threshold)
    """
    if not isinstance(delegation, dict):
        raise TypeError(
            "Delegation information must be a dictionary specifying "
            '"pubkeys" and "threshold" elements.'
        )
    elif not (
        set(delegation) == {"threshold", "pubkeys"}
        and delegation["threshold"] >= 1
        and isinstance(delegation["pubkeys"], list)
        and all([is_hex_key(k) for k in delegation["pubkeys"]])
    ):
        raise ValueError(
            "Delegation information must be a dictionary specifying "
            'exactly two elements: "pubkeys" (assigned a list of '
            "64-character hex strings representing individual ed25519 "
            'public keys) and "threshold", assigned an integer >= 1.'
        )

    # We have the right type, and the right keys.  Check the values.
    checkformat_list_of_hex_keys(delegation["pubkeys"])
    checkformat_natural_int(delegation["threshold"])

    return delegation


def checkformat_delegations(delegations: Any) -> dict[str, Delegation]:
    """
    A dictionary specifying a delegation for any number of role names.
    Index: rolename.  Value: delegation (see checkformat_delegation).
    e.g.
        {   'root.json':
                {'pubkeys': ['01'*32, '02'*32, '03'*32], # each is a lower-case hex string w/ length 64
                 'threshold': 2},                        # integer >= 1
            'channeler.json':
                {'pubkeys': ['04'*32], 'threshold': 1}}
    """
    if not isinstance(delegations, dict):
        raise TypeError(
            '"Delegations" information must be a dictionary indexed by '
            "role names, with values equal to dictionaries that each "
            'specify elements "pubkeys" and "threshold".'
        )

    for index in delegations:
        checkformat_string(index)
        checkformat_delegation(delegations[index])

    return delegations


DelegatingMetadata = Signable


def checkformat_delegating_metadata(metadata: Any) -> DelegatingMetadata:
    """
    Validates argument "metadata" as delegating metadata.  Passes if it is,
    raises a TypeError or ValueError if it is not.

    The required format is a dictionary containing all contents of a delegating
    metadata file, like root.json or key_mgr.json.  (This includes both the
    signatures portion and the signed contents portion, in the usual envelope
    -- see also checkformat_signable.)

    The required structure:
        {
          'signatures': {}, # for each entry in the 'signatures' dict:
                            #  - the key must pass checkformat_hex_key
                            #  - the value must pass checkformat_signature()
                            #    or checkformat_gpg_signature()
          'signed': {
            'type': <type>: # must match a string in SUPPORTED_DELEGATING_METADATA_TYPES (e.g. 'root')
            'metadata_spec_version': <SemVer string>,
            'delegations': {}, # value must pass checkformat_delegations()
            'expiration': <date>, # date must pass checkformat_utc_isoformat()

            # The 'signed' dict must always include either a 'timestamp' entry,
            # a 'version' entry, or both.  Further, in root metadata the
            # 'signed' dict must always include a 'version' entry (to support
            # root chaining).

            'timestamp': <date>, # if included, must pass checkformat_utc_isoformat()
            'version': <integer> # if included, must pass checkformat_natural_int(), i.e. be an integer >= 1
          }
        }

    e.g.
        {
          "signatures": {       # 0 or more signatures over the signed contents
            <public key>: {
              "other_headers": "04001608001d162104f075dd2f6f4cb3bd76134bbb81b6ca16ef9cd58905025f0bf546",
              "signature": "ab3e03385f757da74e08b46f1bf82709fbc2ce21823c28e2f0e3452415e2a9f1e2c82e418cc44e2908618cf0c7375f32fe0a5a75494909a59a82875ebc703c02",
            },
            ...
          },
          "signed": {           # signed contents
            "delegations": {
              "key_mgr.json": {
                "pubkeys": [
                  "013ddd714962866d12ba5bae273f14d48c89cf0773dee2dbf6d4561e521c83f7"
                ],
                "threshold": 1
              },
              "root.json": {
                "pubkeys": [
                  "bfbeb6554fca9558da7aa05c5e9952b7a1aa3995dede93f3bb89f0abecc7dc07"
                ],
                "threshold": 1
              }
            },
            "expiration": "2021-07-13T05:46:45Z",
            "metadata_spec_version": "0.1.0",
            "timestamp": "2020-07-13T05:46:45Z",
            "type": "root",
            "version": 1
          }
        }
    """
    # Signing envelope required
    checkformat_signable(metadata)

    for k in metadata["signatures"]:
        checkformat_any_signature(metadata["signatures"][k])

    contents = metadata["signed"]

    for entry in [  # required fields
        "type",
        "metadata_spec_version",
        "delegations",
        "expiration",
    ]:
        if entry not in contents:
            raise ValueError(
                'Expected a "' + str(entry) + '" entry in the given '
                "delegating metadata."
            )

    checkformat_string(contents["type"])
    if contents["type"] not in SUPPORTED_DELEGATING_METADATA_TYPES:
        raise ValueError(
            'Given type entry ("' + contents["type"] + '") is not '
            "one of the supported types of delegating metadata."
        )

    checkformat_string(contents["metadata_spec_version"])
    # TODO ✅⚠️: For metadata_spec_version, add semantic versioning checks:
    #                 - check format
    #                 - check for compatibility with common.SECURITY_METADATA_SPEC_VERSION

    checkformat_delegations(contents["delegations"])

    checkformat_utc_isoformat(contents["expiration"])

    # Timestamp and/or Version:
    if "timestamp" not in contents and "version" not in contents:
        raise ValueError(
            'All metadata must include a "version" entry, or a '
            '"timestamp" entry, or both.'
        )

    if contents["type"] == "root" and "version" not in contents:
        raise ValueError("Root metadata must specify its version number.")
    # Catch a possible future coding error at the PR stage, here where the
    # assumption is being made.
    assert "root" in SUPPORTED_DELEGATING_METADATA_TYPES

    if "timestamp" in contents:
        checkformat_utc_isoformat(contents["timestamp"])
    if "version" in contents:  # optional field for non-root metadata
        checkformat_natural_int(contents["version"])
    # TODO ✅: Ensure that expiration > timestamp, to help people not shoot
    #          themselves in the foot.


def checkformat_any_signature(signature: Any) -> Signature | GPGSignature:
    if not is_signature(signature) and not is_gpg_signature(signature):
        raise ValueError(
            "Expected either a hex string representing a raw ed25519 "
            "signature (see checkformat_signature) or a dictionary "
            "representing an OpenPGP/GPG signature "
            "(see checkformat_gpg_signature)."
        )

    return signature


def keyfiles_to_bytes(name):
    """
    Toy function.  Import an ed25519 key pair, in the forms of raw public and
    raw private keys, from name.pub and name.pri respectively.

    Cavalier about private key bytes.
    Does not perform input validation ('/'...).

    Return the 32 bytes of the private key object and the 32 bytes of the
    public key object, in that order.
    """
    with open(name + ".pri", "rb") as fobj:
        private_bytes = fobj.read()

    with open(name + ".pub", "rb") as fobj:
        public_bytes = fobj.read()

    return private_bytes, public_bytes


def keyfiles_to_keys(name):
    """
    Doesn't perform input validation.
    Import an ed25519 key pair, in the forms of raw public key
    bytes and raw private key bytes, from name.pub and name.pri respectively.
    Cavalier about private key bytes.
    Return a private key object and public key object, in that order.
    """
    private_bytes, public_bytes = keyfiles_to_bytes(name)

    private = PrivateKey.from_bytes(private_bytes)
    public = PublicKey.from_bytes(public_bytes)

    return private, public


def checkformat_key(key: Any) -> ed25519.Ed25519PublicKey | ed25519.Ed25519PrivateKey:
    """
    Enforces expectation that argument is an object of type
    cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PublicKey or
    cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey.
    """
    if not isinstance(key, (ed25519.Ed25519PublicKey, ed25519.Ed25519PrivateKey)):
        raise TypeError(
            "Expected an Ed25519PublicKey or Ed25519PrivateKey object "
            'from the "cryptography" library.  Received object of type '
            + str(type(key))
            + " instead."
        )

    return key


def iso8601_time_plus_delta(delta):
    """
    Applies a datetime.timedelta to the current time in UTC with microseconds
    stripped, then converts to ISO8601 format and appends a 'Z' indicating that
    it is UTC time, not local time.  We only deal with UTC times!

    This is used for two purposes:
     - get current time in ISO8601 format, by passing in a 0 timedelta
     - get ISO8601 UTC timestamp for expiration dates

    regex for time: '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$'
    """
    checkformat_expiration_distance(delta)

    unix_expiry = datetime.utcnow().replace(microsecond=0) + delta

    return unix_expiry.isoformat() + "Z"
