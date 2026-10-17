import os
from typing import NotRequired, TypedDict, TYPE_CHECKING, cast

from helpers import files, dirty_json, persist_chat, file_tree, extension
from helpers.print_style import PrintStyle


if TYPE_CHECKING:
    from agent import AgentContext

PROJECTS_PARENT_DIR = "usr/projects"
PROJECT_META_DIR = ".a0proj"
PROJECT_INSTRUCTIONS_DIR = "instructions"
PROJECT_KNOWLEDGE_DIR = "knowledge"
PROJECT_SKILLS_DIR = "skills"
PROJECT_HEADER_FILE = "project.json"
PROJECT_MCP_SERVERS_FILE = "mcp_servers.json"
PROJECT_AGENTS_MD_FILES = (
    "AGENTS.override.md",
    "AGENTS.Override.md",
    "AGENTS.md",
    "Agents.md",
    "agents.md",
)
DEFAULT_MCP_SERVERS_CONFIG = '{\n    "mcpServers": {}\n}'

CONTEXT_DATA_KEY_PROJECT = "project"


class FileStructureInjectionSettings(TypedDict):
    enabled: bool
    max_depth: int
    max_files: int
    max_folders: int
    max_lines: int
    gitignore: str

class SubAgentSettings(TypedDict):
    enabled: bool

class BasicProjectData(TypedDict):
    title: str
    description: str
    instructions: str
    include_agents_md: NotRequired[bool]
    mcp_servers: NotRequired[str]
    color: str
    git_url: str
    file_structure: FileStructureInjectionSettings

class GitStatusData(TypedDict, total=False):
    is_git_repo: bool
    remote_url: str
    current_branch: str
    is_dirty: bool
    untracked_count: int
    last_commit: dict
    error: str

class EditProjectData(BasicProjectData):
    name: str
    instruction_files_count: int
    knowledge_files_count: int
    variables: str
    secrets: str
    mcp_servers: str
    git_status: GitStatusData


ProjectExtendedData = dict[str, object]
_PROJECT_CORE_EDIT_KEYS = frozenset(BasicProjectData.__annotations__) | frozenset(
    EditProjectData.__annotations__
)
_PROJECT_TRANSIENT_INPUT_KEYS = frozenset({"git_token", "subagents"})


def get_projects_parent_folder():
    return files.get_abs_path(PROJECTS_PARENT_DIR)


def get_project_folder(name: str):
    return files.get_abs_path(get_projects_parent_folder(), name)


def get_project_meta(name: str, *sub_dirs: str):
    return files.get_abs_path(get_project_folder(name), PROJECT_META_DIR, *sub_dirs)


def validate_project_name(name: str | None) -> str:
    candidate = str(name or "").strip()
    if (
        not candidate
        or candidate in {".", ".."}
        or os.path.basename(candidate) != candidate
    ):
        raise ValueError("Invalid project name")
    return candidate


def delete_project(name: str):
    abs_path = files.get_abs_path(PROJECTS_PARENT_DIR, name)
    files.delete_dir(abs_path)
    deactivate_project_in_chats(name)
    return name


def create_project(name: str, data: BasicProjectData):
    extended_data = _project_extended_data_for_save(data)
    mcp_servers = data.get("mcp_servers") if isinstance(data, dict) else None
    abs_path = files.create_dir_safe(
        files.get_abs_path(PROJECTS_PARENT_DIR, name), rename_format="{name}_{number}"
    )
    create_project_meta_folders(name)
    data = _normalizeBasicData(data)
    save_project_header(name, data)
    save_project_mcp_servers(name, mcp_servers or DEFAULT_MCP_SERVERS_CONFIG)
    save_project_extended_data(name, extended_data)
    return name


