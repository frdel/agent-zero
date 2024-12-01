import asyncio
import importlib
import os
import platform
import socket
import ssl
import tempfile
from dataclasses import dataclass
from operator import attrgetter
from unittest import mock

import aiohttp
import aiohttp.client_exceptions
import pytest
import requests
import trustme
import urllib3
import urllib3.exceptions
from OpenSSL.crypto import X509

import truststore
from tests import SSLContextAdapter

pytestmark = pytest.mark.flaky

# Make sure the httpserver doesn't hang
# if the client drops the connection due to a cert verification error
socket.setdefaulttimeout(10)

successful_hosts = pytest.mark.parametrize("host", ["example.com", "1.1.1.1"])


@dataclass
class FailureHost:
    host: str
    error_messages: list[str]


failure_hosts_list = [
    FailureHost(
        host="wrong.host.badssl.com",
        error_messages=[
            # OpenSSL
            "Hostname mismatch, certificate is not valid for 'wrong.host.badssl.com'",
            # macOS
            "certificate name does not match",
            # macOS with revocation checks
            "certificates do not meet pinning requirements",
            # Windows
            "The certificate's CN name does not match the passed value.",
        ],
    ),
    FailureHost(
        host="expired.badssl.com",
        error_messages=[
            # OpenSSL
            "certificate has expired",
            # macOS
            "“*.badssl.com” certificate is expired",
            # macOS with revocation checks
            "certificates do not meet pinning requirements",
            # Windows
            (
                "A required certificate is not within its validity period when verifying "
                "against the current system clock or the timestamp in the signed file."
            ),
        ],
    ),
    FailureHost(
        host="self-signed.badssl.com",
        error_messages=[
            # OpenSSL
            "self-signed certificate",
            "self signed certificate",
            # macOS
            "“*.badssl.com” certificate is not trusted",
            # macOS with revocation checks
            "certificates do not meet pinning requirements",
            # Windows
            (
                "A certificate chain processed, but terminated in a root "
                "certificate which is not trusted by the trust provider."
            ),
        ],
    ),
    FailureHost(
        host="untrusted-root.badssl.com",
        error_messages=[
            # OpenSSL
            "self-signed certificate in certificate chain",
            "self signed certificate in certificate chain",
            # macOS
            "“BadSSL Untrusted Root Certificate Authority” certificate is not trusted",
            # macOS with revocation checks
            "certificates do not meet pinning requirements",
            # Windows
            (
                "A certificate chain processed, but terminated in a root "
                "certificate which is not trusted by the trust provider."
            ),
        ],
    ),
    FailureHost(
        host="superfish.badssl.com",
        error_messages=[
            # OpenSSL
            "unable to get local issuer certificate",
            # macOS
            "“superfish.badssl.com” certificate is not trusted",
            # macOS with revocation checks
            "certificates do not meet pinning requirements",
            # Windows
            (
                "A certificate chain processed, but terminated in a root "
                "certificate which is not trusted by the trust provider."
            ),
        ],
    ),
]

failure_hosts_no_revocation = pytest.mark.parametrize(
    "failure", failure_hosts_list.copy(), ids=attrgetter("host")
)

if platform.system() != "Linux":
    failure_hosts_list.append(
        FailureHost(
            host="revoked.badssl.com",
            error_messages=[
                # macOS
                # "“revoked.badssl.com” certificate is revoked",
                # Windows
                # "The certificate is revoked.",
                # TODO: Temporary while certificate is expired on badssl.com.
                # Test will start failing against once the certificate is fixed.
                '"revoked.badssl.com","RapidSSL TLS DV RSA Mixed SHA256 2020 CA-1","DigiCert Global Root CA" certificates do not meet pinning requirements',
                "A required certificate is not within its validity period when verifying against the current system clock or the timestamp in the signed file.",
            ],
        )
    )

failure_hosts = pytest.mark.parametrize(
    "failure", failure_hosts_list, ids=attrgetter("host")
)


@pytest.fixture(scope="session")
def trustme_ca():
    ca = trustme.CA()
    yield ca


@pytest.fixture(scope="session")
def httpserver_ssl_context(trustme_ca):
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_cert = trustme_ca.issue_cert("localhost")
    server_cert.configure_cert(server_context)
    return server_context


def connect_to_host(
    host: str, use_server_hostname: bool = True, verify_flags=ssl.VERIFY_CRL_CHECK_CHAIN
):
    with socket.create_connection((host, 443)) as sock:
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if verify_flags and platform.system() != "Linux":
            ctx.verify_flags |= verify_flags
        with ctx.wrap_socket(
            sock, server_hostname=host if use_server_hostname else None
        ):
            pass


@successful_hosts
def test_success(host):
    connect_to_host(host)


@failure_hosts
def test_failures(failure):
    with pytest.raises(ssl.SSLCertVerificationError) as e:
        connect_to_host(failure.host)

    error_repr = repr(e.value)
    assert any(message in error_repr for message in failure.error_messages), error_repr


