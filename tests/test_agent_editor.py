from __future__ import annotations

import asyncio
from io import BytesIO
import json
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import FileStorage

from helpers import yaml as yaml_helper
from plugins._agent_editor.api.agent_editor import AgentEditor
from plugins._agent_editor.api.agent_editor import _context as editor_context
from plugins._agent_editor.api.agent_editor_avatar import AgentEditorAvatar
from plugins._agent_editor.helpers import editor


@pytest.fixture
def user_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "usr" / "agents"
    real_determine_path = editor.plugins.determine_plugin_asset_path

    def determine_plugin_asset_path(
        plugin_name: str,
        project_name: str,
        profile_id: str,
        *parts: str,
    ) -> str:
        if profile_id and not project_name:
            return str(
                root
                / profile_id
                / editor.files.PLUGINS_DIR
                / plugin_name
                / Path(*parts)
            )
        return real_determine_path(plugin_name, project_name, profile_id, *parts)

    monkeypatch.setattr(editor, "USER_AGENTS_ROOT", root)
    monkeypatch.setattr(editor, "STAGED_AVATAR_ROOT", tmp_path / "staged")
    monkeypatch.setattr(
        editor.plugins,
        "determine_plugin_asset_path",
        determine_plugin_asset_path,
    )
    monkeypatch.setattr(editor.plugins, "clear_plugin_cache", lambda _names: None)
    return root


@pytest.fixture
def project_scope(
    user_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[editor._EditorContext, Path]:
    project_folder = tmp_path / "usr" / "projects" / "demo"
    project_meta = project_folder / ".a0proj"
    project_meta.mkdir(parents=True)
    real_folder = editor.projects.get_project_folder
    real_meta = editor.projects.get_project_meta
    monkeypatch.setattr(
        editor.projects,
        "get_project_folder",
        lambda name: str(project_folder) if name == "demo" else real_folder(name),
    )
    monkeypatch.setattr(
        editor.projects,
        "get_project_meta",
        lambda name, *parts: (
            str(project_meta.joinpath(*parts))
            if name == "demo"
            else real_meta(name, *parts)
        ),
    )
    return editor._EditorContext("demo"), project_meta / "agents"


def _write_manual_files(root: Path) -> dict[Path, bytes]:
    manual_files = {
        root / "prompts" / "manual.md": b"prompt",
        root / "tools" / "manual.py": b"tool",
        root / "extensions" / "manual.py": b"extension",
        root / "skills" / "manual" / "SKILL.md": b"skill",
        root / "assets" / "manual.bin": b"asset",
        root / "plugins" / "manual" / "config.json": b"{}",
        root / "unknown.bin": b"unknown",
    }
    for path, payload in manual_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return manual_files


def test_new_easy_profile_writes_only_minimum_exact_files(user_root: Path) -> None:
    instructions = "Keep this exact.  \n\nNo rewrite."
    plan = editor.build_change_plan(
        {
            "profile_id": "legal-research",
            "creating": True,
            "editor_mode": "easy",
            "metadata": {"set": {"title": "Legal Research"}, "reset": []},
            "prompts": {
                "set": {editor.SPECIFICS_FILE: instructions},
                "reset": [],
            },
            "tool_policy": {"mode": "inherit"},
        }
    )

    assert {path.relative_to(user_root).as_posix() for path in plan.changes} == {
        "legal-research/agent.yaml",
        f"legal-research/prompts/{editor.SPECIFICS_FILE}",
    }
    editor.apply_change_plan(plan)

    profile = user_root / "legal-research"
    assert yaml_helper.loads((profile / "agent.yaml").read_text()) == {
        "title": "Legal Research"
    }
    assert (profile / "prompts" / editor.SPECIFICS_FILE).read_text() == instructions
    assert not list(profile.rglob("*.json"))
    assert stat.S_IMODE((profile / "agent.yaml").stat().st_mode) == 0o644
    assert (
        stat.S_IMODE((profile / "prompts" / editor.SPECIFICS_FILE).stat().st_mode)
        == 0o644
    )


def test_quick_create_uses_the_easy_sparse_save_path(user_root: Path) -> None:
    profile_id, receipt = editor.save_easy_profile(
        "Café Research",
        "Verify sources and return concise citations.",
    )

    assert profile_id == "cafe-research"
    assert len(receipt["written"]) == 2
    assert yaml_helper.loads(
        (user_root / profile_id / "agent.yaml").read_text(encoding="utf-8")
    ) == {"title": "Café Research"}
    assert not list((user_root / profile_id).rglob("*.json"))


def test_editor_lifecycle_needs_no_model_or_utility_configuration(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import litellm
    from plugins._model_config.helpers import model_config

    def forbidden(*_args, **_kwargs):
        raise AssertionError("the Agent Editor attempted a model request")

    for name in ("completion", "acompletion", "embedding", "aembedding"):
        monkeypatch.setattr(litellm, name, forbidden, raising=False)
    monkeypatch.setattr(model_config, "get_presets", lambda: [{"name": "No utility"}])
    monkeypatch.setattr(
        model_config,
        "resolve_config_settings",
        lambda _settings: {
            "chat_model": {"provider": "offline", "name": "main"},
            "utility_model": {},
            "embedding_model": {},
        },
    )
    monkeypatch.setattr(
        model_config,
        "get_configured_preset_name",
        lambda **_kwargs: "No utility",
    )
    monkeypatch.setattr(editor.tool_policy, "get_tool_catalog", lambda _agent: [])
    monkeypatch.setattr(editor.skills, "list_skill_catalog", lambda agent=None: [])

    state = editor.build_editor_state("offline-editor")
    plan = editor.build_change_plan(
        {
            "profile_id": "offline-editor",
            "creating": True,
            "editor_mode": "easy",
            "metadata": {"set": {"title": "Offline Editor"}, "reset": []},
            "prompts": {"set": {editor.SPECIFICS_FILE: "Exact text."}, "reset": []},
        }
    )
    receipt = plan.response()

    assert state["model_presets"][0]["utility"] == {"provider": "", "name": ""}
    assert editor.apply_change_plan(plan) == receipt


def test_state_catalog_is_complete_truthful_and_omits_internal_tools() -> None:
    state = editor.build_editor_state("researcher")

    assert all(
        preset[slot]["provider"] and preset[slot]["name"]
        for preset in state["model_presets"]
        for slot in ("main", "utility", "embedding")
    )
    assert {prompt["group"] for prompt in state["prompts"]} == {
        f"2.{index}" for index in range(1, 11)
    }
    assert all(
        {
            "effective",
            "override",
            "has_override",
            "source",
            "source_chain",
            "state",
        }.issubset(prompt)
        for prompt in state["prompts"]
    )
    assert "AGENTS.md" not in {prompt["filename"] for prompt in state["prompts"]}
    specifics = next(
        prompt for prompt in state["prompts"]
        if prompt["filename"] == editor.SPECIFICS_FILE
    )
    assert specifics["source_chain"] == ["Framework", "Plugin · _agent_profiles"]
    assert any(
        any(source.startswith("Plugin ·") for source in prompt["source_chain"])
        for prompt in state["prompts"]
    )
    assert not {
        item["name"] for item in state["tools"]["catalog"]
    }.intersection({"response", "vision_load"})


def test_builtin_prompt_override_never_touches_bundled_profile(user_root: Path) -> None:
    bundled = Path("plugins/_agent_profiles/agents/researcher")
    before = {path: path.read_bytes() for path in bundled.rglob("*") if path.is_file()}
    content = "Only the user-layer instructions change."
    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "prompts": {
                "set": {editor.SPECIFICS_FILE: content},
                "reset": [],
            },
        }
    )

    assert list(plan.changes) == [
        user_root / "researcher" / "prompts" / editor.SPECIFICS_FILE
    ]
    editor.apply_change_plan(plan)
    assert all(path.read_bytes() == payload for path, payload in before.items())

    reset = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "prompts": {"set": {}, "reset": [editor.SPECIFICS_FILE]},
        }
    )
    editor.apply_change_plan(reset)
    assert not (user_root / "researcher" / "prompts" / editor.SPECIFICS_FILE).exists()


