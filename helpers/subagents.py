from helpers import files
from helpers import cache
from helpers import yaml as yaml_helper
from typing import TypedDict, TYPE_CHECKING, Literal
from pydantic import BaseModel, model_validator
import json
import logging
import os

GLOBAL_DIR = "."
USER_DIR = "usr"
DEFAULT_AGENTS_DIR = "agents"
USER_AGENTS_DIR = "usr/agents"
PATHS_CACHE_AREA = "subagent_paths(plugins)"

logger = logging.getLogger(__name__)

# projects whose agents.json registrations were already cross-checked against
# discovery in this process; keeps the check from spamming on every call
# (get_available_agents_dict is a hot path)
_UNDISCOVERED_CHECKED_PROJECTS: set[str] = set()

cache.toggle_area(PATHS_CACHE_AREA, False)

type Origin = Literal["default", "user", "project", "plugin"]

if TYPE_CHECKING:
    from agent import Agent


class SubAgentListItem(BaseModel):
    name: str = ""
    title: str = ""
    description: str = ""
    context: str = ""
    path: str = ""
    origin: list[Origin] = []
    enabled: bool = True
    avatar: dict[str, str] | None = None

    @model_validator(mode="after")
    def post_validator(self):
        if "title" not in self.model_fields_set and self.name:
            object.__setattr__(self, "title", self.name)
        return self


class SubAgent(SubAgentListItem):
    prompts: dict[str, str] = {}


def get_agents_list(project_name: str | None = None) -> list[SubAgentListItem]:
    return list(get_agents_dict(project_name).values())


def get_agents_dict(
    project_name: str | None = None,
) -> dict[str, SubAgentListItem]:
    def _merge_agent_dicts(
        base: dict[str, SubAgentListItem],
        overrides: dict[str, SubAgentListItem],
    ) -> dict[str, SubAgentListItem]:
        merged: dict[str, SubAgentListItem] = dict(base)
        for name, override in overrides.items():
            base_agent = merged.get(name)
            merged[name] = (
                _merge_agent_list_item(base_agent, override)
                if base_agent
                else override
            )
        return merged

    from helpers import plugins

    # load default, plugin, and custom agents and merge
    default_agents = _get_agents_list_from_dir(DEFAULT_AGENTS_DIR, origin="default")
    merged: dict[str, SubAgentListItem] = dict(default_agents)

    # merge with plugin agents
    plugin_dirs = plugins.get_enabled_plugin_paths(None, "agents")
    for plugin_dir in sorted(
        plugin_dirs, key=plugins.get_plugin_root_priority, reverse=True
    ):
        plugin_agents = _get_agents_list_from_dir(plugin_dir, origin="plugin")
        merged = _merge_agent_dicts(merged, plugin_agents)

    custom_agents = _get_agents_list_from_dir(USER_AGENTS_DIR, origin="user")
    merged = _merge_agent_dicts(merged, custom_agents)

    # merge with project agents if possible
    if project_name:
        from helpers import projects

        project_agents_dir = projects.get_project_meta(project_name, "agents")
        project_agents = _get_agents_list_from_dir(project_agents_dir, origin="project")
        merged = _merge_agent_dicts(merged, project_agents)

    return merged


def _get_agents_list_from_dir(dir: str, origin: Origin) -> dict[str, SubAgentListItem]:
    result: dict[str, SubAgentListItem] = {}
    subdirs = files.get_subdirectories(dir)

    for subdir in subdirs:
        try:
            try:
                raw = _read_agent_definition(dir, subdir)
            except FileNotFoundError:
                if origin == "default":
                    continue
                raw = {}
            agent_data = SubAgentListItem.model_validate(raw)
            name = agent_data.name or subdir
            agent_data.name = name
            if "title" not in agent_data.model_fields_set:
                object.__setattr__(agent_data, "title", name)
            agent_data.path = files.get_abs_path(dir, subdir)
            agent_data.origin = [origin]
            result[name] = agent_data
        except Exception as e:
            logger.warning(
                "Skipping agent definition '%s' in '%s' (origin=%s): %s: %s",
                subdir,
                dir,
                origin,
                type(e).__name__,
                e,
            )
            continue

    return result


