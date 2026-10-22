from helpers.api import ApiHandler, Request, Response


class Pause(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
            # input data
            paused = input.get("paused", False)
            ctxid = input.get("context", "")

            from helpers.durable.runtime import service
            owner = service()
            if owner and getattr(owner, "distributed", False):
                from helpers.durable.review import command_receipt
                from helpers.durable.store import _identity
                import uuid
                receipt = owner.pause_remote(_identity(ctxid, "context"), bool(paused),
                                             _identity(input.get("request_id") or uuid.uuid4().hex, "request id"))
                return {**command_receipt(receipt, ctxid), "pause": bool(paused),
                        "message": "Pause requested." if paused else "Resume requested."}

            # context instance - get or create
            context = self.use_context(ctxid)

            from helpers.durable.runtime import pause_context
            pause_context(context, paused)

            return {
                "message": "Agent paused." if paused else "Agent unpaused.",
                "pause": paused,
            }    
