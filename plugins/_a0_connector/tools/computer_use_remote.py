"""computer_use_remote tool — drive the CLI host machine through the connected frontend."""
from __future__ import annotations

import asyncio
from pathlib import Path
import uuid
from typing import Any

from helpers import chat_media, history, media_artifacts
from helpers.print_style import PrintStyle
from helpers.tool import Response, Tool, coerce_bool
from helpers.ws_manager import ConnectionNotFoundError, get_shared_ws_manager

from plugins._a0_connector.helpers.ws_runtime import (
    clear_pending_computer_use_op,
    computer_use_metadata_for_sid,
    emit_connector_event,
    select_computer_use_target_sid,
    store_pending_computer_use_op,
)


COMPUTER_USE_OP_TIMEOUT = 180.0
COMPUTER_USE_OP_EVENT = "connector_computer_use_op"
CAPTURE_TOKENS_ESTIMATE = 1500
MAX_CAPTURE_ARTIFACT_SIZE_BYTES = 25 * 1024 * 1024
CAPTURE_VERIFICATION_NOTE = (
    "Inspect the attached screenshot before the next action; do not claim or proceed "
    "from assumed state. If you cannot see the screenshot, stop and report that visual "
    "verification is unavailable."
)
REARM_REQUIRED_DEFAULT_MESSAGE = (
    "Computer use is configured, but the installed desktop-control backend is not armed."
)
_AUTO_CAPTURE_ACTIONS = {
    "start_session",
    "element_action",
    "ax_action",
    "uia_action",
    "move",
    "click",
    "scroll",
    "key",
    "type",
}
_SETTLE_DELAY_START_SESSION = 0.2
_SETTLE_DELAY_MOVE = 0.1
_SETTLE_DELAY_CLICK = 0.35
_SETTLE_DELAY_SCROLL = 0.35
_SETTLE_DELAY_KEY = 0.2
_SETTLE_DELAY_TYPE = 0.25
_SETTLE_DELAY_AX_ACTION = 0.25
_SETTLE_DELAY_UIA_ACTION = 0.25
_SETTLE_DELAY_GLOBAL_FOCUS = 0.45
_SETTLE_DELAY_PLAIN_ENTER = 0.3
_SETTLE_DELAY_SUBMIT = 0.45
_FRESH_CAPTURE_TIMEOUT = 0.45
_SUPPORTED_ACTIONS = {
    "start_session",
    "status",
    "capture",
    "list_windows",
    "get_window_state",
    "element_action",
    "ax_snapshot",
    "ax_action",
    "uia_snapshot",
    "uia_action",
    "move",
    "click",
    "scroll",
    "key",
    "type",
    "stop_session",
}