def clone_git_project(name: str, git_url: str, git_token: str, data: BasicProjectData):
    """Clone a git repository as a new A0 project. Token is used only for cloning via http header."""
    from helpers import git

    extended_data = _project_extended_data_for_save(data)
    mcp_servers = data.get("mcp_servers") if isinstance(data, dict) else None
    
    abs_path = files.create_dir_safe(
        files.get_abs_path(PROJECTS_PARENT_DIR, name), rename_format="{name}_{number}"
    )
    actual_name = files.basename(abs_path)
    
    try:
        # Clone with token via http.extraHeader (token never in URL or git config)
        git.clone_repo(git_url, abs_path, token=git_token)
        clean_url = git.strip_auth_from_url(git_url)
        
        # Check if cloned repo already has .a0proj
        meta_path = os.path.join(abs_path, PROJECT_META_DIR, PROJECT_HEADER_FILE)
        if os.path.exists(meta_path):
            # Merge: keep cloned content, override only user-specified fields
            cloned_header: BasicProjectData = dirty_json.parse(files.read_file(meta_path)) # type: ignore
            cloned_header["title"] = data.get("title") or cloned_header.get("title", "")
            cloned_header["color"] = data.get("color") or cloned_header.get("color", "")
            cloned_header["git_url"] = clean_url
            save_project_header(actual_name, cloned_header)
        else:
            # New project: create meta folders and save header
            create_project_meta_folders(actual_name)
            data = _normalizeBasicData(data)
            data["git_url"] = clean_url
            save_project_header(actual_name, data)

        if mcp_servers:
            save_project_mcp_servers(actual_name, mcp_servers)
        save_project_extended_data(actual_name, extended_data)
        
        return actual_name
    except Exception as e:
        try:
            files.delete_dir(abs_path)
        except Exception:
            pass
        raise e


def load_project_header(name: str):
    abs_path = files.get_abs_path(
        PROJECTS_PARENT_DIR, name, PROJECT_META_DIR, PROJECT_HEADER_FILE
    )
    header: dict = dirty_json.parse(files.read_file(abs_path))  # type: ignore
    header["name"] = name
    return header


def _default_file_structure_settings():
    try:
        gitignore = files.read_file("conf/projects.default.gitignore")
    except Exception:
        gitignore = ""
    return FileStructureInjectionSettings(
        enabled=True,
        max_depth=5,
        max_files=20,
        max_folders=20,
        max_lines=250,
        gitignore=gitignore,
    )


def _normalizeBasicData(data: BasicProjectData) -> BasicProjectData:
    return {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "instructions": data.get("instructions", ""),
        "include_agents_md": _normalize_include_agents_md(
            data.get("include_agents_md", True)
        ),
        "color": data.get("color", ""),
        "git_url": data.get("git_url", ""),
        "file_structure": data.get(
            "file_structure",
            _default_file_structure_settings(),
        ),
    }


def _normalizeEditData(data: EditProjectData) -> EditProjectData:
    normalized: EditProjectData = {
        "name": data.get("name", ""),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "instructions": data.get("instructions", ""),
        "include_agents_md": _normalize_include_agents_md(
            data.get("include_agents_md", True)
        ),
        "variables": data.get("variables", ""),
        "mcp_servers": data.get("mcp_servers", DEFAULT_MCP_SERVERS_CONFIG),
        "color": data.get("color", ""),
        "git_url": data.get("git_url", ""),
        "git_status": data.get("git_status", {"is_git_repo": False}),
        "instruction_files_count": data.get("instruction_files_count", 0),
        "knowledge_files_count": data.get("knowledge_files_count", 0),
        "secrets": data.get("secrets", ""),
        "file_structure": data.get(
            "file_structure",
            _default_file_structure_settings(),
        ),
    }
    return normalized


def _edit_data_to_basic_data(data: EditProjectData):
    return _normalizeBasicData(data)


def _basic_data_to_edit_data(data: BasicProjectData) -> EditProjectData:
    base: EditProjectData = cast(
        EditProjectData,
        {
            **data,
            "name": "",
            "instruction_files_count": 0,
            "knowledge_files_count": 0,
            "variables": "",
            "secrets": "",
            "git_status": {"is_git_repo": False},
        },
    )
    return _normalizeEditData(base)


def update_project(name: str, data: EditProjectData):
    extended_data = _project_extended_data_for_save(data)

    # merge with current state
    current = load_edit_project_data(name)
    current.update(data)
    current = _normalizeEditData(current)

    # save header data
    header = _edit_data_to_basic_data(current)
    save_project_header(name, header)

    # save secrets
    save_project_variables(name, current["variables"])
    save_project_secrets(name, current["secrets"])
    save_project_mcp_servers(name, current["mcp_servers"])
    save_project_extended_data(name, extended_data)

    reactivate_project_in_chats(name)
    return name


def load_basic_project_data(name: str) -> BasicProjectData:
    data = cast(BasicProjectData, load_project_header(name))
    normalized = _normalizeBasicData(data)
    return normalized


