# Developer Agent Profile DOX

## Purpose

- Own the bundled software development specialist profile.
- Keep development, debugging, refactoring, and architecture behavior separate from general agent defaults.

## Ownership

- `agent.yaml` owns title, description, and delegation context for software development work.
- `prompts/agent.system.main.specifics.md` owns engineering intake, method, and task-specific delivery checks.
- `extensions/` owns developer-specific lifecycle hooks when present.

## Local Contracts

- Keep this profile focused on software engineering tasks.
- Do not hardcode repository-local credentials, paths, or project-specific conventions.
- Prompt overrides must preserve the framework tool-call and response contracts.
- Inherit shared communication and coding discipline; keep specialist directives compact without dropping technical constraints or verification.
- Engineering specifics require cause/caller tracing, defect-valid reproduction, independent expected results, and checks of the final diff; distinguish setup and pre-existing failures from regressions.

## Work Guidance

- Align developer behavior with the root engineering and tool contracts.
- Prefer profile prompt edits over core prompt edits when the behavior is specific to development tasks.

## Verification

- Manually inspect `agent.yaml` for valid YAML after edits.
- Run prompt/profile tests when changing profile loading or developer prompt behavior.
- For wording changes, compare direct tokenizer counts and inspect rendered prompts for retained engineering checks and shared communication.

## Child DOX Index

No child DOX files.
