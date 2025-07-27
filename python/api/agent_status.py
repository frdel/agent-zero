from python.helpers.api import ApiHandler, Request, Response


class AgentStatus(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Get status of a specific agent"""
        ctxid = input.get("context", "")
        agent_id = input.get("agent_id", "")
        
        if not agent_id:
            return Response(
                response="agent_id is required",
                status=400,
                mimetype="text/plain"
            )
        
        # Get the agent context
        context = self.get_context(ctxid)
        
        # Check if it's the main agent
        if agent_id == context.agent0.agent_name:
            return {
                "success": True,
                "agent_id": agent_id,
                "type": "main",
                "status": "active" if not context.paused else "paused",
                "streaming": context.streaming_agent is not None,
                "capabilities": ["all_tools", "memory", "reasoning"]
            }
        
        # check subordinates
        if hasattr(context, 'subordinate_manager') and context.subordinate_manager:
            subordinate = context.subordinate_manager.get_subordinate_by_agent_id(agent_id)
            if subordinate:
                return {
                    "success": True,
                    "agent_id": agent_id,
                    "type": "subordinate",
                    "role": subordinate.role,
                    "status": subordinate.status,
                    "url": subordinate.url,
                    "port": subordinate.port,
                    "capabilities": subordinate.capabilities,
                    "spawned_at": subordinate.spawned_at.isoformat(),
                    "last_contact": subordinate.last_contact.isoformat()
                }
        
        # Check A2A peers
        if hasattr(context, 'a2a_peers') and agent_id in context.a2a_peers:
            peer = context.a2a_peers[agent_id]
            return {
                "success": True,
                "agent_id": agent_id,
                "type": "peer",
                "status": peer.get("status", "unknown"),
                "url": peer.get("url", ""), 
                "capabilities": peer.get("capabilities", []),
                "last_contact": peer.get("last_contact", "")
            }
        
        return Response(
            response=f"Agent not found: {agent_id}",
            status=404,
            mimetype="text/plain"
        )