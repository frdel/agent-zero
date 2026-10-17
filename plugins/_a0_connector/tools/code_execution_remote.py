"""code_execution_remote tool — run shell-backed frontend operations on the CLI machine via `/ws`."""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

from helpers.tool import Response, Tool, coerce_bool
from helpers.ws_manager import (
    ConnectionNotFoundError,
    WsPayloadTooLargeError,
    get_shared_ws_manager,
)

from plugins._a0_connector.helpers.exec_config import build_exec_config
from plugins._a0_connector.helpers.ws_runtime import (
    clear_pending_exec_op,
    emit_connector_event,
    remote_exec_metadata_for_sid,
    remote_file_metadata_for_sid,
    remote_tool_sids_for_context,
    select_remote_exec_target_sid,
    store_pending_exec_op,
)


EXEC_OP_TRANSPORT_GRACE = 15.0
EXEC_OP_DEFAULT_TIMEOUT = 120.0
EXEC_OP_EVENT = "connector_exec_op"
_TIMEOUT_KEYS = (
    "first_output_timeout",
    "between_output_timeout",
    "max_exec_timeout",
    "dialog_timeout",
)


class CodeExecutionRemote(Tool):
    """Send shell-backed frontend execution operations to the connected CLI machine."""

    _allow_running = False

    @staticmethod
    def _runtime_requires_write_access(runtime: str) -> bool:
        return runtime in {"terminal", "python", "nodejs"}

    @staticmethod
    def _timeout_group_for_runtime(
        runtime: str,
        exec_config: dict[str, Any],
    ) -> dict[str, int] | None:
        if runtime == "output":
            source = exec_config.get("output_timeouts")
        elif runtime in {"terminal", "python", "nodejs"}:
            source = exec_config.get("code_exec_timeouts")
        else:
            return None

        if not isinstance(source, dict):
            return None

        timeouts: dict[str, int] = {}
        for key in _TIMEOUT_KEYS:
            try:
                timeouts[key] = max(0, int(source[key]))
            except (KeyError, TypeError, ValueError):
                return None
        return timeouts

    @staticmethod
    def _wait_timeout_for_runtime(runtime: str, exec_config: dict[str, Any]) -> float:
        timeouts = CodeExecutionRemote._timeout_group_for_runtime(runtime, exec_config)
        if not timeouts:
            return EXEC_OP_DEFAULT_TIMEOUT
        return max(float(value) for value in timeouts.values()) + EXEC_OP_TRANSPORT_GRACE

    def get_log_object(self):
        import uuid

        return self.agent.context.log.log(
            type="code_exe",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self, text: str = "") -> str:
        if not text:
            name = str(getattr(self, "name", "code_execution_remote"))
            runtime = str(self.args.get("runtime", "unknown") or "unknown")
            text = f"{name} - {runtime}"

        normalized = " ".join(str(text).split())
        if len(normalized) > 200:
            normalized = normalized[:197].rstrip() + "..."

        session = self.args.get("session", None)
        session_text = f"[{session}] " if session or session == 0 else ""
        return f"icon://terminal {session_text}{normalized}"

    async def execute(self, **kwargs: Any) -> Response:
        runtime = str(self.args.get("runtime", "")).strip().lower()
        if runtime not in {"terminal", "python", "nodejs", "output", "reset"}:
            return Response(
                message="runtime is required (terminal, python, nodejs, output, reset)",
                break_loop=False,
            )

        context_id = self.agent.context.id
        candidates = remote_tool_sids_for_context(context_id)
        require_writes = self._runtime_requires_write_access(runtime)
        sid = select_remote_exec_target_sid(context_id, require_writes=require_writes)
        if not sid:
            exec_enabled = False
            write_blocked = False
            for candidate_sid in candidates:
                exec_metadata = remote_exec_metadata_for_sid(candidate_sid)
                if exec_metadata is None or not exec_metadata.get("enabled"):
                    continue
                exec_enabled = True
                if not require_writes:
                    break
                file_metadata = remote_file_metadata_for_sid(candidate_sid)
                if file_metadata is None or (
                    not file_metadata.get("enabled", True)
                    or not file_metadata.get("write_enabled")
                ):
                    write_blocked = True

            return Response(
                message=(
                    "code_execution_remote: no connected CLI currently allows "
                    "shell-backed execution that may modify local files. Press F3 to switch "
                    "the CLI to Read&Write. `runtime=output` and `runtime=reset` remain "
                    "available for existing sessions."
                    if candidates and require_writes and exec_enabled and write_blocked
                    else "code_execution_remote: no connected CLI currently has "
                    "remote execution enabled. Connect the CLI and press F4 to switch exec on."
                    if candidates
                    else "code_execution_remote: no CLI client connected to Agent Zero. "
                    "Make sure the CLI is connected to this instance."
                ),
                break_loop=False,
            )

        try:
            session = int(self.args.get("session", 0) or 0)
        except (TypeError, ValueError):
            return Response(
                message="session must be an integer",
                break_loop=False,
            )

        op_id = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "op_id": op_id,
            "runtime": runtime,
            "session": session,
            "context_id": context_id,
        }
        if runtime != "reset" and coerce_bool(self.args.get("reset"), False):
            payload["reset"] = True

        if runtime in {"terminal", "python", "nodejs"}:
            code = self.args.get("code")
            if code is None or (not self._allow_running and not str(code).strip()):
                return Response(
                    message=f"code is required for runtime={runtime}",
                    break_loop=False,
                )
            payload["code"] = str(code)
            if self._allow_running:
                payload["allow_running"] = True

        elif runtime == "reset":
            reason = self.args.get("reason")
            if reason is not None:
                payload["reason"] = str(reason)

        exec_config = build_exec_config(agent=self.agent)
        if timeouts := self._timeout_group_for_runtime(runtime, exec_config):
            payload["timeouts"] = timeouts
        wait_timeout = self._wait_timeout_for_runtime(runtime, exec_config)

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        store_pending_exec_op(
            op_id,
            sid=sid,
            future=future,
            loop=loop,
            context_id=context_id,
        )

        try:
            await emit_connector_event(
                sid,
                EXEC_OP_EVENT,
                payload,
                handler_id=f"{self.__class__.__module__}.{self.__class__.__name__}",
                manager=get_shared_ws_manager(),
            )
            result = await asyncio.wait_for(future, timeout=wait_timeout)
        except WsPayloadTooLargeError as exc:
            clear_pending_exec_op(op_id)
            return Response(message=str(exc), break_loop=False)
        except ConnectionNotFoundError:
            clear_pending_exec_op(op_id)
            return Response(
                message=(
                    "code_execution_remote: the selected CLI client disconnected before "
                    "the execution request could be delivered"
                ),
                break_loop=False,
            )
        except asyncio.TimeoutError:
            clear_pending_exec_op(op_id)
            return Response(
                message=(
                    "code_execution_remote: timed out waiting for CLI to respond "
                    f"to runtime={runtime!r} in session {session} after "
                    f"{wait_timeout:g} seconds"
                ),
                break_loop=False,
            )
        except Exception as exc:
            clear_pending_exec_op(op_id)
            return Response(
                message=f"code_execution_remote: error sending exec_op: {exc}",
                break_loop=False,
            )
        finally:
            clear_pending_exec_op(op_id)

        return Response(
            message=self._extract_result(result, runtime, session),
            break_loop=False,
        )

    def _extract_result(self, result: Any, runtime: str, session: int) -> str:
        if not isinstance(result, dict):
            return f"Unexpected response format from CLI: {result!r}"

        ok = bool(result.get("ok"))
        data = result.get("result")
        error = result.get("error")

        if not ok:
            return (
                f"Error (runtime={runtime!r}, session={session}): "
                f"{error or 'Unknown error'}"
            )

        if not isinstance(data, dict):
            data = {}

        output = str(data.get("output") or data.get("text") or "").strip()
        message = str(data.get("message") or "").strip()
        running = bool(data.get("running"))

        parts: list[str] = []
        if message:
            parts.append(message)
        if output:
            parts.append(output)

        if not parts:
            state = "running" if running else "completed"
            parts.append(f"Session {session} {state}.")

        return "\n\n".join(parts)
