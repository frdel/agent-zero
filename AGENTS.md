# Agent Zero DOX

## Purpose

- Own project-wide engineering rules and the top-level DOX index.
- Keep detailed contracts in the closest applicable child `AGENTS.md`.

## Project

- Stack: Python 3.12+ framework, Python 3.13 agent execution runtime, Flask, Alpine.js, LiteLLM, and Socket.IO.
- Start the WebUI with `python run_ui.py`; discover its URL from startup output, Docker mappings, or explicit configuration rather than assuming a port.
- Run the full test suite with `pytest` or a focused file with `pytest tests/test_name.py`.
- Human-facing documentation lives in `README.md` and `docs/`.

## Root Ownership

- `agent.py` owns `Agent`, `AgentContext`, and loop data.
- `Agent.hist_add_message` updates `AgentContext.last_message`, the activity timestamp used by snapshots and chat persistence; `created_at` remains unchanged. Context initialization preserves an explicitly supplied activity timestamp across greeting/history hooks.
- `Agent.hist_add_ai_response` owns Responses-API state advancement: it calls `_remember_llm_result_state` internally. Model turns pass an `LLMResult`; omitted results and legacy positional string IDs use the non-LLM sentinel. Callers must not invoke `_remember_llm_result_state` manually.
- Prepared local Responses input may project intact native history through `helpers/responses_history.py`; retain original Chat/fallback messages, current protocol/extras, summaries and masking. Durable capability metadata stores only a stable-prefix digest for eligibility; per-turn extras snapshots live separately in result metadata and count toward Responses history compression.
- `Agent.call_chat_model_turn` builds native function tools only when the chat model's `a0_api_mode` selects Responses; Chat Completions turns pass an empty tool list and name map, since that transport drops them.
- Native function calls use canonical call content for history and combine public response text with calls for repeat comparison. The canonical history content passes through the normal history template/masking hook; provider output metadata remains intact.
- `initialize.py` owns framework initialization.
- `models.py` owns model-provider configuration and LiteLLM integration. `get_api_key_raw()` reads the stored key or key list for settings/editing; `get_api_key()` selects a runtime key and runs provider extension hooks.
- Local sentence-transformers load only on an embedding cache miss, not when importing `models`. `run_ui.init_a0` starts deferred preload before chat restoration and returns a completion callback so its end hooks (including watchdog registration) overlap warmup. `run` invokes that callback, allowing up to ten additional seconds for preload before starting MCP and the job loop, then HTTP. Chat restoration and extension hooks are outside this wait limit. Timeout leaves preload running, so a first chat can still wait for an uncached model. Waiting is best-effort: timeout or task failure does not prevent HTTP startup. Initialization hooks may disable preload or suppress completion; disabled preload still allows MCP/jobs, while a skipped initializer skips them. `preload.py` constructs the configured local embedding model in a worker thread; it must not import unused speech runtimes or block the shared background event loop.
- `models._merge_provider_defaults` merges YAML-declared `extra_body` defaults with legacy top-level values for those declared fields and explicit nested overrides, in that order; unrelated kwargs and original-provider API-key selection remain intact.
- `models.apply_rate_limiter` skips token counting and returns no limiter when all request, input, and output limits are unset; any configured limit retains normal accounting.
- `requirements.txt` includes HTTPX's SOCKS extra so framework clients support SOCKS proxy environment variables before plugin setup.
- LiteLLM and OpenAI pins must remain compatible. Retain shared dependency security floors and verify upgrades with installed-SDK HTTP tests in `tests/test_litellm_sdk.py` using the framework runtime.
- Native agent-turn response callbacks may receive a display-only commentary preview as their full text; legacy callbacks, accumulated model output, usage and native dispatch retain the original text and result metadata.
- `run_ui.py` is the WebUI entry point.
- `DockerfileLocal` must remain compatible with the contracts under `docker/`.
- Runtime or user state under `usr/` and `tmp/` is intentionally outside tracked DOX unless the user explicitly asks otherwise.

## Project-Wide Contracts

