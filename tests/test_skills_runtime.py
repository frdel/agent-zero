import importlib.util
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILLS_HELPER_PATH = PROJECT_ROOT / "helpers" / "skills.py"
HELPER_STUB_MODULES = (
    "helpers",
    "helpers.files",
    "helpers.projects",
    "helpers.plugins",
    "helpers.subagents",
    "helpers.file_tree",
    "helpers.runtime",
    "helpers.extension",
)


def _register_helpers_stubs():
    helpers_pkg = types.ModuleType("helpers")
    helpers_pkg.__path__ = []

    files = types.ModuleType("helpers.files")
    files.normalize_a0_path = lambda path: str(path).replace("\\", "/")
    files.fix_dev_path = lambda path: str(path).replace("\\", "/")
    files.get_abs_path = lambda *parts: "/" + "/".join(str(part).strip("/") for part in parts if part)
    files.exists = lambda path: False
    files.is_in_dir = lambda path, root: str(path).startswith(str(root))
    files.find_existing_paths_by_pattern = lambda pattern: []
    files.read_file = lambda path: ""

    projects = types.ModuleType("helpers.projects")
    projects.get_context_project_name = lambda context: context.get_data("project")
    projects.get_project_meta = lambda project_name, *parts: (
        f"/projects/{project_name}/" + "/".join(str(part).strip("/") for part in parts if part)
        if project_name
        else ""
    )

    plugins = types.ModuleType("helpers.plugins")
    plugins.get_plugin_config = lambda *args, **kwargs: {}
    plugins.get_enabled_plugin_paths = lambda *args, **kwargs: []

    subagents = types.ModuleType("helpers.subagents")
    subagents.get_paths = lambda agent, *parts: []

    file_tree = types.ModuleType("helpers.file_tree")
    file_tree.file_tree = lambda *args, **kwargs: ""

    extension = types.ModuleType("helpers.extension")
    extension.extensible = lambda func: func

    runtime = types.ModuleType("helpers.runtime")
    runtime.is_development = lambda: False

    helpers_pkg.files = files
    helpers_pkg.projects = projects
    helpers_pkg.plugins = plugins
    helpers_pkg.subagents = subagents
    helpers_pkg.file_tree = file_tree
    helpers_pkg.runtime = runtime

    sys.modules["helpers"] = helpers_pkg
    sys.modules["helpers.files"] = files
    sys.modules["helpers.projects"] = projects
    sys.modules["helpers.plugins"] = plugins
    sys.modules["helpers.subagents"] = subagents
    sys.modules["helpers.file_tree"] = file_tree
    sys.modules["helpers.runtime"] = runtime
    sys.modules["helpers.extension"] = extension


def _load_skills_helper_module():
    missing = object()
    original_modules = {name: sys.modules.get(name, missing) for name in HELPER_STUB_MODULES}
    _register_helpers_stubs()
    try:
        spec = importlib.util.spec_from_file_location("test_skills_helper_module", SKILLS_HELPER_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in original_modules.items():
            if original is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


runtime = _load_skills_helper_module()


class DummyContext:
    def __init__(self):
        self.data = {}
        self.agent = None

    def get_data(self, key, recursive=True):
        return self.data.get(key)

    def set_data(self, key, value, recursive=True):
        self.data[key] = value

    def get_agent(self):
        return self.agent


class DummyAgent:
    def __init__(self):
        self.context = DummyContext()
        self.context.agent = self
        self.data = {}


def _scope_config(entries=None, *, hidden_entries=None, max_active_skills=None):
    config = {}
    if entries is not None:
        config["active_skills"] = entries
    if hidden_entries is not None:
        config["hidden_skills"] = hidden_entries
    if max_active_skills is not None:
        config["max_active_skills"] = max_active_skills
    return config


def _write_skill_catalog(root: Path, *names: str) -> Path:
    skills_root = root / "skills"
    for name in names:
        skill_dir = skills_root / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name} description\n---\nBody\n",
            encoding="utf-8",
        )
    return skills_root


def test_active_skills_cap_is_twenty():
    assert runtime.MAX_ACTIVE_SKILLS == 20
    assert runtime.get_max_active_skills() == 20


