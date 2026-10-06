from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_agent_profile_switching_has_no_running_guard() -> None:
    endpoint = PROJECT_ROOT.joinpath("api", "agent_profile_set.py").read_text(encoding="utf-8")
    mixin = PROJECT_ROOT.joinpath(
        "plugins", "_model_config", "webui", "switcher-mixin.js"
    ).read_text(encoding="utf-8")

    assert "is_running" not in endpoint
    assert "409" not in endpoint
    assert "Agent profile can be changed after the current run finishes." not in endpoint
    assert "selectedContext?.running" not in mixin
    assert "Agent profile can be changed after the current run finishes." not in mixin


def test_agent_profile_dropdown_items_stay_enabled_during_run() -> None:
    switcher = PROJECT_ROOT.joinpath(
        "plugins",
        "_model_config",
        "extensions",
        "webui",
        "chat-input-progress-start",
        "model-switcher.html",
    ).read_text(encoding="utf-8")

    assert ':disabled="$store.modelConfig.agentProfileSaving"' in switcher
    assert "selectedContext.running" not in switcher