def load_edit_project_data(name: str) -> EditProjectData:
    from helpers import git
    
    data = load_basic_project_data(name)
    create_project_meta_folders(name)
    additional_instructions = get_additional_instructions_files(name)
    variables = load_project_variables(name)
    mcp_servers = load_project_mcp_servers(name)
    secrets = load_project_secrets_masked(name)
    knowledge_files_count = get_knowledge_files_count(name)
    git_status = cast(GitStatusData, git.get_repo_status(get_project_folder(name)))
    
    data = cast(
        EditProjectData,
        {
            **data,
            "name": name,
            "instruction_files_count": len(additional_instructions),
            "knowledge_files_count": knowledge_files_count,
            "variables": variables,
            "mcp_servers": mcp_servers,
            "secrets": secrets,
            "git_status": git_status,
        },
    )
    data = _normalizeEditData(data)
    _merge_project_extended_data(data, load_project_extended_data(name))
    return data


def save_project_header(name: str, data: BasicProjectData):
    # save project header file
    header = dirty_json.stringify(_project_header_for_save(data))
    abs_path = files.get_abs_path(
        PROJECTS_PARENT_DIR, name, PROJECT_META_DIR, PROJECT_HEADER_FILE
    )

    files.write_file(abs_path, header)


@extension.extensible
def load_project_extended_data(name: str) -> ProjectExtendedData:
    return {}


@extension.extensible
def save_project_extended_data(name: str, project_data: ProjectExtendedData):
    return None


def _project_extended_data_for_save(data: object) -> ProjectExtendedData:
    if not isinstance(data, dict):
        return {}
    return {
        str(key): value
        for key, value in data.items()
        if str(key) not in _PROJECT_CORE_EDIT_KEYS
        and str(key) not in _PROJECT_TRANSIENT_INPUT_KEYS
    }


def _merge_project_extended_data(
    data: EditProjectData,
    extended_data: object,
) -> None:
    if not isinstance(extended_data, dict):
        return

    conflicts = sorted(str(key) for key in extended_data if key in _PROJECT_CORE_EDIT_KEYS)
    if conflicts:
        raise ValueError(
            "Project extension data cannot overwrite core project fields: "
            + ", ".join(conflicts)
        )

    data.update(extended_data)  # type: ignore[typeddict-item]


def load_project_mcp_servers(name: str) -> str:
    project_name = validate_project_name(name)
    try:
        return files.read_file(get_project_meta(project_name, PROJECT_MCP_SERVERS_FILE))
    except Exception:
        return DEFAULT_MCP_SERVERS_CONFIG


def save_project_mcp_servers(name: str, mcp_servers: str):
    project_name = validate_project_name(name)
    content = mcp_servers if isinstance(mcp_servers, str) else DEFAULT_MCP_SERVERS_CONFIG
    files.write_file(get_project_meta(project_name, PROJECT_MCP_SERVERS_FILE), content)


def get_active_projects_list():
    return _get_projects_list(get_projects_parent_folder())


def _get_projects_list(parent_dir):
    projects = []

    # folders in project directory
    for name in os.listdir(parent_dir):
        try:
            abs_path = os.path.join(parent_dir, name)
            if os.path.isdir(abs_path):
                project_data = load_basic_project_data(name)
                projects.append(
                    {
                        "name": name,
                        "title": project_data.get("title", ""),
                        "description": project_data.get("description", ""),
                        "color": project_data.get("color", ""),
                    }
                )
        except Exception as e:
            PrintStyle.error(f"Error loading project {name}: {str(e)}")

    # sort projects by name
    projects.sort(key=lambda x: x["name"])
    return projects


def get_project_default_agent(name: str | None) -> str | None:
    """Return the project's preferred default agent profile, or None."""
    if not name:
        return None
    try:
        abs_path = files.get_abs_path(get_project_meta(name), "default_agent.json")
        data = dirty_json.parse(files.read_file(abs_path))
        agent = str(data.get("agent", "") or "").strip() if isinstance(data, dict) else ""
        return agent or None
    except Exception:
        return None