def test_skills_config_can_raise_active_cap_above_default():
    config = runtime.normalize_skills_config(
        {
            "max_active_skills": 25,
            "active_skills": [{"name": f"Skill {index}"} for index in range(25)],
        }
    )

    assert config["max_active_skills"] == 25
    assert len(config["active_skills"]) == 25


def test_hidden_skills_are_not_capped_like_active_skills():
    agent = DummyAgent()
    entries = [{"name": f"Hidden {index}"} for index in range(25)]
    agent.context.set_data(runtime.CONTEXT_DATA_NAME_CHAT_DISABLED_SKILLS, entries)

    assert len(runtime.get_chat_disabled_skills(agent.context)) == 25
    assert len(runtime.get_hidden_skills(agent)) == 25


def test_active_skill_prompt_protocol_is_disabled(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config([{"name": "Pinned"}]),
    )
    agent = DummyAgent()

    assert runtime.get_active_skills(agent) == [{"name": "Pinned"}]
    assert runtime.build_active_skills_prompt(agent) == ""


def test_hiding_skill_does_not_unload_history_loaded_skill():
    agent = DummyAgent()
    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_LOADED_SKILLS,
        ["history-skill"],
    )

    runtime.hide_chat_skill(agent, {"name": "history-skill"})

    assert agent.context.get_data(runtime.CONTEXT_DATA_NAME_LOADED_SKILLS) == [
        "history-skill"
    ]
    assert runtime.get_chat_disabled_skills(agent.context) == [
        {"name": "history-skill"}
    ]


def test_chat_activation_can_override_scope_defaults(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config([{"name": "Pinned"}]),
    )
    agent = DummyAgent()

    assert [entry["name"] for entry in runtime.get_active_skills(agent)] == [
        "Pinned"
    ]

    runtime.activate_chat_skill(agent, {"name": "Extra"})
    assert [entry["name"] for entry in runtime.get_active_skills(agent)] == [
        "Pinned",
        "Extra",
    ]
    assert [entry["name"] for entry in runtime.get_chat_active_skills(agent.context)] == [
        "Extra"
    ]

    runtime.deactivate_chat_skill(agent, {"name": "Pinned"})
    assert [entry["name"] for entry in runtime.get_active_skills(agent)] == [
        "Extra"
    ]
    assert [entry["name"] for entry in runtime.get_chat_disabled_skills(agent.context)] == [
        "Pinned"
    ]

    runtime.activate_chat_skill(agent, {"name": "Pinned"})
    assert [entry["name"] for entry in runtime.get_active_skills(agent)] == [
        "Pinned",
        "Extra",
    ]
    assert runtime.get_chat_disabled_skills(agent.context) == []


def test_chat_deactivation_hides_name_only_scope_default_by_path(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config([{"name": "Pinned"}]),
    )
    agent = DummyAgent()

    runtime.deactivate_chat_skill(
        agent,
        {"name": "Pinned", "path": "/a0/usr/skills/custom/pinned"},
    )

    assert runtime.get_active_skills(agent) == []
    assert runtime.get_chat_disabled_skills(agent.context) == [
        {"name": "Pinned", "path": "/a0/usr/skills/custom/pinned"}
    ]


def test_reactivating_name_only_scope_default_by_path_clears_hidden_override(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config([{"name": "Pinned"}]),
    )
    agent = DummyAgent()

    runtime.deactivate_chat_skill(
        agent,
        {"name": "Pinned", "path": "/a0/usr/skills/custom/pinned"},
    )
    runtime.activate_chat_skill(
        agent,
        {"name": "Pinned", "path": "/a0/usr/skills/custom/pinned"},
    )

    assert runtime.get_active_skills(agent) == [{"name": "Pinned"}]
    assert runtime.get_chat_active_skills(agent.context) == []
    assert runtime.get_chat_disabled_skills(agent.context) == []


