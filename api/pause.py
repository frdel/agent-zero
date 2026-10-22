from helpers.api import ApiHandler, Request, Response


class Pause(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            paused = input.get("paused", False)
            ctxid = input.get("context", "")

            # context instance - get or create
            context = self.use_context(ctxid)

            from helpers.durable.runtime import pause_context
            pause_context(context, paused)

            return {
                "message": "Agent paused." if paused else "Agent unpaused.",
                "pause": paused,
            }    
