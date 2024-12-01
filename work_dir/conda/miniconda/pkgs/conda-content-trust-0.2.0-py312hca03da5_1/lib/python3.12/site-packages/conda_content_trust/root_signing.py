# Copyright (C) 2019 Anaconda, Inc
# SPDX-License-Identifier: BSD-3-Clause
"""
This module contains functions that sign data in an OpenPGP-compliant (i.e.
GPG-friendly) way.  Root metadata may be signed in this manner.  Functions that
perform simpler, direct signing using raw ed25519 keys are provided in
conda_content_trust.signing instead.

This library takes advantage of the securesystemslib library for its gpg
signing interface.

Function Manifest for this Module:
    sign_via_gpg                  # requires securesystemslib
    sign_root_metadata_via_gpg    # requires securesystemslib
    fetch_keyval_from_gpg         # requires securesystemslib

Note that there is a function in conda_content_trust.authentication that verifies these
signatures without requiring securesystemslib.
"""
# securesystemslib is an optional dependency, and required only for signing
# root metadata via GPG.  Verification of those signatures, and signing other
# metadata with raw ed25519 signatures, does not require securesystemslib.
try:
    import securesystemslib.formats  # noqa: F401
    from securesystemslib.gpg import functions as gpg_funcs

    SSLIB_AVAILABLE = True
except ImportError:  # pragma: no cover
    SSLIB_AVAILABLE = False

from .common import (
    canonserialize,
    checkformat_byteslike,
    checkformat_gpg_fingerprint,
    checkformat_hex_key,
    is_signable,
    load_metadata_from_file,
    write_metadata_to_file,
)


def _check_sslib_available():
    if not SSLIB_AVAILABLE:
        raise ImportError(
            "The securesystemslib library is required, which appears to be unavailable."
        )


def sign_via_gpg(data_to_sign, gpg_key_fingerprint, include_fingerprint=False):
    """
    <Purpose>

        This is an alternative to the conda_content_trust.common.PrivateKey.sign() method, for
        use with OpenPGP keys, allowing us to use protected keys in YubiKeys
        (which provide an OpenPGP interface) to sign data.

        The signature is not simply over data_to_sign, as is the case with the
        PrivateKey.sign() function, but over an expanded payload with
        metadata about the signature to be signed, as specified by the OpenPGP
        standard (RFC 4880).  See data_to_sign and Security Note below.

        This process is nominally deterministic, but varies with the precise
        time, since there is a timestamp added by GPG into the signed payload.
        Nonetheless, this process does not depend at any point on the ability
        to generate random data (unlike key generation).

        This function requires securesystemslib, which is otherwise an optional
        dependency.

    <Arguments>

        data_to_sign
            The raw bytes of interest that will be signed by GPG.  Note that
            pursuant to the OpenPGP standard, GPG will add to this data:
            specifically, it includes metadata about the signature that is
            about to be made into the data that will be signed.  We do not care
            about that metadata, and we do not want to burden signature
            verification with its processing, so we essentially ignore it.
            This should have negligible security impact, but for more
            information, see "A note on security" below.


        gpg_key_fingerprint
            This is a (fairly) unique identifier for an OpenPGP key pair.
            Also Known as a "long" GPG keyid, a GPG fingerprint is
            40-hex-character string representing 20 bytes of raw data, the
            SHA-1 hash of a collection of the GPG key's properties.
            Internally, GPG uses the key fingerprint to identify keys the
            client knows of.

            Note that an OpenPGP public key is a larger object identified by a
            fingerprint.  GPG public keys include two things, from our
            perspective:

             - the raw bytes of the actual cryptographic key
               (in our case the 32-byte value referred to as "q" for an ed25519
               public key)

             - lots of data that is totally extraneous to us, including a
               timestamp, some representations of relationships with other keys
               (subkeys, signed-by lists, etc.), Superman's real name
               (see also https://bit.ly/38GcaGj), potential key revocations,
               etc.
               We do not care about this extra data because we are using the
               OpenPGP standard not for its key-to-key semantics or any element
               of its Public Key Infrastructure features (revocation, vouching
               for other keys, key relationships, etc.), but simply as a means
               of asking YubiKeys to sign data for us, with ed25519 keys whose
               raw public key value ("q") we know to expect.


    <Returns>
        Returns a dictionary representing a GPG signature.  This is similar to
        but not *quite* the same as
        securesystemslib.formats.GPG_SIGNATURE_SCHEMA (which uses 'keyid'
        as the key for the fingerprint, instead of 'gpg_key_fingerprint').

        Specifically, this looks like:
            {'gpg_key_fingerprint': <gpg key fingerprint>,
            'other_headers':       <extra data mandated in OpenPGP signatures>,
            'signature':        <ed25519 signature, 64 bytes as 128 hex chars>}


        This is unlike conda_content_trust.signing.sign(), which simply returns 64 bytes of raw
        ed25519 signature.


    <Security Note>

        A note on the security implications of this treatment of OpenPGP
        signatures:

        TL;DR:
            It is NOT easier for an attacker to find a collision; however, it
            IS easier, IF an attacker CAN find a collision, to do so in a way
            that presents a specific, arbitrary payload.

        Note that pursuant to the OpenPGP standard, GPG will add to the data we
        ask it to sign (data_to_sign) before signing it. Specifically, GPG will
        add, to the payload-to-be-signed, OpenPGP metadata about the signature
        it is about to create.  We do not care about that metadata, and we do
        not want to burden signature verification with its processing (that is,
        we do not want to use GPG to verify these signatures; conda will do
        that with simpler code).  As a result, we will ignore this data when
        parsing the signed payload.  This will mean that there will be many
        different messages that have the same meaning to us:

            signed:
                <some raw data we send to GPG: 'ABCDEF...'>
                <some data GPG adds in: '123456...'>

            Since we will not be processing the '123456...' above, '654321...'
            would have the same effect: as long as the signature is verified,
            we don't care what's in that portion of the payload.

        Since there are many, many payloads that mean the same thing to us, an
        attacker has a vast space of options all with the same meaning to us in
        which to search for (effectively) a useful SHA256 hash collision to
        find different data that says something *specific* and still
        *succeeds* in signature verification using the same signature.
        While that is not ideal, it is difficult enough simply to find a SHA256
        collision that this is acceptable.
    """
    _check_sslib_available()

    # Argument validation
    checkformat_gpg_fingerprint(gpg_key_fingerprint)
    checkformat_byteslike(data_to_sign)

    sig = gpg_funcs.create_signature(data_to_sign, gpg_key_fingerprint)

    # securesystemslib.gpg makes use of the GPG key fingerprint.  We don't
    # care about that as much -- we want to use the raw ed25519 public key
    # value to refer to the key in a manner consistent with the way we refer to
    # non-GPG (non-OpenPGP) keys.
    keyval = fetch_keyval_from_gpg(gpg_key_fingerprint)

    # ssl gpg sigs look like this:
    #
    #   {'keyid': <gpg key fingerprint>,
    #    'other_headers': <extra data mandated in OpenPGP signatures>,
    #    'signature': <actual ed25519 signature, 64 bytes as 128 hex chars>}
    #
    # We want to store the real public key instead of just the gpg key
    # fingerprint, so we add that, and we'll rename keyid to
    # gpg_key_fingerprint.  That gives us:
    #
    #   {'gpg_key_fingerprint': <gpg key fingerprint>,
    #    'other_headers': <extra data mandated in OpenPGP signatures>,
    #    'signature': <actual ed25519 signature, 64 bytes as 128 hex chars>}

    # sig['key'] = keyval  # q, the 32-byte raw ed25519 public key value, expressed as 64 hex characters

    # The OpenPGP Fingerprint of the OpenPGP key used to sign.  This is not
    # required for verification, but it's useful for debugging and for
    # root keyholder convenience.  So it's optional.
    if include_fingerprint:
        sig["see_also"] = sig[
            "keyid"
        ]  # strictly not needed, useful for debugging; 20-byte sha1 gpg key identifier per OpenPGP spec, expressed as 40 hex characters

    del sig["keyid"]

    return sig


