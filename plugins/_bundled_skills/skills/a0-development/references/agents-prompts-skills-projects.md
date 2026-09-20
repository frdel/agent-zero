# Agents, Prompts, Skills, And Projects

## Source Anchors

- Agent profiles: `/a0/helpers/subagents.py`, `/a0/agents/AGENTS.md`
- Prompt rendering: `/a0/agent.py`, `/a0/helpers/files.py`, `/a0/prompts/AGENTS.md`
- Skill runtime: `/a0/helpers/skills.py`, `/a0/tools/skills_tool.py`, `/a0/plugins/_bundled_skills/skills/AGENTS.md`
- Project metadata: `/a0/helpers/projects.py`, `/a0/api/projects.py`, `/a0/webui/components/projects/`

## Agent Profiles

Bundled profiles live under `agents/<profile>/`. User-created profiles live under `usr/agents/<profile>/`. Plugin-distributed profiles live under plugin `agents/` directories.

The current profile loader accepts `agent.yaml` or `agent.json` and validates through `helpers.subagents.SubAgentListItem` / `SubAgent` fields:

| Field | Meaning |
|---|---|
| `title` | Human-readable display name. Defaults to profile name if empty. |
| `description` | Brief specialization. |
| `context` | Delegation guidance for when to use the profile. |
| `enabled` | Optional availability flag in list contexts. |

Bundled `agent.yaml` files currently use `title`, `description`, and `context`. Model settings are not read from `agent.yaml`; the `_model_config` plugin owns model configuration and scoped overrides.

Profile folders may contain `prompts/`, `tools/`, `extensions/`, and `skills/`, but verify discovery code before relying on example layout. Source and DOX beat stale examples.

## Prompt System

Agents render prompt fragments through `Agent.read_prompt(...)`, which calls `helpers.files.read_prompt_file(...)`.

Prompt capabilities:

- Placeholder replacement with `{{variable_name}}`.
- Conditional blocks with `{{if ...}} ... {{endif}}`.
- Include directives such as `{{include "file.md"}}`.
- `{{include original}}` to include the same file from a lower-priority directory.

Prompt locations include:

| Location | Use |
|---|---|
| `prompts/` | Core framework prompts. |
| `agents/<profile>/prompts/` | Bundled profile overrides. |
| `usr/agents/<profile>/prompts/` | User profile overrides. |
| `plugins/<plugin>/prompts/` | Bundled plugin prompt additions or overrides. |
| `usr/plugins/<plugin>/prompts/` | User plugin prompts. |

Prompt changes can change agent behavior. Keep edits narrow and run targeted prompt, budget, snapshot, tool, or behavior tests.

## Skills

Skills are directories containing `SKILL.md` frontmatter plus optional `references/`, `scripts/`, or `assets/`.

Skill roots come from `helpers.skills.get_skill_roots(...)`, including bundled skills, user skills, project metadata, profile skills, and plugin skills.

`skills_tool` actions:

| Action | Purpose |
|---|---|
| `list` | List available skills without full content. |
| `search` | Search skill metadata and triggers. |
| `load` | Load `SKILL.md` body and show the skill file tree. |
| `read_file` | Read a file inside the skill directory, such as `references/foo.md`. |

Keep always-loaded `SKILL.md` concise. Move long examples, schemas, policies, and variant-specific details into one-level-deep `references/` files and tell the agent when to read them.

Use `build-skill` for skill creation and skill format work.

## Projects

Projects live under `usr/projects/<name>/` and store metadata in `.a0proj/`.

Important project files and folders:

| Path | Purpose |
|---|---|
| `.a0proj/project.json` | Project title, description, instructions, color, git URL, include-AGENTS option, and file-structure settings. |
| `.a0proj/instructions/` | Additional text instruction files. |
| `.a0proj/knowledge/` | Project knowledge files. |
| `.a0proj/variables.env` | Non-sensitive project variables. |
| `.a0proj/secrets.env` | Encrypted project secrets. |
| `.a0proj/agents/` | Per-project agent profile material. |
| `.a0proj/skills/` | Project-scoped skills. |
| `.a0proj/mcp_servers.json` | Project MCP server configuration. |

`helpers.projects.BasicProjectData` currently normalizes `title`, `description`, `instructions`, `include_agents_md`, `color`, `git_url`, and `file_structure`. `EditProjectData` adds runtime/editing fields such as `variables`, `secrets`, `mcp_servers`, `subagents`, and git status.

Project file-structure injection uses settings for `enabled`, `max_depth`, `max_files`, `max_folders`, `max_lines`, and `gitignore`.

## Verification

- Run profile-loading tests when changing agent profile schema or discovery.
- Inspect rendered prompts when changing prompt filenames, include behavior, placeholders, or prompt order.
- Run skill runtime/catalog tests after changing skill loading, search, active/hidden behavior, or skill format.
- For project changes, test create/load/edit paths and project prompt injection when relevant.