def test_unrelated_empty_user_directory_survives_save(user_root: Path) -> None:
    manual = user_root / "researcher" / "tools" / "reserved-for-manual-use"
    manual.mkdir(parents=True)

    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "prompts": {
                "set": {editor.SPECIFICS_FILE: "Sparse change only."},
                "reset": [],
            },
        }
    )
    editor.apply_change_plan(plan)

    assert manual.is_dir()


def test_profile_collision_includes_disabled_plugin_profiles(
    user_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin_profile = tmp_path / "disabled-plugin" / "agents" / "reserved-agent"
    plugin_profile.mkdir(parents=True)
    monkeypatch.setattr(
        editor.plugins,
        "get_plugin_paths",
        lambda *parts: [str(plugin_profile)] if parts == ("agents", "reserved-agent") else [],
    )

    assert editor.profile_exists("reserved-agent") is True


def test_metadata_empty_values_and_unknown_keys_survive(user_root: Path) -> None:
    profile = user_root / "researcher"
    profile.mkdir(parents=True)
    metadata = profile / "agent.yaml"
    metadata.write_text("custom_key: keep\ndescription: old\n", encoding="utf-8")

    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "metadata": {
                "set": {"description": "", "context": ""},
                "reset": [],
            },
        }
    )
    editor.apply_change_plan(plan)

    saved = yaml_helper.loads(metadata.read_text())
    assert saved == {"custom_key": "keep", "description": "", "context": ""}


