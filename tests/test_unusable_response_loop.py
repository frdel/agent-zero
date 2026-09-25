from pathlib import Path
from types import SimpleNamespace

from helpers.errors import HandledException
from helpers.files import read_prompt_file
from helpers.settings import get_default_settings, normalize_settings
from extensions.python._functions.agent.Agent.hist_add_warning.end import (
    _90_stop_unusable_response_loop as response_loop,
)


class FakeLog:
    def __init__(self):
        self.entries = []

    def log(self, **entry):
        self.entries.append(entry)


def _agent():
    prompts = {
        "fw.msg_misformat.md": "misformatted",
        "fw.msg_repeat.md": "repeated",
        "fw.msg_empty_response.md": "empty response",
        "fw.msg_reasoning_only.md": "reasoning only",
        "fw.msg_thoughts_fallback.md": "thoughts fallback",
        "fw.msg_output_limit.md": "output limit",
    }

    def read_prompt(name, **kwargs):
        if name == "fw.msg_unusable_response_limit.md":
            return f"stopped at {kwargs['limit']}"
        return prompts[name]

    return SimpleNamespace(
        loop_data=SimpleNamespace(iteration=0, params_persistent={}),
        context=SimpleNamespace(log=FakeLog()),
        read_prompt=read_prompt,
    )


def _run(extension, agent, message):
    data = {"args": (agent, message), "kwargs": {}, "exception": None}
    extension.execute(data=data)
    return data


def test_stops_at_configured_failure_limit(monkeypatch):
    monkeypatch.setattr(
        response_loop,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 3},
    )
    agent = _agent()
    extension = response_loop.StopUnusableResponseLoop(agent=agent)

    assert _run(extension, agent, "misformatted")["exception"] is None

    agent.loop_data.iteration = 1
    assert _run(extension, agent, "empty response")["exception"] is None

    agent.loop_data.iteration = 2
    data = _run(extension, agent, "repeated")

    assert isinstance(data["exception"], HandledException)
    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 3
    assert agent.context.log.entries == [
        {"type": "warning", "content": "stopped at 3"}
    ]


def test_nonconsecutive_failure_starts_a_new_recovery_window(monkeypatch):
    monkeypatch.setattr(
        response_loop,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 2},
    )
    agent = _agent()
    extension = response_loop.StopUnusableResponseLoop(agent=agent)

    assert _run(extension, agent, {"structured": "warning"})["exception"] is None
    _run(extension, agent, "misformatted")
    agent.loop_data.iteration = 2
    data = _run(extension, agent, "repeated")

    assert data["exception"] is None
    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 1


def test_reasoning_only_warning_counts_toward_the_limit(monkeypatch):
    monkeypatch.setattr(
        response_loop,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 1},
    )
    agent = _agent()
    extension = response_loop.StopUnusableResponseLoop(agent=agent)

    data = _run(extension, agent, "reasoning only")

    assert isinstance(data["exception"], HandledException)
    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 1


def test_thoughts_fallback_warning_counts_toward_the_limit(monkeypatch):
    monkeypatch.setattr(
        response_loop,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 1},
    )
    agent = _agent()
    extension = response_loop.StopUnusableResponseLoop(agent=agent)

    data = _run(extension, agent, "thoughts fallback")

    assert isinstance(data["exception"], HandledException)
    assert agent.loop_data.params_persistent[response_loop.STATE_KEY]["count"] == 1


def test_general_settings_expose_the_default_failure_limit():
    settings = get_default_settings()
    assert settings["max_consecutive_unusable_responses"] == 5
    settings["max_consecutive_unusable_responses"] = 0
    assert normalize_settings(settings)["max_consecutive_unusable_responses"] == 1

    html = Path("webui/components/settings/agent/agent.html").read_text()
    assert (
        'x-model.number="$store.settings.settings.max_consecutive_unusable_responses"'
        in html
    )
    assert "after 3 consecutive" in read_prompt_file(
        "fw.msg_unusable_response_limit.md", ["prompts"], limit=3
    )


def test_output_limit_warning_counts_toward_the_limit(monkeypatch):
    monkeypatch.setattr(
        response_loop,
        "get_settings",
        lambda: {"max_consecutive_unusable_responses": 1},
    )
    agent = _agent()
    extension = response_loop.StopUnusableResponseLoop(agent=agent)

    data = _run(extension, agent, "output limit")

    assert isinstance(data["exception"], HandledException)
