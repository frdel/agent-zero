# A2A Chat Plugin DOX

## Purpose

- Own the `a2a_chat` tool for agent-to-agent communication over FastA2A.

## Ownership

- `tools/a2a_chat.py` owns session caching, message extraction, and remote dispatch.
- The tool logs its message as type `a2a_chat` with an `icon://hub Chatting: <agent_url>` headline; `extensions/webui/get_message_handler/` owns the `A2A` badge presentation and `extensions/webui/get_process_step_types/` registers the type.
- `helpers/fasta2a_client.py` owns the FastA2A client connection, message dispatch, and task polling.
- `prompts/` owns the tool prompt and the framework messages for failures.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Session state is stored on `agent.data["_a2a_sessions"]`, keyed by a normalized agent URL that strips an explicit `/a2a` suffix.
- The `reset` argument coerces through the shared `coerce_bool` helper instead of returning a repairable error; absent values default to `false`, other unrecognized values fall back to truthiness.
- Remote text extraction prefers the newest assistant history message, then status message, then artifacts; an empty extraction returns a distinct failed-response error instead of success.
- The tool reports a2a unavailability without raising.

## Work Guidance

- Keep tool output concise, model-readable, and safe for history persistence.
- Coordinate argument or behavior changes with the tool prompt and the fasta2a client contract.
- Respect intervention flow before remote dispatch and polling.

## Verification

- Import the tool in the framework runtime and run the a2a tool contract tests after changes.

## Child DOX Index

No child DOX files.
