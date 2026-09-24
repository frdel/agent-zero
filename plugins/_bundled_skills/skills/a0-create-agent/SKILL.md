---
name: a0-create-agent
description: "Create Agent Zero profiles with agent.yaml, prompt overrides, tools and extensions."
version: 1.0.0
tags: ["agents", "profile", "create", "new", "subordinate"]
trigger_patterns:
  - "create agent"
  - "new agent profile"
  - "add agent profile"
  - "make agent profile"
  - "agent profile template"
  - "build agent profile"
---

# Create an Agent Zero Agent Profile

> [!IMPORTANT]
> Do **not** create new profiles in `/a0/agents/` — that directory is reserved for core framework profiles (`default`, `agent0`, `_example`). Bundled specialist profiles (`developer`, `hacker`, `researcher`, `tiny-local`) are plugin-distributed under `/a0/plugins/_agent_profiles/agents/`. User profiles belong in `/a0/usr/agents/<profile_name>/`.

Related skills: `/a0/plugins/_bundled_skills/skills/a0-development/SKILL.md` (broader framework guide) | `/a0/plugins/_bundled_skills/skills/a0-create-plugin/SKILL.md` (bundle a profile inside a plugin).

Primary references:
- `/a0/agents/_example/` — the canonical reference profile (tool + extension + prompt overrides)
- `/a0/agents/default/` — the base profile every other profile inherits from
- `/a0/plugins/AGENTS.md` — plugin-distributed profiles + per-profile config

---

## Existing Profile Pattern

The built-in profiles are intentionally split into two layers:

1. `agent.yaml` is tiny metadata for discovery and delegation:
   - `title`
   - `description`
   - `context`
2. The actual profile behavior usually lives in `prompts/agent.system.main.specifics.md`.

Use the shipped profiles as calibration:

| Profile | Pattern to copy |
|---|---|
| `agent0` | Minimal top-level assistant identity (`/a0/agents/agent0/`) |
| `_example` | Minimal demo of prompt/tool/extension override surfaces (`/a0/agents/_example/`) |
| `developer` | Rich capabilities, methodology, output requirements (`/a0/plugins/_agent_profiles/agents/developer/`) |
| `researcher` | Rich capabilities, methodology, evidence standards (`/a0/plugins/_agent_profiles/agents/researcher/`) |
| `hacker` | Short, direct operational identity plus optional environment override (`/a0/plugins/_agent_profiles/agents/hacker/`) |
| `tiny-local` | Small local model workarounds via tool prompt overrides (`/a0/plugins/_agent_profiles/agents/tiny-local/`) |

For most new profiles, create `agent.yaml` plus one strong `agent.system.main.specifics.md`. Add other prompt overrides, tools, or extensions only when the blueprint explicitly needs them.

---

## Step 0: Progressive Intake

Do not ask the user a long form. New users are easily overwhelmed. Guide them with lossy compression: ask only the next highest-value question, one or two questions per turn maximum.

Default assumptions unless the user says otherwise:

- Scope: user profile in `/a0/usr/agents/<name>`.
- Models: inherit global/project `_model_config`.
- Response contract: keep the standard Agent Zero JSON tool-call contract.
- Extras: no custom tools or lifecycle extensions.
- Prompt strategy: `agent.yaml` plus `prompts/agent.system.main.specifics.md`.

Recommended interview flow:

1. First ask only:
   - "What should this agent be excellent at?"
   - Optionally: "Do you already have a name/title in mind?"
2. After the purpose is clear, propose a short summary with inferred `name`, `title`, `description`, and `context`, then ask for confirmation or corrections.
3. Ask about behavior only if needed:
   - "Should it work more like a concise specialist, a rigorous researcher, a code-heavy implementer, or something else?"
4. Ask about advanced options only when the user's request implies them:
   - custom output format
   - a profile-specific model preset
   - custom tools
   - lifecycle extensions
   - plugin/project scope
