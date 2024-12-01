# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.

import datetime
import json
import os

import certifi

from cryptography import x509

from ..utils import load_vectors_from_file


def test_object_identifier_constructor(benchmark):
    benchmark(x509.ObjectIdentifier, "1.3.6.1.4.1.11129.2.4.5")


def test_aki_public_bytes(benchmark):
    aki = x509.AuthorityKeyIdentifier(
        key_identifier=b"\x00" * 16,
        authority_cert_issuer=None,
        authority_cert_serial_number=None,
    )
    benchmark(aki.public_bytes)


def test_load_der_certificate(benchmark):
    cert_bytes = load_vectors_from_file(
        os.path.join("x509", "PKITS_data", "certs", "GoodCACert.crt"),
        loader=lambda pemfile: pemfile.read(),
        mode="rb",
    )

    benchmark(x509.load_der_x509_certificate, cert_bytes)


def test_load_pem_certificate(benchmark):
    cert_bytes = load_vectors_from_file(
        os.path.join("x509", "cryptography.io.pem"),
        loader=lambda pemfile: pemfile.read(),
        mode="rb",
    )

    benchmark(x509.load_pem_x509_certificate, cert_bytes)


def test_verify_docs_python_org(benchmark, pytestconfig):
    limbo_root = pytestconfig.getoption("--x509-limbo-root", skip=True)
    with open(os.path.join(limbo_root, "limbo.json"), "rb") as f:
        [testcase] = [
            tc
            for tc in json.load(f)["testcases"]
            if tc["id"] == "online::docs.python.org"
        ]

    with open(certifi.where(), "rb") as f:
        store = x509.verification.Store(
            x509.load_pem_x509_certificates(f.read())
        )

    leaf = x509.load_pem_x509_certificate(
        testcase["peer_certificate"].encode()
    )
    intermediates = [
        x509.load_pem_x509_certificate(c.encode())
        for c in testcase["untrusted_intermediates"]
    ]
    time = datetime.datetime.fromisoformat(testcase["validation_time"])

    def bench():
        verifier = (
            x509.verification.PolicyBuilder()
            .store(store)
            .time(time)
            .build_server_verifier(x509.DNSName("docs.python.org"))
        )
        verifier.verify(leaf, intermediates)

    benchmark(bench)