- Import `AgentContext` and `AgentContextType` from `agent`, not `helpers.context`.
- Never commit secrets, `.env` files, API keys, tokens, or private user data.
- Preserve authentication and CSRF protections.
- Use Linux paths and commands in examples.
- When a live Dockerized Agent Zero target is explicitly named, verify that exact runtime instead of assuming a fixed localhost port.
- Message-loop completion flows through a response tool with `break_loop`; plain or malformed Chat Completions text enters repair, and native Responses output text is normalized through the same response-tool path.
- Reuse the startup-preloaded local embedding model for matching runtime configurations; wrappers retain their own rate-limit configuration while sharing the underlying inference model.
- Embedding wrappers expose batch-shaped `embed(inputs)` for provider-ready inputs; keep `embed_documents` and `embed_query` as LangChain compatibility adapters.
- Embedding requests never forward the chat-only `a0_api_mode` control to providers.
- Prompt Markdown may retain fenced JSON examples for readability; final system-prompt rendering removes only their JSON fence markers before model calls and preserves non-JSON fences.
- System section owners register request-only alternatives with `helpers.responses_tools`; `helpers.responses_history` owns their per-build state and prepared-history capture in existing loop parameters. Responses applies them to copied input, preserving original Chat/fallback messages and stored history.
- Copy live core-plugin changes back into tracked source under `plugins/`.
- Develop new custom plugins under ignored `usr/plugins/`; tracked bundled plugins live under `plugins/`.
- Use the framework runtime for backend and plugin-hook verification, not the separate agent execution runtime.
- Dependency changes must cover both image installation declarations and existing self-updated instances. Use startup migrations for core dependencies and the owning installation hooks for plugin dependencies.

## Permissions

Allowed without asking:

- Read repository files.
- Update files under `usr/`.

Ask before:

- Installing dependencies.
- Deleting core files outside `usr/` or `tmp/`.
- Modifying `agent.py` or `initialize.py`.
- Creating commits or pushing branches.

## DOX Workflow

- `AGENTS.md` files are binding contracts for their subtrees.
- Before editing, read this file and every `AGENTS.md` on the path to each target; the closest contract controls local details without weakening parent rules.
- Keep work understandable from the applicable DOX chain. Put project-wide rules here and concrete ownership, workflows, inputs, outputs, side effects, and verification in child docs.
- Create a child `AGENTS.md` only for a durable boundary with distinct ownership or workflow.
- Child docs should use: Purpose, Ownership, Local Contracts, Work Guidance, Verification, and Child DOX Index.
- After every meaningful change, re-check the affected paths, update the closest owning docs and indexes, remove stale guidance, and run relevant verification.
- Do not document ignored `usr/` or `tmp/` changes unless explicitly requested.
- Keep DOX concise, current, operational, and free of diary entries or duplicated parent guidance.

## Child DOX Index

| Child | Scope |
| --- | --- |
| [.github/AGENTS.md](.github/AGENTS.md) | GitHub Actions workflows and release automation scripts. |
| [agents/AGENTS.md](agents/AGENTS.md) | Bundled agent profiles, profile-local prompts, and tools. |
| [api/AGENTS.md](api/AGENTS.md) | HTTP API and WebSocket handler entry points. |
| [conf/AGENTS.md](conf/AGENTS.md) | Repository-shipped configuration defaults and templates. |
| [docker/AGENTS.md](docker/AGENTS.md) | Docker build contexts, images, compose files, and runtime layout. |
| [docs/AGENTS.md](docs/AGENTS.md) | Human-facing documentation and screenshots. |
| [extensions/AGENTS.md](extensions/AGENTS.md) | Backend and WebUI lifecycle extensions. |
| [helpers/AGENTS.md](helpers/AGENTS.md) | Shared backend utilities and runtime services. |
| [knowledge/AGENTS.md](knowledge/AGENTS.md) | Built-in agent self-knowledge. |
| [lib/AGENTS.md](lib/AGENTS.md) | Lightweight browser-side helpers outside the WebUI bundle. |
| [plugins/AGENTS.md](plugins/AGENTS.md) | Bundled system plugins and custom-plugin architecture. |
| [prompts/AGENTS.md](prompts/AGENTS.md) | Core prompt templates. |
| [scripts/AGENTS.md](scripts/AGENTS.md) | Repository maintenance scripts and automation inputs. |
| [skills/AGENTS.md](skills/AGENTS.md) | Bundled Agent Zero skills. |
| [tests/AGENTS.md](tests/AGENTS.md) | Pytest regression and contract tests. |
| [tools/AGENTS.md](tools/AGENTS.md) | Core agent tool implementations. |
| [webui/AGENTS.md](webui/AGENTS.md) | Alpine.js WebUI shell, components, JavaScript, CSS, and assets. |

Intentionally unindexed local or generated roots:

| Path | Reason |
| --- | --- |
| `.conda/`, `.venv/` | Local Python environments. |
| `.pytest_cache/`, `__pycache__/` | Generated test and bytecode caches. |
| `.vscode/`, `.windsurf/` | Editor-local configuration and assistant metadata. |
| `tmp/` | Ignored runtime caches, uploads, and generated work. |
| `usr/` | Ignored local user data, settings, plugins, chats, and workdirs. |
| `python/` | Generated or legacy runtime mirror; current source is in root modules and tracked source directories. |