5. Before writing files, show the compact blueprint summary and ask for confirmation.
6. Only after confirmation, produce the full AgentProfileBlueprint JSON in Step 1 and write files from it.

Never open with all blueprint fields. Do not mention obscure paths until they matter. Hide defaults, but use them.

If the user gives a broad idea, infer sensible defaults and mark uncertainties in `validation.open_questions` instead of stalling.

---

## Step 1: Create an AgentProfileBlueprint JSON

Before writing files, produce exactly one valid JSON object in a fenced `json` block using this schema. This blueprint is the source of truth. Do not require a utility model or prose post-processing to extract fields.

```json
{
  "schema": "agent_zero.agent_profile_blueprint.v1",
  "status": "draft",
  "profile": {
    "scope": "user",
    "root": "/a0/usr/agents",
    "name": "data-analyst",
    "title": "Data Analyst",
    "description": "Agent specialized in data analysis, visualization, and statistical modeling.",
    "context": "Use this agent for data analysis tasks, creating visualizations, statistical analysis, and working with datasets in Python."
  },
  "behavior": {
    "role": "You are a specialized data analysis agent.",
    "primary_capabilities": [
      "Python data analysis with pandas, numpy, and scipy",
      "Data visualization with matplotlib, seaborn, and plotly",
      "Statistical modeling and hypothesis testing"
    ],
    "operating_principles": [
      "Inspect data before drawing conclusions",
      "Prefer reproducible code and explicit assumptions",
      "Explain uncertainty and limitations"
    ],
    "workflow": [
      "Clarify the question and available data",
      "Profile and clean the dataset",
      "Run analysis with appropriate methods",
      "Visualize and interpret results"
    ],
    "output_preferences": [
      "Concise findings first",
      "Tables or charts when useful",
      "Reproducible code when analysis is performed"
    ]
  },
  "prompt_strategy": {
    "base_pattern": "specifics_only",
    "override_rationale": [
      "Use agent.system.main.specifics.md for role, expertise, and process.",
      "Keep the inherited communication contract unchanged."
    ],
    "root_prompt_overrides": [
      {
        "file": "agent.system.main.communication.md",
        "reason": "Only include if the profile needs a different response JSON schema or output format."
      }
    ]
  },
  "llm_config": {
    "enabled": false,
    "path": "/a0/usr/agents/data-analyst/plugins/_model_config/config.json",
    "source": "inherit_scoped",
    "model_preset": null,
    "notes": [
      "Do not put model settings in agent.yaml.",
      "Only create this config file if the user wants this profile to select a specific global model preset.",
      "Scoped _model_config config stores only model_preset."
    ]
  },
  "files": [
    {
      "path": "/a0/usr/agents/data-analyst/agent.yaml",
      "kind": "yaml",
      "content": "title: Data Analyst\ndescription: Agent specialized in data analysis, visualization, and statistical modeling.\ncontext: Use this agent for data analysis tasks, creating visualizations, statistical analysis, and working with datasets in Python.\n"
    },
    {
      "path": "/a0/usr/agents/data-analyst/prompts/agent.system.main.specifics.md",
      "kind": "markdown",
      "content": "## Your role\n\nYou are a specialized data analysis agent.\n\n## Expertise\n- Python data analysis with pandas, numpy, and scipy\n- Data visualization with matplotlib, seaborn, and plotly\n- Statistical modeling and hypothesis testing\n\n## Process\n1. Clarify the question and available data\n2. Profile and clean the dataset\n3. Run analysis with appropriate methods\n4. Visualize and interpret results\n"
    }
  ],
  "optional_components": {
    "extra_prompt_overrides": [],
    "tools": [],
    "extensions": []
  },
  "validation": {
    "needs_user_confirmation": true,
    "unique_name_checked": false,
    "yaml_valid": false,
    "open_questions": []
  }
}
```

Rules for the blueprint:

