from helpers import chat_media, parallel_tools
from helpers.errors import RepairableException
from helpers.tool import Tool, Response


def _response_context_id(agent) -> str:
    context = getattr(agent, "context", None)
    get_data = getattr(context, "get_data", None)
    parent_id = get_data(parallel_tools.PARALLEL_WORKER_PARENT_CONTEXT_KEY) if get_data else ""
    return str(parent_id or getattr(context, "id", "") or "").strip()


class ResponseTool(Tool):

    async def execute(self, **kwargs):
        for key in ("text", "message"):
            message = self.args.get(key)
            if isinstance(message, str) and message.strip():
                return Response(message=message, break_loop=True)
        raise RepairableException(
            "response tool requires a non-empty top-level text or message string argument"
        )

    async def before_execution(self, **kwargs):
        # self.log = self.agent.context.log.log(type="response", heading=f"{self.agent.agent_name}: Responding", content=self.args.get("text", ""))
        # don't log here anymore, we have the live_response extension now
        pass

    async def after_execution(self, response, **kwargs):
        # do not add anything to the history or output

        if self.loop_data and "log_item_response" in self.loop_data.params_temporary:
            log = self.loop_data.params_temporary["log_item_response"]
            content = log.content or (
                response.message if isinstance(response.message, str) else ""
            )
            snapshotted = chat_media.snapshot_image_refs(
                content,
                context_id=_response_context_id(self.agent),
            )
            updates = {"finished": True}
            if snapshotted != log.content:
                updates["content"] = snapshotted
            log.update(**updates)
