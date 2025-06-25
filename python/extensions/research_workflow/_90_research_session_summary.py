from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.extensions.research_workflow._10_research_session_start import (
    get_research_session, update_research_session, is_research_session_active
)
from python.extensions.research_workflow._20_research_tool_tracking import get_research_tool_usage
from python.extensions.research_workflow._30_research_artifact_tracking import get_research_artifacts
from python.helpers import memory
from datetime import datetime, timedelta
import json

class ResearchSessionSummary(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Generate research session summaries and handle session lifecycle"""
        
        session_data = get_research_session(self.agent)
        
        if not session_data.get("active", False):
            return
        
        # Check if session should be automatically summarized
        last_activity = session_data.get("last_activity")
        if last_activity:
            last_activity_time = datetime.fromisoformat(last_activity)
            time_since_activity = datetime.now() - last_activity_time
            
            # Auto-summarize after 30 minutes of inactivity
            if time_since_activity > timedelta(minutes=30):
                await self._generate_session_summary()
                return
        
        # Check for explicit session end commands
        user_message = (loop_data.user_message.output_text() if loop_data.user_message else "").lower()
        end_indicators = [
            "end research session",
            "finish research", 
            "research session complete",
            "summarize research",
            "research summary"
        ]
        
        should_end_session = any(indicator in user_message for indicator in end_indicators)
        
        if should_end_session:
            await self._generate_session_summary()
    
    async def _generate_session_summary(self):
        """Generate comprehensive research session summary"""
        session_data = get_research_session(self.agent)
        tool_usage = get_research_tool_usage(self.agent)
        artifacts = get_research_artifacts(self.agent)
        
        # Calculate session duration
        start_time = session_data.get("start_time")
        duration = "Unknown"
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
            duration_td = datetime.now() - start_dt
            hours = duration_td.seconds // 3600
            minutes = (duration_td.seconds % 3600) // 60
            duration = f"{hours}h {minutes}m"
        
        # Generate summary
        summary = {
            "session_id": session_data.get("session_id", "unknown"),
            "start_time": start_time,
            "end_time": datetime.now().isoformat(),
            "duration": duration,
            "tools_used": list(tool_usage.get("tools_used", [])),
            "total_tools_used": tool_usage.get("total_tools", 0),
            "artifacts_created": artifacts.get("artifacts", []),
            "total_artifacts": artifacts.get("total_count", 0),
            "artifacts_by_type": artifacts.get("by_type", {}),
            "topics_explored": list(session_data.get("topics_explored", set())),
            "key_findings": "Research session completed with artifact generation and tool usage",
            "next_steps": "Review generated artifacts and continue research as needed"
        }
        
        # Save summary to memory
        try:
            db = await memory.Memory.get(self.agent)
            await db.save_research_session(summary)
        except Exception as e:
            # Handle memory save error gracefully
            self.agent.context.log.log(
                type="error",
                heading="Failed to save research session summary",
                content=f"Error: {str(e)}"
            )
        
        # Log session summary
        self.agent.context.log.log(
            type="research",
            heading=f"Research Session Summary: {summary['session_id']}",
            content=f"""
Research Session Completed:
- Duration: {duration}
- Tools Used: {summary['total_tools_used']}
- Artifacts Created: {summary['total_artifacts']}
- Topics Explored: {len(summary['topics_explored'])}

Artifacts by Type:
{json.dumps(summary['artifacts_by_type'], indent=2)}

Session saved to memory for future reference.
            """.strip()
        )
        
        # Mark session as inactive
        update_research_session(self.agent, {
            "active": False,
            "end_time": datetime.now().isoformat(),
            "summary_generated": True
        })


def get_session_summary(agent: Agent) -> dict:
    """Get current session summary data"""
    session_data = get_research_session(agent)
    tool_usage = get_research_tool_usage(agent)
    artifacts = get_research_artifacts(agent)
    
    return {
        "session_active": session_data.get("active", False),
        "session_id": session_data.get("session_id", "None"),
        "start_time": session_data.get("start_time", "Unknown"),
        "last_activity": session_data.get("last_activity", "Unknown"),
        "tools_used": tool_usage.get("total_tools", 0),
        "artifacts_created": artifacts.get("total_count", 0),
        "topics_explored": len(session_data.get("topics_explored", set()))
    }

async def force_session_summary(agent: Agent):
    """Force generation of session summary"""
    extension = ResearchSessionSummary(agent)
    await extension._generate_session_summary()