- Output strict JSON: no comments, no trailing commas, no markdown inside string values except the intended file content.
- `profile.name` must be lowercase letters, numbers, hyphens, or underscores only.
- `prompt_strategy.root_prompt_overrides` must list any inherited root `/prompts` files being considered or replaced and why.
- If a root prompt override is only a possibility, list it in `prompt_strategy` but do not add it to `files` until confirmed.
- `llm_config.enabled` controls whether a profile-scoped `_model_config/config.json` file is created. Keep it `false` when the preset should inherit from broader project/global settings.
- `files[*].content` must be the exact file content to write.
- Include only files that should actually be created.
- Set `status` to `draft` until all required choices are known; set it to `ready` only after resolving open questions.
- Ask the user to confirm or edit the blueprint before writing files unless they explicitly authorized immediate creation.

---

## Step 2: Required Fields

The blueprint must contain these required profile inputs:

| Input | Rule | Example |
|---|---|---|
| **name** (directory name) | lowercase letters, numbers, hyphens or underscores; must be unique across profile search paths | `data-analyst` |
| **title** | human-readable display name shown in the UI | `Data Analyst` |
| **description** | one-line specialization summary | `Agent specialized in data analysis, visualization, and statistical modeling.` |
| **context** | instructions telling the *superior* agent when to delegate to this profile | `Use this agent for data analysis tasks, creating visualizations, statistical analysis, and working with datasets in Python.` |

> [!NOTE]
> `agent.yaml` has **only** these three content fields (`title`, `description`, `context`). Do not add model, temperature, or `allowed_tools` fields to `agent.yaml`. A profile-specific preset selection lives in a companion `_model_config` plugin config file, and tool availability is controlled by plugin activation.

---

## Step 3: Write Files from the Blueprint

After the user confirms the blueprint, create exactly the paths listed in `files`.

```
<PROFILE_ROOT>/<name>/
├── agent.yaml                # Required
├── prompts/                  # Optional — prompt overrides
├── tools/                    # Optional — profile-specific tools
└── extensions/               # Optional — profile-specific extensions
```

`agent.yaml`:

```yaml
title: Data Analyst
description: Agent specialized in data analysis, visualization, and statistical modeling.
context: Use this agent for data analysis tasks, creating visualizations, statistical
  analysis, and working with datasets in Python.
```

A profile with only `agent.yaml` is valid — it inherits everything from `default/`. Add the sections below only when you need to change something.

---

## Step 4: Optional profile-specific model preset

Agent Zero does **not** read model settings from `agent.yaml`. The `_model_config` plugin is always enabled and supports per-agent-profile preset selection. If the user wants this profile to use a specific existing global preset, create a companion config file:

| Profile scope | Model config path |
|---|---|
| User profile | `/a0/usr/agents/<profile>/plugins/_model_config/config.json` |
| Plugin-distributed profile | `/a0/usr/plugins/<plugin>/agents/<profile>/plugins/_model_config/config.json` |
| Project-scoped profile | `<project>/.a0proj/agents/<profile>/plugins/_model_config/config.json` |

Scoped `_model_config/config.json` files contain only the selected global preset name. Preset definitions are managed centrally in Model Configuration and are not copied into profiles.

Profile-scoped selection:

```json
{
  "model_preset": "Research"
}
```

Rules:

- Ask whether the profile should inherit its scoped preset or select an existing global preset.
- Verify the preset exists before adding the file. If new model choices are needed, create a global preset through Model Configuration first.
- Do not store API keys or model dictionaries in this file; API keys and preset definitions are managed centrally.
- Add this file to `files` only when `llm_config.enabled` is `true`.

---

## Step 5: Override prompts (the most common customization)

Profiles inherit all prompts from `/a0/prompts/` and from `/a0/agents/default/`. To change behavior, drop a file with the **same filename** into `<PROFILE_ROOT>/<name>/prompts/`. The loader searches profile-specific prompts first and falls back to the defaults.

