# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import datetime
import ipaddress
import json
import os

import pytest

from cryptography import x509
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.verification import (
    ClientVerifier,
    PolicyBuilder,
    ServerVerifier,
    Store,
    VerificationError,
)

LIMBO_UNSUPPORTED_FEATURES = {
    # NOTE: Path validation is required to reject wildcards on public suffixes,
    # however this isn't practical and most implementations make no attempt to
    # comply with this.
    "pedantic-public-suffix-wildcard",
    # TODO: We don't support Distinguished Name Constraints yet.
    "name-constraint-dn",
    # Our support for custom EKUs is limited, and we (like most impls.) don't
    # handle all EKU conditions under CABF.
    "pedantic-webpki-eku",
    # Most CABF validators do not enforce the CABF key requirements on
    # subscriber keys (i.e., in the leaf certificate).
    "pedantic-webpki-subscriber-key",
    # Tests that fail based on a strict reading of RFC 5280
    # but are widely ignored by validators.
    "pedantic-rfc5280",
    # In rare circumstances, CABF relaxes RFC 5280's prescriptions in
    # incompatible ways. Our validator always tries (by default) to comply
    # closer to CABF, so we skip these.
    "rfc5280-incompatible-with-webpki",
    # We do not support policy constraints.
    "has-policy-constraints",
}

LIMBO_SKIP_TESTCASES = {
    # We unconditionally count intermediate certificates for pathlen and max
    # depth constraint purposes, even when self-issued.
    # This is a violation of RFC 5280, but is consistent with Go's crypto/x509
    # and Rust's webpki crate do.
    "pathlen::self-issued-certs-pathlen",
    "pathlen::max-chain-depth-1-self-issued",
    # We allow certificates with serial numbers of zero. This is
    # invalid under RFC 5280 but is widely violated by certs in common
    # trust stores.
    "rfc5280::serial::zero",
    # We allow CAs that don't have AKIs, which is forbidden under
    # RFC 5280. This is consistent with what Go's crypto/x509 and Rust's
    # webpki crate do.
    "rfc5280::ski::root-missing-ski",
    "rfc5280::ski::intermediate-missing-ski",
    # We currently allow intermediate CAs that don't have AKIs, which
    # is technically forbidden under CABF. This is consistent with what
    # Go's crypto/x509 and Rust's webpki crate do.
    "rfc5280::aki::intermediate-missing-aki",
    # We allow root CAs where the AKI and SKI mismatch, which is technically
    # forbidden under CABF. This is consistent with what
    # Go's crypto/x509 and Rust's webpki crate do.
    "webpki::aki::root-with-aki-ski-mismatch",
    # We allow RSA keys that aren't divisible by 8, which is technically
    # forbidden under CABF. No other implementation checks this either.
    "webpki::forbidden-rsa-not-divisable-by-8-in-root",
    # We disallow CAs in the leaf position, which is explicitly forbidden
    # by CABF (but implicitly permitted under RFC 5280). This is consistent
    # with what webpki and rustls do, but inconsistent with Go and OpenSSL.
    "rfc5280::ca-as-leaf",
    "pathlen::validation-ignores-pathlen-in-leaf",
}


def _get_limbo_peer(expected_peer):
    kind = expected_peer["kind"]
    assert kind in ("DNS", "IP", "RFC822")
    value = expected_peer["value"]
    if kind == "DNS":
        return x509.DNSName(value)
    elif kind == "IP":
        return x509.IPAddress(ipaddress.ip_address(value))
    else:
        return x509.RFC822Name(value)


def _limbo_testcase(id_, testcase):
    if id_ in LIMBO_SKIP_TESTCASES:
        pytest.skip(f"explicitly skipped testcase: {id_}")

    features = testcase["features"]
    unsupported = LIMBO_UNSUPPORTED_FEATURES.intersection(features)
    if unsupported:
        pytest.skip(f"explicitly skipped features: {unsupported}")

    assert testcase["signature_algorithms"] == []

    trusted_certs = [
        load_pem_x509_certificate(cert.encode())
        for cert in testcase["trusted_certs"]
    ]
    untrusted_intermediates = [
        load_pem_x509_certificate(cert.encode())
        for cert in testcase["untrusted_intermediates"]
    ]
    peer_certificate = load_pem_x509_certificate(
        testcase["peer_certificate"].encode()
    )
    validation_time = testcase["validation_time"]
    validation_time = (
        datetime.datetime.fromisoformat(validation_time)
        if validation_time is not None
        else None
    )
    max_chain_depth = testcase["max_chain_depth"]
    should_pass = testcase["expected_result"] == "SUCCESS"

    builder = PolicyBuilder().store(Store(trusted_certs))
    if validation_time is not None:
        builder = builder.time(validation_time)
    if max_chain_depth is not None:
        builder = builder.max_chain_depth(max_chain_depth)

    verifier: ServerVerifier | ClientVerifier
    if testcase["validation_kind"] == "SERVER":
        assert testcase["extended_key_usage"] == [] or testcase[
            "extended_key_usage"
        ] == ["serverAuth"]
        peer_name = _get_limbo_peer(testcase["expected_peer_name"])
        # Some tests exercise invalid leaf SANs, which get caught before
        # validation even begins.
        try:
            verifier = builder.build_server_verifier(peer_name)
        except ValueError:
            assert not should_pass
            return
    else:
        assert testcase["extended_key_usage"] == ["clientAuth"]
        verifier = builder.build_client_verifier()

    if should_pass:
        if isinstance(verifier, ServerVerifier):
            built_chain = verifier.verify(
                peer_certificate, untrusted_intermediates
            )
        else:
            verified_client = verifier.verify(
                peer_certificate, untrusted_intermediates
            )

            expected_subjects = [
                _get_limbo_peer(p) for p in testcase["expected_peer_names"]
            ]
            assert expected_subjects == verified_client.subjects

            built_chain = verified_client.chain

        # Assert that the verifier returns chains in [EE, ..., TA] order.
        assert built_chain[0] == peer_certificate
        for intermediate in built_chain[1:-1]:
            assert intermediate in untrusted_intermediates
        assert built_chain[-1] in trusted_certs
    else:
        with pytest.raises(VerificationError):
            verifier.verify(peer_certificate, untrusted_intermediates)


def test_limbo(subtests, pytestconfig):
    limbo_root = pytestconfig.getoption("--x509-limbo-root", skip=True)
    limbo_path = os.path.join(limbo_root, "limbo.json")
    with open(limbo_path, mode="rb") as limbo_file:
        limbo = json.load(limbo_file)
        testcases = limbo["testcases"]
        for testcase in testcases:
            with subtests.test():
                # NOTE: Pass in the id separately to make pytest
                # error renderings slightly nicer.
                _limbo_testcase(testcase["id"], testcase)