def reconcile_agent_profile(
    context: "AgentContext", project_name: str | None, available: dict | None = None
) -> bool:
    from helpers import subagents
    from initialize import initialize_agent

    if available is None:
        available = subagents.get_available_agents_dict(project_name)
    if getattr(context.config, "profile", "") in available:
        # project default agent: switch only when the context still runs the
        # global default (i.e. no explicit per-chat selection has been made)
        manually_set = context.get_data("agent_profile_manually_set")
        default_agent = get_project_default_agent(project_name)
        if (
            not manually_set
            and default_agent
            and default_agent in available
            and default_agent != getattr(context.config, "profile", "")
        ):
            from helpers import settings as settings_helper

            global_default = settings_helper.get_settings().get("agent_profile", "")
            if getattr(context.config, "profile", "") == global_default:
                config = initialize_agent(
                    override_settings={"agent_profile": default_agent}
                )
                context.config = config
                context.agent0.config = config
                return True
        return False

    config = initialize_agent()
    default_agent = get_project_default_agent(project_name)
    if config.profile not in available or (
        default_agent
        and default_agent in available
        and config.profile != default_agent
    ):
        fallback = (
            default_agent
            if default_agent in available
            else "agent0"
            if "agent0" in available
            else next(iter(available), "agent0")
        )
        config = initialize_agent(override_settings={"agent_profile": fallback})
    context.config = config
    context.agent0.config = config
    return True


def reconcile_agent_profiles(
    project_name: str | None, *, all_scopes: bool = False
) -> None:
    from agent import AgentContext
    from helpers import subagents
    from helpers.state_monitor_integration import mark_dirty_for_context

    available_by_project: dict[str | None, dict] = {}
    for context in AgentContext.all():
        context_project = get_context_project_name(context)
        if not all_scopes and context_project != project_name:
            continue
        if context_project not in available_by_project:
            available_by_project[context_project] = (
                subagents.get_available_agents_dict(context_project)
            )
        if not reconcile_agent_profile(
            context, context_project, available_by_project[context_project]
        ):
            continue
        persist_chat.save_tmp_chat(context)
        mark_dirty_for_context(
            context.id, reason="projects.reconcile_agent_profiles"
        )


def activate_project(context_id: str, name: str, *, mark_dirty: bool = True):
    from agent import AgentContext

    data = load_edit_project_data(name)
    context = AgentContext.get(context_id)
    if context is None:
        raise Exception("Context not found")
    display_name = str(data.get("title", name))
    display_name = display_name[:22] + "..." if len(display_name) > 25 else display_name
    context.set_data(CONTEXT_DATA_KEY_PROJECT, name)
    context.set_output_data(
        CONTEXT_DATA_KEY_PROJECT,
        {"name": name, "title": display_name, "color": data.get("color", "")},
    )
    reconcile_agent_profile(context, name)

    # persist
    persist_chat.save_tmp_chat(context)

    if mark_dirty:
        from helpers.state_monitor_integration import mark_dirty_all
        mark_dirty_all(reason="projects.activate_project")


def deactivate_project(context_id: str, *, mark_dirty: bool = True):
    from agent import AgentContext

    context = AgentContext.get(context_id)
    if context is None:
        raise Exception("Context not found")
    context.set_data(CONTEXT_DATA_KEY_PROJECT, None)
    context.set_output_data(CONTEXT_DATA_KEY_PROJECT, None)
    reconcile_agent_profile(context, None)

    # persist
    persist_chat.save_tmp_chat(context)

    if mark_dirty:
        from helpers.state_monitor_integration import mark_dirty_all
        mark_dirty_all(reason="projects.deactivate_project")


def reactivate_project_in_chats(name: str):
    from agent import AgentContext

    for context in AgentContext.all():
        if context.get_data(CONTEXT_DATA_KEY_PROJECT) == name:
            activate_project(context.id, name, mark_dirty=False)

    from helpers.state_monitor_integration import mark_dirty_all
    mark_dirty_all(reason="projects.reactivate_project_in_chats")


def deactivate_project_in_chats(name: str):
    from agent import AgentContext

    for context in AgentContext.all():
        if context.get_data(CONTEXT_DATA_KEY_PROJECT) == name:
            deactivate_project(context.id, mark_dirty=False)

    from helpers.state_monitor_integration import mark_dirty_all
    mark_dirty_all(reason="projects.deactivate_project_in_chats")


def build_system_prompt_vars(name: str):
    project_data = load_basic_project_data(name)
    main_instructions = project_data.get("instructions", "") or ""
    include_agents_md = project_data.get("include_agents_md", True)
    instruction_files = get_project_instruction_files(
        name,
        include_agents_md=include_agents_md,
    )
    instruction_parts = [
        main_instructions,
        _format_project_instruction_files(instruction_files),
    ]
    complete_instructions = "\n\n".join(
        part.strip() for part in instruction_parts if part.strip()
    ).strip()
    return {
        "project_name": project_data.get("title", ""),
        "project_description": project_data.get("description", ""),
        "project_instructions": complete_instructions or "",
        "include_agents_md": include_agents_md,
        "project_path": files.normalize_a0_path(get_project_folder(name)),
        "project_git_url": project_data.get("git_url", ""),
    }


