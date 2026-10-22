import os
from pathlib import Path
import sys
import tempfile

repo_root = next(
    parent for parent in Path(__file__).resolve().parents if (parent / "agent.py").is_file()
)
sys.path.insert(0, str(repo_root))

from plugins._orchestrator.helpers.adapters.cursor import CursorCliAdapter
from plugins._orchestrator.helpers.adapters.gemini import _env_file_has_key
from plugins._orchestrator.helpers.adapters.gemini import GeminiCliAdapter
from plugins._orchestrator.helpers.adapters.grok import _toml_has_secret
from plugins._orchestrator.helpers.adapters.grok import GrokBuildAdapter
from plugins._orchestrator.helpers.adapters.base import TerminalAgentAdapter
from plugins._orchestrator.helpers.registry import list_adapters


class DummyAdapter(TerminalAgentAdapter):
    id = "dummy"
    binary = "missing-dummy-agent"

    def auth_status(self, config=None):
        return {"connected": True, "mode": "external", "auth_path": ""}


def test_configured_absolute_binary_is_installed():
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / "agent"
        binary.write_text("#!/bin/sh\n")
        binary.chmod(0o755)

        adapter = DummyAdapter()
        config = {"binary": str(binary)}
        assert adapter.resolve_binary(config) == str(binary)
        assert adapter.is_installed(config)


def test_registry_order_puts_a0_first():
    assert [adapter.id for adapter in list_adapters()] == [
        "a0",
        "codex",
        "claude",
        "cursor",
        "gemini",
        "grok",
        "hermes",
        "opencode",
    ]


def test_adapters_are_status_only():
    for adapter in list_adapters():
        assert not hasattr(adapter, "install_command")
        assert not hasattr(adapter, "build_command")
        assert not hasattr(adapter, "parse_session_id")
        assert not hasattr(adapter, "format_output")


def test_tool_runner_files_are_removed():
    plugin_root = Path(__file__).resolve().parents[1]
    assert not (plugin_root / "tools" / "terminal_agent.py").exists()
    assert not (plugin_root / "helpers" / "runner.py").exists()
    assert not (
        plugin_root / "prompts" / "agent.system.tool.terminal_agent.md"
    ).exists()


def test_claude_defaults_skip_permissions():
    config_text = (Path(__file__).resolve().parents[1] / "default_config.yaml").read_text()
    assert "permission_mode: bypassPermissions" in config_text


def test_grok_defaults_headless_automation():
    config_text = (Path(__file__).resolve().parents[1] / "default_config.yaml").read_text()
    assert "grok:" in config_text
    assert "output_format: json" in config_text
    assert "always_approve: true" in config_text
    assert "no_auto_update: true" in config_text


def test_cursor_defaults_headless_automation():
    config_text = (Path(__file__).resolve().parents[1] / "default_config.yaml").read_text()
    assert "cursor:" in config_text
    assert "binary: agent" in config_text
    assert "output_format: text" in config_text
    assert "force: true" in config_text


def test_cursor_detects_agent_zero_cursor_env_key():
    old_cursor = os.environ.pop("CURSOR_API_KEY", None)
    old_a0_cursor = os.environ.get("API_KEY_CURSOR")
    try:
        os.environ["API_KEY_CURSOR"] = "secret"
        assert CursorCliAdapter().auth_status()["auth_path"] == "API_KEY_CURSOR"
    finally:
        if old_cursor is not None:
            os.environ["CURSOR_API_KEY"] = old_cursor
        if old_a0_cursor is None:
            os.environ.pop("API_KEY_CURSOR", None)
        else:
            os.environ["API_KEY_CURSOR"] = old_a0_cursor


def test_gemini_detects_supported_auth_sources():
    old_value = os.environ.get("GEMINI_API_KEY")
    try:
        os.environ["GEMINI_API_KEY"] = "secret"
        assert GeminiCliAdapter().auth_status()["auth_path"] == "GEMINI_API_KEY"
    finally:
        if old_value is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = old_value

    with tempfile.TemporaryDirectory() as tmp:
        env_path = Path(tmp) / ".env"
        env_path.write_text('GEMINI_API_KEY="secret"\n')
        assert _env_file_has_key(env_path)


def test_grok_env_key_requires_present_environment_value():
    old_value = os.environ.pop("GROK_TEST_KEY", None)
    try:
        assert not _toml_has_secret('env_key = "GROK_TEST_KEY"')
        os.environ["GROK_TEST_KEY"] = "secret"
        assert _toml_has_secret('env_key = "GROK_TEST_KEY"')
    finally:
        if old_value is None:
            os.environ.pop("GROK_TEST_KEY", None)
        else:
            os.environ["GROK_TEST_KEY"] = old_value


def test_grok_detects_agent_zero_xai_env_key():
    old_xai = os.environ.pop("XAI_API_KEY", None)
    old_a0_xai = os.environ.get("API_KEY_XAI")
    try:
        os.environ["API_KEY_XAI"] = "secret"
        assert GrokBuildAdapter().auth_status()["auth_path"] == "API_KEY_XAI"
    finally:
        if old_xai is not None:
            os.environ["XAI_API_KEY"] = old_xai
        if old_a0_xai is None:
            os.environ.pop("API_KEY_XAI", None)
        else:
            os.environ["API_KEY_XAI"] = old_a0_xai


