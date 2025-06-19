import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import os
import asyncio
import pytest
from httpx import AsyncClient

import httpx
from asgi_lifespan import LifespanManager
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from src.main import app
from src.models import init_db


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    await init_db()
    yield
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.mark.asyncio
async def test_healthcheck():
    async with LifespanManager(app):
        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/ga/healthcheck")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_run_report_dry_run():
    async with LifespanManager(app):
        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post(
                "/ga/run_report",
                json={"property_id": "123", "dims": ["a"], "mets": ["b"], "dry_run": True},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dry_run"


@pytest.mark.asyncio
async def test_reports_empty():
    async with LifespanManager(app):
        async with AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/reports")
        assert resp.status_code == 200
        assert resp.json() == []