def test_loaded_skill_entries_come_from_context_data():
    agent = DummyAgent()
    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_LOADED_SKILLS,
        [
            "host-computer-use",
            "",
            "a0-development",
        ],
    )

    assert runtime.get_loaded_skill_entries(agent) == [
        {"name": "host-computer-use"},
        {"name": "a0-development"},
    ]


def test_loaded_skill_entries_migrate_legacy_agent_data():
    agent = DummyAgent()
    agent.data[runtime.AGENT_DATA_NAME_LOADED_SKILLS] = [
        "host-computer-use",
        "",
        "a0-development",
    ]

    assert runtime.get_loaded_skill_entries(agent) == [
        {"name": "host-computer-use"},
        {"name": "a0-development"},
    ]
    assert agent.context.get_data(runtime.CONTEXT_DATA_NAME_LOADED_SKILLS) == [
        "host-computer-use",
        "a0-development",
    ]
    assert runtime.AGENT_DATA_NAME_LOADED_SKILLS not in agent.data


def test_unloading_last_migrated_skill_does_not_restore_legacy_agent_data():
    agent = DummyAgent()
    agent.data[runtime.AGENT_DATA_NAME_LOADED_SKILLS] = ["host-computer-use"]

    assert runtime.unload_agent_skill(agent, {"name": "host-computer-use"}) is True
    assert agent.context.get_data(runtime.CONTEXT_DATA_NAME_LOADED_SKILLS) is None
    assert runtime.get_loaded_skill_entries(agent) == []


def test_skill_runtime_does_not_alias_old_office_skill_references():
    entries = runtime.normalize_active_skills(
        [
            "office-artifacts",
            {"name": "word-documents"},
            {"path": "/a0/plugins/_office/skills/excel-workbooks"},
            {"name": "Desktop", "path": "/a0/plugins/_office/skills/linux-desktop"},
            "presentation-decks",
        ]
    )

    assert entries == [
        {"name": "office-artifacts"},
        {"name": "word-documents"},
        {"path": "/a0/plugins/_office/skills/excel-workbooks"},
        {"name": "Desktop", "path": "/a0/plugins/_office/skills/linux-desktop"},
        {"name": "presentation-decks"},
    ]

    agent = DummyAgent()
    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_LOADED_SKILLS,
        [
            "office-artifacts",
            "word-documents",
            "excel-workbooks",
            "presentation-decks",
        ],
    )

    assert runtime.get_loaded_skill_entries(agent) == [
        {"name": "office-artifacts"},
        {"name": "word-documents"},
        {"name": "excel-workbooks"},
        {"name": "presentation-decks"},
    ]

    assert runtime.unload_agent_skill(agent, {"name": "office-artifacts"}) is True
    assert agent.context.get_data(runtime.CONTEXT_DATA_NAME_LOADED_SKILLS) == [
        "word-documents",
        "excel-workbooks",
        "presentation-decks",
    ]


def test_builtin_plugin_skill_delete_is_rejected_before_filesystem_delete():
    with pytest.raises(PermissionError, match="Built-in plugin skills cannot be deleted"):
        runtime.delete_skill("/a0/plugins/_office/skills/office-artifacts")


def test_invalid_skill_frontmatter_reports_yaml_errors():
    frontmatter, errors = runtime.parse_frontmatter("name: [unterminated\n")

    assert frontmatter == {}
    assert errors
    assert errors[0].startswith("Invalid YAML frontmatter")


def test_invalid_skill_frontmatter_warns_when_skill_is_skipped(monkeypatch, tmp_path: Path):
    skills_root = tmp_path / "skills"
    broken = skills_root / "broken-skill"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text(
        "---\nname: broken-skill\ndescription: missing closing fence\nBody\n",
        encoding="utf-8",
    )

    warnings: list[str] = []
    runtime._WARNED_SKILL_PARSE_PATHS.clear()
    monkeypatch.setattr(runtime, "get_skill_roots", lambda agent=None: [str(skills_root)])
    monkeypatch.setattr(runtime, "_emit_skill_scan_warning", warnings.append)

    assert runtime.list_skills() == []
    assert warnings == [
        "skill broken-skill skipped: invalid frontmatter at line 4: "
        "Unterminated YAML frontmatter"
    ]

    assert runtime.list_skills() == []
    assert len(warnings) == 1


