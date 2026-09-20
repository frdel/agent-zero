# Local Model Tool Use

Small local models can struggle with Agent Zero's full default communication shape. The safest first fix is prompt/profile/plugin-only: use a smaller behavior contract while leaving Agent Zero's core parser and execution code unchanged.

Use this guide for Ollama, LM Studio, Qwen, and similar local chat models when the model explains commands instead of calling tools.

## Use The Tiny Local Profile

Choose the **Tiny Local** profile when starting or switching a chat that uses a small local model.

The bundled profile lives at:

```text
plugins/_agent_profiles/agents/tiny-local/
```

Tiny Local keeps the normal Agent Zero tool-call shape, but removes visible reasoning fields from the communication prompt. It tells the model to emit one executable JSON object with `tool_name` and `tool_args`.

## Use A Project Prompt Include

If you want to keep your current profile, create a project-local file that matches the Prompt Include plugin pattern (`*.promptinclude.md`):

```text
local-model-tool-use.promptinclude.md
```

Put this content in that file:

```markdown
## Local model tool-use discipline

You are Agent Zero. Act on the user's behalf.

When the user asks you to do something, do it directly. Do not explain how the user could do it themselves.

Your visible assistant message must be exactly one valid JSON object.

Use exactly these top-level fields: `tool_name` and `tool_args`.

Do not include markdown fences, prose before the JSON, prose after the JSON, hidden reasoning, analysis, thoughts, or headlines.

Choose a tool from the tools listed in the system prompt. Do not invent tool names, action names, or generic names such as `read`, `write`, `terminal`, or `multi`.

For a final user-facing answer, use the `response` tool:

`{"tool_name":"response","tool_args":{"text":"Done."}}`

Use `response` only when the work is complete, blocked, or no tool is needed. If the user says "proceed", "continue", "go ahead", or similar after the agent named a next step, call the next appropriate tool instead of replying with a promise or status update.

For work that requires a command, file action, browser action, or any other available tool, call the appropriate tool immediately.

If the framework warns that your prior message was malformed, repeated, or reasoning-only, output a corrected JSON tool request immediately without explaining the warning.
```

## Keep This Prompt-Only

Do not change `agent.py` for this workflow.

Do not change `helpers/extract_tools.py` for this workflow.

Do not create parser repair code for this workflow.

Do not add duplicate execution suppression, LiteLLM transport changes, memory runtime changes, or text-editor file operation changes for this workflow.

If a specific local model still cannot follow the prompt/profile/plugin-only contract, capture the exact model, prompt, response, and tool warning before considering deeper framework changes.
