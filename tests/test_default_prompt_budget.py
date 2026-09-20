import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import AgentConfig, AgentContext, AgentContextType
from helpers import runtime, tokens, tool_policy


CONFIGURABLE_TOOL_NAMES = {
    path.stem
    for path in [
        *PROJECT_ROOT.glob("tools/*.py"),
        *PROJECT_ROOT.glob("agents/*/tools/*.py"),
        *PROJECT_ROOT.glob("plugins/*/tools/*.py"),
    ]
    if path.stem not in {"__init__", "response", "unknown", "vision_load"}
}


def _advertised_configurable_tools(text: str) -> set[str]:
    advertised: set[str] = set()
    for name in CONFIGURABLE_TOOL_NAMES:
        escaped = re.escape(name)
        if "_" in name:
            pattern = rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])"
        else:
            pattern = (
                rf"`{escaped}`|[\"']{escaped}[\"']|"
                rf"(?<![A-Za-z0-9_]){escaped}\s+tool\b"
            )
        if re.search(pattern, text, re.IGNORECASE):
            advertised.add(name)
    return advertised


def _iter_prompt_files():
    yield from (PROJECT_ROOT / "prompts").rglob("*.md")
    yield from (PROJECT_ROOT / "agents" / "agent0" / "prompts").rglob("*.md")
    yield from (PROJECT_ROOT / "knowledge" / "main").rglob("*.md")
    for prompts_dir in (PROJECT_ROOT / "plugins").glob("*/prompts"):
        yield from prompts_dir.rglob("*.md")


async def _build_system_text(profile: str = "agent0", rendered: bool = False) -> str:
    old_args = dict(runtime.args)
    runtime.args.clear()
    runtime.args["dockerized"] = "true"

    ctx = AgentContext(
        config=AgentConfig(
            profile=profile,
            knowledge_subdirs=["custom", "default"],
            mcp_servers='{"mcpServers": {}}',
        ),
        type=AgentContextType.USER,
        set_current=False,
    )
    try:
        if rendered:
            prompt = await ctx.agent0.prepare_prompt(ctx.agent0.loop_data)
            return str(prompt[0].content)
        system = await ctx.agent0.get_system_prompt(ctx.agent0.loop_data)
        return "\n\n".join(system)
    finally:
        AgentContext.remove(ctx.id)
        runtime.args.clear()
        runtime.args.update(old_args)


@pytest.mark.asyncio
async def test_default_agent0_prompt_contracts():
    system_text = await _build_system_text()
    rendered_system_text = await _build_system_text(rendered=True)
    communication_prompt = (
        PROJECT_ROOT / "prompts" / "agent.system.main.communication.md"
    ).read_text(encoding="utf-8")

    assert "`tool_name` must be one listed tool name" in system_text
    assert "- tool_args: key value pairs tool arguments" in system_text
    assert '"*.promptinclude.md" files in workdir auto-injected' in system_text
    assert '"tool_name": "call_subordinate"' in system_text
    assert "always use specialized subordinate agents" in system_text
    assert "delegate them to separate subordinates" in system_text
    assert '"tool_name": "parallel"' in system_text
    assert "Each `tool_calls` item is a normal tool request object" in system_text
    assert '"reset": true' in system_text
    assert '"tool_name": "text_editor"' in system_text
    assert '"action": "read"' in system_text
    assert '"tool_name": "code_execution_tool"' in system_text
    assert "informative but tight" in system_text
    assert "Your actual output starts with `{` and ends with `}`" in system_text
    assert "~~~json" in communication_prompt
    assert "~~~json" not in rendered_system_text
    assert "```json" not in rendered_system_text
    for name in ("code_execution_remote", "text_editor_remote", "computer_use_remote"):
        assert name not in system_text
        assert name not in rendered_system_text
    assert "- host-" not in system_text
    assert "- setup-a0-cli:" in system_text
    assert "Computer Use enablement is scoped to the current CLI session" not in system_text


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", ["developer", "researcher", "hacker"])
async def test_standard_specialist_profiles_keep_the_shared_communication_contract(
    profile: str,
):
    system_text = await _build_system_text(profile)

    for instruction in (
        "Output must be valid JSON with double quotes for all keys and string values",
        "No JSON in markdown fences",
        "Do not invent unavailable tool names and args",
        "`tool_name` must be one listed tool name",
        "To do dependent operations, call one tool now",
        "No text output before or after the JSON object",
        "Your actual output starts with `{` and ends with `}`",
    ):
        assert instruction in system_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("profile", "intake_instruction"),
    [
        ("developer", "clear bounded task: inspect facts choose reasonable local defaults implement verify"),
        ("researcher", "clear bounded task: start discovery and validation without interview"),
    ],
)
async def test_specialists_keep_intake_guidance_without_response_overrides(
    profile: str, intake_instruction: str
):
    system_text = await _build_system_text(profile)

    assert intake_instruction in system_text
    assert "Use the 'response' tool iteratively" not in system_text
    assert "must utilize the 'response' tool iteratively" not in system_text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    ["agent0", "default", "developer", "hacker", "researcher", "tiny-local"],
)
async def test_block_all_policy_does_not_advertise_configurable_tools(
    monkeypatch, profile: str
):
    policy = {
        "mode": "custom",
        "default": "block",
        "mcp_default": "block",
        "allowed": [],
        "blocked": [],
    }
    monkeypatch.setattr(tool_policy, "get_policy", lambda _agent: policy)

    system_text = await _build_system_text(profile)

    assert _advertised_configurable_tools(system_text) == set()
    assert "memory tools" not in system_text.casefold()
    assert "using tools and subordinates" not in system_text.casefold()
    assert "subordinate agent orchestration" not in system_text.casefold()
    assert "always use specialized subordinate agents" not in system_text.casefold()
    assert "delegate them to separate subordinates" not in system_text.casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile", ["agent0", "default", "developer", "researcher", "tiny-local"]
)
async def test_rendered_profiles_strip_json_fences(profile: str):
    system_text = await _build_system_text(profile, rendered=True)

    assert "~~~json" not in system_text
    assert "```json" not in system_text


