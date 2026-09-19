from typing import Any

from helpers.tool import Tool, Response, coerce_bool

from helpers.print_style import PrintStyle
from plugins._a2a_chat.helpers.fasta2a_client import connect_to_agent, is_client_available


A2A_EMPTY_RESPONSE_ERROR = (
    "A2A chat failed: the remote task completed but no assistant text was found. "
    "Expected final.result.history to include an assistant message with a text "
    "part, or a text artifact/status message. Treat this as a failed remote "
    "response, not success."
)


def _session_key(agent_url: str) -> str:
    """Keep root and explicit /a2a URLs in the same conversation cache."""
    normalized = agent_url.rstrip("/")
    if normalized.endswith("/a2a"):
        return normalized[:-4].rstrip("/")
    return normalized


def _text_from_part(part: Any) -> str:
    if not isinstance(part, dict):
        return ""
    for key in ("text", "content"):
        value = part.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _text_from_message(message: Any) -> str:
    if isinstance(message, str):
        return message.strip()
    if not isinstance(message, dict):
        return ""

    parts = message.get("parts")
    if isinstance(parts, list):
        texts = [_text_from_part(part) for part in parts]
        text = "\n".join(text for text in texts if text)
        if text:
            return text

    for key in ("text", "content", "message", "output"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return ""


def _extract_latest_assistant_text(task_response: Any) -> str:
    if not isinstance(task_response, dict):
        return ""

    result = task_response.get("result", task_response)
    if not isinstance(result, dict):
        return ""

    history = result.get("history")
    if isinstance(history, list):
        for message in reversed(history):
            if isinstance(message, dict) and message.get("role") == "user":
                continue
            text = _text_from_message(message)
            if text:
                return text

    status = result.get("status")
    if isinstance(status, dict):
        text = _text_from_message(status.get("message"))
        if text:
            return text

    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in reversed(artifacts):
            text = _text_from_message(artifact)
            if text:
                return text

    return _text_from_message(result)


class A2AChatTool(Tool):
    """Communicate with another FastA2A-compatible agent."""

    async def execute(self, **kwargs):
        if not is_client_available():
            return Response(message="FastA2A client not available on this instance.", break_loop=False)

        agent_url: str | None = kwargs.get("agent_url")  # required
        user_message: str | None = kwargs.get("message")  # required
        attachments = kwargs.get("attachments", None)  # optional list[str]
        reset = coerce_bool(kwargs.get("reset", False), False)
        if not agent_url or not isinstance(agent_url, str):
            return Response(message="agent_url argument missing", break_loop=False)
        if not user_message or not isinstance(user_message, str):
            return Response(message="message argument missing", break_loop=False)

        # Retrieve or create session cache on the Agent instance
        sessions: dict[str, str] = self.agent.get_data("_a2a_sessions") or {}
        cache_key = _session_key(agent_url)

        # Handle reset flag: start fresh conversation
        if reset and cache_key in sessions:
            sessions.pop(cache_key, None)

        context_id = None if reset else sessions.get(cache_key)
        try:
            async with await connect_to_agent(agent_url) as conn:
                task_resp = await conn.send_message(user_message, attachments=attachments, context_id=context_id)
                task_id = task_resp.get("result", {}).get("id")  # type: ignore[index]
                if not task_id:
                    return Response(message="Remote agent failed to create task.", break_loop=False)
                final = await conn.wait_for_completion(task_id)
                new_context_id = final["result"].get("context_id")  # type: ignore[index]
                if isinstance(new_context_id, str):
                    # re-read to merge with concurrent calls instead of overwriting them
                    current: dict[str, str] = self.agent.get_data("_a2a_sessions") or sessions
                    current[cache_key] = new_context_id
                    self.agent.set_data("_a2a_sessions", current)
                assistant_text = _extract_latest_assistant_text(final)
                if not assistant_text:
                    return Response(
                        message=A2A_EMPTY_RESPONSE_ERROR,
                        break_loop=False,
                    )
                return Response(message=assistant_text, break_loop=False)
        except Exception as e:
            PrintStyle.error(f"A2A chat error: {e}")
            return Response(message=f"A2A chat error: {e}", break_loop=False)
