from agent import AgentContext
from helpers.defer import DeferredTask
from api.message import Message


class MessageAsync(Message):
    async def respond(self, task: DeferredTask, context: AgentContext):
        if task is None:
            return {
                "message": "Model not configured.",
                "model_not_configured": True,
                "context": context.id,
            }
        return {
            "message": "Message received.",
            "context": context.id,
        }