def test_plugin_configs_preserve_unowned_keys_and_use_json(user_root: Path) -> None:
    profile = user_root / "researcher" / "plugins"
    model = profile / "_model_config" / "config.json"
    tools = profile / "_tool_access" / "config.json"
    skill = profile / "_skills" / "config.json"
    for path, value in (
        (model, {"manual": 1}),
        (tools, {"manual": 2}),
        (skill, {"active_skills": [{"name": "existing"}]}),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    preset = editor.build_editor_state("researcher")["model_presets"][0]["name"]
    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "model_preset": {"mode": "preset", "name": preset},
            "tool_policy": {
                "mode": "custom",
                "default": "block",
                "mcp_default": "allow",
                "allowed": ["local:search_engine"],
                "blocked": ["local:shell"],
            },
            "skill_policy": {
                "mode": "custom",
                "default": "block",
                "allowed": ["a0-development"],
                "blocked": [],
            },
        }
    )
    editor.apply_change_plan(plan)

    assert json.loads(model.read_text())["manual"] == 1
    assert set(json.loads(tools.read_text())) >= {
        "manual", "mode", "default", "mcp_default", "allowed", "blocked"
    }
    skill_data = json.loads(skill.read_text())
    assert skill_data["active_skills"] == [{"name": "existing"}]
    assert skill_data["visibility_policy"]["default"] == "block"

    editor.apply_change_plan(editor.plan_remove_changes("researcher"))

    assert json.loads(model.read_text()) == {"manual": 1}
    assert json.loads(tools.read_text()) == {"manual": 2}
    assert json.loads(skill.read_text()) == {
        "active_skills": [{"name": "existing"}]
    }
    assert editor.build_profile_state("researcher")["scope_has_overrides"] is False


def test_model_and_off_tool_choices_write_only_their_json_contracts(
    user_root: Path,
) -> None:
    preset = editor.build_editor_state("researcher")["model_presets"][1]["name"]
    model_path = user_root / "researcher" / "plugins" / "_model_config" / "config.json"
    tool_path = user_root / "researcher" / "plugins" / "_tool_access" / "config.json"

    inherit = editor.build_change_plan(
        {"profile_id": "researcher", "model_preset": {"mode": "inherit"}}
    )
    assert inherit.changes == {}

    selected = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "model_preset": {"mode": "preset", "name": preset},
        }
    )
    assert list(selected.changes) == [model_path]
    assert json.loads(selected.changes[model_path].content) == {"model_preset": preset}

    off = editor.build_change_plan(
        {"profile_id": "researcher", "tool_policy": {"mode": "off"}}
    )
    assert list(off.changes) == [tool_path]
    assert json.loads(off.changes[tool_path].content) == {
        "mode": "custom",
        "default": "block",
        "mcp_default": "block",
        "allowed": [],
        "blocked": [],
    }


