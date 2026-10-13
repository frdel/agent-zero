# Prompts DOX

## Purpose

- Own core prompt templates used by agents, tools, framework messages, behavior updates, summaries, skills, projects, and system context.
- Keep prompt contracts explicit and synchronized with code that renders them.

## Ownership

- `agent.*.md` and companion `.py` files provide system, context, tool, project, skill, and behavior prompt material.
- `fw.*.md` files provide framework-generated message templates.
- Profile-specific prompt overrides belong under `agents/<profile>/prompts/`.
- Plugin prompt additions belong under the relevant plugin `prompts/` directory.

## Local Contracts

- Do not include secrets, real API keys, or private user data in prompt templates.
- Keep placeholder names, include aliases, and template assumptions synchronized with prompt-loading code and extensions.
- `agent.system.main.communication.native.md` owns native function-call formatting; profiles may override it alongside the legacy communication template. Shared communication additions remain transport-neutral; the brace terminator belongs only to legacy JSON formatting.
- Native communication requests public commentary without a sentence limit; the display maps it to thoughts without adding fields to native arguments.
- Prompt changes can alter agent behavior; keep edits narrow and intentional.
- Shared solving guidance owns observable success, evidence-driven replanning, task progress notes, source-preserving synthesis, and bug reproduction; specialist methods belong in profile specifics.
- Maintain clear separation between core behavior prompts and profile/plugin-specific customization.
- Delegation catalogs show profile IDs, titles, and context (description fallback) on separate lines; preserve project-scoped discovery.
- Environment prompts keep runtime boundaries visible and route framework/API procedures to `a0-development` references.
- Keep configurable capability names and usage guidance in their
  `agent.system.tool.*.md` prompts so tool policy removes the guidance together
  with the capability; non-tool system fragments stay capability-neutral.
- MCP prompt templates own the static outer, server, and tool framing;
  `helpers/mcp_handler.py` supplies policy-filtered names, descriptions, and
  schemas.
- Summary prompts that compress history should preserve loaded skill names from `skill_instructions` metadata without copying full skill bodies.
- `Agent.read_prompt` and `Agent.parse_prompt` strip trailing newlines from returned content, so prompt template files may safely keep a final newline. Do not rely on trailing newlines for formatting; render-time joins in `output_text()` already separate turns.
- `fw.initial_user_message.md` owns the placeholder user turn (`Hello!`) that `extensions/python/agent_init/_10_initial_message.py` pairs before the AI greeting from `fw.initial_message.md`; the user-first ordering guarantees `output_langchain` does not pop the greeting as a leading `AIMessage` on project or non-project paths. Do not remove either prompt without replacing the turn-order guarantee.
- `fw.msg_reasoning_only.md` and `fw.msg_reasoning_only_response.md` own the reasoning-only turn warning pair used by `extensions/python/message_loop_result/_20_empty_response.py`.
- `fw.msg_output_limit.md` and `fw.msg_output_limit_response.md` own the output-limit truncation warning pair used by `extensions/python/message_loop_result/_05_truncated_response.py`.

## Work Guidance

- Read the rendering path before changing placeholders or filenames.
- Prefer small prompt additions over broad rewrites when fixing a specific behavior.
- Keep document/OCR routing explicit: image files, screenshots, scans, charts, photos, and diagrams should prefer vision tools when available, while `document_query` is for documents, large text-heavy files, and fallback OCR.
- Keep the single `vision_load` tool prompt route-agnostic and preserve one-call loading for related images; internal image-analysis instructions belong in framework prompts, not Python strings.
- Update tests or snapshots when prompt budget, required sections, or generated system content changes.

## Verification

- Run targeted prompt, budget, snapshot, tool, or behavior tests after prompt changes.
- Inspect rendered prompt output when changing template wiring or placeholders.

## Child DOX Index

No child DOX files.
