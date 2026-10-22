from __future__ import annotations

from types import SimpleNamespace

import pytest

from extensions.python.tool_execute_before._10_unmask_secrets import UnmaskToolSecrets
from helpers import parallel_tools


class _Response:
    message = "done"


@pytest.mark.asyncio
async def test_parallel_execute_applies_hook_mutations_to_tool_args(
    monkeypatch,
) -> None:
    observed = {}

    class FakeTool:
        def __init__(self, args):
            self.args = args

        def get_log_object(self):
            return None

        async def before_execution(self, **kwargs):
            pass

        async def execute(self, **kwargs):
            observed["tool_args"] = self.args
            observed["kwargs"] = kwargs
            return _Response()

        async def after_execution(self, response):
            pass

    class FakeAgent:
        context = SimpleNamespace()
        loop_data = SimpleNamespace(current_tool=None)

        def get_tool(self, **kwargs):
            return FakeTool(kwargs["args"])

        async def handle_intervention(self):
            pass

    async def unmask_secret(*_args, **kwargs):
        if not _args or _args[0] != "tool_execute_before":
            return
        tool_args = kwargs["tool_args"]
        tool_args["code"] = tool_args["code"].replace(
            "§§secret(TOKEN)", "resolved-secret"
        )

    monkeypatch.setattr(parallel_tools, "call_extensions_async", unmask_secret)
    worker_args = {"code": "curl -H 'Authorization: Bearer §§secret(TOKEN)'"}

    result = await parallel_tools.execute_tool_call(
        FakeAgent(),  # type: ignore[arg-type]
        "code_execution_tool",
        worker_args,
    )

    assert result == "done"
    assert observed["tool_args"] is worker_args
    assert observed["tool_args"]["code"] == (
        "curl -H 'Authorization: Bearer resolved-secret'"
    )
    assert observed["kwargs"]["code"] == (
        "curl -H 'Authorization: Bearer resolved-secret'"
    )


@pytest.mark.asyncio
async def test_parallel_tool_arguments_unmask_nested_secret_placeholders(
    monkeypatch,
) -> None:
    observed = {}

    class FakeSecretsManager:
        def replace_placeholders(self, value):
            return value.replace("§§secret(FIXTURE_KEY)", "synthetic-fixture-value")

    class FakeContext:
        def get_data(self, _key):
            return None

    class FakeTool:
        def __init__(self, args):
            self.args = args

        def get_log_object(self):
            return None

        async def before_execution(self, **_kwargs):
            pass

        async def execute(self, **kwargs):
            observed["access_token"] = kwargs["access_token"]
            observed["tool_calls"] = kwargs["tool_calls"]
            return _Response()

        async def after_execution(self, _response):
            pass

    class FakeAgent:
        context = FakeContext()
        loop_data = SimpleNamespace(current_tool=None)

        def get_tool(self, **kwargs):
            return FakeTool(kwargs["args"])

        async def handle_intervention(self):
            pass

    monkeypatch.setattr(
        "extensions.python.tool_execute_before._10_unmask_secrets.get_secrets_manager",
        lambda _context: FakeSecretsManager(),
    )

    async def run_before_extension(event, agent, **kwargs):
        if event == "tool_execute_before":
            await UnmaskToolSecrets(agent).execute(**kwargs)

    monkeypatch.setattr(parallel_tools, "call_extensions_async", run_before_extension)
    tool_args = {
        "access_token": "Bearer §§secret(FIXTURE_KEY)",
        "tool_calls": [
            {
                "tool_name": "mock_lookup",
                "tool_args": {
                    "headers": {"Authorization": "Bearer §§secret(FIXTURE_KEY)"},
                    "values": ["prefix-§§secret(FIXTURE_KEY)", 7],
                },
            }
        ]
    }

    result = await parallel_tools.execute_tool_call(
        FakeAgent(),  # type: ignore[arg-type]
        "mock_parallel",
        tool_args,
    )

    assert result == "done"
    assert observed["access_token"] == "Bearer synthetic-fixture-value"
    assert observed["tool_calls"] == [
        {
            "tool_name": "mock_lookup",
            "tool_args": {
                "headers": {"Authorization": "Bearer synthetic-fixture-value"},
                "values": ["prefix-synthetic-fixture-value", 7],
            },
        }
    ]