def load_agent_data(name: str, project_name: str | None = None) -> SubAgent:
    from helpers import plugins

    # load default, plugin, and user agents and merge
    default_agent = _load_agent_data_from_dir(
        DEFAULT_AGENTS_DIR, name, origin="default"
    )
    merged = default_agent

    # merge with plugin agents
    # TODO review this
    plugin_dirs = plugins.get_enabled_plugin_paths(None, "agents")
    for plugin_dir in sorted(
        plugin_dirs, key=plugins.get_plugin_root_priority, reverse=True
    ):
        plugin_agent = _load_agent_data_from_dir(plugin_dir, name, origin="plugin")
        merged = _merge_agent(merged, plugin_agent)

    user_agent = _load_agent_data_from_dir(USER_AGENTS_DIR, name, origin="user")
    merged = _merge_agent(merged, user_agent)

    # merge with project agent if possible
    if project_name:
        from helpers import projects

        project_agents_dir = projects.get_project_meta(project_name, "agents")
        project_agent = _load_agent_data_from_dir(
            project_agents_dir, name, origin="project"
        )
        merged = _merge_agent(merged, project_agent)

    if merged is None:
        raise FileNotFoundError(
            f"Agent '{name}' not found in default, plugin, or custom directories"
        )

    return merged


def save_agent_data(name: str, subagent: SubAgent) -> None:
    # write agent.json in custom directory
    agent_dir = f"{USER_AGENTS_DIR}/{name}"
    agent_json = {
        "title": subagent.title,
        "description": subagent.description,
        "context": subagent.context,
        "enabled": subagent.enabled,
    }
    files.write_file(f"{agent_dir}/agent.json", json.dumps(agent_json, indent=2))

    # replace prompts in custom directory
    prompts_dir = f"{agent_dir}/prompts"
    # clear existing custom prompts directory (if any)
    files.delete_dir(prompts_dir)

    prompts = subagent.prompts or {}
    for name, content in prompts.items():
        safe_name = files.safe_file_name(name)
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        files.write_file(f"{prompts_dir}/{safe_name}", content)


def delete_agent_data(name: str) -> None:
    files.delete_dir(f"{USER_AGENTS_DIR}/{name}")


def _load_agent_data_from_dir(dir: str, name: str, origin: Origin) -> SubAgent | None:
    agent_dir = files.get_abs_path(dir, name)
    if not os.path.isdir(agent_dir):
        return None

    try:
        subagent = SubAgent.model_validate(_read_agent_definition(dir, name))
    except Exception:
        # backward compatibility (before agent.json existed)
        try:
            subagent = SubAgent(
                context=files.read_file(files.get_abs_path(dir, name, "_context.md"))
            )
        except Exception:
            subagent = SubAgent()

    # non-stored fields
    subagent.name = name
    if "title" not in subagent.model_fields_set:
        object.__setattr__(subagent, "title", name)
    subagent.path = agent_dir
    subagent.origin = [origin]

    prompts_dir = f"{dir}/{name}/prompts"
    try:
        prompts = files.read_text_files_in_dir(prompts_dir, pattern="*.md")
    except Exception:
        prompts = {}

    subagent.prompts = prompts or {}
    return subagent


def _read_agent_definition(dir: str, name: str) -> dict:
    yaml_path = files.get_abs_path(dir, name, "agent.yaml")
    if files.exists(yaml_path):
        return yaml_helper.loads(files.read_file(yaml_path)) or {}
    json_path = files.get_abs_path(dir, name, "agent.json")
    if files.exists(json_path):
        return json.loads(files.read_file(json_path)) or {}
    raise FileNotFoundError


