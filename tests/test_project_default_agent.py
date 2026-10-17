import json
from pathlib import Path

import initialize
from agent import AgentConfig, AgentContext
from helpers import projects, settings, subagents
from helpers import state_monitor_integration

from tests.test_projects import _prepare_project_tree


GLOBAL_DEFAULT = "global-default"
CAPTAIN = "captain"


def _make_context(context_id: str, profile: str) -> AgentContext:
    AgentContext.remove(context_id)
    return AgentContext(
        config=AgentConfig(mcp_servers="", profile=profile),
        id=context_id,
        set_current=False,
    )


def _stub_reconcile_deps(
    monkeypatch,
    available_profiles: dict[str, str],
) -> None:
    monkeypatch.setattr(
        subagents,
        "get_available_agents_dict",
        lambda _project_name: {
            name: subagents.SubAgentListItem(name=name)
            for name in available_profiles
        },
    )
    monkeypatch.setattr(
        initialize,
        "initialize_agent",
        lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", GLOBAL_DEFAULT),
        ),
    )
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: {"agent_profile": GLOBAL_DEFAULT},
    )


def _write_default_agent_file(tmp_path: Path, payload) -> None:
    meta = tmp_path / "usr" / "projects" / "demo" / ".a0proj"
    meta.mkdir(parents=True, exist_ok=True)
    target = meta / "default_agent.json"
    if isinstance(payload, bytes):
        target.write_bytes(payload)
    else:
        target.write_text(json.dumps(payload), encoding="utf-8")


def test_no_default_file_keeps_global_default_profile(monkeypatch, tmp_path: Path) -> None:
    _prepare_project_tree(monkeypatch, tmp_path)
    _stub_reconcile_deps(monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, "other": "other"})
    context = _make_context("ctx-default-agent-no-file", GLOBAL_DEFAULT)

    try:
        assert projects.get_project_default_agent("demo") is None
        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == GLOBAL_DEFAULT
        assert context.agent0.config.profile == GLOBAL_DEFAULT
    finally:
        AgentContext.remove(context.id)


def test_default_file_switches_context_on_global_default(monkeypatch, tmp_path: Path) -> None:
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    context = _make_context("ctx-default-agent-switch", GLOBAL_DEFAULT)

    try:
        assert projects.get_project_default_agent("demo") == CAPTAIN
        assert projects.reconcile_agent_profile(context, "demo") is True
        assert context.config.profile == CAPTAIN
        assert context.agent0.config.profile == CAPTAIN
    finally:
        AgentContext.remove(context.id)


def test_default_file_never_overrides_manual_selection(monkeypatch, tmp_path: Path) -> None:
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch,
        {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN, "manual-pick": "manual-pick"},
    )
    context = _make_context("ctx-default-agent-manual", "manual-pick")

    try:
        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == "manual-pick"
        assert context.agent0.config.profile == "manual-pick"
    finally:
        AgentContext.remove(context.id)


def test_default_naming_unavailable_agent_is_ignored(monkeypatch, tmp_path: Path) -> None:
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT})
    context = _make_context("ctx-default-agent-unavailable", GLOBAL_DEFAULT)

    try:
        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == GLOBAL_DEFAULT
        assert context.agent0.config.profile == GLOBAL_DEFAULT
    finally:
        AgentContext.remove(context.id)


def test_malformed_default_file_is_treated_as_absent(monkeypatch, tmp_path: Path) -> None:
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, b"not json at all")
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    context = _make_context("ctx-default-agent-malformed", GLOBAL_DEFAULT)

    try:
        assert projects.get_project_default_agent("demo") is None
        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == GLOBAL_DEFAULT
        assert context.agent0.config.profile == GLOBAL_DEFAULT
    finally:
        AgentContext.remove(context.id)


def test_disabled_global_default_falls_back_to_project_default(monkeypatch, tmp_path: Path) -> None:
    """Sysop pilot case: global default profile is disabled in the project;
    reconcile's fallback branch must prefer the project default agent over
    agent0/first-in-dict."""
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch,
        {CAPTAIN: CAPTAIN, "agent0": "agent0", "someother": "someother"},
    )
    context = _make_context("ctx-default-agent-fallback", GLOBAL_DEFAULT)

    try:
        assert projects.reconcile_agent_profile(context, "demo") is True
        assert context.config.profile == CAPTAIN
        assert context.agent0.config.profile == CAPTAIN
    finally:
        AgentContext.remove(context.id)