def test_profile_summaries_do_not_build_removal_plans(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = user_root / "researcher"
    (profile / "plugins" / "manual").mkdir(parents=True)
    (profile / "plugins" / "manual" / "config.json").write_text("{}")
    monkeypatch.setattr(
        editor,
        "plan_remove_changes",
        lambda *_args, **_kwargs: pytest.fail("profile summaries built a removal plan"),
    )

    assert editor.build_profile_state("researcher")["scope_has_overrides"] is False
    assert next(
        item for item in editor.list_profiles() if item["id"] == "researcher"
    )["scope_has_overrides"] is False

    prompts = profile / "prompts"
    prompts.mkdir()
    (prompts / editor.SPECIFICS_FILE).write_text("Scoped instructions")
    assert editor.build_profile_state("researcher")["scope_has_overrides"] is True


def test_project_tool_policy_reads_effective_access_and_writes_project_scope(
    project_scope: tuple[editor._EditorContext, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(editor.tool_policy, "get_tool_catalog", lambda _agent: [])
    effective_policy = {
        "mode": "custom",
        "default": "allow",
        "allowed": [],
        "blocked": ["local:shell"],
    }
    monkeypatch.setattr(editor.tool_policy, "get_policy", lambda _agent: effective_policy)
    monkeypatch.setattr(editor.skills, "list_skill_catalog", lambda agent=None: [])
    context, project_agents = project_scope

    state = editor.build_editor_state("researcher", context)
    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "tool_policy": {"mode": "off"},
        },
        context,
    )

    assert state["tools"]["has_override"] is False
    assert state["tools"]["effective_policy"] == effective_policy
    assert list(plan.changes) == [
        project_agents
        / "researcher"
        / "plugins"
        / "_tool_access"
        / "config.json"
    ]


def test_tri_state_tool_mcp_and_skill_policies_write_at_both_scopes(
    user_root: Path,
    project_scope: tuple[editor._EditorContext, Path],
) -> None:
    tool_policy = {
        "mode": "custom",
        "default": "block",
        "mcp_default": "allow",
        "allowed": ["local:shell"],
        "blocked": ["mcp:docs:write"],
    }
    skill_policy = {
        "mode": "custom",
        "default": "allow",
        "allowed": ["Research"],
        "blocked": ["Unsafe"],
    }
    patch = {
        "profile_id": "researcher",
        "tool_policy": tool_policy,
        "skill_policy": skill_policy,
    }
    context, project_agents = project_scope

    for plan, root in (
        (editor.build_change_plan(patch), user_root),
        (editor.build_change_plan(patch, context), project_agents),
    ):
        editor.apply_change_plan(plan)
        profile_root = root / "researcher" / "plugins"
        assert json.loads(
            (profile_root / "_tool_access" / "config.json").read_text()
        ) == tool_policy
        assert json.loads(
            (profile_root / "_skills" / "config.json").read_text()
        )["visibility_policy"] == skill_policy


def test_project_agents_are_scope_owned_and_never_leak_global_writes(
    user_root: Path,
    project_scope: tuple[editor._EditorContext, Path],
) -> None:
    context, project_agents = project_scope
    profile_id = "project-helper"
    plan = editor.build_change_plan(
        {
            "profile_id": profile_id,
            "creating": True,
            "editor_mode": "easy",
            "metadata": {"set": {"title": "Project Helper"}, "reset": []},
            "prompts": {
                "set": {editor.SPECIFICS_FILE: "Help only this project."},
                "reset": [],
            },
        },
        context,
    )

    assert plan.project_name == "demo"
    assert all(path.is_relative_to(project_agents / profile_id) for path in plan.changes)
    assert not (user_root / profile_id).exists()
    editor.apply_change_plan(plan)

    state = editor.build_profile_state(profile_id, context)
    assert state["scope_has_overrides"] is True
    assert state["deletable"] is True
    assert any(item["id"] == profile_id for item in editor.list_profiles(context))
    assert all(item["id"] != profile_id for item in editor.list_profiles())

    delete = editor.plan_delete_custom(profile_id, context)
    assert delete.project_name == "demo"
    editor.apply_change_plan(delete)
    assert not (project_agents / profile_id).exists()


def test_project_customizations_inherit_global_agent_and_remove_only_project_files(
    user_root: Path,
    project_scope: tuple[editor._EditorContext, Path],
) -> None:
    context, project_agents = project_scope
    global_profile = user_root / "shared-helper"
    global_profile.mkdir(parents=True)
    (global_profile / "agent.yaml").write_text(
        "title: Shared Helper\ndescription: Global description\n",
        encoding="utf-8",
    )

    inherited = editor.build_profile_state("shared-helper", context)
    assert inherited["metadata"]["description"]["effective"] == "Global description"
    assert inherited["scope_has_overrides"] is False
    assert inherited["deletable"] is False
    with pytest.raises(ValueError, match="created in this scope"):
        editor.plan_delete_custom("shared-helper", context)

    plan = editor.build_change_plan(
        {
            "profile_id": "shared-helper",
            "metadata": {"set": {"description": "Project description"}, "reset": []},
        },
        context,
    )
    project_yaml = project_agents / "shared-helper" / "agent.yaml"
    assert list(plan.changes) == [project_yaml]
    editor.apply_change_plan(plan)
    assert editor.build_profile_state("shared-helper", context)["deletable"] is False

    reset = editor.plan_remove_changes("shared-helper", context)
    assert list(reset.changes) == [project_yaml]
    editor.apply_change_plan(reset)
    assert yaml_helper.loads((global_profile / "agent.yaml").read_text())["description"] == "Global description"


def test_project_scope_is_validated_at_api_and_apply_boundaries(
    user_root: Path,
    project_scope: tuple[editor._EditorContext, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _project_agents = project_scope
    assert editor.projects.get_context_project_name(editor_context({"project_name": "demo"})) == "demo"
    with pytest.raises(ValueError, match="Project not found"):
        editor_context({"project_name": "missing-agent-editor-project"})
    monkeypatch.setattr(
        "plugins._agent_editor.api.agent_editor.AgentContext.get",
        lambda _context_id: SimpleNamespace(
            get_data=lambda _key, recursive=True: "../outside"
        ),
    )
    with pytest.raises(ValueError, match="Invalid project name"):
        editor_context({"context_id": "unsafe-project-context"})

    forged = editor.ChangePlan(profile_id="researcher", project_name="demo")
    forged.write(user_root / "researcher" / "agent.yaml", "title: Wrong scope\n")
    with pytest.raises(ValueError, match="outside the selected profile directory"):
        editor.apply_change_plan(forged)


def test_unavailable_skill_policy_ids_are_retained_in_editor_state(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = user_root / "researcher" / "plugins" / "_skills" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "visibility_policy": {
                    "mode": "custom",
                    "default": "allow",
                    "allowed": [],
                    "blocked": ["removed-skill"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(editor.skills, "list_skill_catalog", lambda agent=None: [])
    monkeypatch.setattr(
        editor.skills,
        "get_visibility_policy",
        lambda _agent: {
            "mode": "custom",
            "default": "allow",
            "allowed": [],
            "blocked": ["removed-skill"],
        },
    )

    state = editor.build_editor_state("researcher")

    assert state["skills"]["policy"]["blocked"] == ["removed-skill"]
    assert state["skills"]["catalog"] == [
        {
            "name": "removed-skill",
            "description": "",
            "path": "removed-skill",
            "origin": "Unavailable",
            "hidden": True,
            "tags": [],
            "allowed_tools": [],
            "available": False,
        }
    ]


def test_display_title_change_keeps_profile_id_and_builtin_delete_is_rejected(
    user_root: Path,
) -> None:
    with pytest.raises(ValueError, match="created in this scope"):
        editor.plan_delete_custom("researcher")

    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "metadata": {"set": {"title": "Renamed Display"}, "reset": []},
        }
    )
    assert list(plan.changes) == [user_root / "researcher" / "agent.yaml"]
    editor.apply_change_plan(plan)

    assert (user_root / "researcher" / "agent.yaml").is_file()
    assert not (user_root / "renamed-display").exists()


def test_profile_availability_is_a_sparse_global_override(user_root: Path) -> None:
    disabled = editor.plan_profile_enabled("researcher", False)

    assert list(disabled.changes) == [user_root / "researcher" / "agent.yaml"]
    editor.apply_change_plan(disabled)
    assert yaml_helper.loads(
        (user_root / "researcher" / "agent.yaml").read_text(encoding="utf-8")
    ) == {"enabled": False}

    restored = editor.plan_profile_enabled("researcher", True)
    editor.apply_change_plan(restored)
    assert not (user_root / "researcher" / "agent.yaml").exists()


def test_default_profile_can_be_disabled_when_another_profile_is_available(
    user_root: Path,
    project_scope: tuple[editor._EditorContext, Path],
) -> None:
    context, _ = project_scope

    editor.set_profile_enabled("default", False)
    assert yaml_helper.loads(
        (user_root / "default" / "agent.yaml").read_text(encoding="utf-8")
    ) == {"enabled": False}
    editor.set_profile_enabled("default", True)
    assert not (user_root / "default" / "agent.yaml").exists()

    editor.set_profile_enabled("default", False, context)
    assert editor.projects.load_project_subagents("demo") == {
        "default": {"enabled": False}
    }


def test_last_available_profile_cannot_be_disabled(
    user_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        editor.subagents,
        "get_available_agents_dict",
        lambda _project=None: {
            "default": editor.subagents.SubAgentListItem(name="default")
        },
    )

    with pytest.raises(ValueError, match="At least one agent profile"):
        editor.set_profile_enabled("default", False)

    assert not (user_root / "default").exists()


def test_duplicate_profile_materializes_the_effective_profile(
    user_root: Path,
) -> None:
    plan, title = editor.plan_duplicate_profile("developer")

    assert plan.profile_id == "developer-1"
    assert title == "Developer 1"
    assert all(path.is_relative_to(user_root / "developer-1") for path in plan.changes)
    editor.apply_change_plan(plan)

    duplicate = user_root / "developer-1"
    metadata = yaml_helper.loads(
        (duplicate / "agent.yaml").read_text(encoding="utf-8")
    )
    assert metadata["title"] == "Developer 1"
    assert metadata["description"] == "Agent specialized in complex software development."
    assert "enabled" not in metadata
    assert (duplicate / "prompts" / editor.SPECIFICS_FILE).read_bytes() == (
        Path("plugins/_agent_profiles/agents/developer/prompts") / editor.SPECIFICS_FILE
    ).read_bytes()
    assert not (duplicate / "AGENTS.md").exists()

    next_plan, next_title = editor.plan_duplicate_profile("developer")
    assert next_plan.profile_id == "developer-2"
    assert next_title == "Developer 2"


def test_duplicate_profile_targets_the_selected_project(
    project_scope: tuple[editor._EditorContext, Path],
) -> None:
    context, project_agents = project_scope

    plan, title = editor.plan_duplicate_profile("developer", context)

    assert plan.project_name == "demo"
    assert plan.profile_id == "developer-1"
    assert title == "Developer 1"
    assert all(
        path.is_relative_to(project_agents / "developer-1")
        for path in plan.changes
    )


def test_project_profile_availability_uses_project_settings(
    project_scope: tuple[editor._EditorContext, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _ = project_scope
    reconciled: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        editor.projects,
        "reconcile_agent_profiles",
        lambda *args, **kwargs: reconciled.append((args, kwargs)),
    )
    monkeypatch.setattr(
        editor.subagents,
        "get_agents_dict",
        lambda _project=None: {
            "default": editor.subagents.SubAgentListItem(
                name="default", enabled=True
            ),
            "researcher": editor.subagents.SubAgentListItem(
                name="researcher", enabled=True
            )
        },
    )

    editor.set_profile_enabled("researcher", False, context)

    assert editor.projects.load_project_subagents("demo") == {
        "researcher": {"enabled": False}
    }

    editor.set_profile_enabled("researcher", True, context)

    assert editor.projects.load_project_subagents("demo") == {}
    assert reconciled == [(("demo",), {"all_scopes": False})]


def test_save_rolls_back_every_file_after_commit_failure(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = user_root / "rollback-agent"
    first = root / "agent.yaml"
    second = root / "prompts" / editor.SPECIFICS_FILE
    second.parent.mkdir(parents=True)
    first.write_bytes(b"title: Before\n")
    second.write_bytes(b"before")
    plan = editor.ChangePlan(profile_id="rollback-agent")
    plan.write(first, b"title: After\n")
    plan.write(second, b"after")

    original_replace = editor.os.replace
    calls = 0
    invalidations: list[bool] = []
    monkeypatch.setattr(
        editor,
        "_invalidate_profile_caches",
        lambda: invalidations.append(True),
    )

    def fail_second(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated commit failure")
        return original_replace(source, destination)

    monkeypatch.setattr(editor.os, "replace", fail_second)
    with pytest.raises(OSError, match="simulated"):
        editor.apply_change_plan(plan)

    assert first.read_bytes() == b"title: Before\n"
    assert second.read_bytes() == b"before"
    assert invalidations == []


def test_remove_my_changes_preserves_manual_and_unknown_files(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = user_root / "researcher"
    prompt = root / "prompts" / editor.SPECIFICS_FILE
    manual_files = _write_manual_files(root)
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text("override", encoding="utf-8")
    (root / "agent.yaml").write_text(
        "title: Mine\nunknown_key: keep\n", encoding="utf-8"
    )
    tool_config = root / "plugins" / "_tool_access" / "config.json"
    tool_config.parent.mkdir(parents=True)
    tool_config.write_text(
        json.dumps({"mode": "custom", "default": "block", "manual": True}),
        encoding="utf-8",
    )

    real_catalog = editor.prompt_catalog

    def catalog(agent):
        items = real_catalog(agent)
        for item in items:
            if item["filename"] == editor.SPECIFICS_FILE:
                item.update({"has_override": True, "inherited_source": "agents/researcher"})
        return items

    monkeypatch.setattr(editor, "prompt_catalog", catalog)
    plan = editor.plan_remove_changes("researcher")
    assert set(manual_files).isdisjoint(plan.changes)
    editor.apply_change_plan(plan)

    assert all(path.read_bytes() == payload for path, payload in manual_files.items())
    assert yaml_helper.loads((root / "agent.yaml").read_text()) == {
        "unknown_key": "keep"
    }
    assert json.loads(tool_config.read_text()) == {"manual": True}


def test_destructive_cleanup_deletes_only_its_enumerated_plan(
    user_root: Path,
) -> None:
    root = user_root / "researcher"
    planned_files = _write_manual_files(root)
    agent_yaml = root / "agent.yaml"
    agent_yaml.write_text("title: Mine\n", encoding="utf-8")
    planned_files[agent_yaml] = agent_yaml.read_bytes()

    plan = editor.plan_remove_changes("researcher", destructive=True)
    assert set(plan.changes) == set(planned_files)

    unplanned = root / "created-after-plan.txt"
    unplanned.write_text("keep", encoding="utf-8")
    editor.apply_change_plan(plan)

    assert all(not path.exists() for path in planned_files)
    assert unplanned.read_text(encoding="utf-8") == "keep"


def test_mixed_save_matches_plan_preserves_every_unrelated_family_and_refreshes_cache(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = user_root / "researcher"
    manual_files = _write_manual_files(root)
    preset = editor.build_editor_state("researcher")["model_presets"][1]["name"]
    cleared: list[object] = []
    monkeypatch.setattr(editor.cache, "clear", lambda area: cleared.append(area))
    monkeypatch.setattr(
        editor.plugins,
        "clear_plugin_cache",
        lambda names: cleared.append(tuple(names)),
    )
    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "metadata": {"set": {"description": "Scoped"}, "reset": []},
            "prompts": {
                "set": {editor.SPECIFICS_FILE: "Only this prompt."},
                "reset": [],
            },
            "model_preset": {"mode": "preset", "name": preset},
        }
    )
    expected = plan.response()

    assert {
        path.relative_to(user_root).as_posix()
        for path, change in plan.changes.items()
        if change.action == "write"
    } == {
        "researcher/agent.yaml",
        f"researcher/prompts/{editor.SPECIFICS_FILE}",
        "researcher/plugins/_model_config/config.json",
    }
    assert editor.apply_change_plan(plan) == expected
    assert cleared == [
        editor.subagents.PATHS_CACHE_AREA,
        ("_agent_editor", "_model_config", "_tool_access", "_skills"),
    ]
    assert all(path.read_bytes() == payload for path, payload in manual_files.items())


def test_empty_prompt_override_and_selected_project_scope_are_distinct(
    user_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    framework = tmp_path / "framework"
    user_prompts = user_root / "researcher" / "prompts"
    project_meta = tmp_path / "project" / ".a0proj"
    project_prompts = project_meta / "agents" / "researcher" / "prompts"
    for path, text in (
        (framework / editor.SPECIFICS_FILE, "framework"),
        (user_prompts / editor.SPECIFICS_FILE, ""),
        (project_prompts / editor.SPECIFICS_FILE, "project"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(
        editor.subagents,
        "get_paths",
        lambda _agent, *parts: (
            [str(user_prompts), str(framework)]
            if not editor.projects.get_context_project_name(_agent.context)
            else [str(project_prompts), str(user_prompts), str(framework)]
        ),
    )
    original_meta = editor.projects.get_project_meta
    monkeypatch.setattr(
        editor.projects,
        "get_project_meta",
        lambda name, *parts: str(project_meta.joinpath(*parts))
        if name == "acceptance-project"
        else original_meta(name, *parts),
    )

    empty = next(
        item
        for item in editor.prompt_catalog(editor.EditorAgent("researcher"))
        if item["filename"] == editor.SPECIFICS_FILE
    )
    project = next(
        item
        for item in editor.prompt_catalog(
            editor.EditorAgent(
                "researcher",
                editor._EditorContext("acceptance-project"),
            )
        )
        if item["filename"] == editor.SPECIFICS_FILE
    )

    assert empty["state"] == "Overridden here (empty)"
    assert empty["has_override"] is True
    assert empty["effective"] == ""
    assert project["state"] == "Overridden here"
    assert project["effective"] == "project"
    assert project["source_chain"][-2:] == ["Global", "Your override"]

    reset = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "prompts": {"set": {}, "reset": [editor.SPECIFICS_FILE]},
        }
    )
    assert list(reset.changes) == [user_prompts / editor.SPECIFICS_FILE]
    assert next(iter(reset.changes.values())).action == "delete"


def test_avatar_is_normalized_and_avatar_only_edit_is_sparse(user_root: Path) -> None:
    from PIL import Image

    source = BytesIO()
    Image.new("RGB", (800, 400), "red").save(source, format="PNG")
    upload = FileStorage(stream=BytesIO(source.getvalue()), filename="avatar.png")
    staged = editor.stage_avatar(upload)
    plan = editor.build_change_plan(
        {
            "profile_id": "researcher",
            "metadata": {
                "set": {"avatar": {"kind": "image", "token": staged["token"]}},
                "reset": [],
            },
        }
    )

    assert {path.relative_to(user_root).as_posix() for path in plan.changes} == {
        "researcher/agent.yaml",
        "researcher/assets/avatar.webp",
    }
    editor.apply_change_plan(plan)
    avatar = user_root / "researcher" / "assets" / "avatar.webp"
    with Image.open(avatar) as normalized:
        assert normalized.format == "WEBP"
        assert normalized.size == (editor.AVATAR_SIZE, editor.AVATAR_SIZE)
        assert not normalized.getexif()


@pytest.mark.asyncio
async def test_truncated_avatar_is_a_validation_error(user_root: Path) -> None:
    from PIL import Image

    source = BytesIO()
    Image.new("RGB", (32, 32), "red").save(source, format="PNG")
    upload = FileStorage(
        stream=BytesIO(source.getvalue()[:-24]),
        filename="truncated.png",
    )
    response = await AgentEditorAvatar(None, None).process(  # type: ignore[arg-type]
        {},
        SimpleNamespace(method="POST", files={"avatar": upload}),
    )

    assert response.status_code == 400
    assert "valid PNG, JPEG, or WebP" in response.get_data(as_text=True)


@pytest.mark.asyncio
async def test_destructive_removal_requires_a_boolean_and_confirmation(
    user_root: Path,
) -> None:
    profile_root = user_root / "researcher"
    manual = profile_root / "manual.txt"
    manual.parent.mkdir(parents=True)
    manual.write_text("keep until confirmed", encoding="utf-8")
    handler = AgentEditor(None, None)  # type: ignore[arg-type]

    malformed = await handler.process(
        {
            "action": "remove_changes",
            "profile_id": "researcher",
            "destructive": "false",
        },
        None,  # type: ignore[arg-type]
    )
    unconfirmed = await handler.process(
        {
            "action": "remove_changes",
            "profile_id": "researcher",
            "destructive": True,
        },
        None,  # type: ignore[arg-type]
    )

    assert malformed.status_code == 400
    assert unconfirmed.status_code == 400
    assert manual.read_text(encoding="utf-8") == "keep until confirmed"

    applied = await handler.process(
        {
            "action": "remove_changes",
            "profile_id": "researcher",
            "destructive": True,
            "confirm": True,
        },
        None,  # type: ignore[arg-type]
    )
    assert applied["ok"] is True
    assert not manual.exists()


@pytest.mark.asyncio
async def test_running_custom_profile_cannot_be_deleted(
    user_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_root = user_root / "running-custom"
    profile_root.mkdir(parents=True)
    (profile_root / "agent.yaml").write_text(
        "title: Running custom\n",
        encoding="utf-8",
    )
    running = SimpleNamespace(
        config=SimpleNamespace(profile="running-custom"),
        is_running=lambda: True,
    )
    monkeypatch.setattr(
        "plugins._agent_editor.api.agent_editor.AgentContext.all",
        lambda: [running],
    )

    response = await AgentEditor(None, None).process(  # type: ignore[arg-type]
        {
            "action": "delete",
            "profile_id": "running-custom",
            "confirm": True,
        },
        None,  # type: ignore[arg-type]
    )

    assert response.status_code == 400
    assert "running" in response.get_data(as_text=True)
    assert profile_root.is_dir()


def test_stale_create_plan_cannot_overwrite_a_new_profile(user_root: Path) -> None:
    patch = {
        "profile_id": "create-race",
        "creating": True,
        "editor_mode": "easy",
        "metadata": {"set": {"title": "Create race"}, "reset": []},
        "prompts": {
            "set": {editor.SPECIFICS_FILE: "First writer wins."},
            "reset": [],
        },
    }
    first = editor.build_change_plan(patch)
    stale = editor.build_change_plan(patch)

    editor.apply_change_plan(first)
    with pytest.raises(ValueError, match="created before this save completed"):
        editor.apply_change_plan(stale)

    assert yaml_helper.loads(
        (user_root / "create-race" / "agent.yaml").read_text(encoding="utf-8")
    ) == {"title": "Create race"}


def test_settings_default_profile_catalog_uses_global_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from helpers import settings

    monkeypatch.setattr(
        settings.subagents,
        "get_available_agents_dict",
        lambda _project: {
            "default": settings.subagents.SubAgentListItem(
                name="default", title="Default"
            ),
            "agent0": settings.subagents.SubAgentListItem(
                name="agent0", title="Agent 0"
            ),
        },
    )
    configured = settings.get_default_settings().copy()
    configured["agent_profile"] = "disabled-profile"

    options = settings.convert_out(configured)["additional"]["agent_subdirs"]

    assert options == [
        {"value": "agent0", "label": "Agent 0"},
        {
            "value": "disabled-profile",
            "label": "disabled-profile (unavailable)",
        },
    ]


def test_shared_profile_catalog_drives_generic_and_web_selectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from api import agents
    from helpers import integration_commands, subagents

    profiles = [{"key": "agent0", "label": "Agent 0"}]
    monkeypatch.setattr(subagents, "get_all_agents_list", lambda: profiles)

    handler = agents.Agents.__new__(agents.Agents)
    response = asyncio.run(handler.process({"action": "list"}, None))
    assert [item["key"] for item in response["data"]] == ["agent0"]

    context = SimpleNamespace(
        agent0=SimpleNamespace(config=SimpleNamespace(profile="default")),
        is_running=lambda: False,
    )
    status = integration_commands._handle_agent(context, "")
    assert "Current agent: default" in status
    assert "Agent 0 (agent0)" in status
    assert "Default (default)" not in status
    assert "was not found" in integration_commands._handle_agent(context, "default")


@pytest.mark.parametrize(
    ("relative_path", "patch", "label"),
    (
        (
            "agent.yaml",
            {"metadata": {"set": {"description": "new"}, "reset": []}},
            "profile metadata",
        ),
        (
            "plugins/_tool_access/config.json",
            {"tool_policy": {"mode": "off"}},
            "tool policy configuration",
        ),
    ),
)
def test_invalid_existing_authored_files_are_never_overwritten(
    user_root: Path,
    relative_path: str,
    patch: dict,
    label: str,
) -> None:
    path = user_root / "researcher" / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    original = b"{ definitely not valid\n"
    path.write_bytes(original)

    with pytest.raises(ValueError, match=label):
        editor.build_change_plan({"profile_id": "researcher", **patch})

    assert path.read_bytes() == original


def test_editor_preview_raw_reads_markdown_without_running_dynamic_processor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_root = tmp_path / "prompts"
    prompt_root.mkdir()
    (prompt_root / editor.SPECIFICS_FILE).write_text(
        "Raw {{value}}", encoding="utf-8"
    )
    (prompt_root / "agent.system.main.specifics.py").write_text(
        "raise RuntimeError('must not run')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        editor.subagents,
        "get_paths",
        lambda *_args, **_kwargs: [str(prompt_root)],
    )
    monkeypatch.setattr(
        editor.files,
        "read_prompt_file",
        lambda *_args, **_kwargs: pytest.fail("dynamic prompt loader ran"),
    )

    item = next(
        item
        for item in editor.prompt_catalog(editor.EditorAgent("researcher"))
        if item["filename"] == editor.SPECIFICS_FILE
    )

    assert item["effective"] == "Raw {{value}}"
    assert item["preview"] == "Raw {{value}}"
    assert item["dynamic_processor"] is True


def test_editor_api_keeps_default_auth_and_csrf_protection() -> None:
    for handler in (AgentEditor, AgentEditorAvatar):
        assert handler.requires_auth() is True
        assert handler.requires_csrf() is True


def test_backend_has_no_legacy_save_or_model_request_path() -> None:
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            Path(editor.__file__),
            Path("plugins/_agent_editor/api/agent_editor.py"),
            Path("plugins/_agent_editor/api/agent_editor_avatar.py"),
        )
    )

    assert "save_agent_data" not in sources
    assert "call_llm" not in sources
    assert "call_utility_model" not in sources
    assert "litellm" not in sources
