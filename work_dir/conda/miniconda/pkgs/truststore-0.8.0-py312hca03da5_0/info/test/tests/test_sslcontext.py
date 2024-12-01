import json
import ssl

import pytest
import urllib3
from urllib3.exceptions import InsecureRequestWarning, SSLError

import truststore


def test_minimum_maximum_version():
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.maximum_version = ssl.TLSVersion.TLSv1_2

    with urllib3.PoolManager(ssl_context=ctx) as http:
        resp = http.request("GET", "https://howsmyssl.com/a/check")
        data = json.loads(resp.data)
        assert data["tls_version"] == "TLS 1.2"

    assert ctx.minimum_version in (
        ssl.TLSVersion.TLSv1_2,
        ssl.TLSVersion.MINIMUM_SUPPORTED,
    )
    assert ctx.maximum_version == ssl.TLSVersion.TLSv1_2


def test_check_hostname_false():
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED

    with urllib3.PoolManager(ssl_context=ctx, retries=False) as http:
        with pytest.raises(SSLError) as e:
            http.request("GET", "https://wrong.host.badssl.com/")
        assert "match" in str(e.value)


def test_verify_mode_cert_none():
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE

    with urllib3.PoolManager(ssl_context=ctx) as http, pytest.warns(
        InsecureRequestWarning
    ) as w:
        http.request("GET", "https://expired.badssl.com/")
    assert len(w) == 1