def get_agents_md_chain(root: str, target: str) -> list[tuple[str, str]]:
    root_real = os.path.realpath(files.fix_dev_path(root))
    target_real = os.path.realpath(files.fix_dev_path(target))
    if os.path.isfile(target_real):
        target_real = os.path.dirname(target_real)

    if files.is_in_dir(target_real, root_real):
        dirs = []
        cursor = target_real
        while True:
            dirs.append(cursor)
            if cursor == root_real:
                break
            parent = os.path.dirname(cursor)
            if parent == cursor:
                break
            cursor = parent
        dirs.reverse()
    else:
        dirs = [root_real]

    chain = []
    for dir_path in dirs:
        for filename in PROJECT_AGENTS_MD_FILES:
            matches = files.read_text_files_in_dir(dir_path, pattern=filename)
            if filename not in matches:
                continue
            chain.append((files.get_abs_path(dir_path, filename), matches[filename]))
            break
    return chain


def build_agents_md_protocol(name: str, target: str | None = None) -> str:
    project_folder = get_project_folder(name)
    project_agents_md = get_project_agents_md_instruction_file(name)
    project_agents_md_path = (
        os.path.realpath(files.fix_dev_path(project_agents_md[0]))
        if project_agents_md
        else ""
    )
    entries = [
        (path, content)
        for path, content in get_agents_md_chain(
            files.get_abs_path(""),
            target or project_folder,
        )
        if os.path.realpath(path) != project_agents_md_path
    ]
    if not entries:
        return ""

    instructions = []
    for path, content in entries:
        instructions.append(
            f"### path: {files.normalize_a0_path(path)}\n\n{content.strip()}"
        )
    return files.read_prompt_file(
        "agent.protocol.projects.agents_md.md",
        _directories=["prompts"],
        agents_md_instructions="\n\n".join(instructions),
    ).strip()


def get_additional_instructions_files(name: str):
    instructions_folder = files.get_abs_path(
        get_project_folder(name), PROJECT_META_DIR, PROJECT_INSTRUCTIONS_DIR
    )
    return files.read_text_files_in_dir(instructions_folder)


def get_project_instruction_files(
    name: str,
    include_agents_md: bool = True,
) -> list[tuple[str, str]]:
    project_folder = get_project_folder(name)
    result: list[tuple[str, str]] = []

    if include_agents_md:
        agents_md = get_project_agents_md_instruction_file(name)
        if agents_md:
            result.append(agents_md)

    additional_instructions = get_additional_instructions_files(name)
    for filename in sorted(additional_instructions):
        path = files.get_abs_path(
            project_folder,
            PROJECT_META_DIR,
            PROJECT_INSTRUCTIONS_DIR,
            filename,
        )
        result.append(
            (files.normalize_a0_path(path), additional_instructions[filename])
        )

    return result


def get_project_agents_md_instruction_file(name: str) -> tuple[str, str] | None:
    project_folder = get_project_folder(name)
    for path, content in get_agents_md_chain(project_folder, project_folder):
        return (files.normalize_a0_path(path), content)
    return None


def _format_project_instruction_files(instruction_files: list[tuple[str, str]]) -> str:
    if not instruction_files:
        return ""

    parts = ["## project instruction files"]
    for path, content in instruction_files:
        parts.append(f"### path: {path}\n\n{content}")
    return "\n\n".join(parts)


