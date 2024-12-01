import asyncio
import ssl

import pytest
import requests
import urllib3
from aiohttp import ClientSession

import truststore
from tests import SSLContextAdapter
from tests.conftest import Server


@pytest.mark.asyncio
async def test_urllib3_custom_ca(server: Server) -> None:
    def test_urllib3():
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with urllib3.PoolManager(ssl_context=ctx) as client:
            resp = client.request("GET", server.base_url)
        assert resp.status == 200

    thread = asyncio.to_thread(test_urllib3)
    await thread


@pytest.mark.asyncio
async def test_aiohttp_custom_ca(server: Server) -> None:
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    async with ClientSession() as client:
        resp = await client.get(server.base_url, ssl=ctx)
        assert resp.status == 200


@pytest.mark.asyncio
async def test_requests_custom_ca(server: Server) -> None:
    def test_requests():
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with requests.Session() as http:
            http.mount("https://", SSLContextAdapter(ssl_context=ctx))
            resp = http.request("GET", server.base_url)
        assert resp.status_code == 200

    thread = asyncio.to_thread(test_requests)
    await thread
