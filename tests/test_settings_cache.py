import copy
from contextvars import Context, copy_context

import pytest

from helpers import extension, settings


def test_version_cache_scope_nests_and_expires_in_inherited_contexts(monkeypatch):
    reads = []

    def get_version():
        reads.append("fresh")
        return "fresh"

    monkeypatch.setattr(settings.git, "get_version", get_version)

    with settings.version_cache_scope("outer"):
        outer_context = copy_context()
        with pytest.raises(RuntimeError, match="scope failed"):
            with settings.version_cache_scope():
                assert settings._get_version() == "outer"
                with settings.version_cache_scope("inner"):
                    assert settings._get_version() == "inner"
                    inner_context = copy_context()
                assert settings._get_version() == "outer"
                raise RuntimeError("scope failed")
        assert settings._get_version() == "outer"
        assert Context().run(settings._get_version) == "fresh"

    assert settings._get_version() == "fresh"
    assert outer_context.run(settings._get_version) == "fresh"
    assert inner_context.run(settings._get_version) == "fresh"
    assert inner_context.run(settings._get_version) == "fresh"
    assert reads == ["fresh"] * 5


@pytest.mark.parametrize("fail_apply", [False, True])
def test_settings_apply_reuses_only_version_and_restores_scope(monkeypatch, fail_apply):
    configured = settings.get_default_settings()
    version = "v1"
    version_reads = []
    sensitive_reads = []
    inherited = []

    def get_version():
        version_reads.append(version)
        return version

    def load_sensitive(current):
        sensitive_reads.append(current)
        current["auth_password"] = str(len(sensitive_reads))

    def apply(previous, browser_timezone):
        nonlocal version
        assert previous is configured
        assert browser_timezone == "Europe/Rome"
        for index in range(3):
            current = settings.get_settings()
            assert current["version"] == "v1"
            assert current["auth_password"] == str(index + 1)
        assert version_reads == ["v1"]
        version = "v2"
        assert Context().run(settings._get_version) == "v2"
        assert settings._get_version() == "v1"
        inherited.append(copy_context())
        if fail_apply:
            raise RuntimeError("apply failed")

    monkeypatch.setattr(settings.git, "get_version", get_version)
    monkeypatch.setattr(settings, "_settings", configured)
    monkeypatch.setattr(settings, "_read_settings_file", lambda: configured)
    monkeypatch.setattr(settings, "_write_settings_file", lambda current: None)
    monkeypatch.setattr(settings, "_load_sensitive_settings", load_sensitive)
    monkeypatch.setattr(settings, "_apply_settings", apply)

    if fail_apply:
        with pytest.raises(RuntimeError, match="apply failed"):
            settings.set_settings(configured, browser_timezone="Europe/Rome")
    else:
        saved = settings.set_settings(configured, browser_timezone="Europe/Rome")
        assert saved["version"] == "v2"
        assert saved["auth_password"] == "4"

    assert settings._get_version() == "v2"
    assert inherited[0].run(settings._get_version) == "v2"
    version = "v3"
    assert settings.set_settings(configured, apply=False)["version"] == "v3"


def test_settings_snapshot_is_limited_to_one_prompt(monkeypatch):
    configured = settings.get_default_settings()
    configured["api_keys"] = {"provider": "secret"}
    versions = iter(["first", "second", "third", "fourth"])
    calls = 0

    def defaults():
        nonlocal calls
        calls += 1
        result = copy.deepcopy(configured)
        result["version"] = next(versions)
        return result

    monkeypatch.setattr(settings, "_settings", configured)
    monkeypatch.setattr(settings, "_read_settings_file", lambda: configured)
    monkeypatch.setattr(settings, "get_default_settings", defaults)
    monkeypatch.setattr(settings, "_load_sensitive_settings", lambda _value: None)

    token = settings.begin_prompt_settings_snapshot()
    try:
        configured["workdir_show"] = False
        first = settings.get_settings_for_prompt()
        second = settings.get_settings_for_prompt()

        assert calls == 1
        assert first == second
        assert first["workdir_show"] is True
        assert first is not second
        assert first["api_keys"] is not second["api_keys"]

        first["api_keys"]["provider"] = "masked"
        assert settings.get_settings_for_prompt()["api_keys"]["provider"] == "secret"

        current = settings.get_settings()
        assert current["version"] == "second"
        assert current["workdir_show"] is False
        assert settings.get_settings_for_prompt()["workdir_show"] is True

        reloaded = settings.reload_settings()
        assert reloaded["version"] == "third"
        assert reloaded["workdir_show"] is False
        assert settings.get_settings_for_prompt() == reloaded
    finally:
        settings.end_prompt_settings_snapshot(token)

    refreshed = settings.get_settings()
    assert refreshed["workdir_show"] is False
    assert refreshed["version"] == "fourth"
    assert calls == 4


def test_prompt_snapshot_hooks_are_registered_and_paired():
    start = next(
        cls
        for cls in extension._get_extension_classes(  # type: ignore[attr-defined]
            "_functions/agent/Agent/prepare_prompt/start"
        )
        if cls.__name__ == "SnapshotPromptSettings"
    )
    end = next(
        cls
        for cls in extension._get_extension_classes(  # type: ignore[attr-defined]
            "_functions/agent/Agent/prepare_prompt/end"
        )
        if cls.__name__ == "RestorePromptSettings"
    )
    previous = settings._prompt_settings_snapshot.get()
    data = {}

    start(agent=None).execute(data=data)
    try:
        assert settings._prompt_settings_snapshot.get() is not None
    finally:
        end(agent=None).execute(data=data)

    assert settings._prompt_settings_snapshot.get() is previous
