from __future__ import annotations

import asyncio
import importlib
import sys
import types
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _FakeResponse:
    message: str
    break_loop: bool
    additional: dict | None = None


class _FakeTool:
    def __init__(
        self,
        agent,
        name: str,
        method: str | None,
        args: dict | None,
        message: str,
        loop_data=None,
        **kwargs,
    ) -> None:
        self.agent = agent
        self.name = name
        self.method = method
        self.args = args or {}
        self.message = message
        self.loop_data = loop_data


class _FakeContext:
    def __init__(self, data: dict | None = None) -> None:
        self.id = "ctx"
        self.data = data or {}

    def get_data(self, key, recursive=True):
        return self.data.get(key)

    def set_data(self, key, value, recursive=True):
        self.data[key] = value


class _FakeAgent:
    def __init__(self) -> None:
        self.data = {}
        self.context = _FakeContext()
        self.history = types.SimpleNamespace(output=lambda: [])

    def read_prompt(self, _name: str, **kwargs) -> str:
        return f"deleted {kwargs.get('memory_count', 0)}"


@dataclass
class _FakeSkill:
    name: str
    description: str
    path: Path
    version: str = ""
    tags: list[str] | None = None


def _normalize_loaded_skill_names(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [name for value in raw if (name := str(value or "").strip())]


def _get_loaded_skill_names(agent) -> list[str]:
    names = _normalize_loaded_skill_names(agent.context.get_data("loaded_skills"))
    if names:
        return names
    names = _normalize_loaded_skill_names(agent.data.get("loaded_skills"))
    if names:
        _set_loaded_skill_names(agent, names)
    return names


def _set_loaded_skill_names(agent, names) -> list[str]:
    names = _normalize_loaded_skill_names(names)
    agent.context.set_data("loaded_skills", names or None)
    return names


def _add_loaded_skill_name(agent, skill_name, *, limit=None) -> list[str]:
    skill_name = str(skill_name or "").strip()
    names = [name for name in _get_loaded_skill_names(agent) if name != skill_name]
    if skill_name:
        names.append(skill_name)
    return _set_loaded_skill_names(agent, names[-(limit or 20):])


def _skill_instruction_name(message) -> str:
    match message:
        case {
            "content": {
                "skill_instructions": {
                    "content_included": included,
                    "name": name,
                }
            }
        } if included:
            return str(name or "").strip()
    return ""


def _install_tool_stub(monkeypatch) -> None:
    tool_stub = types.ModuleType("helpers.tool")
    tool_stub.Tool = _FakeTool
    tool_stub.Response = _FakeResponse
    monkeypatch.setitem(sys.modules, "helpers.tool", tool_stub)


def _load_skills_tool(monkeypatch, skill_root: Path):
    _install_tool_stub(monkeypatch)

    skills_stub = types.ModuleType("helpers.skills")
    skills_stub.AGENT_DATA_NAME_LOADED_SKILLS = "loaded_skills"
    skills_stub.CONTEXT_DATA_NAME_LOADED_SKILLS = "loaded_skills"
    skills_stub.MAX_ACTIVE_SKILLS = 20
    fake_skill = _FakeSkill(
        name="browser-form-workflows",
        description="Use for complex browser forms.",
        path=skill_root,
        tags=[],
    )
    skills_stub.list_skills = lambda *args, **kwargs: [fake_skill]
    skills_stub.search_skills = lambda *args, **kwargs: [fake_skill]
    skills_stub.find_skill = lambda *args, **kwargs: fake_skill
    skills_stub.load_skill_for_agent = (
        lambda *args, **kwargs: "Skill: browser-form-workflows\n\nInstructions:\nUse labels before typing."
    )
    skills_stub.add_loaded_skill_name = _add_loaded_skill_name
    skills_stub.get_loaded_skill_names = _get_loaded_skill_names
    skills_stub.set_loaded_skill_names = _set_loaded_skill_names
    skills_stub.skill_instruction_name = _skill_instruction_name
    monkeypatch.setitem(sys.modules, "helpers.skills", skills_stub)
    import helpers
    monkeypatch.setattr(helpers, "skills", skills_stub, raising=False)

    print_style_stub = types.ModuleType("helpers.print_style")
    print_style_stub.PrintStyle = lambda *args, **kwargs: types.SimpleNamespace(
        print=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "helpers.print_style", print_style_stub)

    sys.modules.pop("tools.skills_tool", None)
    return importlib.import_module("tools.skills_tool")


class _FakeExtension:
    def __init__(self, agent=None):
        self.agent = agent


class _FakeLoadedSkillAgent:
    def __init__(self) -> None:
        self.data = {}
        self.context = _FakeContext({"loaded_skills": ["browser-form-workflows"]})
        self.added_tool_results = []

    def hist_add_tool_result(self, tool_name: str, tool_result: str, **kwargs):
        content = {"tool_name": tool_name, "tool_result": tool_result, **kwargs}
        self.added_tool_results.append(content)
        return types.SimpleNamespace(
            output=lambda: [{"ai": False, "content": content}]
        )


def _load_loaded_skills_extension(monkeypatch, skill_root: Path):
    extension_stub = types.ModuleType("helpers.extension")
    extension_stub.Extension = _FakeExtension
    monkeypatch.setitem(sys.modules, "helpers.extension", extension_stub)

    agent_stub = types.ModuleType("agent")
    agent_stub.LoopData = lambda **kwargs: types.SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "agent", agent_stub)

    skills_stub = types.ModuleType("helpers.skills")
    fake_skill = _FakeSkill(
        name="browser-form-workflows",
        description="Use for complex browser forms.",
        path=skill_root,
        tags=[],
    )
    skills_stub.find_skill = lambda *args, **kwargs: fake_skill
    skills_stub.load_skill_for_agent = (
        lambda *args, **kwargs: "Skill: browser-form-workflows\n\nInstructions:\nUse labels before typing."
    )
    skills_stub.get_loaded_skill_names = _get_loaded_skill_names
    skills_stub.set_loaded_skill_names = _set_loaded_skill_names
    skills_stub.skill_instruction_name = _skill_instruction_name
    monkeypatch.setitem(sys.modules, "helpers.skills", skills_stub)

    tokens_stub = types.ModuleType("helpers.tokens")
    tokens_stub.approximate_tokens = lambda text: len(str(text).split())
    monkeypatch.setitem(sys.modules, "helpers.tokens", tokens_stub)

    import helpers

    monkeypatch.setattr(helpers, "skills", skills_stub, raising=False)
    monkeypatch.setattr(helpers, "tokens", tokens_stub, raising=False)

    skills_tool_stub = types.ModuleType("tools.skills_tool")
    skills_tool_stub.DATA_NAME_LOADED_SKILLS = "loaded_skills"
    monkeypatch.setitem(sys.modules, "tools.skills_tool", skills_tool_stub)

    module_name = "extensions.python.message_loop_prompts_after._65_include_loaded_skills"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _load_relevant_skills_extension(
    monkeypatch, queries: list[str], *, skills_tool_allowed: bool = True
):
    extension_stub = types.ModuleType("helpers.extension")
    extension_stub.Extension = _FakeExtension
    monkeypatch.setitem(sys.modules, "helpers.extension", extension_stub)

    agent_stub = types.ModuleType("agent")
    agent_stub.LoopData = lambda **kwargs: types.SimpleNamespace(**kwargs)
    monkeypatch.setitem(sys.modules, "agent", agent_stub)

    skills_stub = types.ModuleType("helpers.skills")

    def _search_skills(query, *args, **kwargs):
        queries.append(query)
        return []

    skills_stub.search_skills = _search_skills
    monkeypatch.setitem(sys.modules, "helpers.skills", skills_stub)

    tool_policy_stub = types.ModuleType("helpers.tool_policy")
    tool_policy_stub.resolve_tool = lambda *args, **kwargs: types.SimpleNamespace(
        allowed=skills_tool_allowed
    )
    monkeypatch.setitem(sys.modules, "helpers.tool_policy", tool_policy_stub)

    import helpers

    monkeypatch.setattr(helpers, "skills", skills_stub, raising=False)
    monkeypatch.setattr(helpers, "tool_policy", tool_policy_stub, raising=False)

    module_name = "extensions.python.message_loop_prompts_after._63_recall_relevant_skills"
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _load_computer_use_remote_tool(monkeypatch):
    _install_tool_stub(monkeypatch)

    history_stub = types.ModuleType("helpers.history")

    class _RawMessage(dict):
        def __init__(self, raw_content, preview):
            super().__init__(raw_content=raw_content, preview=preview)

    history_stub.RawMessage = _RawMessage
    monkeypatch.setitem(sys.modules, "helpers.history", history_stub)

    print_style_stub = types.ModuleType("helpers.print_style")
    print_style_stub.PrintStyle = lambda *args, **kwargs: types.SimpleNamespace(
        print=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "helpers.print_style", print_style_stub)

    ws_stub = types.ModuleType("helpers.ws")
    ws_stub.NAMESPACE = "/test"
    monkeypatch.setitem(sys.modules, "helpers.ws", ws_stub)

    ws_manager_stub = types.ModuleType("helpers.ws_manager")
    ws_manager_stub.ConnectionNotFoundError = RuntimeError
    ws_manager_stub.get_shared_ws_manager = lambda: types.SimpleNamespace(
        emit_to=lambda *a, **k: None
    )
    monkeypatch.setitem(sys.modules, "helpers.ws_manager", ws_manager_stub)

    ws_runtime_stub = types.ModuleType("plugins._a0_connector.helpers.ws_runtime")
    ws_runtime_stub.clear_pending_computer_use_op = lambda *args, **kwargs: None
    ws_runtime_stub.computer_use_metadata_for_sid = lambda *args, **kwargs: {}
    async def _emit_connector_event(*args, **kwargs):
        return None

    ws_runtime_stub.emit_connector_event = _emit_connector_event
    ws_runtime_stub.select_computer_use_target_sid = lambda *args, **kwargs: "sid"
    ws_runtime_stub.store_pending_computer_use_op = lambda *args, **kwargs: None
    monkeypatch.setitem(
        sys.modules,
        "plugins._a0_connector.helpers.ws_runtime",
        ws_runtime_stub,
    )

    sys.modules.pop("plugins._a0_connector.tools.computer_use_remote", None)
    return importlib.import_module("plugins._a0_connector.tools.computer_use_remote")


