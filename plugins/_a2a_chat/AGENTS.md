# A2A Chat Plugin DOX

## Purpose

- Own the `a2a_chat` tool for agent-to-agent communication over FastA2A.

## Ownership

- `tools/a2a_chat.py` owns session caching, message extraction, and remote dispatch.
- `helpers/fasta2a_client.py` owns the FastA2A client connection, message dispatch, and task polling.
- `prompts/` owns the tool prompt.
- `plugin.yaml` and `README.md` own metadata and docs.

## Local Contracts

- Session state is stored on `agent.data["_a2a_sessions"]`, keyed by a normalized agent URL that strips an explicit `/a2a` suffix.
- Remote text extraction prefers the newest assistant history message, then status message, then artifacts; an empty extraction returns a distinct failed-response error instead of success.
- `helpers/fasta2a_client.py` owns the FastA2A client connection and polling helpers; the tool reports unavailability without raising.

## Verification

- Import the tool in the framework runtime and run the a2a tool contract tests after changes.

## Child DOX Index

No child DOX files.
