import asyncio
import logging
import pathlib
import ssl
import typing
from dataclasses import dataclass
from tempfile import TemporaryDirectory

import pytest
import pytest_asyncio
from aiohttp import web

MKCERT_CA_NOT_INSTALLED = b"local CA is not installed in the system trust store"
MKCERT_CA_ALREADY_INSTALLED = b"local CA is now installed in the system trust store"
SUBPROCESS_TIMEOUT = 5

# To avoid getting the SSLContext injected by truststore.
original_SSLContext = ssl.SSLContext


successful_hosts = pytest.mark.parametrize("host", ["example.com", "1.1.1.1"])

logger = logging.getLogger("aiohttp.web")


@pytest_asyncio.fixture
async def mkcert() -> typing.AsyncIterator[None]:
    async def is_mkcert_available() -> bool:
        try:
            p = await asyncio.create_subprocess_exec(
                "mkcert",
                "-help",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return False
        await asyncio.wait_for(p.wait(), timeout=SUBPROCESS_TIMEOUT)
        return p.returncode == 0

    # Checks to see if mkcert is available at all.
    if not await is_mkcert_available():
        pytest.skip("Install mkcert to run custom CA tests")

    # Now we attempt to install the root certificate
    # to the system trust store. Keep track if we should
    # call mkcert -uninstall at the end.
    should_mkcert_uninstall = False
    try:
        p = await asyncio.create_subprocess_exec(
            "mkcert",
            "-install",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await p.wait()
        assert p.returncode == 0

        # See if the root cert was installed for the first
        # time, if so we want to leave no trace.
        stdout, _ = await p.communicate()
        should_mkcert_uninstall = MKCERT_CA_ALREADY_INSTALLED in stdout

        yield

    finally:
        # Only uninstall mkcert root cert if it wasn't
        # installed before our attempt to install.
        if should_mkcert_uninstall:
            p = await asyncio.create_subprocess_exec(
                "mkcert",
                "-uninstall",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await p.wait()


@dataclass
class CertFiles:
    key_file: pathlib.Path
    cert_file: pathlib.Path


@pytest_asyncio.fixture
async def mkcert_certs(mkcert: None) -> typing.AsyncIterator[CertFiles]:
    with TemporaryDirectory() as tmp_dir:
        # Create the structure we'll eventually return
        # as long as mkcert succeeds in creating the certs.
        tmpdir_path = pathlib.Path(tmp_dir)
        certs = CertFiles(
            cert_file=tmpdir_path / "localhost.pem",
            key_file=tmpdir_path / "localhost-key.pem",
        )

        cmd = (
            "mkcert"
            f" -cert-file {certs.cert_file}"
            f" -key-file {certs.key_file}"
            " localhost"
        )
        p = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await asyncio.wait_for(p.wait(), timeout=SUBPROCESS_TIMEOUT)

        # Check for any signs that mkcert wasn't able to issue certs
        # or that the CA isn't installed
        stdout, _ = await p.communicate()
        if MKCERT_CA_NOT_INSTALLED in stdout or p.returncode != 0:
            raise RuntimeError(
                f"mkcert couldn't issue certificates "
                f"(exited with {p.returncode}): {stdout.decode()}"
            )

        yield certs


@dataclass
class Server:
    host: str
    port: int

    @property
    def base_url(self) -> str:
        return f"https://{self.host}:{self.port}"


@pytest_asyncio.fixture(scope="function")
async def server(mkcert_certs: CertFiles) -> typing.AsyncIterator[Server]:
    async def handler(request: web.Request) -> web.Response:
        # Check the request was served over HTTPS.
        assert request.scheme == "https"

        return web.Response(status=200)

    app = web.Application()
    app.add_routes([web.get("/", handler)])

    ctx = original_SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # We use str(pathlib.Path) here because PyPy doesn't accept Path objects.
    # TODO: This is a bug in PyPy and should be reported to them, but their
    # GitLab instance was offline when we found this bug. :'(
    ctx.load_cert_chain(
        certfile=str(mkcert_certs.cert_file),
        keyfile=str(mkcert_certs.key_file),
    )

    # we need keepalive_timeout=0
    # see https://github.com/aio-libs/aiohttp/issues/5426
    runner = web.AppRunner(app, keepalive_timeout=0)
    await runner.setup()
    port = 9999  # Arbitrary choice.
    site = web.TCPSite(runner, ssl_context=ctx, port=port)

    await site.start()
    try:
        yield Server(host="localhost", port=port)
    finally:
        await site.stop()
        await runner.cleanup()