def _merge_agent(base: SubAgent | None, override: SubAgent | None) -> SubAgent | None:
    if base is None:
        return override
    if override is None:
        return base

    data = _merge_agent_metadata(base, override)
    data["prompts"] = {**(base.prompts or {}), **(override.prompts or {})}
    return SubAgent.model_validate(data)


def _merge_agent_list_item(
    base: SubAgentListItem, override: SubAgentListItem
) -> SubAgentListItem:
    return SubAgentListItem.model_validate(_merge_agent_metadata(base, override))


def _merge_agent_metadata(
    base: SubAgentListItem, override: SubAgentListItem
) -> dict:
    data = base.model_dump()
    data.update(
        override.model_dump(
            exclude_unset=True, exclude={"name", "path", "origin", "prompts"}
        )
    )
    data.update(
        name=override.name or base.name,
        path=override.path or base.path,
        origin=[*base.origin, *override.origin],
    )
    return data


def get_agents_roots() -> list[str]:
    # from helpers import plugins

    plugin_agents = sorted(
        plugins.get_enabled_plugin_paths(None, "agents"),
        key=plugins.get_plugin_root_priority,
        reverse=True,
    )
    project_agents = files.find_existing_paths_by_pattern("usr/projects/*/.a0proj/agents")
    paths = [
        files.get_abs_path(DEFAULT_AGENTS_DIR),
        *plugin_agents,
        files.get_abs_path(USER_AGENTS_DIR),
        *project_agents,
    ]
    unique: list[str] = []
    seen = set()
    for p in paths:
        if not p:
            continue
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if os.path.exists(p):
            unique.append(p)
    return unique


def get_all_agents_list() -> list[dict[str, str]]:
    def _origin_from_root(root: str) -> Origin:
        rel = files.deabsolute_path(root).replace("\\", "/")
        if rel.startswith("usr/projects/"):
            return "project"
        if rel.startswith("usr/agents"):
            return "user"
        if "/plugins/" in rel or rel.startswith("plugins/"):
            return "plugin"
        return "default"

    merged: dict[str, SubAgentListItem] = {}
    for root in get_agents_roots():
        origin = _origin_from_root(root)
        items = _get_agents_list_from_dir(root, origin=origin)
        for name, item in items.items():
            if name in merged:
                merged[name] = _merge_agent_list_item(merged[name], item)
            else:
                merged[name] = item

    return [
        {"key": key, "label": item.title or key}
        for key, item in sorted(merged.items())
        if key != "default"
    ]


def get_default_promp_file_names() -> list[str]:
    return files.list_files("prompts", filter="*.md")


def _warn_undiscovered_project_agents(
    project_name: str, discovered: dict[str, SubAgentListItem]
) -> None:
    """Warn (once per project per process) when a slug is registered in the
    project's agents.json but was not discovered by agent discovery — e.g. its
    agent.yaml failed to parse and was skipped."""
    if project_name in _UNDISCOVERED_CHECKED_PROJECTS:
        return
    _UNDISCOVERED_CHECKED_PROJECTS.add(project_name)

    from helpers import projects

    try:
        abs_path = files.get_abs_path(
            projects.get_project_meta(project_name), "agents.json"
        )
        data = json.loads(files.read_file(abs_path))
    except Exception:
        return

    registered: list[str] = []
    if isinstance(data, dict):
        agents_field = data.get("agents")
        if isinstance(agents_field, list):
            # manifest format: {"agents": [{"slug": ...}, ...]}
            for entry in agents_field:
                if isinstance(entry, dict) and isinstance(entry.get("slug"), str):
                    registered.append(entry["slug"])
        else:
            # flat availability format: {"<slug>": {"enabled": ...}}
            registered = [
                key for key, value in data.items() if isinstance(value, dict)
            ]
    if not registered:
        return

    undiscovered = [slug for slug in registered if slug not in discovered]
    if undiscovered:
        logger.warning(
            "Project '%s': agents registered in agents.json but not discovered: %s "
            "(check their agent.yaml for parse errors)",
            project_name,
            ", ".join(sorted(undiscovered)),
        )