def test_skill_documents_human_setup_loop_and_a0_exception():
    skill_root = Path(__file__).resolve().parents[1] / "skills" / "orchestrator"
    skill_text = (skill_root / "SKILL.md").read_text()
    references = skill_root / "references"
    a0_text = (references / "a0.md").read_text()
    codex_text = (references / "codex.md").read_text()
    claude_text = (references / "claude.md").read_text()
    cursor_text = (references / "cursor.md").read_text()
    gemini_text = (references / "gemini.md").read_text()
    grok_text = (references / "grok.md").read_text()
    hermes_text = (references / "hermes.md").read_text()
    opencode_text = (references / "opencode.md").read_text()

    assert "setup is part of the workflow" in skill_text
    assert "code_execution_remote" in skill_text
    assert "  - memory\n" in skill_text
    assert "`memory` action=save" in skill_text
    assert "own local <agent>" in skill_text
    assert "Agent Zero Docker/container shell" in skill_text
    assert "For orchestrator, the user prefers Claude Code" in skill_text
    assert "Never use Computer Use" in skill_text
    assert "ACP may be available as a community plugin" in skill_text
    assert "## Host CLI Flow" in skill_text
    assert "curl -LsSf https://cli.agent-zero.ai/install.sh | sh" in skill_text
    assert "irm https://cli.agent-zero.ai/install.ps1 | iex" in skill_text
    assert "open a terminal and run:" in skill_text
    assert "press F4 to allow Remote Code Execution" in skill_text
    assert "Press F3 too if the task needs host file writes" in skill_text
    assert "host-code-execution" in skill_text
    assert "not `/a0/usr/workdir`" in skill_text
    assert "## Container Pal Flow" in skill_text
    assert "Keep authentication human-in-the-loop" in skill_text
    assert "show those choices to the user in chat" in skill_text
    assert "do not run the bare CLI as a login fallback" in skill_text
    assert "read `references/a0.md`" in skill_text
    assert "target-selection flow" in skill_text
    assert "## Reference Files" in skill_text
    assert "references/a0.md" in skill_text
    assert "references/codex.md" in skill_text
    assert "references/claude.md" in skill_text
    assert "references/cursor.md" in skill_text
    assert "references/gemini.md" in skill_text
    assert "references/grok.md" in skill_text
    assert "references/hermes.md" in skill_text
    assert "references/opencode.md" in skill_text

    assert "A0 is the setup exception" in a0_text
    assert "--new-chat" in a0_text
    assert "--chat \"$CONTEXT_ID\"" in a0_text

    assert "CODEX_HOME" in codex_text
    assert "codex login" in codex_text
    assert "--dangerously-bypass-approvals-and-sandbox" in codex_text

    assert "claude auth login" in claude_text
    assert "Do not start plain `claude`" in claude_text
    assert "Never start a full-screen CLI/TUI" in skill_text
    assert "Reset that terminal session" in claude_text
    assert "do not press Enter, do not send `/login`" in claude_text
    assert "Do not redirect them to a Docker shell just to choose a menu option" in claude_text
    assert "claude auth login --claudeai" in claude_text
    assert "claude auth login --console" in claude_text
    assert "claude auth login --sso" in claude_text
    assert "Settings > External Services > Secrets Management" in claude_text
    assert "/a0/usr/.env" in claude_text
    assert "ANTHROPIC_API_KEY" in claude_text
    assert "API_KEY_ANTHROPIC" in claude_text
    assert "Do not run bare `claude auth login`" in claude_text

    assert "agent -p --output-format text" in cursor_text
    assert "agent -p --force --output-format text" in cursor_text
    assert "CURSOR_API_KEY" in cursor_text
    assert "API_KEY_CURSOR" in cursor_text
    assert "NO_OPEN_BROWSER=1 agent login" in cursor_text
    assert "agent status" in cursor_text
    assert "not with an invented flag" in cursor_text

    assert 'gemini -p "Respond exactly: TERMINAL_AGENT_SMOKE_OK"' in gemini_text
    assert "--output-format json" in gemini_text
    assert "--approval-mode=yolo" in gemini_text
    assert "--skip-trust" in gemini_text
    assert "GEMINI_API_KEY" in gemini_text
    assert "§§secret(GEMINI_API_KEY)" in gemini_text
    assert "do not source `/a0/usr/.env`" in gemini_text
    assert "Do not append version, help, or smoke commands" in gemini_text
    assert "GOOGLE_APPLICATION_CREDENTIALS" in gemini_text
    assert "Do not start bare `gemini`" in gemini_text

    assert "grok --no-auto-update --cwd \"$WORKDIR\" -p" in grok_text
    assert "--output-format json" in grok_text
    assert "--always-approve" in grok_text
    assert "XAI_API_KEY" in grok_text
    assert "API_KEY_XAI" in grok_text
    assert "/a0/usr/.env" in grok_text
    assert "grok login --device-auth" in grok_text
    assert "Do not run bare `grok`" in grok_text

    assert "hermes setup --portal" in hermes_text
    assert "opencode auth login" in opencode_text


if __name__ == "__main__":
    test_configured_absolute_binary_is_installed()
    test_registry_order_puts_a0_first()
    test_adapters_are_status_only()
    test_tool_runner_files_are_removed()
    test_claude_defaults_skip_permissions()
    test_cursor_defaults_headless_automation()
    test_cursor_detects_agent_zero_cursor_env_key()
    test_gemini_detects_supported_auth_sources()
    test_grok_defaults_headless_automation()
    test_grok_env_key_requires_present_environment_value()
    test_grok_detects_agent_zero_xai_env_key()
    test_skill_documents_human_setup_loop_and_a0_exception()
