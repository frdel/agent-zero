# Copyright (C) 2019 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
This module contains functions that sign data using ed25519 keys, via the
pyca/cryptography library.  Functions that perform OpenPGP-compliant (e.g. GPG)
signing are provided instead in root_signing.

Function Manifest for this Module:
    serialize_and_sign
    wrap_as_signable
    sign_signable
"""
from binascii import hexlify
from copy import deepcopy

from .common import (
    SUPPORTED_SERIALIZABLE_TYPES,
    PrivateKey,
    PublicKey,
    canonserialize,
    checkformat_hex_key,
    checkformat_key,
    checkformat_signable,
    checkformat_signature,
    checkformat_string,
    load_metadata_from_file,
    write_metadata_to_file,
)


def serialize_and_sign(obj, private_key):
    """
    Given a JSON-compatible object, does the following:
     - serializes the dictionary as utf-8-encoded JSON, lazy-canonicalized
       such that any dictionary keys in any dictionaries inside <dictionary>
       are sorted and indentation is used and set to 2 spaces (using json lib)
     - creates a signature over that serialized result using private_key
     - returns that signature as a hex string

    See comments in common.canonserialize()

    Arguments:
      obj: a JSON-compatible object -- see common.canonserialize()
      private_key: a conda_content_trust.common.PrivateKey object

    # TODO ✅: Consider taking the private key data as a hex string instead?
    #          On the other hand, it's useful to support an object that could
    #          obscure the key (or provide an interface to a hardware key).
    """

    # Try converting to a JSON string.
    serialized = canonserialize(obj)

    signature_as_bytes = private_key.sign(serialized)

    signature_as_hexstr = hexlify(signature_as_bytes).decode("utf-8")

    return signature_as_hexstr


def wrap_as_signable(obj):
    """
    Given a JSON-serializable object (dictionary, list, string, numeric, etc.),
    returns a wrapped copy of that object:

        {'signatures': {},
         'signed': <deep copy of the given object>}

    Expects strict typing matches (not duck typing), for no good reason.
    (Trying JSON serialization repeatedly could be too time consuming.)

    TODO: ✅ Consider whether or not the copy can be shallow instead, for speed.

    Raises ❌TypeError if the given object is not a JSON-serializable type per
    SUPPORTED_SERIALIZABLE_TYPES
    """
    if not type(obj) in SUPPORTED_SERIALIZABLE_TYPES:
        raise TypeError(
            "wrap_dict_as_signable requires a JSON-serializable object, "
            "but the given argument is of type " + str(type(obj)) + ", "
            "which is not supported by the json library functions."
        )

    # TODO: ✅ Later on, consider switching back to TUF-style
    #          signatures-as-a-list.  (Is there some reason it's saner?)
    #          Going with my sense of what's best now, which is dicts instead.
    #          It's simpler and it naturally avoids duplicates.  We don't do it
    #          this way in TUF, but we also don't depend on it being an ordered
    #          list anyway, so a dictionary is probably better.

    return {"signatures": {}, "signed": deepcopy(obj)}


def sign_signable(signable, private_key):
    """
    Given a JSON-compatible signable dictionary (as produced by calling
    wrap_dict_as_signable with a JSON-compatible dictionary), calls
    serialize_and_sign on the enclosed dictionary at signable['signed'],
    producing a signature, and places the signature in
    signable['signatures'], in an entry indexed by the public key
    corresponding to the given private_key.

    Updates the given signable in place, returning nothing.
    Overwrites if there is already an existing signature by the given key.

    # TODO ✅: Take hex string keys for sign_signable and serialize_and_sign
    #          instead of constructed PrivateKey objects?  Add the comment
    #          below if so:
    # # Unlike with lower-level functions, both signatures and public keys are
    # # always written as hex strings.

    Raises ❌TypeError if the given object is not a JSON-serializable type per
    SUPPORTED_SERIALIZABLE_TYPES
    """
    # Argument checking
    checkformat_key(private_key)
    checkformat_signable(signable)
    # if not is_a_signable(signable):
    #     raise TypeError(
    #             'Expected a signable dictionary; the given argument of type ' +
    #             str(type(signable)) + ' failed the check.')

    # private_key = PrivateKey.from_hex(private_key_hex)

    signature_as_hexstr = serialize_and_sign(signable["signed"], private_key)

    public_key_as_hexstr = PublicKey.to_hex(private_key.public_key())

    # To fit a general format, we wrap it this way, instead of just using the
    # hexstring.  This is because OpenPGP signatures that we use for root
    # signatures look similar and have a few extra fields beyond the signature
    # value itself.
    signature_dict = {"signature": signature_as_hexstr}

    checkformat_signature(signature_dict)

    # TODO: ✅⚠️ Log a warning in whatever conda's style is (or conda-build):
    #
    # if public_key_as_hexstr in signable['signatures']:
    #   warn(    # replace: log, 'warnings' module, print statement, whatever
    #           'Overwriting existing signature by the same key on given '
    #           'signable.  Public key: ' + public_key + '.')

    # Add signature in-place, in the usual signature format.
    signable["signatures"][public_key_as_hexstr] = signature_dict


def sign_all_in_repodata(fname, private_key_hex):
    """
    Given a repodata.json filename, reads the "packages" entries in that file,
    and produces a signature over each artifact, with the given key.  The
    signatures are then placed in a "signatures" entry parallel to the
    "packages" entry in the json file.  The file is overwritten.

    Arguments:
        fname: filename of a repodata.json file
        private_key_hex:
            a private ed25519 key value represented as a 64-char hex string
    """
    checkformat_hex_key(private_key_hex)
    checkformat_string(fname)
    # TODO ✅⚠️: Consider filename validation.  What does conda use for that?

    private = PrivateKey.from_hex(private_key_hex)
    public_hex = PublicKey.to_hex(private.public_key())

    # Loading the whole file at once instead of reading it as we go, because
    # it's less complex and this only needs to run repository-side.
    repodata = load_metadata_from_file(fname)
    # with open(fname, 'rb') as fobj:
    #     repodata = json.load(fname)

    # TODO ✅: Consider more validation for the gross structure expected of
    #            repodata.json
    if "packages" not in repodata:
        raise ValueError('Expected a "packages" entry in given repodata file.')

    # Add an empty 'signatures' dict to repodata.
    # If it's already there for whatever reason, we replace it entirely.  This
    # avoids leaving existing signatures that might not get replaced -- e.g. if
    # the artifact is not in the "packages" dict, but is in the "signatures"
    # dict for some reason.  What comes out of this process will be limited to
    # what we sign in this function.
    repodata["signatures"] = {}

    for artifact_name, metadata in repodata["packages"].items():
        # TODO ✅: Further consider the significance of the artifact name
        #          itself not being part of the signed metadata.  The info used
        #          to generate the name (package name + version + build) is
        #          part of the signed metadata, but the full name is not.
        #          Keep in mind attacks that swap metadata among artifacts;
        #          signatures would still read as correct in that circumstance.
        signature_hex = serialize_and_sign(metadata, private)

        # To fit a general format, we wrap it this way, instead of just using
        # the hexstring.  This is because OpenPGP signatures that we use for
        # root signatures look similar and have a few extra fields beyond the
        # signature value itself.
        signature_dict = {"signature": signature_hex}

        checkformat_signature(signature_dict)

        repodata["signatures"][artifact_name] = {public_hex: signature_dict}

    # Repeat for the .conda packages in 'packages.conda'.
    for artifact_name, metadata in repodata.get("packages.conda", {}).items():
        signature_hex = serialize_and_sign(metadata, private)
        repodata["signatures"][artifact_name] = {
            public_hex: {"signature": signature_hex}
        }

    # Note: takes >0.5s on a macbook for large files
    write_metadata_to_file(repodata, fname)