@failure_hosts_no_revocation
def test_failures_without_revocation_checks(failure):
    # On macOS with revocation checks required, we get a
    # "certificates do not meet pinning requirements"
    # error for some of the badssl certs. So let's also test
    # with revocation checks disabled and make sure we get the
    # expected error messages in that case.
    with pytest.raises(ssl.SSLCertVerificationError) as e:
        connect_to_host(failure.host, verify_flags=None)

    error_repr = repr(e.value)
    assert any(message in error_repr for message in failure.error_messages), error_repr


@successful_hosts
def test_sslcontext_api_success(host):
    if host == "1.1.1.1":
        pytest.skip("urllib3 doesn't pass server_hostname for IP addresses")

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with urllib3.PoolManager(ssl_context=ctx, retries=5) as http:
        resp = http.request("GET", f"https://{host}")
    assert resp.status == 200
    assert len(resp.data) > 0


@successful_hosts
@pytest.mark.asyncio
async def test_sslcontext_api_success_async(host):
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    async with aiohttp.ClientSession() as http:
        resp = await http.request("GET", f"https://{host}", ssl=ctx)

        assert resp.status == 200
        assert len(await resp.text()) > 0
    # workaround https://github.com/aio-libs/aiohttp/issues/5426
    await asyncio.sleep(0.2)


@failure_hosts
def test_sslcontext_api_failures(failure):
    host = failure.host
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if platform.system() != "Linux":
        ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_CHAIN
    with urllib3.PoolManager(ssl_context=ctx) as http:
        with pytest.raises(urllib3.exceptions.SSLError) as e:
            http.request("GET", f"https://{host}", retries=False)

    assert "cert" in repr(e.value).lower() and "verif" in repr(e.value).lower()


@failure_hosts
@pytest.mark.asyncio
async def test_sslcontext_api_failures_async(failure):
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if platform.system() != "Linux":
        ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_CHAIN
    async with aiohttp.ClientSession() as http:
        with pytest.raises(
            aiohttp.client_exceptions.ClientConnectorCertificateError
        ) as e:
            await http.request("GET", f"https://{failure.host}", ssl=ctx)

    # workaround https://github.com/aio-libs/aiohttp/issues/5426
    await asyncio.sleep(0.2)

    assert "cert" in repr(e.value).lower() and "verif" in repr(e.value).lower()


@successful_hosts
def test_requests_sslcontext_api_success(host):
    if host == "1.1.1.1":
        pytest.skip("urllib3 doesn't pass server_hostname for IP addresses")

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    with requests.Session() as http:
        http.mount("https://", SSLContextAdapter(ssl_context=ctx))
        resp = http.request("GET", f"https://{host}")

    assert resp.status_code == 200
    assert len(resp.content) > 0


@failure_hosts
def test_requests_sslcontext_api_failures(failure):
    host = failure.host

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if platform.system() != "Linux":
        ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_CHAIN

    with requests.Session() as http:
        http.mount("https://", SSLContextAdapter(ssl_context=ctx))

        with pytest.raises(requests.exceptions.SSLError) as e:
            http.request("GET", f"https://{host}")

    assert "cert" in repr(e.value).lower() and "verif" in repr(e.value).lower()


def test_trustme_cert(trustme_ca, httpserver):
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    trustme_ca.configure_trust(ctx)

    httpserver.expect_request("/", method="GET").respond_with_json({})

    with urllib3.PoolManager(ssl_context=ctx) as http:
        resp = http.request("GET", httpserver.url_for("/"))
    assert resp.status == 200
    assert len(resp.data) > 0


def test_trustme_cert_loaded_via_capath(trustme_ca, httpserver):
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    with tempfile.TemporaryDirectory() as capath:
        with open(f"{capath}/cert.pem", "wb") as certfile:
            certfile.write(trustme_ca.cert_pem.bytes())
        cert_hash = X509.from_cryptography(trustme_ca._certificate).subject_name_hash()
        os.symlink(f"{capath}/cert.pem", f"{capath}/{cert_hash:x}.0")
        assert set(os.listdir(capath)) == {"cert.pem", f"{cert_hash:x}.0"}

        ctx.load_verify_locations(capath=capath)

        httpserver.expect_request("/", method="GET").respond_with_json({})

        with urllib3.PoolManager(ssl_context=ctx) as http:
            resp = http.request("GET", httpserver.url_for("/"))
        assert resp.status == 200
        assert len(resp.data) > 0


def test_trustme_cert_still_uses_system_certs(trustme_ca):
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    trustme_ca.configure_trust(ctx)

    with urllib3.PoolManager(ssl_context=ctx) as http:
        resp = http.request("GET", "https://example.com")
    assert resp.status == 200
    assert len(resp.data) > 0


def test_macos_10_7_import_error():
    with mock.patch("platform.mac_ver") as mac_ver:
        # This isn't the full structure, but the version is the first element.
        mac_ver.return_value = ("10.7",)

        with pytest.raises(ImportError) as e:
            # We want to force a fresh import, so either we get it on the
            # first try because the OS isn't macOS or we get it on
            # the call to importlib.reload(...).
            import truststore._macos

            importlib.reload(truststore._macos)

        assert str(e.value) == "Only OS X 10.8 and newer are supported, not 10.7"