### The canonical override: `agent.system.main.specifics.md`

This is the designated extension slot for profile-specific role, identity, and behavior instructions. The file ships **empty** in both `/a0/prompts/agent.system.main.specifics.md` and `/a0/agents/default/prompts/agent.system.main.specifics.md` precisely so profiles can fill it in without fighting the base prompt. It is included from `agent.system.main.md` right after `agent.system.main.role.md`, so whatever you put here layers on top of the inherited role.

**Every core and bundled specialist profile overrides this file** (tiny-local overrides tool prompts instead) — a good sanity check that this is the right place for your specialization. Look at the existing profiles for concrete shape:

| Profile | What its `agent.system.main.specifics.md` does |
|---|---|
| `/a0/agents/agent0/prompts/agent.system.main.specifics.md` | Establishes the top-level user-facing agent's behavior |
| `/a0/plugins/_agent_profiles/agents/developer/prompts/agent.system.main.specifics.md` | Full "Master Developer" role + process spec (most elaborate example) |
| `/a0/plugins/_agent_profiles/agents/hacker/prompts/agent.system.main.specifics.md` | Concise red/blue team pentester identity |
| `/a0/plugins/_agent_profiles/agents/researcher/prompts/agent.system.main.specifics.md` | Research methodology and deliverable expectations |
| `/a0/agents/_example/prompts/agent.system.main.specifics.md` | Minimal demo override (fictional "Agent Zero" persona) |

Start by copying whichever existing profile's `specifics.md` is closest to your target, then rewrite.

Example `agent.system.main.specifics.md` for a data analyst:

```markdown
## Your role

You are a specialized data analysis agent.
Your expertise includes:
- Python data analysis (pandas, numpy, scipy)
- Data visualization (matplotlib, seaborn, plotly)
- Statistical modeling and hypothesis testing
- SQL queries and database analysis
- Data cleaning and preprocessing

## Process
1. Understand the data and the question
2. Choose appropriate tools and methods
3. Execute analysis with `code_execution_tool`
4. Visualize results when applicable
5. Provide clear interpretation of findings
```

### High-value inherited prompt levers

The root `/a0/prompts` directory contains powerful defaults. A profile can override any of these by placing a file with the same name in `<PROFILE_ROOT>/<name>/prompts/`. Use this when the requested profile needs a different protocol, not just a different specialty.

| File | Override when the user wants... |
|---|---|
| `agent.system.main.communication.md` | A different response contract, such as no `thoughts` array, a different JSON schema, plain Markdown answers, or a domain-specific output envelope. This is the main lever for output format changes. |
| `agent.system.main.solving.md` | A different problem-solving loop, delegation policy, verification standard, or autonomy level. |
| `agent.system.main.tips.md` | Different file-handling, skill-use, memory, or operational best-practice defaults. |
| `agent.system.main.environment.md` | A different runtime/environment description than the default Kali/Docker Agent Zero environment. |
| `agent.system.main.role.md` | A fundamentally different base identity. Rare; prefer `specifics.md` unless replacing the base role is intentional. |
| `agent.system.tool.response.md` | Different final-response tool instructions, such as stricter final formatting or use of includes for long output. |
| `fw.user_message.md` / `fw.ai_response.md` | Different framework message wrapping. Advanced and fragile; override only with a clear reason. |

When a blueprint includes any of these, add an entry to `prompt_strategy.root_prompt_overrides` and include the exact override file in `files`.

### Secondary overrides (use only when needed)

