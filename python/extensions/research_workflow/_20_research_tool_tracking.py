from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.extensions.research_workflow._10_research_session_start import (
    get_research_session, update_research_session, is_research_session_active
)
from datetime import datetime

class ResearchToolTracking(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Track usage of research tools during active research sessions"""
        
        if not is_research_session_active(self.agent):
            return
        
        # Get tool usage from loop data - these would need to be passed via kwargs or stored elsewhere
        # For now, we'll skip tool tracking as iteration_data doesn't exist
        tool_name = kwargs.get("tool_name", "")
        tool_method = kwargs.get("tool_method", "")
        
        # Check if this is a SakanaAI research tool
        sakana_tools = [
            "sakana_research",
            "sakana_experiment_designer", 
            "sakana_paper_writer",
            "sakana_peer_reviewer"
        ]
        
        is_research_tool = any(tool in tool_name for tool in sakana_tools)
        
        if is_research_tool:
            session_data = get_research_session(self.agent)
            
            # Track tool usage
            tools_used = session_data.get("tools_used", set())
            if isinstance(tools_used, list):
                tools_used = set(tools_used)
            
            tool_identifier = f"{tool_name}:{tool_method}" if tool_method else tool_name
            tools_used.add(tool_identifier)
            
            # Update session data
            updates = {
                "tools_used": tools_used,
                "last_tool_used": tool_identifier,
                "last_tool_time": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
            
            update_research_session(self.agent, updates)
            
            # Log tool usage
            self.agent.context.log.log(
                type="info",
                heading=f"Research Tool Used: {tool_identifier}",
                content=f"Tool used at {updates['last_tool_time']} during research session {session_data.get('session_id', 'unknown')}"
            )


def get_research_tool_usage(agent: Agent) -> dict:
    """Get research tool usage statistics"""
    session_data = get_research_session(agent)
    tools_used = session_data.get("tools_used", set())
    
    if isinstance(tools_used, set):
        tools_used = list(tools_used)
    
    return {
        "tools_used": tools_used,
        "total_tools": len(tools_used),
        "last_tool": session_data.get("last_tool_used", "None"),
        "last_tool_time": session_data.get("last_tool_time", "Unknown")
    }