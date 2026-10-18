"""Shared local and remote editor log presentation."""

import uuid


def create_editor_log(tool, *, remote: bool = False):
    action = str(tool.args.get("action") or "")
    path = str(tool.args.get("path") or "")
    verb = {"read": "Reading", "write": "Writing", "patch": "Patching"}.get(action)
    suffix = " (remote)" if remote else ""
    heading = (
        f"icon://construction {verb} {path}{suffix}".strip()
        if verb and path
        else f"icon://construction Using tool '{tool.name}'{suffix}"
    )
    return tool.agent.context.log.log(
        type="text_editor",
        heading=heading,
        content="",
        kvps=tool.args,
        _tool_name=tool.name,
        id=str(uuid.uuid4()),
    )
