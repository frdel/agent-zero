from agent import AgentContext
from helpers.api import ApiHandler, Request, Response
from helpers.persist_chat import remove_chat, ensure_removal_supported, SharedDeletionHeld
from helpers.print_style import PrintStyle
import json


class ApiTerminateChat(ApiHandler):
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

            try:
                ensure_removal_supported(context_id)
            except SharedDeletionHeld as exc:
                return Response(json.dumps({"error": str(exc)}), status=409, mimetype="application/json")

            # Check if context exists
            context = AgentContext.use(context_id)
            if not context:
                return Response(
                    '{"error": "Chat context not found"}',
                    status=404,
                    mimetype="application/json"
                )

            # Delete the chat context
            AgentContext.remove(context.id)
            remove_chat(context.id)

            # Log the deletion
            PrintStyle(
                background_color="#E74C3C", font_color="white", bold=True, padding=True
            ).print(f"API Chat deleted: {context_id}")

            # Return success response
            return {
                "success": True,
                "message": "Chat deleted successfully",
                "context_id": context_id
            }

        except Exception as e:
            from helpers.durable.runtime import service
            owner = service()
            if owner and getattr(owner, "distributed", False):
                return Response(json.dumps({"error": "Shared chat removal failed safely. Chat records were retained for review."}), status=503, mimetype="application/json")
            PrintStyle.error(f"API terminate chat error: {str(e)}")
            return Response(
                json.dumps({"error": f"Internal server error: {str(e)}"}),
                status=500,
                mimetype="application/json"
            )