class ComputerUseRemote(Tool):
    def get_log_object(self):
        return self.agent.context.log.log(
            type="computer_use_remote",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    _HEADING_VERBS = {
        "start_session": "Starting session",
        "status": "Checking status",
        "capture": "Capturing screen",
        "list_windows": "Listing windows",
        "get_window_state": "Reading window state",
        "element_action": "Acting on element",
        "ax_snapshot": "Taking accessibility snapshot",
        "ax_action": "Acting via accessibility",
        "uia_snapshot": "Taking UIA snapshot",
        "uia_action": "Acting via UIA",
        "move": "Moving pointer",
        "click": "Clicking",
        "scroll": "Scrolling",
        "key": "Pressing keys",
        "type": "Typing",
        "stop_session": "Ending session",
    }

    def get_heading(self):
        action = str(self.args.get("action") or "").strip().lower()
        verb = self._HEADING_VERBS.get(action, "Working on desktop")
        text = f"Computer use: {verb}" if action else "Computer use"
        return f"icon://desktop_windows {text}"

    async def execute(self, **kwargs: Any) -> Response:
        self._latest_capture_content: list[dict[str, Any]] | None = None
        self._latest_capture_preview = ""
        action = str(self.args.get("action") or "").strip().lower()
        if action not in _SUPPORTED_ACTIONS:
            return Response(
                message=(
                    "action is required and must be one of: "
                    "start_session, status, capture, list_windows, get_window_state, "
                    "element_action, ax_snapshot, ax_action, "
                    "uia_snapshot, uia_action, "
                    "move, click, scroll, key, type, stop_session"
                ),
                break_loop=False,
            )

        context_id = self.agent.context.id
        sid = select_computer_use_target_sid(context_id)
        if not sid:
            return Response(
                message=(
                    "computer_use_remote: no connected CLI currently advertises enabled local "
                    "computer use. Enable it in the CLI and choose a trust mode first."
                ),
                break_loop=False,
            )

        metadata = computer_use_metadata_for_sid(sid) or {}
        if str(metadata.get("status", "") or "").strip().lower() == "rearm required":
            return Response(
                message=self._format_error(
                    {
                        "code": "COMPUTER_USE_REARM_REQUIRED",
                        "error": str(metadata.get("last_error", "") or "").strip()
                        or REARM_REQUIRED_DEFAULT_MESSAGE,
                    }
                ),
                break_loop=False,
            )

        try:
            payload = self._build_payload(op_id=str(uuid.uuid4()), context_id=context_id, action=action)
            result = await self._dispatch_payload(sid=sid, payload=payload)
            session_note = ""
            if (
                not result.get("ok")
                and result.get("code") == "COMPUTER_USE_SESSION_REQUIRED"
                and action not in {"start_session", "status", "stop_session"}
                and not payload.get("session_id")
            ):
                # This rejection happens before input dispatch. Start once on the
                # same host/context; never retry a permission or ambiguous failure.
                started = await self._dispatch_payload(
                    sid=sid,
                    payload={
                        "op_id": str(uuid.uuid4()),
                        "context_id": context_id,
                        "action": "start_session",
                    },
                )
                if not started.get("ok"):
                    return self._response(self._format_error(started))
                data = started.get("result")
                session_id = str(data.get("session_id") or "").strip() if isinstance(data, dict) else ""
                if not session_id:
                    raise ValueError("Host started computer use without returning a session_id")
                session_note = self._extract_result("start_session", started)
                result = await self._dispatch_payload(
                    sid=sid,
                    payload={**payload, "op_id": str(uuid.uuid4()), "session_id": session_id},
                )
            capture_note = await self._maybe_attach_latest_capture(
                action=action,
                sid=sid,
                context_id=context_id,
                result=result,
            )
            message = self._extract_result(action, result)
            if session_note:
                message = f"{session_note}\n{message}"
        except ValueError as exc:
            return Response(
                message=f"computer_use_remote: {exc}",
                break_loop=False,
            )
        except ConnectionNotFoundError:
            return Response(
                message=(
                    "computer_use_remote: the selected CLI disconnected before the request "
                    "could be delivered."
                ),
                break_loop=False,
            )
        except asyncio.TimeoutError:
            return Response(
                message=f"computer_use_remote: timed out waiting for action={action!r}",
                break_loop=False,
            )
        except Exception as exc:
            return Response(
                message=f"computer_use_remote: error sending action={action!r}: {exc}",
                break_loop=False,
            )

        if capture_note:
            message = f"{message} {capture_note}".strip()

        return self._response(message)

    async def after_execution(self, response: Response, **kwargs: Any) -> None:
        if not response.additional or not response.additional.get("raw_content"):
            await super().after_execution(response, **kwargs)
            return

        text = _sanitize_tool_text(response.message.strip())
        additional = dict(response.additional)
        raw_content = additional.pop("raw_content", None)
        preview = str(additional.pop("preview", "") or "").strip() or text
        token_estimate = self._coerce_token_estimate(additional.pop("_tokens", CAPTURE_TOKENS_ESTIMATE))
        log_id = str(getattr(getattr(self, "log", None), "id", "") or "")
        self.agent.hist_add_tool_result(
            self.name,
            text,
            id=log_id,
            **additional,
        )
        self.agent.hist_add_message(
            False,
            content=history.RawMessage(raw_content=raw_content, preview=preview),
            tokens=token_estimate,
        )

        agent_name = str(getattr(self.agent, "agent_name", "Agent Zero") or "Agent Zero")
        PrintStyle(
            font_color="#1B4F72",
            background_color="white",
            padding=True,
            bold=True,
        ).print(f"{agent_name}: Response from tool '{self.name}'")
        PrintStyle(font_color="#85C1E9").print(text)
        if getattr(self, "log", None) is not None:
            self.log.update(content=text)
        self._prune_prior_capture_history()

    async def _dispatch_payload(self, *, sid: str, payload: dict[str, Any]) -> dict[str, Any]:
        op_id = str(payload.get("op_id") or "").strip()
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        store_pending_computer_use_op(
            op_id,
            sid=sid,
            future=future,
            loop=loop,
            context_id=str(payload.get("context_id") or "").strip() or None,
        )

        try:
            await emit_connector_event(
                sid,
                COMPUTER_USE_OP_EVENT,
                payload,
                handler_id=f"{self.__class__.__module__}.{self.__class__.__name__}",
                manager=get_shared_ws_manager(),
            )
            result = await asyncio.wait_for(future, timeout=COMPUTER_USE_OP_TIMEOUT)
        finally:
            clear_pending_computer_use_op(op_id)

        if isinstance(result, dict):
            return result
        raise RuntimeError(f"Unexpected response format from CLI: {result!r}")

    async def _maybe_attach_latest_capture(
        self,
        *,
        action: str,
        sid: str,
        context_id: str,
        result: dict[str, Any],
    ) -> str:
        if action not in _AUTO_CAPTURE_ACTIONS or not bool(result.get("ok")):
            return ""

        data = result.get("result")
        result_data = dict(data) if isinstance(data, dict) else {}
        if action == "element_action":
            actual_dispatch = str(result_data.get("actual_dispatch") or "").strip().lower()
            if actual_dispatch in {"background", "none"}:
                return ""

        session_id = str(result_data.get("session_id") or self.args.get("session_id") or "").strip()
        if not session_id:
            return ""

        settle_seconds = self._auto_capture_settle_seconds(action)
        if settle_seconds > 0:
            await asyncio.sleep(settle_seconds)

        capture_payload = {
            "op_id": str(uuid.uuid4()),
            "context_id": context_id,
            "action": "capture",
            "session_id": session_id,
            "fresh": True,
            "fresh_timeout_seconds": _FRESH_CAPTURE_TIMEOUT,
        }
        capture_result = await self._dispatch_payload(sid=sid, payload=capture_payload)
        if not bool(capture_result.get("ok")):
            return f"Automatic screen refresh failed: {self._format_error(capture_result)}"

        capture_data = capture_result.get("result")
        if not isinstance(capture_data, dict):
            return "Automatic screen refresh failed: missing capture payload."

        try:
            summary = self._record_capture(capture_data)
        except Exception as exc:
            return f"Automatic screen refresh failed: {exc}"
        return f"Latest screen attached: {summary} {CAPTURE_VERIFICATION_NOTE}"

    def _auto_capture_settle_seconds(self, action: str) -> float:
        if action == "start_session":
            return _SETTLE_DELAY_START_SESSION
        if action == "move":
            return _SETTLE_DELAY_MOVE
        if action == "click":
            return _SETTLE_DELAY_CLICK
        if action == "scroll":
            return _SETTLE_DELAY_SCROLL
        if action == "ax_action":
            return _SETTLE_DELAY_AX_ACTION
        if action == "uia_action":
            return _SETTLE_DELAY_UIA_ACTION
        if action == "type" and coerce_bool(self.args.get("submit"), False):
            return _SETTLE_DELAY_SUBMIT
        if action == "type":
            return _SETTLE_DELAY_TYPE
        if action != "key":
            return 0.0

        keyset = {key.lower() for key in self._requested_keys()}
        if "super" in keyset or ("alt" in keyset and "tab" in keyset):
            return _SETTLE_DELAY_GLOBAL_FOCUS
        if keyset == {"enter"}:
            return _SETTLE_DELAY_PLAIN_ENTER
        return _SETTLE_DELAY_KEY

    def _requested_keys(self) -> list[str]:
        keys_value = self.args.get("keys")
        if isinstance(keys_value, (list, tuple)):
            return [str(item).strip() for item in keys_value if str(item).strip()]
        raw = str(keys_value or self.args.get("key", "") or "").strip()
        if not raw:
            return []
        return [part.strip() for part in raw.split("+") if part.strip()]

    def _build_payload(self, *, op_id: str, context_id: str, action: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "op_id": op_id,
            "context_id": context_id,
            "action": action,
        }
        session_id = str(self.args.get("session_id", "") or "").strip()
        if session_id:
            payload["session_id"] = session_id

        if action == "move":
            payload["x"] = self.args.get("x")
            payload["y"] = self.args.get("y")
        elif action == "click":
            if "x" in self.args:
                payload["x"] = self.args.get("x")
            if "y" in self.args:
                payload["y"] = self.args.get("y")
            payload["button"] = self.args.get("button", "left")
            payload["count"] = self._coerce_int(self.args.get("count", 1), name="count")
        elif action == "scroll":
            payload["dx"] = self._coerce_int(self.args.get("dx", self.args.get("delta_x", 0)), name="dx")
            payload["dy"] = self._coerce_int(self.args.get("dy", self.args.get("delta_y", 0)), name="dy")
        elif action == "key":
            if "keys" in self.args:
                payload["keys"] = self.args.get("keys")
            elif "key" in self.args:
                payload["key"] = self.args.get("key")
        elif action == "type":
            payload["text"] = self.args.get("text", "")
            if "window_id" in self.args:
                payload["window_id"] = self.args.get("window_id")
            if coerce_bool(self.args.get("submit"), False):
                payload["submit"] = True
        elif action == "list_windows":
            for key in ("include_hidden", "include_offscreen", "max_windows"):
                if key in self.args:
                    payload[key] = self.args.get(key)
        elif action == "get_window_state":
            for key in ("pid", "window_id", "mode", "max_depth", "max_nodes"):
                if key in self.args:
                    payload[key] = self.args.get(key)
        elif action == "element_action":
            for key in (
                "pid",
                "window_id",
                "element_index",
                "path",
                "operation",
                "name",
                "dispatch",
                "value",
                "text",
                "submit",
            ):
                if key in self.args:
                    payload[key] = self.args.get(key)
            target = self.args.get("target")
            if isinstance(target, dict):
                payload["target"] = dict(target)
            if "selector" in self.args:
                payload["selector"] = self.args.get("selector")
        elif action == "ax_snapshot":
            for key in ("pid", "window_id"):
                if key in self.args:
                    payload[key] = self.args.get(key)
            if "max_depth" in self.args:
                payload["max_depth"] = self._coerce_int(self.args.get("max_depth"), name="max_depth")
            if "max_nodes" in self.args:
                payload["max_nodes"] = self._coerce_int(self.args.get("max_nodes"), name="max_nodes")
        elif action == "ax_action":
            target = self.args.get("target")
            if isinstance(target, dict):
                payload["target"] = dict(target)
            if "path" in self.args:
                payload["path"] = self.args.get("path")
            operation = self.args.get("operation", self.args.get("ax_action", self.args.get("name")))
            if operation is not None:
                payload["operation"] = operation
            if "value" in self.args:
                payload["value"] = self.args.get("value")
            if "text" in self.args:
                payload["text"] = self.args.get("text", "")
        elif action == "uia_snapshot":
            if "max_depth" in self.args:
                payload["max_depth"] = self._coerce_int(self.args.get("max_depth"), name="max_depth")
            if "max_nodes" in self.args:
                payload["max_nodes"] = self._coerce_int(self.args.get("max_nodes"), name="max_nodes")
        elif action == "uia_action":
            target = self.args.get("target")
            normalized_target: dict[str, Any] = {}
            if isinstance(target, dict):
                normalized_target.update(target)
            if "selector" in self.args:
                normalized_target["selector"] = str(self.args.get("selector") or "").strip()
            if normalized_target:
                payload["target"] = normalized_target
            if "path" in self.args:
                payload["path"] = self.args.get("path")
            operation = self.args.get("operation", self.args.get("uia_action", self.args.get("name")))
            if operation is not None:
                payload["operation"] = operation
            if "value" in self.args:
                payload["value"] = self.args.get("value")
            if "text" in self.args:
                payload["text"] = self.args.get("text", "")
            if coerce_bool(self.args.get("submit"), False):
                payload["submit"] = True

        return payload

    def _extract_result(self, action: str, result: Any) -> str:
        if not isinstance(result, dict):
            return f"Unexpected response format from CLI: {result!r}"

        ok = bool(result.get("ok"))
        data = result.get("result")

        if not ok:
            return self._format_error(result)

        if not isinstance(data, dict):
            data = {}

        if action == "capture":
            summary = self._record_capture(data)
            return f"Current screen attached: {summary} {CAPTURE_VERIFICATION_NOTE}"
        if action == "list_windows":
            return self._format_window_list(data)
        if action == "get_window_state":
            return self._format_window_state(data)
        if action == "element_action":
            return self._format_element_action(data)
        if action == "ax_snapshot":
            return self._format_ax_snapshot(data)
        if action == "ax_action":
            target = data.get("target") if isinstance(data.get("target"), dict) else {}
            operation = str(data.get("operation") or "?")
            path = target.get("path", "?")
            return f"Performed AX {operation} on {self._ax_target_label(target)} path={path}."
        if action == "uia_snapshot":
            return self._format_uia_snapshot(data)
        if action == "uia_action":
            target = data.get("target") if isinstance(data.get("target"), dict) else {}
            operation = str(data.get("operation") or "?")
            path = target.get("path", "?")
            return f"Performed Windows UIA {operation} on {self._uia_target_label(target)} path={path}."
        if action == "status":
            return self._format_status(data)
        if action == "start_session":
            message = (
                f"Computer-use session started: session_id={data.get('session_id', '?')} "
                f"size={data.get('width', '?')}x{data.get('height', '?')}"
            )
            backend_details = self._format_backend_details(data)
            if backend_details:
                message = f"{message}, {backend_details}"
            skill_hint = self._backend_skill_hint(data)
            if skill_hint:
                return f"{message}.{skill_hint}"
            return message
        if action == "stop_session":
            return "Computer-use session stopped."
        if action == "move":
            return f"Pointer moved to x={data.get('x')} y={data.get('y')}."
        if action == "click":
            return f"Clicked {data.get('button', 'left')} button {data.get('count', 1)} time(s)."
        if action == "scroll":
            return f"Scrolled dx={data.get('dx', 0)} dy={data.get('dy', 0)}."
        if action == "key":
            keys = data.get("keys") or []
            return f"Sent keys: {keys!r}."
        if action == "type":
            text = str(data.get("text", "") or "")
            window_id = str(data.get("window_id") or "").strip()
            submitted = " and submitted" if data.get("submitted") else ""
            if data.get("focus_verified") and window_id:
                return (
                    f"Sent {len(text)} keyboard character(s){submitted} to verified active "
                    f"window_id={window_id}."
                )
            return (
                f"Sent {len(text)} global keyboard character(s){submitted}; destination was not verified. "
                "Inspect the attached screen before claiming where the text landed."
            )
        return str(data)

    def _format_error(self, result: dict[str, Any]) -> str:
        error = str(result.get("error") or "Unknown error")
        code = str(result.get("code") or "")
        if code in {"COMPUTER_USE_REARM_REQUIRED", "COMPUTER_USE_APPROVAL_REQUIRED"} or error in {
            "COMPUTER_USE_REARM_REQUIRED",
            "COMPUTER_USE_APPROVAL_REQUIRED",
        }:
            detail = error if error and error != code else REARM_REQUIRED_DEFAULT_MESSAGE
            return (
                "COMPUTER_USE_REARM_REQUIRED: "
                f"{detail} Stop using computer_use_remote for now; ask the user to re-arm "
                "Computer Use with /computer-use on in the A0 Launcher chat when using "
                "Launcher Host access, or in A0 CLI, and approve the platform permission "
                "prompt if shown. "
                "Do not retry or use screenshot fallbacks."
            )
        if code:
            return f"{code}: {error}"
        return error

    def _format_backend_details(self, data: dict[str, Any]) -> str:
        backend_id = str(data.get("backend_id", "") or "").strip()
        backend_family = str(data.get("backend_family", "") or "").strip()
        features = self._backend_features(data)
        parts: list[str] = []
        if backend_id:
            backend_text = backend_id
            if backend_family:
                backend_text = f"{backend_text}/{backend_family}"
            parts.append(f"backend={backend_text}")
        contract_version = data.get("contract_version")
        if not contract_version and isinstance(data.get("capabilities"), dict):
            contract_version = data["capabilities"].get("contract_version")
        if contract_version:
            parts.append(f"contract=v{contract_version}")
        if features:
            parts.append(f"features={', '.join(features)}")
        return ", ".join(parts)

    def _backend_features(self, data: dict[str, Any]) -> list[str]:
        raw_features = data.get("features") or []
        if not isinstance(raw_features, (list, tuple, set)):
            return []
        features: list[str] = []
        for feature in raw_features:
            text = str(feature or "").strip()
            if text:
                features.append(text)
        return features

    def _backend_skill_hint(self, data: dict[str, Any]) -> str:
        backend_id = str(data.get("backend_id", "") or "").strip().lower()
        backend_family = str(data.get("backend_family", "") or "").strip().lower()
        features = {feature.lower() for feature in self._backend_features(data)}
        has_linux_atspi = bool(
            features
            & {
                "atspi-tree-snapshot",
                "atspi-structural-targeting",
                "atspi-element-action",
                "atspi-set-value",
            }
        )
        if backend_id in {"wayland", "x11", "linux"} or backend_family == "linux" or has_linux_atspi:
            return (
                " Load skill `host-computer-use-linux` before using Linux AT-SPI "
                "structural actions."
            )
        has_macos_ax = bool(
            features
            & {
                "accessibility-tree-snapshot",
                "accessibility-structural-targeting",
            }
        )
        if backend_id == "macos" or backend_family == "macos" or has_macos_ax:
            return (
                " Load skill `host-computer-use-macos` before using macOS AX "
                "structural actions."
            )
        has_windows_uia = bool(
            features
            & {
                "uia-tree-snapshot",
                "uia-structural-targeting",
                "uia-element-action",
                "uia-window-management",
            }
        )
        if backend_id == "windows" or backend_family == "windows" or has_windows_uia:
            return (
                " Load skill `host-computer-use-windows` before using Windows UIA "
                "structural actions and window-management operations."
            )
        return ""

    def _format_status(self, data: dict[str, Any]) -> str:
        status = str(data.get("status", "unknown") or "unknown")
        trust_mode = str(data.get("trust_mode", "") or "")
        active_contexts = data.get("active_contexts") or []
        active_text = ", ".join(str(item) for item in active_contexts) if active_contexts else "none"
        rearm_guidance = ""
        if status == "rearm required":
            detail = str(data.get("last_error") or "").strip()
            if detail and detail != "COMPUTER_USE_REARM_REQUIRED":
                rearm_guidance = (
                    f" {detail} Stop using computer_use_remote until the user re-arms it."
                )
            else:
                rearm_guidance = (
                    " Computer Use is configured but the installed desktop-control backend "
                    "is not armed. "
                    "Stop using computer_use_remote until the user re-arms it."
                )
        backend_details = self._format_backend_details(data)
        if backend_details:
            return (
                f"Computer use status={status}, trust_mode={trust_mode or 'unknown'}, "
                f"{backend_details}, active_contexts={active_text}."
                f"{self._backend_skill_hint(data)}{rearm_guidance}"
            )
        return (
            f"Computer use status={status}, trust_mode={trust_mode or 'unknown'}, "
            f"active_contexts={active_text}.{rearm_guidance}"
        )

    def _format_window_list(self, data: dict[str, Any]) -> str:
        windows = data.get("windows") if isinstance(data.get("windows"), list) else []
        count = data.get("count", len(windows))
        if not windows:
            return (
                "No native windows were returned by the computer-use backend. "
                "Use capture or backend-specific snapshots as a fallback."
            )
        lines = [
            (
                f"Computer-use native window list: {count} window(s). "
                "Prefer get_window_state(pid/window_id) before element_action."
            )
        ]
        for item in windows[:40]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or "").strip()
            app_name = str(item.get("app_name") or item.get("app") or "").strip()
            pid = item.get("pid")
            window_id = str(item.get("window_id") or "").strip()
            role = str(item.get("role") or "window").strip()
            parts = [f"- window_id={window_id or '?'}"]
            if pid is not None:
                parts.append(f"pid={pid}")
            if app_name:
                parts.append(f"app={app_name!r}")
            if title:
                parts.append(f"title={title!r}")
            parts.append(f"role={role}")
            frame = item.get("frame")
            if isinstance(frame, dict):
                parts.append(
                    f"frame=({frame.get('x', '?')},{frame.get('y', '?')} "
                    f"{frame.get('width', '?')}x{frame.get('height', '?')})"
                )
            flags: list[str] = []
            for flag in ("is_on_screen", "on_current_space", "active", "focused", "visible"):
                if flag in item:
                    flags.append(f"{flag}={item.get(flag)}")
            if flags:
                parts.append(" ".join(flags))
            lines.append(" ".join(parts))
        if len(windows) > 40:
            lines.append("... window list truncated; request a narrower app/window target.")
        return "\n".join(lines)

    def _format_window_state(self, data: dict[str, Any]) -> str:
        tree = data.get("tree") if isinstance(data.get("tree"), dict) else {}
        window = data.get("window") if isinstance(data.get("window"), dict) else {}
        app = data.get("app") if isinstance(data.get("app"), dict) else {}
        title = str(window.get("title") or app.get("name") or "target window").strip()
        window_id = str(window.get("window_id") or data.get("window_id") or "").strip()
        node_count = data.get("node_count", "?")
        truncated = " truncated" if data.get("truncated") else ""
        mode = str(data.get("mode") or "auto").strip()
        state_parts = [
            f"{flag}={window.get(flag)}"
            for flag in ("active", "focused")
            if flag in window
        ]
        state_text = f" {' '.join(state_parts)}." if state_parts else ""
        return (
            f"Window state for {title!r}"
            f"{f' window_id={window_id}' if window_id else ''}: "
            f"{node_count} element(s){truncated}, mode={mode}.{state_text} "
            "Use element_action with element_index; dispatch defaults to background."
            f"{self._structural_tree_outline(tree)}"
        )

    def _format_element_action(self, data: dict[str, Any]) -> str:
        target = data.get("target") if isinstance(data.get("target"), dict) else {}
        operation = str(data.get("operation") or "?")
        requested_dispatch = str(data.get("requested_dispatch") or data.get("dispatch") or "background")
        actual_dispatch = str(data.get("actual_dispatch") or data.get("dispatch") or requested_dispatch)
        fallback = bool(data.get("foreground_fallback_used") or data.get("fallback_used"))
        index = target.get("element_index", data.get("element_index", "?"))
        label = (
            self._uia_target_label(target)
            if target.get("selector") or target.get("automation_id")
            else self._ax_target_label(target)
        )
        if data.get("background_unavailable"):
            reason = str(data.get("reason") or "background dispatch was unavailable")
            return (
                f"Background element action unavailable for element_index={index}: {reason}. "
                "Use dispatch='auto' or dispatch='foreground' only if foreground control is acceptable."
            )
        dispatch_text = (
            f"requested_dispatch={requested_dispatch}, actual_dispatch={actual_dispatch}"
            f"{', foreground_fallback_used=true' if fallback else ''}"
        )
        verification = ", focus_verified=true" if data.get("focus_verified") else ""
        return f"Performed {operation} on element_index={index} {label}; {dispatch_text}{verification}."

    def _format_ax_snapshot(self, data: dict[str, Any]) -> str:
        app = data.get("app") if isinstance(data.get("app"), dict) else {}
        tree = data.get("tree") if isinstance(data.get("tree"), dict) else {}
        app_name = str(app.get("name") or app.get("bundle_id") or "frontmost app")
        node_count = data.get("node_count", "?")
        truncated = " truncated" if data.get("truncated") else ""
        root_label = self._ax_target_label(tree)
        window_id = str(data.get("window_id") or "").strip()
        scope = f" scoped to window_id={window_id}" if data.get("scoped") and window_id else ""
        return (
            f"AX snapshot for {app_name}{scope}: {node_count} node(s){truncated}. "
            f"Root {root_label}. Use path or semantic target fields with ax_action."
            f"{self._structural_tree_outline(tree)}"
        )

    def _format_uia_snapshot(self, data: dict[str, Any]) -> str:
        app = data.get("app") if isinstance(data.get("app"), dict) else {}
        tree = data.get("tree") if isinstance(data.get("tree"), dict) else {}
        app_name = str(app.get("name") or "Windows desktop")
        node_count = data.get("node_count", "?")
        truncated = " truncated" if data.get("truncated") else ""
        root_label = self._uia_target_label(tree)
        return (
            f"Windows UIA snapshot for {app_name}: {node_count} node(s){truncated}. "
            f"Root {root_label}. Prefer node actions with uia_action; use "
            f"focus_window/minimize/restore/maximize for windows, and reserve click "
            f"for a last resort."
            f"{self._structural_tree_outline(tree)}"
        )

    def _structural_tree_outline(self, tree: dict[str, Any], *, max_lines: int = 80) -> str:
        if not tree:
            return ""
        lines: list[str] = ["", "", "Nodes:"]
        truncated = False

        def visit(node: dict[str, Any], depth: int) -> None:
            nonlocal truncated
            if len(lines) - 3 >= max_lines:
                truncated = True
                return
            lines.append(self._structural_node_line(node, depth=depth))
            children = node.get("children")
            if not isinstance(children, list):
                return
            for child in children:
                if len(lines) - 3 >= max_lines:
                    truncated = True
                    break
                if isinstance(child, dict):
                    visit(child, depth + 1)

        visit(tree, 0)
        if truncated:
            lines.append("... outline truncated; request a narrower max_depth/max_nodes snapshot if needed.")
        return "\n".join(lines)

    def _structural_node_line(self, node: dict[str, Any], *, depth: int) -> str:
        indent = "  " * max(0, depth)
        role = str(node.get("role") or "element")
        path = node.get("path", [])
        element_index = node.get("element_index")
        prefix = f"{indent}-"
        if element_index is not None:
            prefix = f"{prefix} element_index={element_index}"
        parts = [f"{prefix} path={path} role={role}"]
        for key in ("title", "name", "description", "automation_id", "class_name", "selector"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{key}={value.strip()[:120]!r}")
                break
        frame = node.get("frame")
        if isinstance(frame, dict):
            x = frame.get("x", "?")
            y = frame.get("y", "?")
            width = frame.get("width", "?")
            height = frame.get("height", "?")
            parts.append(f"frame=({x},{y} {width}x{height})")
        actions = node.get("actions")
        if isinstance(actions, list) and actions:
            names = [
                str(item.get("name") or "").strip()
                for item in actions
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            if names:
                parts.append(f"actions={','.join(names[:6])}")
        states = node.get("states")
        if isinstance(states, list) and states:
            values = [str(item).strip() for item in states if str(item).strip()]
            if values:
                parts.append(f"states={','.join(values[:8])}")
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(f"text={text.strip()[:120]!r}")
        return " ".join(parts)

    def _ax_target_label(self, target: dict[str, Any]) -> str:
        role = str(target.get("role") or "element")
        title = str(target.get("title") or target.get("description") or target.get("identifier") or "").strip()
        if title:
            return f"{role} {title!r}"
        return role

    def _uia_target_label(self, target: dict[str, Any]) -> str:
        role = str(target.get("role") or "element")
        title = str(
            target.get("title")
            or target.get("name")
            or target.get("automation_id")
            or target.get("class_name")
            or ""
        ).strip()
        if title:
            return f"{role} {title!r}"
        return role

    def _record_capture(self, data: dict[str, Any]) -> str:
        display_ref, resolved_capture_id = self._resolve_capture_ref(data)
        width = data.get("width", "?")
        height = data.get("height", "?")
        capture_id = str(data.get("capture_id") or resolved_capture_id or "?").strip()
        coordinate_space = str(data.get("coordinate_space") or "normalized_global_screen").strip()
        summary = (
            f"Computer-use capture id={capture_id} {width}x{height}, "
            f"coordinates={coordinate_space} [0,1]."
        )
        if data.get("fresh") is True:
            if "fresh_after_satisfied" in data:
                fresh_state = "confirmed" if data.get("fresh_after_satisfied") is not False else "not confirmed"
                summary = f"{summary} Fresh frame {fresh_state}."
            else:
                summary = f"{summary} Fresh capture requested."
        self._latest_capture_content = [
            {"type": "text", "text": summary},
            {"type": "image_url", "image_url": {"url": display_ref}},
        ]
        self._latest_capture_preview = summary
        return summary

    def _response(self, message: str) -> Response:
        capture_content = self._latest_capture_content
        if not capture_content:
            return Response(message=message, break_loop=False)

        raw_content = [dict(item) for item in capture_content]
        if raw_content and raw_content[0].get("type") == "text":
            raw_content[0] = {"type": "text", "text": message}
        else:
            raw_content.insert(0, {"type": "text", "text": message})

        return Response(
            message=message,
            break_loop=False,
            additional={
                "raw_content": raw_content,
                "preview": self._latest_capture_preview or message,
                "_tokens": CAPTURE_TOKENS_ESTIMATE,
            },
        )

    @staticmethod
    def _coerce_token_estimate(value: object) -> int:
        try:
            estimate = int(value or 0)
        except (TypeError, ValueError):
            estimate = 0
        return estimate if estimate > 0 else CAPTURE_TOKENS_ESTIMATE

    def _prune_prior_capture_history(self) -> None:
        history_obj = getattr(self.agent, "history", None)
        if history_obj is None:
            return

        capture_messages = self._collect_capture_messages(history_obj)
        if len(capture_messages) <= 1:
            return

        latest = capture_messages[-1]
        for message in capture_messages[:-1]:
            if message is latest:
                continue
            preview = self._capture_preview_from_message(message)
            if not preview:
                continue
            message.content = f"{preview} [image reference superseded]"
            if hasattr(message, "summary"):
                message.summary = ""
            if hasattr(message, "calculate_tokens"):
                message.tokens = message.calculate_tokens()

    def _resolve_capture_ref(self, data: dict[str, Any]) -> tuple[str, str]:
        path_error: FileNotFoundError | None = None
        try:
            image_path, display_path = self._resolve_capture_path(data)
        except FileNotFoundError as exc:
            path_error = exc
        else:
            saved = chat_media.save_image_file(
                context_id=self.agent.context.id,
                path=image_path,
                category="screenshots",
                source="computer-use",
                preferred_name=Path(display_path).name or image_path.name,
                max_bytes=MAX_CAPTURE_ARTIFACT_SIZE_BYTES,
            )
            return saved.a0_path, Path(saved.path).stem

        artifact = data.get("artifact")
        if isinstance(artifact, dict) and str(artifact.get("encoding", "")).strip().lower() == "base64":
            encoded = str(artifact.get("data") or "")
            if encoded:
                estimated_size = media_artifacts.estimated_base64_decoded_size(encoded)
                if estimated_size > MAX_CAPTURE_ARTIFACT_SIZE_BYTES:
                    raise RuntimeError(
                        "Computer-use capture artifact is too large to attach safely "
                        f"({estimated_size} bytes, limit {MAX_CAPTURE_ARTIFACT_SIZE_BYTES} bytes)."
                    )
                mime = str(artifact.get("mime") or "image/png").strip()
                if not mime.startswith("image/"):
                    mime = "image/png"
                filename = media_artifacts.safe_filename(
                    str(artifact.get("filename") or "computer-use-capture.png"),
                    default=f"computer-use-{uuid.uuid4().hex}.png",
                    default_extension=".png",
                )
                saved = chat_media.save_image_base64(
                    context_id=self.agent.context.id,
                    data=encoded,
                    mime_type=mime,
                    category="screenshots",
                    source="computer-use",
                    preferred_name=filename,
                    max_bytes=MAX_CAPTURE_ARTIFACT_SIZE_BYTES,
                )
                return saved.a0_path, Path(saved.path).stem

        if path_error is not None:
            raise path_error
        raise FileNotFoundError("Capture artifact was not found in the tool response.")

    def _collect_capture_messages(self, history_obj: Any) -> list[Any]:
        messages: list[Any] = []

        def collect_topic(topic: Any) -> None:
            topic_messages = getattr(topic, "messages", None)
            if isinstance(topic_messages, list):
                for message in topic_messages:
                    if self._capture_preview_from_message(message):
                        messages.append(message)

        bulks = getattr(history_obj, "bulks", None)
        if isinstance(bulks, list):
            for bulk in bulks:
                self._collect_capture_messages_from_record(bulk, messages)

        topics = getattr(history_obj, "topics", None)
        if isinstance(topics, list):
            for topic in topics:
                collect_topic(topic)

        current = getattr(history_obj, "current", None)
        if current is not None:
            collect_topic(current)

        return messages

    def _collect_capture_messages_from_record(self, record: Any, messages: list[Any]) -> None:
        topic_messages = getattr(record, "messages", None)
        if isinstance(topic_messages, list):
            for message in topic_messages:
                if self._capture_preview_from_message(message):
                    messages.append(message)
            return

        nested_records = getattr(record, "records", None)
        if isinstance(nested_records, list):
            for nested in nested_records:
                self._collect_capture_messages_from_record(nested, messages)

    def _capture_preview_from_message(self, message: Any) -> str:
        content = getattr(message, "content", None)
        if not isinstance(content, dict):
            return ""
        raw_content = content.get("raw_content")
        preview = content.get("preview")
        if raw_content is None or not isinstance(preview, str):
            return ""
        if preview.startswith("Computer-use capture "):
            return preview
        return ""

    def _resolve_capture_path(self, data: dict[str, Any]) -> tuple[Path, str]:
        candidates = [
            str(data.get("path", "") or "").strip(),
            str(data.get("capture_path", "") or "").strip(),
            str(data.get("container_path", "") or "").strip(),
            str(data.get("host_path", "") or "").strip(),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate), candidate
        raise FileNotFoundError(
            f"Capture artifact was not found in any advertised path: {candidates!r}"
        )

    def _coerce_int(self, value: object, *, name: str) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be an integer") from exc


def _sanitize_tool_text(value: str) -> str:
    try:
        from helpers.strings import sanitize_string
    except Exception:
        return value
    return sanitize_string(value)
