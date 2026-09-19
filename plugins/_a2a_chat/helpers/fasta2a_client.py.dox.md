# fasta2a_client.py DOX

## Purpose

- Own the `fasta2a_client.py` helper module of the `_a2a_chat` plugin.
- This module connects Agent Zero to external A2A agents; the `_a2a_chat` tool is its only consumer.
- Keep this file-level DOX profile synchronized with `fasta2a_client.py`.

## Ownership

- `fasta2a_client.py` owns the runtime implementation.
- `fasta2a_client.py.dox.md` owns durable notes about responsibilities, contracts, side effects, and verification for that implementation.
- Classes:
- `AgentConnection` (no explicit base class)
  - `async get_agent_card(self) -> Dict[str, Any]`
  - `async send_message(self, message: str, attachments: Optional[List[str]]=..., context_id: Optional[str]=..., metadata: Optional[Dict[str, Any]]=...) -> Dict[str, Any]`
  - `async get_task(self, task_id: str) -> Dict[str, Any]`
  - `async wait_for_completion(self, task_id: str, poll_interval: int=..., max_wait: int=...) -> Dict[str, Any]`
  - `async close(self)`
- Top-level functions:
- `async connect_to_agent(agent_url: str, timeout: int=...) -> AgentConnection`: Create a connection to a remote agent.
- `is_client_available() -> bool`: Check if FastA2A client is available.
- Notable constants/configuration names: `_PRINTER`.

## Runtime Contracts

- Helper modules own reusable framework APIs and must preserve public callers unless all callers, tests, and docs are updated together.
- Update this file whenever public functions, classes, persistence behavior, path/security assumptions, side effects, or cross-module contracts change.
- Observed side-effect areas: filesystem writes, network calls, WebSocket state, settings/state persistence, secret handling, scheduler state.
- Imported dependency areas include: `helpers.print_style`, `typing`, `uuid`.

## Key Concepts

- Important called helpers/classes observed in the source: `PrintStyle`, `AgentConnection`, `PrintStyle.warning`, `agent_url.rstrip`, `httpx.AsyncClient`, `A2AClient`, `TimeoutError`, `connection.get_agent_card`, `RuntimeError`, `agent_url.startswith`, `os.getenv`, `self._http_client.aclose`, `self.close`, `response.raise_for_status`, `response.json`, `self.get_agent_card`, `uuid.uuid4`, `self._a2a_client.send_message`, `self._a2a_client.get_task`, `self.get_task`.
- Keep request/response, tool, or helper semantics documented here at the same time as source changes.

## Work Guidance

- Preserve public helper APIs used by core code and plugins unless every caller is updated.
- Keep path, auth, secret, persistence, network, and subprocess behavior explicit and bounded.
- Prefer adding cohesive helper functions here only when behavior is reused across modules.

## Verification

- Run targeted tests for changed helper behavior; run security regressions for auth, filesystem, WebSocket, tunnel, upload, or secret-handling helpers.
- No direct test reference was found by name search; choose the nearest behavioral test or perform a focused smoke check.

## Child DOX Index

No child DOX files.