def _normalize_include_agents_md(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _project_header_for_save(data: BasicProjectData) -> dict:
    header = dict(data)
    header["include_agents_md"] = _normalize_include_agents_md(
        header.get("include_agents_md", True)
    )
    return header


def get_context_project_name(context: "AgentContext") -> str | None:
    return context.get_data(CONTEXT_DATA_KEY_PROJECT)


def load_project_variables(name: str):
    try:
        abs_path = files.get_abs_path(get_project_meta(name), "variables.env")
        return files.read_file(abs_path)
    except Exception:
        return ""


def save_project_variables(name: str, variables: str):
    abs_path = files.get_abs_path(get_project_meta(name), "variables.env")
    files.write_file(abs_path, variables)


def load_project_subagents(name: str) -> dict[str, SubAgentSettings]:
    try:
        abs_path = files.get_abs_path(get_project_meta(name), "agents.json")
        data = dirty_json.parse(files.read_file(abs_path))
        if isinstance(data, dict):
            return _normalize_subagents(data, name)  # type: ignore[arg-type,return-value]
        return {}
    except Exception:
        return {}


def save_project_subagents(name: str, subagents_data: dict[str, SubAgentSettings]):
    abs_path = files.get_abs_path(get_project_meta(name), "agents.json")
    normalized = _normalize_subagents(subagents_data, name)
    content = dirty_json.stringify(normalized)
    files.write_file(abs_path, content)


def set_project_subagent_enabled(name: str, profile_id: str, enabled: bool) -> None:
    from helpers import subagents

    name = validate_project_name(name)
    if not os.path.isdir(get_project_folder(name)):
        raise ValueError("Project not found.")
    if not isinstance(enabled, bool):
        raise ValueError("Agent availability must be true or false.")
    agent = subagents.get_agents_dict(name).get(profile_id)
    if not agent:
        raise ValueError(f'Agent profile "{profile_id}" does not exist.')

    path = get_project_meta(name, "agents.json")
    try:
        settings = dirty_json.parse(files.read_file(path))
    except FileNotFoundError:
        settings = {}
    except Exception as exc:
        raise ValueError("Project agent availability is invalid.") from exc
    if not isinstance(settings, dict) or any(
        not isinstance(key, str)
        or not isinstance(value, dict)
        or not isinstance(value.get("enabled"), bool)
        for key, value in settings.items()
    ):
        raise ValueError("Project agent availability is invalid.")

    if agent.enabled == enabled:
        settings.pop(profile_id, None)
    else:
        settings[profile_id] = {"enabled": enabled}
    save_project_subagents(name, settings)


def _normalize_subagents(
    subagents_data: dict[str, SubAgentSettings], project_name: str = ""
) -> dict[str, SubAgentSettings]:
    from helpers import subagents

    scoped_agents = subagents.get_agents_dict(project_name or None)

    normalized: dict[str, SubAgentSettings] = {}
    for key, value in subagents_data.items():
        agent = scoped_agents.get(key)
        if not agent:
            continue

        enabled = bool(value["enabled"])
        if agent.enabled == enabled:
            continue

        normalized[key] = {"enabled": enabled}

    return normalized


def load_project_secrets_masked(name: str, merge_with_global=False):
    from helpers import secrets

    mgr = secrets.get_project_secrets_manager(name, merge_with_global)
    return mgr.get_masked_secrets()


def save_project_secrets(name: str, secrets: str):
    from helpers.secrets import get_project_secrets_manager

    secrets_manager = get_project_secrets_manager(name)
    secrets_manager.save_secrets_with_merge(secrets)


def create_project_meta_folders(name: str):
    # create instructions folder
    files.create_dir(get_project_meta(name, PROJECT_INSTRUCTIONS_DIR))

    # create knowledge folders (plugins create their own subdirs lazily)
    files.create_dir(get_project_meta(name, PROJECT_KNOWLEDGE_DIR))

    # create project skills folder for Project Settings > Skills > Open Folder
    files.create_dir(get_project_meta(name, PROJECT_SKILLS_DIR))


def get_knowledge_files_count(name: str):
    knowledge_folder = files.get_abs_path(
        get_project_meta(name, PROJECT_KNOWLEDGE_DIR)
    )
    return len(files.list_files_in_dir_recursively(knowledge_folder))

def get_file_structure(
    name: str,
    basic_data: BasicProjectData|None=None,
    output_mode: str = file_tree.OUTPUT_MODE_STRING,
) -> str:
    project_folder = get_project_folder(name)
    if basic_data is None:
        basic_data = load_basic_project_data(name)

    tree = str(file_tree.file_tree(
        project_folder,
        max_depth=basic_data["file_structure"]["max_depth"],
        max_files=basic_data["file_structure"]["max_files"],
        max_folders=basic_data["file_structure"]["max_folders"],
        max_lines=basic_data["file_structure"]["max_lines"],
        ignore=basic_data["file_structure"]["gitignore"],
        output_mode=output_mode
    ))

    # empty?
    if "\n" not in tree:
        tree += "\n # Empty"

    return tree
