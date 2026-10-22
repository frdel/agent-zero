from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from helpers import files
from helpers.print_style import PrintStyle
from helpers.tool import Response, Tool
from plugins._browser.helpers.config import activate_browser_model
from plugins._browser.helpers.selector import get_tool_runtime


HISTORY_SCREENSHOT_QUALITY = 62
HISTORY_SCREENSHOT_ACTION_DENYLIST = {
    "close", "close_all", "list", "state", "content", "detail", "evaluate",
}


async def get_runtime(context_id: str, create: bool = True, agent: Any | None = None):
    if agent is not None:
        return await get_tool_runtime(agent)
    from plugins._browser.helpers.runtime import get_runtime as get_container_runtime

    return await get_container_runtime(context_id, create=create)


class Browser(Tool):
    async def execute(
        self,
        action: str = "",
        browser_id: int | str | None = None,
        url: str = "",
        ref: int | str | None = None,
        target_ref: int | str | None = None,
        text: str = "",
        selector: str = "",
        selectors: list[str] | None = None,
        script: str = "",
        modifiers: list[str] | str | None = None,
        keys: list[str] | None = None,
        key: str = "",
        include_content: bool = False,
        focus_popup: bool | None = None,
        event_type: str = "",
        x: float = 0.0,
        y: float = 0.0,
        to_x: float = 0.0,
        to_y: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        target_offset_x: float = 0.0,
        target_offset_y: float = 0.0,
        delta_x: float = 0.0,
        delta_y: float = 0.0,
        button: str = "left",
        quality: int = 80,
        full_page: bool = False,
        path: str = "",
        paths: list[str] | None = None,
        value: str = "",
        values: list[str] | None = None,
        checked: bool | None = None,
        width: int = 0,
        height: int = 0,
        calls: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Response:
        method_action = str(self.method or "").strip().lower().replace("-", "_")
        requested_action = str(action or "").strip().lower().replace("-", "_")
        clipboard_action = ""
        if method_action == "clipboard" and requested_action in {"copy", "cut", "paste"}:
            clipboard_action = requested_action
            action = "clipboard"
        else:
            action = str(action or self.method or "state").strip().lower().replace("-", "_")
        try:
            activate_browser_model(self.agent)
        except Exception as exc:
            PrintStyle.warning(f"Browser model preset could not be activated: {exc}")
        try:
            if action == "evaluate" and (not isinstance(script, str) or not script.strip()):
                return Response(
                    message="Browser evaluate failed: evaluate requires a non-empty 'script' string",
                    break_loop=False,
                )
            turn = getattr(self.agent.context, "_durable_turn", None)
            if turn and turn.agent is self.agent:
                from helpers.durable import sessions
                if not hasattr(self, "_durable_session_manager"):
                    await sessions.prepare(self, {"action": action, "ref": ref, "calls": calls})
                runtime = self._durable_browser_runtime
            else:
                runtime = await get_runtime(self.agent.context.id, agent=self.agent)
        except Exception as exc:
            return Response(message=f"Browser runtime unavailable: {exc}", break_loop=False)

        if isinstance(modifiers, str):
            modifiers = [modifiers] if modifiers else None
        elif isinstance(modifiers, list) and not modifiers:
            modifiers = None
        keys = self._normalize_keys(keys)

        try:
            if action == "open":
                result = await runtime.call("open", url or "")
            elif action == "screenshot":
                result = await runtime.call(
                    "screenshot_file",
                    browser_id,
                    quality=quality,
                    full_page=full_page,
                    path=path,
                )
            elif action == "list":
                result = await runtime.call("list", include_content=bool(include_content))
            elif action == "state":
                result = await runtime.call("state", browser_id)
            elif action in {"set_active", "setactive", "activate", "focus"}:
                result = await runtime.call("set_active", browser_id)
            elif action == "navigate":
                result = await runtime.call("navigate", browser_id, url)
            elif action == "back":
                result = await runtime.call("back", browser_id)
            elif action == "forward":
                result = await runtime.call("forward", browser_id)
            elif action == "reload":
                result = await runtime.call("reload", browser_id)
            elif action == "content":
                payload = self._selector_payload(selector, selectors)
                result = await runtime.call("content", browser_id, payload)
            elif action == "detail":
                result = await runtime.call(
                    "detail",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                )
            elif action == "click":
                resolved_ref = await self._resolve_ref(
                    runtime,
                    browser_id,
                    ref,
                    selector,
                    action,
                    required=not self._has_coordinates(x, y),
                )
                if resolved_ref is None and self._has_coordinates(x, y):
                    result = await runtime.call(
                        "mouse", browser_id, "click", x, y,
                        button=button or "left", modifiers=modifiers,
                    )
                elif modifiers:
                    result = await runtime.call(
                        "click", browser_id, resolved_ref,
                        modifiers=modifiers, focus_popup=focus_popup,
                    )
                else:
                    result = await runtime.call("click", browser_id, resolved_ref)
            elif action == "type":
                resolved_ref = await self._resolve_ref(
                    runtime,
                    browser_id,
                    ref,
                    selector,
                    action,
                    required=False,
                )
                if resolved_ref is None:
                    result = await runtime.call("keyboard", browser_id, key="", text=text)
                else:
                    result = await runtime.call("type", browser_id, resolved_ref, text)
            elif action == "submit":
                result = await runtime.call(
                    "submit",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                )
            elif action in {"type_submit", "typesubmit"}:
                result = await runtime.call(
                    "type_submit",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                    text,
                )
            elif action == "scroll":
                result = await runtime.call(
                    "scroll",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                )
            elif action == "evaluate":
                result = await runtime.call("evaluate", browser_id, script)
            elif action in {"key_chord", "keychord"}:
                if not keys:
                    raise ValueError("key_chord requires non-empty 'keys' list")
                result = await runtime.call("key_chord", browser_id, keys)
            elif action == "hover":
                result = await runtime.call(
                    "hover",
                    browser_id,
                    ref=ref,
                    x=x,
                    y=y,
                    offset_x=offset_x,
                    offset_y=offset_y,
                )
            elif action == "double_click":
                result = await runtime.call(
                    "double_click",
                    browser_id,
                    ref=ref,
                    x=x,
                    y=y,
                    button=button or "left",
                    modifiers=modifiers,
                    offset_x=offset_x,
                    offset_y=offset_y,
                )
            elif action == "right_click":
                result = await runtime.call(
                    "right_click",
                    browser_id,
                    ref=ref,
                    x=x,
                    y=y,
                    modifiers=modifiers,
                    offset_x=offset_x,
                    offset_y=offset_y,
                )
            elif action == "drag":
                result = await runtime.call(
                    "drag",
                    browser_id,
                    ref=ref,
                    target_ref=target_ref,
                    x=x,
                    y=y,
                    to_x=to_x,
                    to_y=to_y,
                    offset_x=offset_x,
                    offset_y=offset_y,
                    target_offset_x=target_offset_x,
                    target_offset_y=target_offset_y,
                )
            elif action == "wheel":
                result = await runtime.call(
                    "wheel",
                    browser_id,
                    x,
                    y,
                    delta_x,
                    delta_y,
                )
            elif action == "keyboard":
                result = await runtime.call(
                    "keyboard",
                    browser_id,
                    key=key,
                    text=text,
                )
            elif action == "clipboard":
                normalized_clipboard_action = clipboard_action or str(
                    kwargs.get("clipboard_action")
                    or kwargs.get("operation")
                    or event_type
                    or ""
                ).strip().lower()
                result = await runtime.call(
                    "clipboard",
                    browser_id,
                    action=normalized_clipboard_action,
                    text=text,
                )
            elif action in {"copy", "cut", "paste"}:
                result = await runtime.call(
                    "clipboard",
                    browser_id,
                    action=action,
                    text=text,
                )
            elif action == "set_viewport":
                result = await runtime.call("set_viewport", browser_id, width, height)
            elif action == "select_option":
                result = await runtime.call(
                    "select_option",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                    value=value,
                    values=values,
                )
            elif action == "set_checked":
                result = await runtime.call(
                    "set_checked",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                    checked=True if checked is None else bool(checked),
                )
            elif action == "upload_file":
                result = await runtime.call(
                    "upload_file",
                    browser_id,
                    await self._resolve_ref(runtime, browser_id, ref, selector, action),
                    path=path,
                    paths=paths,
                )
            elif action == "mouse":
                result = await runtime.call(
                    "mouse", browser_id, event_type or "click", x, y,
                    button=button or "left", modifiers=modifiers,
                )
            elif action == "multi":
                if not calls:
                    raise ValueError("multi requires non-empty 'calls' list")
                result = await runtime.call("multi", list(calls))
            elif action == "close":
                result = await runtime.call("close_browser", browser_id)
            elif action == "close_all":
                result = await runtime.call("close_all_browsers")
            else:
                return Response(
                    message=f"Unknown browser action: {action}",
                    break_loop=False,
                )
            await self._record_history_screenshot(runtime, action, result, browser_id, calls=calls)
        except Exception as exc:
            return Response(message=f"Browser {action} failed: {exc}", break_loop=False)

        return Response(message=self._format_result(action, result), break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="tool",
            heading=f"icon://captive_portal {self.agent.agent_name}: Using browser",
            content="",
            kvps=self.args,
            _tool_name=self.name,
        )

    @staticmethod
    def _require_ref(ref: int | str | None) -> int | str:
        if ref is None or str(ref).strip() == "":
            raise ValueError("ref is required for this browser action")
        return ref

    @staticmethod
    def _has_ref(ref: int | str | None) -> bool:
        return ref is not None and str(ref).strip() != ""

    @staticmethod
    def _has_coordinates(x: float, y: float) -> bool:
        return bool(float(x or 0) or float(y or 0))

    @classmethod
    async def _resolve_ref(
        cls,
        runtime: Any,
        browser_id: int | str | None,
        ref: int | str | None,
        selector: str = "",
        action: str = "action",
        *,
        required: bool = True,
    ) -> int | str | None:
        if cls._has_ref(ref):
            return ref

        selector = str(selector or "").strip()
        if selector:
            content = await runtime.call("content", browser_id, {"selector": selector})
            resolved = cls._first_ref_from_content(content, selector)
            if resolved is not None:
                return resolved
            raise ValueError(
                f"{action} could not resolve selector {selector!r} to a browser ref"
            )

        if required:
            return cls._require_ref(ref)
        return None

    @staticmethod
    def _first_ref_from_content(content: Any, selector: str = "") -> str | None:
        if isinstance(content, dict):
            values: list[Any] = []
            if selector and selector in content:
                values.append(content.get(selector))
            values.extend(value for key, value in content.items() if key != selector)
            text = "\n".join(str(value or "") for value in values)
        else:
            text = str(content or "")
        match = re.search(r"\[[^\]\n]*?\b(\d+)\]", text)
        return match.group(1) if match else None

    @staticmethod
    def _normalize_keys(keys: list[str] | str | None) -> list[str]:
        if keys is None:
            return []
        if isinstance(keys, str):
            raw = re.split(r"\s*\+\s*|\s*,\s*", keys.strip())
        elif isinstance(keys, list):
            raw = keys
        else:
            raw = [str(keys)]
        aliases = {
            "cmd": "Meta",
            "command": "Meta",
            "control": "Control",
            "ctrl": "Control",
            "escape": "Escape",
            "esc": "Escape",
            "meta": "Meta",
            "option": "Alt",
            "return": "Enter",
            "space": "Space",
        }
        normalized: list[str] = []
        for key in raw:
            value = str(key or "").strip()
            if not value:
                continue
            normalized.append(aliases.get(value.lower(), value.upper() if len(value) == 1 and value.isalpha() else value))
        return normalized

    @staticmethod
    def _selector_payload(selector: str = "", selectors: list[str] | None = None) -> dict | None:
        if selectors:
            return {"selectors": selectors}
        if selector:
            return {"selector": selector}
        return None

    async def _record_history_screenshot(
        self,
        runtime: Any,
        action: str,
        result: Any,
        requested_browser_id: int | str | None = None,
        *,
        calls: list[dict[str, Any]] | None = None,
    ) -> None:
        if not getattr(self, "log", None):
            return
        if action in HISTORY_SCREENSHOT_ACTION_DENYLIST:
            return
        if action == "multi" and calls and all(
            str(call.get("action") or "").strip().lower().replace("-", "_")
            in HISTORY_SCREENSHOT_ACTION_DENYLIST
            for call in calls
        ):
            return

        screenshot = result if action == "screenshot" and isinstance(result, dict) else None
        if not self._screenshot_has_reference(screenshot):
            target_browser_id = self._browser_id_from_result(result) or requested_browser_id
            try:
                screenshot = await runtime.call(
                    "screenshot_file",
                    target_browser_id,
                    quality=HISTORY_SCREENSHOT_QUALITY,
                    full_page=False,
                    path="",
                )
            except Exception as exc:
                PrintStyle.debug(
                    "Browser history screenshot capture failed:",
                    f"browser_id={target_browser_id}",
                    f"quality={HISTORY_SCREENSHOT_QUALITY}",
                    f"error={exc}",
                )
                return

        if not self._screenshot_has_reference(screenshot):
            return

        a0_path = str(screenshot.get("a0_path") or "").strip()
        local_path = str(screenshot.get("path") or (files.fix_dev_path(a0_path) if a0_path else ""))
        state = screenshot.get("state") if isinstance(screenshot.get("state"), dict) else {}
        chat_context_id = self._agent_context_id()
        browser_context_id = str(screenshot.get("context_id") or state.get("context_id") or "").strip()
        snapshot = {
            "mime": screenshot.get("mime") or "image/jpeg",
            "browser_id": screenshot.get("browser_id") or state.get("id") or requested_browser_id,
            "context_id": chat_context_id or browser_context_id,
            "browser_context_id": browser_context_id,
        }
        update_payload: dict[str, Any] = {"browser_snapshot": snapshot}
        if local_path:
            uri = f"img://{local_path}&t={time.time()}"
            snapshot.update(
                {
                    "uri": uri,
                    "path": local_path,
                    "a0_path": screenshot.get("a0_path") or files.normalize_a0_path(local_path),
                    "ephemeral": False,
                }
            )
            update_payload["Screenshot"] = uri
        else:
            ephemeral_ref = self._screenshot_ephemeral_ref(screenshot)
            snapshot.update(
                {
                    "ephemeral": bool(ephemeral_ref),
                    "ephemeral_ref": ephemeral_ref,
                }
            )
        self.log.update(**update_payload)

    def _history_screenshot_path(self, action: str) -> str:
        if not getattr(self, "agent", None) or not getattr(self.agent, "context", None):
            return ""
        context_id = self._agent_context_id()
        if not context_id:
            return ""
        from helpers import persist_chat

        token = str(getattr(getattr(self, "log", None), "id", "") or uuid.uuid4())
        safe_action = files.safe_file_name(str(action or "browser"))
        safe_token = files.safe_file_name(token)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        return str(
            Path(persist_chat.get_chat_folder_path(context_id))
            / "browser"
            / "screenshots"
            / f"{timestamp}-{safe_action}-{safe_token}.jpg"
        )

    @staticmethod
    def _browser_id_from_result(result: Any) -> Any:
        if not isinstance(result, dict):
            return None
        browsers = result.get("browsers") if isinstance(result.get("browsers"), list) else []
        last_interacted_id = result.get("last_interacted_browser_id")
        listed_browser = None
        if last_interacted_id is not None:
            listed_browser = next(
                (
                    browser
                    for browser in browsers
                    if isinstance(browser, dict) and str(browser.get("id")) == str(last_interacted_id)
                ),
                None,
            )
        if listed_browser is None and browsers:
            listed_browser = next((browser for browser in browsers if isinstance(browser, dict)), None)
        state = result.get("state") if isinstance(result.get("state"), dict) else {}
        return (
            result.get("id")
            or result.get("browser_id")
            or state.get("id")
            or last_interacted_id
            or (listed_browser or {}).get("id")
        )

    @staticmethod
    def _screenshot_has_path(screenshot: Any) -> bool:
        return isinstance(screenshot, dict) and bool(screenshot.get("path") or screenshot.get("a0_path"))

    @classmethod
    def _screenshot_has_reference(cls, screenshot: Any) -> bool:
        return cls._screenshot_has_path(screenshot) or bool(cls._screenshot_ephemeral_ref(screenshot))

    @staticmethod
    def _screenshot_ephemeral_ref(screenshot: Any) -> str:
        if not isinstance(screenshot, dict):
            return ""
        ref = str(screenshot.get("ephemeral_ref") or "").strip()
        if ref:
            return ref
        vision_load = screenshot.get("vision_load")
        if isinstance(vision_load, dict):
            tool_args = vision_load.get("tool_args")
            if isinstance(tool_args, dict):
                paths = tool_args.get("paths")
                if isinstance(paths, list) and paths:
                    first = str(paths[0] or "").strip()
                    if first.startswith("a0-ephemeral-image://"):
                        return first
        return ""

    def _agent_context_id(self) -> str:
        return str(getattr(getattr(self.agent, "context", None), "id", "") or "").strip()

    @staticmethod
    def _format_result(action: str, result: Any) -> str:
        if action == "content" and isinstance(result, dict):
            if set(result.keys()) == {"document"}:
                return str(result.get("document") or "")
            return json.dumps(result, ensure_ascii=False, separators=(",", ":"))

        return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)
