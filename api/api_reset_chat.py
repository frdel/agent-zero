from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from helpers.print_style import PrintStyle
from helpers import persist_chat
import json


class ApiResetChat(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return False

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    @classmethod
    def requires_api_key(cls) -> bool:
        return True

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get context_id from input
            context_id = input.get("context_id")

            if not context_id:
                return Response(
                    '{"error": "context_id is required"}',
                    status=400,
                    mimetype="application/json"
                )

            from helpers.durable.runtime import service, control
            owner = service()
            if owner and getattr(owner, "distributed", False):
                from helpers.durable.store import _identity
                try:
                    request_id = _identity(input.get("request_id"), "request id")
                except ValueError:
                    return Response(json.dumps({"error": "Shared reset requires a stable request ID. No records were reset."}), status=409, mimetype="application/json")
                control(context_id, "reset", request_id=request_id)
                return {"success": True, "message": "Shared chat reset recorded. Workers will discard the previous generation.", "context_id": context_id}

            # Check if context exists
            context = AgentContext.use(context_id)
            if not context:
                return Response(
                    '{"error": "Chat context not found"}',
                    status=404,
                    mimetype="application/json"
                )

            # Reset the chat context (clears history but keeps context alive)
            context.reset()
            # Save the reset context to persist the changes
            persist_chat.save_tmp_chat(context)
            persist_chat.remove_msg_files(context_id)

            # Log the reset
            PrintStyle(
                background_color="#3498DB", font_color="white", bold=True, padding=True
            ).print(f"API Chat reset: {context_id}")

            # Return success response
            return {
                "success": True,
                "message": "Chat reset successfully",
                "context_id": context_id
            }

        except Exception as e:
            from helpers.durable.runtime import service
            owner = service()
            if owner and getattr(owner, "distributed", False):
                return Response(json.dumps({"error": "Shared reset failed safely. Retry only with the same request ID."}), status=503, mimetype="application/json")
            PrintStyle.error(f"API reset chat error: {str(e)}")
            return Response(
                json.dumps({"error": f"Internal server error: {str(e)}"}),
                status=500,
                mimetype="application/json"
            )
