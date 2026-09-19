# Tiny Local Agent Profile DOX

## Purpose

- Own the bundled Tiny Local profile for small/local chat models.
- Keep local-model behavior prompt-only and isolated from core framework execution.

## Ownership

- `agent.yaml` owns profile metadata for discovery and profile switching.
- `prompts/agent.system.main.communication.md` owns the local-model communication contract.
- `prompts/agent.system.main.solving.md` owns the local-model problem-solving contract and suppresses inherited visible reasoning requirements.
- `prompts/fw.msg_repeat.md` owns Tiny Local's profile-specific recovery instructions when the framework rejects a duplicate assistant message.
- `prompts/agent.system.tools.md` owns the Tiny Local tools wrapper and final output-shape reminder after tool listing.
- `prompts/agent.system.tool.*.md` files own Tiny Local-specific tool examples that avoid inherited reasoning fields and repeated writes.

## Local Contracts

- Preserve the normal Agent Zero tool-call shape: `tool_name` plus `tool_args`.
- Do not add parser repair, duplicate suppression runtime, model transport, or text-editor runtime behavior here.
- Duplicate-message handling may be tightened through profile prompts only.
- Keep prompt text short enough for small local models to follow.
- Treat continuation requests such as `proceed` or `continue` as commands to execute the next unfinished step, not as prompts for another status response.
- Do not include user-specific provider names, API keys, local paths, or secrets.

## Work Guidance

- Prefer prompt wording changes over new files when tightening this profile, except when replacing inherited tool examples for local-model compliance.
- Keep this profile suitable for Ollama, LM Studio, Qwen, and comparable local models.

## Verification

- Render the `tiny-local` system prompt after communication prompt changes.
- Run `pytest tests/test_default_prompt_budget.py` for prompt and profile regressions.

## Child DOX Index

No child DOX files.