def test_manually_set_flag_blocks_default_agent_switch(monkeypatch, tmp_path: Path) -> None:
    """Explicit per-chat selection (agent_profile_set) sets a manual flag;
    reconcile must never override it with the project default."""
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    context = _make_context("ctx-default-agent-manual-flag", GLOBAL_DEFAULT)
    context.set_data("agent_profile_manually_set", True)

    try:
        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == GLOBAL_DEFAULT
        assert context.agent0.config.profile == GLOBAL_DEFAULT
    finally:
        AgentContext.remove(context.id)


def test_unavailable_profile_with_available_global_default_switches_to_project_default(
    monkeypatch, tmp_path: Path
) -> None:
    """Context runs an unavailable profile X while the global default IS
    available; a configured+available project default must still win in the
    fallback branch."""
    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    context = _make_context("ctx-default-agent-unavailable-x", "profile-x")

    try:
        assert projects.reconcile_agent_profile(context, "demo") is True
        assert context.config.profile == CAPTAIN
        assert context.agent0.config.profile == CAPTAIN
    finally:
        AgentContext.remove(context.id)


def test_agent_command_sets_manual_flag_and_blocks_default_switch(
    monkeypatch, tmp_path: Path
) -> None:
    """The /agent integration command is an explicit selection path: it must
    set agent_profile_manually_set so a later reconcile sweep cannot override
    the selection with the project default agent."""
    from helpers import integration_commands

    _prepare_project_tree(monkeypatch, tmp_path)
    _write_default_agent_file(tmp_path, {"agent": CAPTAIN})
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    monkeypatch.setattr(
        subagents,
        "get_all_agents_list",
        lambda: [{"key": GLOBAL_DEFAULT, "label": "Global"}],
    )
    monkeypatch.setattr(
        integration_commands, "save_tmp_chat", lambda _context: None
    )
    monkeypatch.setattr(
        integration_commands,
        "mark_dirty_for_context",
        lambda _context_id, **_kwargs: None,
    )
    context = _make_context("ctx-default-agent-slash-command", CAPTAIN)

    try:
        result = integration_commands._handle_agent(context, GLOBAL_DEFAULT)
        assert "Global" in result
        assert context.config.profile == GLOBAL_DEFAULT
        assert context.agent0.config.profile == GLOBAL_DEFAULT
        assert context.get_data("agent_profile_manually_set") is True

        assert projects.reconcile_agent_profile(context, "demo") is False
        assert context.config.profile == GLOBAL_DEFAULT
    finally:
        AgentContext.remove(context.id)


def test_connector_create_context_sets_flag_before_activate_project(
    monkeypatch, tmp_path: Path
) -> None:
    """The A0 connector's create_context is an explicit-selection path: with
    agent_profile provided, the manual flag must be set BEFORE activate_project
    triggers reconciliation."""
    from plugins._a0_connector.helpers import chat_context
    from plugins._model_config.helpers import model_config as mc_model_config

    _prepare_project_tree(monkeypatch, tmp_path)
    _stub_reconcile_deps(
        monkeypatch, {GLOBAL_DEFAULT: GLOBAL_DEFAULT, CAPTAIN: CAPTAIN}
    )
    monkeypatch.setattr(
        initialize, "initialize_agent", lambda override_settings=None: AgentConfig(
            mcp_servers="",
            profile=(override_settings or {}).get("agent_profile", GLOBAL_DEFAULT),
        )
    )
    monkeypatch.setattr(settings, "get_settings", lambda: {})
    monkeypatch.setattr(
        state_monitor_integration, "mark_dirty_all", lambda **_kwargs: None
    )
    monkeypatch.setattr(mc_model_config, "is_chat_override_allowed", lambda _agent: False)

    flag_at_activate: list[bool] = []

    def _record_activate(context_id, name, **_kwargs):
        from agent import AgentContext as AC

        ctx = AC.get(context_id)
        flag_at_activate.append(bool(ctx and ctx.get_data("agent_profile_manually_set")))

    monkeypatch.setattr(projects, "activate_project", _record_activate)

    try:
        context = chat_context.create_context(
            agent_profile=CAPTAIN, project_name="demo"
        )
        assert context.config.profile == CAPTAIN
        assert context.get_data("agent_profile_manually_set") is True
        assert flag_at_activate == [True]
    finally:
        AgentContext.remove(context.id)
