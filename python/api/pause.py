from python.helpers.api import ApiHandler, Request, Response


class Pause(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            paused = input.get("paused", False)
            ctxid = input.get("context", "")

            # context instance - get or create
            context = self.get_context(ctxid)

            context.paused = paused

            return {
                "message": "Agent paused." if paused else "Agent unpaused.",
                "pause": paused,
            }    