def get_available_agents_dict(
    project_name: str | None,
) -> dict[str, SubAgentListItem]:
    all_agents = get_agents_dict(project_name)
    from helpers import projects

    project_settings = (
        projects.load_project_subagents(project_name) if project_name else {}
    )

    if project_name:
        _warn_undiscovered_project_agents(project_name, all_agents)

    filtered_agents: dict[str, SubAgentListItem] = {}
    for name, agent in all_agents.items():
        if name == "_example":
            continue
        if name in project_settings:
            agent.enabled = project_settings[name]["enabled"]
        if agent.enabled:
            filtered_agents[name] = agent
    return filtered_agents


def get_paths(
    agent: "Agent|None",
    *subpaths,
    must_exist_completely: bool = True, 
    include_project: bool = True,
    include_user: bool = True,
    include_default: bool = True,
    include_plugins: bool = True,
    default_root: str = "",
) -> list[str]:
    """Returns list of file paths for the given agent and subpaths, searched in order of priority:
    project/agents/, project/, usr/agents/, plugin agents/, agents/, usr/, plugins/, default."""
    cache_key = cache.determine_cache_key(
        agent,
        *subpaths,
        must_exist_completely,
        include_project,
        include_user,
        include_default,
        include_plugins,
        default_root,
    )
    cached = cache.get(PATHS_CACHE_AREA, cache_key)
    if cached is not None:
        return cached

    paths: list[str] = []
    check_subpaths = subpaths if must_exist_completely else []
    profile_name = agent.config.profile if agent and agent.config.profile else ""
    project_name = ""

    if include_project and agent:
        from helpers import projects

        project_name = projects.get_context_project_name(agent.context) or ""

        if project_name and profile_name:
            # project/agents/<profile>/...
            project_agent_dir = projects.get_project_meta(
                project_name, "agents", profile_name
            )
            if files.exists(files.get_abs_path(project_agent_dir, *check_subpaths)):
                paths.append(files.get_abs_path(project_agent_dir, *subpaths))

        if project_name:
            # project/.a0proj/...
            path = projects.get_project_meta(project_name, *subpaths)
            if (not must_exist_completely) or files.exists(path):
                paths.append(path)

    if profile_name:

        # usr/agents/<profile>/...
        path = files.get_abs_path(USER_AGENTS_DIR, profile_name, *subpaths)
        if (not must_exist_completely) or files.exists(files.get_abs_path(USER_AGENTS_DIR, profile_name, *check_subpaths)):
            paths.append(path)

        # plugin agents/<profile>/...
        if include_plugins:
            # from helpers import plugins
            for plugin_dir in plugins.get_enabled_plugin_paths(agent, "agents", profile_name):
                path = files.get_abs_path(plugin_dir, *subpaths)
                if (not must_exist_completely) or files.exists(files.get_abs_path(plugin_dir, *check_subpaths)):
                    paths.append(path)

        # agents/<profile>/...
        path = files.get_abs_path(DEFAULT_AGENTS_DIR, profile_name, *subpaths)
        if (not must_exist_completely) or files.exists(files.get_abs_path(DEFAULT_AGENTS_DIR, profile_name, *check_subpaths)):
            paths.append(path)

    if include_user:
        # usr/...
        path = files.get_abs_path(USER_DIR, *subpaths)
        if (not must_exist_completely) or files.exists(path):
            paths.append(path)

    if include_plugins:
        # plugins/*/subpaths...
        # from helpers import plugins

        for plugin_dir in plugins.get_enabled_plugin_paths(agent):
            path = files.get_abs_path(plugin_dir, *subpaths)
            if (not must_exist_completely) or files.exists(path):
                if path not in paths:
                    paths.append(path)

    if include_default:
        # default_root/...
        path = files.get_abs_path(default_root, *subpaths)
        if (not must_exist_completely) or files.exists(path):
            paths.append(path)

    cache.add(PATHS_CACHE_AREA, cache_key, paths)
    return paths


# end-of-file imports to prevent circular imports
from helpers import plugins
