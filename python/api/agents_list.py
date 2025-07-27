from python.helpers.api import ApiHandler, Request, Response


class AgentsList(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Get list of all available agents in the current context"""
        ctxid = input.get("context", "")
        
        # Get the agent context
        context = self.get_context(ctxid)
        
        # Get all agents in context (including subordinates and peers)
        agents = context.get_agent_roster()
        
        return {
            "success": True,
            "agents": agents,
            "context_id": context.id,
            "active_agent": context.agent0.agent_name
        }