def test_remove_code_fences_can_target_json_only():
    from helpers import files

    prompt = """Before
~~~json
{"tool_name":"response","tool_args":{"text":"done"}}
~~~
~~~python
print("keep me fenced")
~~~
After
"""

    rendered = files.remove_code_fences(prompt, language="json")

    assert "~~~json" not in rendered
    assert '{"tool_name":"response"' in rendered
    assert '~~~python\nprint("keep me fenced")\n~~~' in rendered


@pytest.mark.asyncio
async def test_tiny_local_profile_prompt_is_action_first_json_contract():
    system_text = await _build_system_text("tiny-local")
    communication_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "agent.system.main.communication.md"
    ).read_text(encoding="utf-8")
    code_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "agent.system.tool.code_exe.md"
    ).read_text(encoding="utf-8")
    response_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "agent.system.tool.response.md"
    ).read_text(encoding="utf-8")
    repeat_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "fw.msg_repeat.md"
    ).read_text(encoding="utf-8")
    text_editor_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "agent.system.tool.text_editor.md"
    ).read_text(encoding="utf-8")
    solving_prompt = (
        PROJECT_ROOT / "plugins" / "_agent_profiles" / "agents" / "tiny-local" / "prompts" / "agent.system.main.solving.md"
    ).read_text(encoding="utf-8")

    assert "You are Agent Zero. Act on the user's behalf." in system_text
    assert "Your visible assistant message must be exactly one valid JSON object." in system_text
    assert 'Use exactly these top-level fields: `"tool_name"` and `"tool_args"`.' in system_text
    assert 'For a final user-facing answer, use the `response` tool.' in system_text
    assert "Use `response` only when the work is complete, blocked, or the user is only acknowledging completed work." in system_text
    assert "If the user says \"proceed\", \"continue\", \"go ahead\", \"do it\", \"excellent proceed\"" in system_text
    assert "Do not explain what command the user could run manually." in system_text
    assert "output a corrected JSON tool request immediately" in system_text
    assert "do not resend the same JSON" in system_text
    assert "## Tiny Local Output Rule" in system_text
    assert "~~~json" not in communication_prompt
    assert "~~~json" not in code_prompt
    assert "~~~json" not in response_prompt
    assert "~~~json" not in text_editor_prompt
    assert "No JSON in markdown fences" not in communication_prompt
    assert "thoughts: array thoughts before execution" not in communication_prompt
    assert "headline: short headline summary" not in communication_prompt
    assert "explain each step in thoughts" not in solving_prompt
    assert "Continuation words" in solving_prompt
    assert "Do not respond by saying you will begin, continue, start, proceed, or investigate." in solving_prompt
    assert "Do not use this tool for \"proceed\", \"continue\", \"go ahead\"" in response_prompt
    assert "Your repeated JSON was recorded, but it did not execute another tool." in repeat_prompt
    assert "replace it with the next real tool call" in repeat_prompt
    assert "do not repeat the same status response or exact tool request" in solving_prompt
    assert "do not repeat the same exact tool call" in solving_prompt
    assert '"open_in_canvas":true' in text_editor_prompt
    assert "do not repeat the same tool call" in text_editor_prompt
    assert '"headline"' not in code_prompt
    assert '"headline"' not in response_prompt
    assert '"headline"' not in text_editor_prompt


def test_tiny_local_profile_is_discoverable():
    from helpers import subagents

    profiles = {
        str(item.get("key") or ""): str(item.get("label") or "")
        for item in subagents.get_all_agents_list()
    }

    assert profiles["tiny-local"] == "Tiny Local"


def test_removed_small_profile_and_prompt_text_generic():
    removed_profile = "a0" + "_" + "small"

    assert not (PROJECT_ROOT / "agents" / removed_profile).exists()
    assert not (
        PROJECT_ROOT / "knowledge" / "main" / f"{removed_profile}_tool_call_examples.md"
    ).exists()
    assert not (PROJECT_ROOT / "knowledge" / "main" / "tool_call_reference_examples.md").exists()

    for path in _iter_prompt_files():
        assert removed_profile not in path.read_text(encoding="utf-8")


def test_prompt_token_estimate_omits_embedded_image_data_urls():
    embedded_png = "data:image/png;base64," + ("ABCDabcd0123+/==" * 20_000)
    prompt_text = f"user: please inspect this screenshot {embedded_png}"

    sanitized = tokens.sanitize_embedded_image_data_urls(prompt_text)

    assert "ABCDabcd0123+/==" not in sanitized
    assert "data:image/png;base64," in sanitized
    assert tokens.EMBEDDED_IMAGE_DATA_PLACEHOLDER in sanitized
    assert tokens.approximate_prompt_tokens(prompt_text) < 100
    assert tokens.approximate_prompt_tokens(prompt_text) < tokens.approximate_tokens(prompt_text) / 100