def test_a0_manage_plugin_skill_frontmatter_is_valid_yaml():
    text = (PROJECT_ROOT / "plugins" / "_bundled_skills" / "skills" / "a0-manage-plugin" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    frontmatter, body, errors = runtime.split_frontmatter(text)

    assert errors == []
    assert frontmatter["name"] == "a0-manage-plugin"
    assert "Agent Zero Plugin Management" in body


def test_renamed_skills_use_standard_frontmatter_only():
    skill_paths = [
        PROJECT_ROOT / "plugins" / "_bundled_skills" / "skills" / "build-skill" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_bundled_skills" / "skills" / "scheduled-tasks" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-code-execution" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-computer-use" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-computer-use-macos" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-computer-use-windows" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-file-editing" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_bundled_skills" / "skills" / "setup-a0-cli" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-automation" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-extension-control" / "SKILL.md",
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-form-workflows" / "SKILL.md",
    ]

    for path in skill_paths:
        frontmatter, body, errors = runtime.split_frontmatter(path.read_text(encoding="utf-8"))
        assert errors == []
        expected_keys = {"name", "description"}
        if path.parent.name == "host-computer-use":
            expected_keys.update({"tags", "triggers"})
        if path.parent.name in {"browser-automation", "browser-extension-control", "browser-form-workflows", "setup-a0-cli"}:
            expected_keys.add("triggers")
        assert set(frontmatter) == expected_keys
        assert frontmatter["name"] == path.parent.name
        assert frontmatter["description"]
        assert body


def test_browser_skills_rank_for_browser_trigger_phrases(monkeypatch):
    browser_automation = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-automation" / "SKILL.md"
    )
    browser_forms = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_browser" / "skills" / "browser-form-workflows" / "SKILL.md"
    )
    document_query = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_document_query" / "skills" / "document-query" / "SKILL.md"
    )
    host_computer = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-computer-use" / "SKILL.md"
    )
    assert browser_automation is not None
    assert browser_forms is not None
    assert document_query is not None
    assert host_computer is not None
    monkeypatch.setattr(
        runtime,
        "list_skills",
        lambda *args, **kwargs: [
            document_query,
            host_computer,
            browser_forms,
            browser_automation,
        ],
    )

    browser_queries = (
        "open this URL in my browser and take a screenshot",
        "interact with a JavaScript page and verify it visually",
        "use the host browser for multi-tab browsing",
    )
    for query in browser_queries:
        results = runtime.search_skills(query, limit=3)
        assert results[0].name == "browser-automation"

    form_results = [
        skill.name
        for skill in runtime.search_skills(
            "fill a web form with a checkbox and file upload",
            limit=3,
        )
    ]
    assert "browser-automation" in form_results
    assert "browser-form-workflows" in form_results


def test_skill_search_does_not_score_description_terms_alone(monkeypatch):
    browser_automation = runtime.Skill(
        name="browser-automation",
        description=(
            "Use for browser automation, screenshots, forms, uploads, "
            "and complex tool workflows."
        ),
        path=Path("/skills/browser-automation"),
        skill_md_path=Path("/skills/browser-automation/SKILL.md"),
    )
    monkeypatch.setattr(runtime, "list_skills", lambda *args, **kwargs: [browser_automation])

    rendered_user_message = (
        'user: {"user_message": "Please reply with exactly OK. Do not use tools.", '
        '"attachments": []}'
    )

    assert runtime.search_skills(rendered_user_message) == []
    assert runtime.search_skills("Open a browser screenshot?", limit=1) == [browser_automation]