def sign_root_metadata_dict_via_gpg(root_signable, gpg_key_fingerprint):
    # Signs root_signable in place, returns nothing.

    _check_sslib_available()

    # Make sure it's the right format.
    if not is_signable(root_signable):
        raise TypeError("Expected a signable dictionary.")

    # TODO: Add root-specific checks.

    # Canonicalize and serialize the data, putting it in the form we expect to
    # sign over.  Note that we'll canonicalize and serialize the whole thing
    # again once the signatures have been added.
    data_to_sign = canonserialize(root_signable["signed"])

    sig_dict = sign_via_gpg(data_to_sign, gpg_key_fingerprint)

    # sig_dict looks like this:
    #     {'keyid': 'f075dd2f6f4cb3bd76134bbb81b6ca16ef9cd589',
    #      'other_headers': '04001608001d162104f075dd2f6f4cb3bd76134bbb81b6ca16ef9cd58905025dbc3e68',
    #      'signature': '29282a8fe75871f9d4cf10a5a9e8d92303f8c361ce4b474a0ce641c9b8a74e4baaf810cc383af318a8e21cbe252789c2c30894d94e8b0288c3c45ceacf6c1d0c'}
    # pgp_pubkey looks like this:
    # {'creation_time': 1571411344,
    # 'hashes': ['pgp+SHA2'],
    # 'keyid': 'f075dd2f6f4cb3bd76134bbb81b6ca16ef9cd589',
    # 'keyval': {'private': '',
    #            'public': {'q': 'bfbeb6554fca9558da7aa05c5e9952b7a1aa3995dede93f3bb89f0abecc7dc07'}},
    # 'method': 'pgp+eddsa-ed25519',
    # 'type': 'eddsa'}

    # securesystemslib.gpg makes use of the GPG key fingerprint.  We don't
    # care about that as much -- we want to use the raw ed25519 public key
    # value to refer to the key in a manner consistent with the way we refer to
    # non-GPG (non-OpenPGP) keys.
    # raw_pubkey = pgp_pubkey['keyval']['public']['q']
    raw_pubkey = fetch_keyval_from_gpg(gpg_key_fingerprint)

    # non-GPG signing here would look like this:
    # signature_as_hexstr = serialize_and_sign(signable['signed'], private_key)
    # public_key_as_hexstr = binascii.hexlify(key_to_bytes(
    #         private_key.public_key())).decode('utf-8')

    # Add signature in-place.
    root_signable["signatures"][raw_pubkey] = sig_dict

    return root_signable


