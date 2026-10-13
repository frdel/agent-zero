from __future__ import annotations

from typing import Any

from plugins._chat_naming.helpers import naming


async def run(payload: dict[str, Any]) -> dict[str, Any]:
    invocation = payload.get("invocation") or {}
    raw_name = str(invocation.get("raw_arguments") or "").strip()
    agent = (payload.get("context") or {}).get("agent")

    if not agent:
        return _toast("Open or create a chat context first.", level="error")
    if not raw_name:
        return _toast("Usage: /rename <new name|auto>", level="error")

    if raw_name.casefold() == "auto":
        raw_name = await naming.generate_name(agent)
        agent.context.set_data(naming.MANUAL_NAME_KEY, False)
    else:
        raw_name = naming.normalize_manual_name(raw_name)
        agent.context.set_data(naming.MANUAL_NAME_KEY, True)

    name = naming.save_context_name(agent, raw_name)
    return _toast(f'Chat renamed to "{name}".')


def _toast(message: str, *, level: str = "success") -> dict[str, Any]:
    return {
        "text": "",
        "effects": [{"type": "toast", "message": message, "level": level}],
    }