def test_host_computer_use_ranks_before_linux_desktop_for_host_screen_queries(monkeypatch):
    host_skill = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_a0_connector" / "skills" / "host-computer-use" / "SKILL.md"
    )
    linux_skill = runtime.skill_from_markdown(
        PROJECT_ROOT / "plugins" / "_desktop" / "skills" / "linux-desktop" / "SKILL.md"
    )
    assert host_skill is not None
    assert linux_skill is not None
    monkeypatch.setattr(runtime, "list_skills", lambda *args, **kwargs: [linux_skill, host_skill])

    host_queries = (
        "hide a window on my host computer screen with computer use",
        "take screenshot of my local Ubuntu Wayland desktop",
        "minimize a window on my screen",
    )
    for query in host_queries:
        results = runtime.search_skills(query, limit=2)
        assert results[0].name == "host-computer-use"

    xpra_results = runtime.search_skills(
        "operate Agent Zero built-in Xpra Desktop LibreOffice GUI",
        limit=2,
    )
    assert xpra_results[0].name == "linux-desktop"


def test_unload_agent_skill_removes_loaded_skill_by_name():
    agent = DummyAgent()
    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_LOADED_SKILLS,
        [
            "host-computer-use",
            "a0-development",
        ],
    )

    removed = runtime.unload_agent_skill(
        agent,
        {
            "name": "host-computer-use",
            "path": "/a0/plugins/_a0_connector/skills/host-computer-use",
        },
    )

    assert removed is True
    assert agent.context.get_data(runtime.CONTEXT_DATA_NAME_LOADED_SKILLS) == [
        "a0-development"
    ]


def test_clearing_chat_overrides_restores_scope_defaults(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config([{"name": "Pinned"}]),
    )
    agent = DummyAgent()
    runtime.activate_chat_skill(agent, {"name": "Extra"})
    runtime.deactivate_chat_skill(agent, {"name": "Pinned"})

    runtime.clear_chat_skill_overrides(agent)

    assert [entry["name"] for entry in runtime.get_active_skills(agent)] == [
        "Pinned"
    ]
    assert runtime.get_chat_active_skills(agent.context) == []
    assert runtime.get_chat_disabled_skills(agent.context) == []
    assert runtime.get_chat_visible_skills(agent.context) == []


def test_activating_new_skill_fails_once_limit_is_full(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config(
            [{"name": f"Pinned {index}"} for index in range(20)]
        ),
    )
    agent = DummyAgent()

    with pytest.raises(ValueError, match="at most 20"):
        runtime.activate_chat_skill(agent, {"name": "Overflow"})

    assert len(runtime.get_active_skills(agent)) == 20


def test_chat_activation_respects_scope_configured_cap(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config(max_active_skills=25),
    )
    agent = DummyAgent()

    for index in range(21):
        runtime.activate_chat_skill(agent, {"name": f"Extra {index}"})

    assert len(runtime.get_chat_active_skills(agent.context)) == 21
    assert len(runtime.get_active_skills(agent)) == 21


def test_activating_new_skill_uses_scope_configured_limit(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: _scope_config(
            [{"name": f"Pinned {index}"} for index in range(3)],
            max_active_skills=3,
        ),
    )
    agent = DummyAgent()

    with pytest.raises(ValueError, match="at most 3"):
        runtime.activate_chat_skill(agent, {"name": "Overflow"})

    assert len(runtime.get_active_skills(agent)) == 3


def test_hidden_skills_filter_agent_visible_skill_catalog(monkeypatch, tmp_path: Path):
    skills_root = _write_skill_catalog(tmp_path, "alpha-skill", "beta-skill")

    monkeypatch.setattr(
        runtime.subagents,
        "get_paths",
        lambda agent, *parts: [str(skills_root)],
    )
    monkeypatch.setattr(runtime.files, "exists", lambda path: Path(str(path)) == skills_root)
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: {"hidden_skills": [{"name": "beta-skill"}]},
    )

    agent = DummyAgent()

    assert [skill.name for skill in runtime.list_skills(agent)] == ["alpha-skill"]
    assert [skill.name for skill in runtime.list_skills(agent, include_hidden=True)] == [
        "alpha-skill",
        "beta-skill",
    ]
    assert runtime.search_skills("beta", agent=agent) == []
    assert [skill.name for skill in runtime.search_skills("beta", agent=agent, include_hidden=True)] == [
        "beta-skill"
    ]
    assert runtime.find_skill("beta-skill", agent=agent) is None
    assert runtime.find_skill("beta-skill", agent=agent, include_hidden=True).name == "beta-skill"

    catalog = runtime.list_skill_catalog(agent=agent)
    hidden_by_name = {item["name"]: item["hidden"] for item in catalog}
    assert hidden_by_name == {
        "alpha-skill": False,
        "beta-skill": True,
    }


