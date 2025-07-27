from python.helpers.api import ApiHandler, Request, Response


class AgentSwitch(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Switch the active agent in a context"""
        ctxid = input.get("context", "")
        target_agent_id = input.get("target_agent_id", "")
        
        if not target_agent_id:
            return Response(
                response="target_agent_id is required",
                status=400,
                mimetype="text/plain"
            )
        
        # Get the agent context
        context = self.get_context(ctxid)
        
        # Check if target agent exists in context
        agents = context.get_agent_roster()
        target_agent = None
        
        for agent in agents:
            if agent["id"] == target_agent_id:
                target_agent = agent
                break
        
        if not target_agent:
            return Response(
                response=f"Agent not found: {target_agent_id}",
                status=404,
                mimetype="text/plain"
            )
        
        # For now, we'll store the active agent selection in context
        # This could be expanded to actually switch the primary agent
        if not hasattr(context, 'active_agent_id'):
            context.active_agent_id = context.agent0.agent_name
        
        context.active_agent_id = target_agent_id
        
        return {
            "success": True,
            "active_agent": target_agent_id,
            "agent_info": target_agent,
            "context_id": context.id
        }