def sign_root_metadata_via_gpg(root_md_fname, gpg_key_fingerprint):
    """
    # This is a higher-level function than sign_via_gpg, including code that
    # deals with the filesystem.  It is not actually limited to root metadata,
    # and SHOULD BE RENAMED.
    """
    # Read in json
    root_signable = load_metadata_from_file(root_md_fname)

    root_signable = sign_root_metadata_dict_via_gpg(root_signable, gpg_key_fingerprint)

    # TODO: Consider removing write_metadata_to_file.  It might be better for
    #       readers to see the canonserialize() call being made (again) here,
    #       and it's not that much longer....
    write_metadata_to_file(root_signable, root_md_fname)


def fetch_keyval_from_gpg(fingerprint):
    """
    Retrieve the underlying 32-byte raw ed25519 public key for a GPG key.

    Given a GPG key fingerprint (40-character hex string), retrieve the GPG
    key, parse it, and return "q", the 32-byte ed25519 key value.

    This takes advantage of the GPG key parser in securesystemslib.

    The fingerprint will be stripped of spaces and lowercased, so you can use
    the GPG output even if it's in a funky format:
            94A3 EED0 806C 1F10 7754  A446 FDAD 11B8 2DD4 0E8C
            94A3 EED0 806C 1F10 7754  A446 FDAD 11B8 2DD4 0E8C    # <-- No, this is actually not the same as the previous one, which uses \\xa0....
            94A3EED0806C1F107754A446FDAD11B82DD40E8C
            94a3eed0806c1f107754a446fdad11b82dd40e8c
            etc.
    """
    _check_sslib_available()

    fingerprint = (
        fingerprint.lower().replace(" ", "").replace("\xa0", "")
    )  # \xa0 is another space character that GPG sometimes outputs

    checkformat_gpg_fingerprint(fingerprint)

    key_parameters = gpg_funcs.export_pubkey(fingerprint)

    return key_parameters["keyval"]["public"]["q"]


def _gpg_pubkey_in_ssl_format(fingerprint, q):
    """
    THIS IS PROVIDED ONLY FOR TESTING PURPOSES.
    We do not need to convert pubkeys to securesystemslib's format, except to
    try out securesystemslib's gpg signature verification (which we use only
    for comparison during testing).

    Given a GPG key fingerprint (40 hex characters) and a q value (64 hex
    characters representing a 32-byte ed25519 public key raw value), produces a
    key object in a format that securesystemslib expects, so that we can use
    securesystemslib.gpg.functions.verify_signature for part of the GPG
    signature verification.  For our purposes, this means that we should
    produce a dictionary conforming to
    securesystemslib.formats._GPG_ED25519_PUBKEY_SCHEMA.

    If securesystemslib.formats._GPG_ED25519_PUBKEY_SCHEMA changes, those
    changes will likely need to be reflected here.

    Example value produced:
    {
        'type': 'eddsa',
        'method': 'pgp+eddsa-ed25519',
        'hashes': ['pgp+SHA2'],
        'keyid': 'F075DD2F6F4CB3BD76134BBB81B6CA16EF9CD589',
        'keyval': {
            'public': {'q': 'bfbeb6554fca9558da7aa05c5e9952b7a1aa3995dede93f3bb89f0abecc7dc07'},
            'private': ''}
        }
    }
    """
    checkformat_gpg_fingerprint(fingerprint)
    checkformat_hex_key(q)

    ssl_format_key = {
        "type": "eddsa",
        "method": securesystemslib.formats.GPG_ED25519_PUBKEY_METHOD_STRING,
        "hashes": [securesystemslib.formats.GPG_HASH_ALGORITHM_STRING],
        "keyid": fingerprint,
        "keyval": {"private": "", "public": {"q": q}},
    }

    return ssl_format_key


# def _gpgsig_to_sslgpgsig(gpg_sig):
#
#     conda_content_trust.common.checkformat_gpg_signature(gpg_sig)
#
#     return {
#             'keyid': copy.deepcopy(gpg_sig['key_fingerprint']),
#             'other_headers': copy.deepcopy(gpg_sig[other_headers]),
#             'signature': copy.deepcopy(gpg_sig['signature'])}


# def _sslgpgsig_to_gpgsig(ssl_gpg_sig):
#
#     securesystemslib.formats.GPG_SIGNATURE_SCHEMA.check_match(ssl_gpg_sig)
#
#     return {
#             'key_fingerprint': copy.deepcopy(ssl_gpg_sig['keyid']),
#             'other_headers': copy.deepcopy(ssl_gpg_sig[other_headers]),
#             'signature': copy.depcopy(ssl_gpg_sig['signature'])
#     }