def test_chat_visible_override_restores_scope_hidden_skill(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: {"hidden_skills": [{"name": "beta-skill"}]},
    )
    agent = DummyAgent()

    assert runtime.get_hidden_skills(agent) == [{"name": "beta-skill"}]

    runtime.show_chat_skill(agent, {"name": "beta-skill"})
    assert runtime.get_hidden_skills(agent) == []
    assert runtime.get_chat_visible_skills(agent.context) == [{"name": "beta-skill"}]

    runtime.hide_chat_skill(agent, {"name": "beta-skill"})
    assert runtime.get_hidden_skills(agent) == [{"name": "beta-skill"}]
    assert runtime.get_chat_visible_skills(agent.context) == []


def test_visibility_policy_is_absent_until_explicitly_configured():
    normalized = runtime.normalize_skills_config({"hidden_skills": []})

    assert "visibility_policy" not in normalized
    assert runtime.normalize_visibility_policy(
        {
            "mode": "custom",
            "default": "block",
            "allowed": ["alpha", "alpha", {"name": "missing"}],
            "blocked": [],
        }
    ) == {
        "mode": "custom",
        "default": "block",
        "allowed": ["alpha", "missing"],
        "blocked": [],
    }


def test_allow_only_visibility_blocks_new_skills_without_pinning(
    monkeypatch, tmp_path: Path
):
    skills_root = _write_skill_catalog(tmp_path, "alpha-skill", "new-skill")

    monkeypatch.setattr(
        runtime.subagents,
        "get_paths",
        lambda agent, *parts: [str(skills_root)],
    )
    monkeypatch.setattr(runtime.files, "exists", lambda path: Path(str(path)) == skills_root)
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: {
            "visibility_policy": {
                "mode": "custom",
                "default": "block",
                "allowed": ["alpha-skill"],
                "blocked": [],
            }
        },
    )
    agent = DummyAgent()

    assert [skill.name for skill in runtime.list_skills(agent)] == ["alpha-skill"]
    assert runtime.find_skill("new-skill", agent=agent) is None
    assert runtime.load_skill_for_agent("new-skill", agent=agent) == (
        "Error: skill 'new-skill' not found"
    )
    assert runtime.get_active_skills(agent) == []

    catalog = {item["name"]: item for item in runtime.list_skill_catalog(agent=agent)}
    assert catalog["alpha-skill"]["hidden"] is False
    assert catalog["new-skill"]["hidden"] is True


def test_profile_blocked_skill_cannot_be_reenabled_by_chat_override(monkeypatch):
    monkeypatch.setattr(
        runtime.plugin_helpers,
        "get_plugin_config",
        lambda *args, **kwargs: {
            "visibility_policy": {
                "mode": "custom",
                "default": "allow",
                "allowed": [],
                "blocked": ["beta-skill"],
            }
        },
    )
    agent = DummyAgent()

    with pytest.raises(ValueError, match='Skill "beta-skill" is blocked'):
        runtime.activate_chat_skill(agent, {"name": "beta-skill"})
    with pytest.raises(ValueError, match='Skill "beta-skill" is blocked'):
        runtime.show_chat_skill(agent, {"name": "beta-skill"})
    with pytest.raises(ValueError, match="is blocked"):
        runtime.activate_chat_skill(
            agent, {"path": "/a0/skills/beta-skill"}
        )
    with pytest.raises(ValueError, match="is blocked"):
        runtime.show_chat_skill(agent, {"path": "/a0/skills/beta-skill"})

    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_CHAT_VISIBLE_SKILLS,
        [{"name": "beta-skill"}],
    )
    agent.context.set_data(
        runtime.CONTEXT_DATA_NAME_CHAT_ACTIVE_SKILLS,
        [{"path": "/a0/skills/beta-skill"}],
    )
    assert runtime.get_active_skills(agent) == []