| File | When to override | Shipped example |
|---|---|---|
| `agent.system.main.role.md` | Replace the base role framing wholesale (rare — most profiles layer via `specifics.md` instead) | `/a0/agents/agent0/prompts/agent.system.main.role.md` |
| `agent.system.main.communication.md` | Change reply format / communication style | `/a0/plugins/_agent_profiles/agents/tiny-local/prompts/agent.system.main.communication.md` |
| `agent.system.main.environment.md` | Describe a non-default runtime environment | `/a0/plugins/_agent_profiles/agents/hacker/prompts/agent.system.main.environment.md` (Kali/Docker) |
| `agent.system.tool.<name>.md` | Document a profile-specific tool (see Step 6) | `/a0/agents/_example/prompts/agent.system.tool.example_tool.md` |

> [!TIP]
> Only override what you actually need to change. Copying unchanged prompt files creates silent drift when the framework updates the originals — `specifics.md` is safe to own because its default is empty by design.

---

## Step 6 (optional): Profile-specific tools

Drop a Python tool class in `<PROFILE_ROOT>/<name>/tools/<tool_name>.py`:

```python
from helpers.tool import Tool, Response

class ExampleTool(Tool):
    async def execute(self, **kwargs):
        test_input = kwargs.get("test_input", "")
        return Response(
            message=f"Example tool executed with test_input: {test_input}",
            break_loop=False,
        )
```

Two important rules:

1. To make the tool visible in the system prompt, add `prompts/agent.system.tool.<tool_name>.md` describing its usage and JSON call schema. The prompt loader auto-includes every file matching `agent.system.tool.*.md`.
2. Placing a file with the same name as a core tool (e.g. `tools/response.py`) **replaces** the core tool for this profile only. See `/a0/agents/_example/tools/response.py` for a redefinition example.

---

## Step 7 (optional): Profile-specific extensions

Lifecycle hooks go in `<PROFILE_ROOT>/<name>/extensions/<hook_point>/_NN_<name>.py`. The `_NN_` prefix controls execution order.

Example — rename the agent at init (`/a0/agents/_example/extensions/agent_init/_10_example_extension.py`):

```python
from helpers.extension import Extension

class ExampleExtension(Extension):
    async def execute(self, **kwargs):
        self.agent.agent_name = "SuperAgent" + str(self.agent.number)
```

Available hook points mirror the framework's own `/a0/extensions/python/<point>/` directories — see `a0-development/SKILL.md` for the full list.

---

## Step 8: Test the new profile

1. The profile is picked up on next agent initialization — no restart of individual conversations needed, but a fresh agent/subordinate spawn is required.
2. From the superior agent, delegate to it via `call_subordinate` using the profile's **directory name** (not the title).
3. Verify:
   - Title appears correctly in the UI agent selector.
   - Role override (if any) takes effect in the new agent's system prompt.
   - Profile-specific tools are callable and their prompt files are included.

If the profile does not appear, check:
- Directory name matches the `^[a-z0-9_-]+$` pattern and is unique.
- `agent.yaml` parses as valid YAML.
- It is placed in one of the recognized search paths (see Step 0).

---

## Reference: Complete `_example` profile layout

```
/a0/agents/_example/
├── agent.yaml
├── prompts/
│   ├── agent.system.main.specifics.md     # role override
│   └── agent.system.tool.example_tool.md  # tool usage prompt
├── tools/
│   ├── example_tool.py                    # new tool
│   └── response.py                        # redefines core response tool
└── extensions/
    └── agent_init/
        └── _10_example_extension.py       # init-time hook
```

Copy this shape when in doubt — it demonstrates every customization surface a profile supports.

---

## Quick checklist

- [ ] Confirmed profile scope (user / plugin / project)
- [ ] Produced and confirmed `agent_zero.agent_profile_blueprint.v1` JSON
- [ ] Confirmed whether the model preset inherits or needs a profile-specific `_model_config/config.json` selection
- [ ] Directory name is unique and matches allowed characters
- [ ] `agent.yaml` contains exactly `title`, `description`, `context`
- [ ] Prompt overrides only include files that actually change behavior
- [ ] Any new tool has a matching `agent.system.tool.<name>.md`
- [ ] Profile tested via `call_subordinate` in a fresh conversation
