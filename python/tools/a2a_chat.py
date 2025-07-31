from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

try:
    from python.helpers.fasta2a_client import connect_to_agent, is_client_available  # type: ignore
except ImportError:  # pragma: no cover – client helper missing
    is_client_available = lambda: False  # type: ignore


class A2AChatTool(Tool):
    """Communicate with another FastA2A-compatible agent."""

    async def execute(self, **kwargs):
        if not is_client_available():
            return Response(message="FastA2A client not available on this instance.", break_loop=False)

        agent_url: str | None = kwargs.get("agent_url")  # required
        user_message: str | None = kwargs.get("message")  # required
        attachments = kwargs.get("attachments", None)  # optional list[str]
        reset = bool(kwargs.get("reset", False))
        if not agent_url or not isinstance(agent_url, str):
            return Response(message="agent_url argument missing", break_loop=False)
        if not user_message or not isinstance(user_message, str):
            return Response(message="message argument missing", break_loop=False)

        # Retrieve or create session cache on the Agent instance
        sessions: dict[str, str] = self.agent.get_data("_a2a_sessions") or {}

        # Handle reset flag – start fresh conversation
        if reset and agent_url in sessions:
            sessions.pop(agent_url, None)

        context_id = None if reset else sessions.get(agent_url)
        try:
            async with await connect_to_agent(agent_url) as conn:
                task_resp = await conn.send_message(user_message, attachments=attachments, context_id=context_id)
                task_id = task_resp.get("result", {}).get("id")  # type: ignore[index]
                if not task_id:
                    return Response(message="Remote agent failed to create task.", break_loop=False)
                final = await conn.wait_for_completion(task_id)
                new_context_id = final["result"].get("context_id")  # type: ignore[index]
                if isinstance(new_context_id, str):
                    sessions[agent_url] = new_context_id
                    # persist back to agent data
                    self.agent.set_data("_a2a_sessions", sessions)
                # Extract latest assistant text
                history = final["result"].get("history", [])
                assistant_text = ""
                if history:
                    last_parts = history[-1].get("parts", [])
                    assistant_text = "\n".join(
                        p.get("text", "") for p in last_parts if p.get("kind") == "text"
                    )
                return Response(message=assistant_text or "(no response)", break_loop=False)
        except Exception as e:
            PrintStyle.error(f"A2A chat error: {e}")
            return Response(message=f"A2A chat error: {e}", break_loop=False)