def test_skills_tool_accepts_action_alias_for_search(monkeypatch, tmp_path: Path):
    module = _load_skills_tool(monkeypatch, tmp_path)
    tool = module.SkillsTool(
        _FakeAgent(),
        "skills_tool",
        None,
        {"action": "search", "query": "browser forms"},
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "browser-form-workflows" in response.message


def test_skills_tool_accepts_method_as_deprecated_action_alias(
    monkeypatch, tmp_path: Path
):
    module = _load_skills_tool(monkeypatch, tmp_path)
    tool = module.SkillsTool(
        _FakeAgent(),
        "skills_tool",
        None,
        {"method": "search", "query": "browser forms"},
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "browser-form-workflows" in response.message
    assert tool.args["action"] == "search"


def test_skills_tool_defaults_missing_action_to_list(monkeypatch, tmp_path: Path):
    module = _load_skills_tool(monkeypatch, tmp_path)
    tool = module.SkillsTool(
        _FakeAgent(),
        "skills_tool",
        None,
        {},
        "",
        None,
    )

    response = asyncio.run(tool.execute())

    assert "Available skills" in response.message
    assert "browser-form-workflows" in response.message
    assert "slash commands" not in response.message


def test_skills_tool_load_appends_skill_instructions_as_tool_result(
    monkeypatch, tmp_path: Path
):
    module = _load_skills_tool(monkeypatch, tmp_path)
    agent = _FakeAgent()
    tool = module.SkillsTool(
        agent,
        "skills_tool",
        None,
        {"action": "load", "skill_name": "browser-form-workflows"},
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "Skill: browser-form-workflows" in response.message
    assert response.additional["skill_instructions"]["name"] == "browser-form-workflows"
    assert response.additional["skill_instructions"]["content_included"] is True
    assert agent.context.get_data("loaded_skills") == ["browser-form-workflows"]


def test_skills_tool_load_omits_duplicate_visible_skill(
    monkeypatch, tmp_path: Path
):
    module = _load_skills_tool(monkeypatch, tmp_path)
    agent = _FakeAgent()
    tool = module.SkillsTool(
        agent,
        "skills_tool",
        None,
        {"action": "load", "skill_name": "browser-form-workflows"},
        "",
        None,
    )
    first = asyncio.run(tool.execute(**tool.args))
    loaded_message = {
        "ai": False,
        "content": {"skill_instructions": first.additional["skill_instructions"]},
    }
    agent.history = types.SimpleNamespace(output=lambda: [loaded_message])

    second = asyncio.run(tool.execute(**tool.args))

    assert "already loaded in visible chat history" in second.message
    assert "Instructions:\nUse labels before typing." not in second.message
    assert second.additional["skill_instructions"]["content_included"] is False
    assert second.additional["skill_instructions"]["already_loaded"] is True
    assert agent.context.get_data("loaded_skills") == ["browser-form-workflows"]


def test_skills_tool_load_reloads_when_prior_skill_is_not_model_visible(
    monkeypatch, tmp_path: Path
):
    module = _load_skills_tool(monkeypatch, tmp_path)
    agent = _FakeAgent()
    tool = module.SkillsTool(
        agent,
        "skills_tool",
        None,
        {"action": "load", "skill_name": "browser-form-workflows"},
        "",
        None,
    )
    first = asyncio.run(tool.execute(**tool.args))
    hidden_message = types.SimpleNamespace(
        summary="",
        content={"skill_instructions": first.additional["skill_instructions"]},
    )
    agent.history = types.SimpleNamespace(
        all_messages=lambda: [hidden_message],
        output=lambda: [
            {
                "ai": False,
                "content": "Earlier history was summarized and no skill body is visible.",
            }
        ],
    )

    second = asyncio.run(tool.execute(**tool.args))

    assert "Skill: browser-form-workflows" in second.message
    assert second.additional["skill_instructions"]["content_included"] is True
    assert agent.context.get_data("loaded_skills") == ["browser-form-workflows"]


def test_loaded_skills_extension_reattaches_missing_body_after_compaction(
    monkeypatch, tmp_path: Path
):
    module = _load_loaded_skills_extension(monkeypatch, tmp_path)
    agent = _FakeLoadedSkillAgent()
    loop_data = types.SimpleNamespace(
        protocol_persistent={},
        extras_persistent={},
        history_output=[
            {
                "ai": False,
                "content": "Earlier history was summarized and no skill body is visible.",
            }
        ],
    )

    asyncio.run(module.IncludeLoadedSkills(agent).execute(loop_data))

    assert len(agent.added_tool_results) == 1
    added = agent.added_tool_results[0]
    assert added["tool_name"] == "skills_tool"
    assert "Skill: browser-form-workflows" in added["tool_result"]
    assert added["skill_instructions"] == {
        "name": "browser-form-workflows",
        "path": str(tmp_path),
        "source": "skills_tool:reattach",
        "content_included": True,
    }
    assert loop_data.history_output[-1]["content"] == added


def test_loaded_skills_extension_does_not_reattach_visible_skill(
    monkeypatch, tmp_path: Path
):
    module = _load_loaded_skills_extension(monkeypatch, tmp_path)
    agent = _FakeLoadedSkillAgent()
    loop_data = types.SimpleNamespace(
        protocol_persistent={},
        extras_persistent={},
        history_output=[
            {
                "ai": False,
                "content": {
                    "skill_instructions": {
                        "name": "browser-form-workflows",
                        "content_included": True,
                    }
                },
            }
        ],
    )

    asyncio.run(module.IncludeLoadedSkills(agent).execute(loop_data))

    assert agent.added_tool_results == []


def test_loaded_skills_extension_keeps_reattachments_under_budget(
    monkeypatch, tmp_path: Path
):
    module = _load_loaded_skills_extension(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "SKILL_REATTACHMENT_TOKEN_BUDGET", 1)
    agent = _FakeLoadedSkillAgent()
    loop_data = types.SimpleNamespace(
        protocol_persistent={},
        extras_persistent={},
        history_output=[],
    )

    asyncio.run(module.IncludeLoadedSkills(agent).execute(loop_data))

    assert agent.added_tool_results == []


def test_relevant_skill_recall_uses_raw_user_message(monkeypatch):
    queries: list[str] = []
    module = _load_relevant_skills_extension(monkeypatch, queries)
    agent = types.SimpleNamespace()
    loop_data = types.SimpleNamespace(
        iteration=0,
        user_message=types.SimpleNamespace(
            content={
                "system_message": [],
                "user_message": "Open a browser and take a screenshot.",
                "attachments": [],
            },
            output_text=lambda: 'user: {"user_message": "wrapped"}',
        ),
        extras_temporary={},
    )

    asyncio.run(module.RecallRelevantSkills(agent).execute(loop_data=loop_data))

    assert queries == ["Open a browser and take a screenshot."]


def test_relevant_skill_recall_skips_blocked_skills_tool(monkeypatch):
    queries: list[str] = []
    module = _load_relevant_skills_extension(
        monkeypatch, queries, skills_tool_allowed=False
    )
    loop_data = types.SimpleNamespace(
        iteration=0,
        user_message=types.SimpleNamespace(
            content="Open a browser and take a screenshot.",
            output_text=lambda: "Open a browser and take a screenshot.",
        ),
        extras_temporary={},
    )

    asyncio.run(
        module.RecallRelevantSkills(types.SimpleNamespace()).execute(
            loop_data=loop_data
        )
    )

    assert queries == []


def test_skills_tool_read_file_action_reads_inside_skill_dir(
    monkeypatch, tmp_path: Path
):
    skill_root = tmp_path / "browser-form-workflows"
    skill_root.mkdir()
    (skill_root / "notes.md").write_text("Use labels before typing.\n", encoding="utf-8")
    module = _load_skills_tool(monkeypatch, skill_root)
    tool = module.SkillsTool(
        _FakeAgent(),
        "skills_tool",
        None,
        {
            "action": "read_file",
            "skill_name": "browser-form-workflows",
            "file_path": "notes.md",
        },
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "Skill file: browser-form-workflows/notes.md" in response.message
    assert "Use labels before typing." in response.message


def test_memory_forget_tool_imports_plugin_memory_load(monkeypatch):
    _install_tool_stub(monkeypatch)
    monkeypatch.syspath_prepend(str(Path.cwd()))

    class FakeDb:
        def __init__(self) -> None:
            self.calls = []

        async def delete_documents_by_query(self, **kwargs):
            self.calls.append(kwargs)
            return ["memory-1"]

    fake_db = FakeDb()

    async def get_memory(_agent):
        return fake_db

    memory_stub = types.ModuleType("plugins._memory.helpers.memory")
    memory_stub.Memory = types.SimpleNamespace(get=get_memory)
    monkeypatch.setitem(sys.modules, "plugins._memory.helpers.memory", memory_stub)

    sys.modules.pop("plugins._memory.tools.memory_load", None)
    sys.modules.pop("plugins._memory.tools.memory_forget", None)
    module = importlib.import_module("plugins._memory.tools.memory_forget")
    tool = module.MemoryForget(
        _FakeAgent(),
        "memory_forget",
        None,
        {
            "query": "codex memory forget token",
            "threshold": 0.99,
            "filter": "area=='codex_sweep'",
        },
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert response.message == "deleted 1"
    assert fake_db.calls == [
        {
            "query": "codex memory forget token",
            "threshold": 0.99,
            "filter": "area=='codex_sweep'",
            "include_exact": True,
            "cascade": True,
        }
    ]


def test_memory_load_coerces_numeric_string_args(monkeypatch):
    _install_tool_stub(monkeypatch)
    monkeypatch.syspath_prepend(str(Path.cwd()))

    class FakeDb:
        def __init__(self) -> None:
            self.calls = []

        async def search_similarity_threshold(self, **kwargs):
            self.calls.append(kwargs)
            return []

    fake_db = FakeDb()

    async def get_memory(_agent):
        return fake_db

    memory_stub = types.ModuleType("plugins._memory.helpers.memory")
    memory_stub.Memory = types.SimpleNamespace(get=get_memory)
    monkeypatch.setitem(sys.modules, "plugins._memory.helpers.memory", memory_stub)

    sys.modules.pop("plugins._memory.tools.memory_load", None)
    module = importlib.import_module("plugins._memory.tools.memory_load")
    tool = module.MemoryLoad(
        _FakeAgent(),
        "memory_load",
        None,
        {
            "query": "smoke test project context",
            "threshold": "0.7",
            "limit": "3",
        },
        "",
        None,
    )

    asyncio.run(tool.execute(**tool.args))

    assert fake_db.calls == [
        {
            "query": "smoke test project context",
            "threshold": 0.7,
            "limit": 3,
            "filter": "",
        }
    ]


def test_behaviour_adjustment_normalizes_duplicate_rules(monkeypatch):
    _install_tool_stub(monkeypatch)
    monkeypatch.syspath_prepend(str(Path.cwd()))

    agent_stub = types.ModuleType("agent")
    agent_stub.Agent = object
    monkeypatch.setitem(sys.modules, "agent", agent_stub)

    log_stub = types.ModuleType("helpers.log")
    log_stub.LogItem = object
    monkeypatch.setitem(sys.modules, "helpers.log", log_stub)

    memory_stub = types.ModuleType("plugins._memory.helpers.memory")
    memory_stub.get_memory_subdir_abs = lambda agent: "/tmp"
    monkeypatch.setitem(sys.modules, "plugins._memory.helpers.memory", memory_stub)

    sys.modules.pop("plugins._memory.tools.behaviour_adjustment", None)
    module = importlib.import_module("plugins._memory.tools.behaviour_adjustment")

    rules = module.normalize_ruleset(
        "## Behavioral rules\n"
        "* Favor Linux commands.\n"
        "* Token rule.## Behavioral rules\n"
        "* Favor Linux commands.\n"
        "* Token rule."
    )

    assert rules == "## Behavioral rules\n* Favor Linux commands.\n* Token rule.\n"


def test_behaviour_prompts_preserve_exact_rules_and_avoid_promptinclude():
    behaviour_prompt_path = Path(
        "plugins/_memory/prompts/agent.system.tool.behaviour.md"
    )
    behaviour_prompt = behaviour_prompt_path.read_text(encoding="utf-8")
    merge_prompt = Path("prompts/behaviour.merge.sys.md").read_text(
        encoding="utf-8"
    )
    promptinclude_prompt = Path(
        "plugins/_promptinclude/prompts/agent.system.promptinclude.md"
    ).read_text(encoding="utf-8")

    assert "exact-response rules" in behaviour_prompt
    assert "preserve it verbatim" in behaviour_prompt
    assert "do not edit promptinclude files" in behaviour_prompt
    assert not Path("prompts/agent.system.tool.behaviour.md").exists()
    assert "respond exactly with a phrase" in merge_prompt
    assert "behaviour_adjustment" not in promptinclude_prompt


def _load_a2a_chat_tool(monkeypatch):
    _install_tool_stub(monkeypatch)
    sys.modules.pop("plugins._a2a_chat.tools.a2a_chat", None)
    return importlib.import_module("plugins._a2a_chat.tools.a2a_chat")


def test_a2a_extracts_latest_assistant_text_from_history(monkeypatch):
    module = _load_a2a_chat_tool(monkeypatch)

    final = {
        "result": {
            "history": [
                {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "what is 2+2?"}],
                },
                {
                    "role": "assistant",
                    "parts": [{"kind": "text", "text": "4"}],
                },
            ]
        }
    }

    assert module._extract_latest_assistant_text(final) == "4"


def test_a2a_extracts_status_or_artifact_text_when_history_is_empty(monkeypatch):
    module = _load_a2a_chat_tool(monkeypatch)

    status_final = {
        "result": {
            "status": {
                "message": {
                    "parts": [{"kind": "text", "text": "status answer"}]
                }
            }
        }
    }
    artifact_final = {
        "result": {
            "artifacts": [
                {"parts": [{"kind": "text", "text": "artifact answer"}]}
            ]
        }
    }

    assert module._extract_latest_assistant_text(status_final) == "status answer"
    assert module._extract_latest_assistant_text(artifact_final) == "artifact answer"


def test_a2a_session_key_normalizes_explicit_a2a_path(monkeypatch):
    module = _load_a2a_chat_tool(monkeypatch)

    assert module._session_key("http://localhost:32080/a2a") == "http://localhost:32080"
    assert module._session_key("http://localhost:32080") == "http://localhost:32080"


def test_a2a_empty_response_message_is_explicit_failure(monkeypatch):
    module = _load_a2a_chat_tool(monkeypatch)

    assert module._extract_latest_assistant_text({"result": {"history": []}}) == ""
    assert "failed" in module.A2A_EMPTY_RESPONSE_ERROR
    assert "not success" in module.A2A_EMPTY_RESPONSE_ERROR


def test_notify_user_prompt_documents_numeric_priority_values():
    prompt = Path(
        "plugins/_notify_user/prompts/agent.system.tool.notify_user.md"
    ).read_text(encoding="utf-8")

    assert "priority values: `20` high urgency, `10` normal urgency" in prompt


def test_tool_prompts_prevent_top_level_multi_tool():
    tools_prompt = Path("prompts/agent.system.tools.md").read_text(encoding="utf-8")
    parallel_prompt = Path("prompts/agent.system.tool.parallel.md").read_text(
        encoding="utf-8"
    )
    communication_prompt = Path("prompts/agent.system.main.communication.md").read_text(
        encoding="utf-8"
    )
    browser_prompt = Path("plugins/_browser/prompts/agent.system.tool.browser.md").read_text(
        encoding="utf-8"
    )

    assert "Do not invent top-level `multi` or generic batch tools" in tools_prompt
    assert "`parallel`" not in tools_prompt
    assert "run independent tool calls concurrently" in parallel_prompt
    assert "never an action name such as `read`, `write`, `terminal`, or `multi`" in communication_prompt
    assert "independent operations concurrently" not in communication_prompt
    assert 'Never use `tool_name: "multi"`' in browser_prompt


def test_local_model_tool_use_guide_stays_prompt_profile_plugin_only():
    guide = Path("docs/guides/local-model-tool-use.md").read_text(encoding="utf-8")

    assert "Tiny Local" in guide
    assert "agents/tiny-local/" in guide
    assert "*.promptinclude.md" in guide
    assert "Do not change `agent.py`" in guide
    assert "Do not change `helpers/extract_tools.py`" in guide
    assert "Use exactly these top-level fields: `tool_name` and `tool_args`." in guide
    assert '{"tool_name":"response","tool_args":{"text":"Done."}}' in guide
    assert "If the user says \"proceed\", \"continue\", \"go ahead\", or similar" in guide
    assert "call the next appropriate tool instead of replying with a promise or status update" in guide
    assert "Do not create parser repair code for this workflow." in guide


def _load_scheduler_tool(monkeypatch):
    _install_tool_stub(monkeypatch)

    scheduler_stub = types.ModuleType("helpers.task_scheduler")
    scheduler_stub.TaskScheduler = object
    scheduler_stub.ScheduledTask = type("ScheduledTask", (), {})
    scheduler_stub.AdHocTask = type("AdHocTask", (), {})
    scheduler_stub.PlannedTask = type("PlannedTask", (), {})
    scheduler_stub.serialize_task = lambda task: {}
    scheduler_stub.parse_datetime = lambda value: None
    scheduler_stub.parse_task_plan = lambda value: None
    scheduler_stub.serialize_datetime = lambda value: value
    scheduler_stub.TaskState = types.SimpleNamespace(
        IDLE="idle",
        RUNNING="running",
    )
    scheduler_stub.TaskSchedule = type("TaskSchedule", (), {})
    scheduler_stub.TaskPlan = type("TaskPlan", (), {})
    monkeypatch.setitem(sys.modules, "helpers.task_scheduler", scheduler_stub)

    agent_stub = types.ModuleType("agent")
    agent_stub.AgentContext = types.SimpleNamespace(
        get=lambda *args, **kwargs: None,
        remove=lambda *args, **kwargs: None,
    )
    monkeypatch.setitem(sys.modules, "agent", agent_stub)

    persist_chat_stub = types.ModuleType("helpers.persist_chat")
    persist_chat_stub.remove_chat = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "helpers.persist_chat", persist_chat_stub)

    projects_stub = types.ModuleType("helpers.projects")
    projects_stub.get_context_project_name = lambda context: ""
    projects_stub.load_basic_project_data = lambda project: {}
    monkeypatch.setitem(sys.modules, "helpers.projects", projects_stub)

    sys.modules.pop("plugins._scheduler.tools.scheduler", None)
    return importlib.import_module("plugins._scheduler.tools.scheduler")


def test_scheduler_accepts_action_alias(monkeypatch):
    module = _load_scheduler_tool(monkeypatch)
    tool = module.SchedulerTool(
        _FakeAgent(),
        "scheduler",
        None,
        {"action": "list_tasks"},
        "",
        None,
    )

    async def list_tasks(**kwargs):
        return module.Response("listed", False)

    tool.list_tasks = list_tasks

    response = asyncio.run(tool.execute(**tool.args))

    assert response.message == "listed"


def test_scheduler_requires_action_field(monkeypatch):
    module = _load_scheduler_tool(monkeypatch)
    tool = module.SchedulerTool(
        _FakeAgent(),
        "scheduler",
        "list_tasks",
        {},
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "Unknown scheduler action" in response.message


def test_scheduler_create_defaults_to_dedicated_context(monkeypatch):
    module = _load_scheduler_tool(monkeypatch)

    class FakeTaskSchedule:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

        def to_crontab(self):
            return f"{self.minute} {self.hour} {self.day} {self.month} {self.weekday}"

    class FakeScheduledTask:
        @classmethod
        def create(cls, **kwargs):
            task = cls()
            task.uuid = "task-1"
            task.context_id = kwargs.get("context_id")
            task.schedule = kwargs.get("schedule")
            return task

    class FakeScheduler:
        def __init__(self):
            self.added = None

        async def add_task(self, task):
            self.added = task

    fake_scheduler = FakeScheduler()
    module.TaskSchedule = FakeTaskSchedule
    module.ScheduledTask = FakeScheduledTask
    module.TaskScheduler = types.SimpleNamespace(get=lambda: fake_scheduler)
    tool = module.SchedulerTool(
        _FakeAgent(),
        "scheduler",
        None,
        {
            "action": "create_scheduled_task",
            "name": "check stuff",
            "prompt": "tell me if anything changed",
            "schedule": {"minute": "0", "hour": "9", "day": "*", "month": "*", "weekday": "*"},
        },
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "created" in response.message
    assert fake_scheduler.added.context_id is None


def test_scheduler_local_timezone_alias_uses_current_user_timezone(monkeypatch):
    module = _load_scheduler_tool(monkeypatch)

    class FakeTaskSchedule:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    module.TaskSchedule = FakeTaskSchedule
    module.Localization = types.SimpleNamespace(
        get=lambda: types.SimpleNamespace(get_timezone=lambda: "Europe/Rome")
    )

    assert module._schedule_timezone({"schedule": {"timezone": "local"}}) == "Europe/Rome"
    schedule = module._task_schedule_from_input(
        {"minute": "30", "hour": "9", "day": "*", "month": "*", "weekday": "*", "timezone": "current"}
    )

    assert schedule.timezone == "Europe/Rome"


def test_scheduler_invalid_timezone_returns_repairable_message(monkeypatch):
    module = _load_scheduler_tool(monkeypatch)
    tool = module.SchedulerTool(
        _FakeAgent(),
        "scheduler",
        None,
        {
            "action": "create_scheduled_task",
            "name": "bad timezone",
            "prompt": "tell me something",
            "schedule": {
                "minute": "0",
                "hour": "9",
                "day": "*",
                "month": "*",
                "weekday": "*",
                "timezone": "Mars/Base",
            },
        },
        "",
        None,
    )

    response = asyncio.run(tool.execute(**tool.args))

    assert "Invalid timezone: Mars/Base" in response.message


def test_scheduler_prompt_includes_update_timezone_and_dedicated_context():
    project_root = Path(__file__).resolve().parents[1]
    text = (
        project_root / "plugins/_scheduler/prompts/agent.system.tool.scheduler.md"
    ).read_text(encoding="utf-8")

    assert "update_task" in text
    assert "timezone" in text
    assert "IANA" in text
    assert "dedicated context" in text


def test_skills_prompt_renders_catalog_placeholder():
    project_root = Path(__file__).resolve().parents[1]
    text = (project_root / "prompts/agent.system.skills.md").read_text(
        encoding="utf-8"
    )

    assert "{{skills}}" in text


def test_corrected_tool_prompts_only_teach_action_contract():
    project_root = Path(__file__).resolve().parents[1]
    prompt_paths = [
        project_root / "plugins/_text_editor/prompts/agent.system.tool.text_editor.md",
        project_root / "prompts/agent.system.tool.skills.md",
        project_root / "plugins/_scheduler/prompts/agent.system.tool.scheduler.md",
        project_root / "plugins/_a0_connector/prompts/agent.system.tool.text_editor_remote.md",
        project_root / "plugins/_office/prompts/agent.system.tool.office_artifact.md",
        project_root / "plugins/_office/skills/office-artifacts/SKILL.md",
        project_root / "plugins/_office/skills/markdown-documents/SKILL.md",
        project_root / "plugins/_office/skills/writer-documents/SKILL.md",
        project_root / "plugins/_office/skills/calc-spreadsheets/SKILL.md",
        project_root / "plugins/_office/skills/impress-presentations/SKILL.md",
    ]
    forbidden = (
        "text_editor:",
        "skills_tool:",
        "scheduler:",
        "office_artifact:",
        "`method`",
        "`op`",
        "`operation`",
        "alias",
    )

    for path in prompt_paths:
        text = path.read_text(encoding="utf-8")
        assert "action" in text
        for token in forbidden:
            assert token not in text
        if "document" in path.name or "_office/skills" in str(path):
            assert "faux UI action labels" in text
            assert "Open document" in text
            assert "Download file" in text
            assert "Canvas was not opened automatically" not in text
            assert "Open Document, or Desktop edit actions" not in text


def test_computer_use_remote_is_runtime_checked_standard_tool():
    project_root = Path(__file__).resolve().parents[1]
    standard_prompt_path = (
        project_root
        / "plugins/_a0_connector/prompts/agent.system.tool.computer_use_remote.md"
    )
    standard_prompt_text = standard_prompt_path.read_text(encoding="utf-8")
    skill_text = (
        project_root
        / "plugins/_a0_connector/skills/host-computer-use/SKILL.md"
    ).read_text(encoding="utf-8")
    macos_skill_text = (
        project_root
        / "plugins/_a0_connector/skills/host-computer-use-macos/SKILL.md"
    ).read_text(encoding="utf-8")
    windows_skill_text = (
        project_root
        / "plugins/_a0_connector/skills/host-computer-use-windows/SKILL.md"
    ).read_text(encoding="utf-8")

    assert standard_prompt_path.exists()
    assert not (
        project_root
        / "plugins/_a0_connector/prompts/agent.system.runtime_tool.computer_use_remote.md"
    ).exists()
    assert '"tool_name": "computer_use_remote"' in standard_prompt_text
    assert "not scoped to a single chat context" in standard_prompt_text
    assert "checked when the tool runs" in standard_prompt_text
    assert "visual verification is unavailable" in standard_prompt_text
    assert "host-computer-use-macos" in standard_prompt_text
    assert "host-computer-use-windows" in standard_prompt_text
    assert "ax_snapshot" not in standard_prompt_text
    assert "ax_action" not in standard_prompt_text
    assert "uia_snapshot" not in standard_prompt_text
    assert "uia_action" not in standard_prompt_text
    assert '"tool_name": "computer_use_remote"' in skill_text
    assert "ax_snapshot" not in skill_text
    assert "ax_action" not in skill_text
    assert "uia_snapshot" not in skill_text
    assert "uia_action" not in skill_text
    assert '"tool_name": "computer_use_remote"' in macos_skill_text
    assert "ax_snapshot" in macos_skill_text
    assert "ax_action" in macos_skill_text
    assert '"tool_name": "computer_use_remote"' in windows_skill_text
    assert "uia_snapshot" in windows_skill_text
    assert "uia_action" in windows_skill_text
    assert "focus_window" in windows_skill_text
    assert "If a node offers `invoke`, use `invoke`, not `click`" in windows_skill_text
    assert "Backend-specific macOS guidance" in macos_skill_text
    assert "Backend-specific Windows guidance" in windows_skill_text
    assert "Beta desktop control" in skill_text


def test_computer_use_remote_start_session_reports_backend_features_and_macos_skill(monkeypatch):
    module = _load_computer_use_remote_tool(monkeypatch)
    tool = object.__new__(module.ComputerUseRemote)

    message = tool._extract_result(
        "start_session",
        {
            "ok": True,
            "result": {
                "session_id": "s1",
                "width": 1920,
                "height": 1080,
                "backend_id": "macos",
                "backend_family": "macos",
                "features": [
                    "accessibility-tree-snapshot",
                    "accessibility-structural-targeting",
                ],
            },
        },
    )

    assert "session_id=s1" in message
    assert "backend=macos/macos" in message
    assert "features=accessibility-tree-snapshot, accessibility-structural-targeting" in message
    assert "host-computer-use-macos" in message


def test_computer_use_remote_start_session_reports_backend_features_and_windows_skill(monkeypatch):
    module = _load_computer_use_remote_tool(monkeypatch)
    tool = object.__new__(module.ComputerUseRemote)

    message = tool._extract_result(
        "start_session",
        {
            "ok": True,
            "result": {
                "session_id": "s1",
                "width": 3840,
                "height": 2160,
                "backend_id": "windows",
                "backend_family": "windows",
                "features": [
                    "uia-tree-snapshot",
                    "uia-structural-targeting",
                ],
            },
        },
    )

    assert "session_id=s1" in message
    assert "backend=windows/windows" in message
    assert "features=uia-tree-snapshot, uia-structural-targeting" in message
    assert "host-computer-use-windows" in message


def test_computer_use_remote_forwards_documented_macos_app_scope(monkeypatch):
    import json
    import re

    module = _load_computer_use_remote_tool(monkeypatch)
    tool = object.__new__(module.ComputerUseRemote)
    skill = (Path(__file__).resolve().parents[1] / "plugins/_a0_connector/skills/host-computer-use-macos/SKILL.md").read_text()
    example = json.loads(re.search(r"```json\n(.*?)\n```", skill, re.S).group(1))
    tool.args = example["tool_args"]
    payload = tool._build_payload(op_id="scoped", context_id="ctx", action="element_action")
    assert payload["target"] == {"bundle_id": "com.example.editor", "role": "AXButton", "title": "Save"}
    assert payload["dispatch"] == "background"
    assert payload["operation"] == "press"
    tool.args = {**tool.args, "pid": 123, "window_id": "ax-pid:123:path:0", "element_index": 2}
    payload = tool._build_payload(op_id="indexed", context_id="ctx", action="element_action")
    assert (payload["pid"], payload["window_id"], payload["element_index"]) == (123, "ax-pid:123:path:0", 2)
    assert "element_index" not in payload["target"]


def test_computer_use_remote_forwards_linux_window_scope_and_type_guard(monkeypatch):
    module = _load_computer_use_remote_tool(monkeypatch)
    tool = object.__new__(module.ComputerUseRemote)
    window_id = "atspi-pid:57929:path:20.0"

    tool.args = {
        "action": "ax_snapshot",
        "pid": 57929,
        "window_id": window_id,
        "max_depth": 4,
        "max_nodes": 80,
    }
    snapshot = tool._build_payload(op_id="op-snapshot", context_id="ctx", action="ax_snapshot")
    tool.args = {"action": "type", "window_id": window_id, "text": "hello", "submit": True}
    typed = tool._build_payload(op_id="op-type", context_id="ctx", action="type")

    assert snapshot["pid"] == 57929
    assert snapshot["window_id"] == window_id
    assert snapshot["max_depth"] == 4
    assert snapshot["max_nodes"] == 80
    assert typed["window_id"] == window_id
    assert typed["text"] == "hello"
    assert typed["submit"] is True


def test_computer_use_remote_receipts_separate_injection_from_verified_result(monkeypatch):
    module = _load_computer_use_remote_tool(monkeypatch)
    tool = object.__new__(module.ComputerUseRemote)
    window_id = "atspi-pid:57929:path:20.0"

    verified = tool._extract_result(
        "type",
        {
            "ok": True,
            "result": {
                "text": "hello",
                "window_id": window_id,
                "focus_verified": True,
            },
        },
    )
    unverified = tool._extract_result(
        "type",
        {"ok": True, "result": {"text": "hello"}},
    )
    focused = tool._extract_result(
        "element_action",
        {
            "ok": True,
            "result": {
                "operation": "focus",
                "target": {"element_index": 0, "role": "frame", "title": "Discord"},
                "requested_dispatch": "foreground",
                "actual_dispatch": "foreground",
                "focus_verified": True,
            },
        },
    )
    scoped = tool._extract_result(
        "ax_snapshot",
        {
            "ok": True,
            "result": {
                "app": {"name": "Discord"},
                "tree": {"role": "frame", "title": "Discord"},
                "node_count": 2,
                "window_id": window_id,
                "scoped": True,
            },
        },
    )

    assert f"verified active window_id={window_id}" in verified
    assert "destination was not verified" in unverified
    assert "focus_verified=true" in focused
    assert f"scoped to window_id={window_id}" in scoped


def test_computer_use_remote_capture_artifact_is_chat_scoped(monkeypatch, tmp_path: Path):
    module = _load_computer_use_remote_tool(monkeypatch)

    def fake_get_abs_path(*parts):
        return str(tmp_path.joinpath(*parts))

    def fake_normalize_a0_path(path):
        return "/a0/" + str(Path(path).relative_to(tmp_path)).replace("\\", "/")

    monkeypatch.setattr(module.chat_media.files, "get_abs_path", fake_get_abs_path)
    monkeypatch.setattr(module.chat_media.files, "normalize_a0_path", fake_normalize_a0_path)

    tool = object.__new__(module.ComputerUseRemote)
    tool.agent = types.SimpleNamespace(context=types.SimpleNamespace(id="ctx-computer"))

    display_ref, capture_id = tool._resolve_capture_ref(
        {
            "artifact": {
                "filename": "capture.png",
                "mime": "image/png",
                "encoding": "base64",
                "data": "ZmFrZQ==",
            },
        }
    )

    assert display_ref.startswith("/a0/usr/chats/ctx-computer/screenshots/computer-use/capture-")
    stored_path = tmp_path / display_ref.removeprefix("/a0/")
    assert stored_path.read_bytes() == b"fake"
    assert capture_id == stored_path.stem
