import asyncio
import ssl

import httpx
import pytest
import requests
import urllib3
from aiohttp import ClientSession

import truststore
from tests.conftest import Server, successful_hosts


@pytest.fixture(scope="function")
def inject_truststore():
    truststore.inject_into_ssl()
    try:
        yield
    finally:
        truststore.extract_from_ssl()


def test_inject_and_extract():
    assert ssl.SSLContext is not truststore.SSLContext
    try:
        original_SSLContext = ssl.SSLContext

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx._ctx, original_SSLContext)

        truststore.inject_into_ssl()
        assert ssl.SSLContext is truststore.SSLContext
        assert urllib3.util.ssl_.SSLContext is truststore.SSLContext

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx._ctx, original_SSLContext)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx, truststore.SSLContext)

        ctx = ssl.create_default_context()
        assert isinstance(ctx, truststore.SSLContext)

        truststore.extract_from_ssl()
        assert ssl.SSLContext is original_SSLContext
        assert urllib3.util.ssl_.SSLContext is original_SSLContext

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx._ctx, original_SSLContext)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert isinstance(ctx, original_SSLContext)

        ctx = ssl.create_default_context()
        assert isinstance(ctx, original_SSLContext)
    finally:
        truststore.extract_from_ssl()


@successful_hosts
@pytest.mark.usefixtures("inject_truststore")
def test_success_with_inject(host):
    with urllib3.PoolManager() as http:
        resp = http.request("GET", f"https://{host}")
        assert resp.status == 200


@pytest.mark.usefixtures("inject_truststore")
def test_inject_set_values():
    ctx = ssl.create_default_context()
    assert isinstance(ctx, truststore.SSLContext)

    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


@pytest.mark.asyncio
@pytest.mark.usefixtures("inject_truststore")
async def test_urllib3_works_with_inject(server: Server) -> None:
    def test_urllib3():
        with urllib3.PoolManager() as client:
            resp = client.request("GET", server.base_url)
        assert resp.status == 200

    thread = asyncio.to_thread(test_urllib3)
    await thread


@pytest.mark.asyncio
@pytest.mark.usefixtures("inject_truststore")
async def test_aiohttp_works_with_inject(server: Server) -> None:
    async with ClientSession() as client:
        resp = await client.get(server.base_url)
        assert resp.status == 200


@pytest.mark.asyncio
@pytest.mark.usefixtures("inject_truststore")
async def test_requests_works_with_inject(server: Server) -> None:
    def test_requests():
        with requests.Session() as http:
            resp = http.request("GET", server.base_url)
        assert resp.status_code == 200

    thread = asyncio.to_thread(test_requests)
    await thread


@pytest.mark.asyncio
@pytest.mark.usefixtures("inject_truststore")
async def test_sync_httpx_works_with_inject(server: Server) -> None:
    def test_httpx():
        with httpx.Client() as client:
            resp = client.request("GET", server.base_url)
            assert resp.status_code == 200

    thread = asyncio.to_thread(test_httpx)
    await thread


@pytest.mark.usefixtures("inject_truststore")
@pytest.mark.asyncio
async def test_async_httpx_works_with_inject(server: Server) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.request("GET", server.base_url)
        assert resp.status_code == 200
