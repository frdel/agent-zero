from helpers.errors import RepairableException
from helpers.tool import Tool, Response


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
        # Streaming normally owns the response bubble; only successful calls need a fallback.
        pass

    async def after_execution(self, response, **kwargs):
        if not self.loop_data:
            return
        params = self.loop_data.params_temporary
        if "log_item_response" not in params:
            generating = params.get("log_item_generating")
            params["log_item_response"] = self.agent.context.log.log(
                type="response",
                heading=f"icon://chat {self.agent.agent_name}: Responding",
                content=response.message,
                id=generating.id if generating else "",
            )
        params["log_item_response"].update(finished=True)
