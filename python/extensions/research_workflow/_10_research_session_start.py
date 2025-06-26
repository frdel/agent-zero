from python.helpers.extension import Extension
from agent import Agent, LoopData
from python.helpers import memory
from datetime import datetime
import json

DATA_NAME_RESEARCH_SESSION = "research_session"
DATA_NAME_RESEARCH_TOPIC = "research_topic"
DATA_NAME_RESEARCH_START_TIME = "research_start_time"
DATA_NAME_RESEARCH_ARTIFACTS = "research_artifacts"

class ResearchSessionStart(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Initialize or continue research session tracking"""
        
        # Check if this is a research-focused interaction
        user_message = loop_data.user_message.output_text() if loop_data.user_message else ""
        
        # Keywords that indicate research activity
        research_keywords = [
            "research", "study", "analyze", "investigate", "explore", 
            "literature", "paper", "experiment", "hypothesis", "methodology",
            "sakana_research", "sakana_experiment", "sakana_paper", "sakana_peer"
        ]
        
        is_research_activity = any(keyword in user_message.lower() for keyword in research_keywords)
        
        # Get or initialize research session data
        session_data = self.agent.get_data(DATA_NAME_RESEARCH_SESSION) or {}
        
        if is_research_activity:
            # Start new session or continue existing one
            if not session_data.get("active", False):
                # Start new research session
                session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                session_data = {
                    "active": True,
                    "session_id": session_id,
                    "start_time": datetime.now().isoformat(),
                    "artifacts_created": 0,
                    "tools_used": set(),
                    "topics_explored": set(),
                    "last_activity": datetime.now().isoformat()
                }
                
                self.agent.set_data(DATA_NAME_RESEARCH_SESSION, session_data)
                self.agent.set_data(DATA_NAME_RESEARCH_START_TIME, datetime.now().isoformat())
                self.agent.set_data(DATA_NAME_RESEARCH_ARTIFACTS, [])
                
                # Log session start
                self.agent.context.log.log(
                    type="info",
                    heading=f"Research Session Started: {session_id}",
                    content=f"New research session initiated at {session_data['start_time']}"
                )
            else:
                # Update existing session
                session_data["last_activity"] = datetime.now().isoformat()
                self.agent.set_data(DATA_NAME_RESEARCH_SESSION, session_data)
        
        # Store topic if mentioned
        if is_research_activity and user_message:
            # Simple topic extraction (could be enhanced with NLP)
            topic_indicators = ["research", "study", "analyze", "investigate"]
            for indicator in topic_indicators:
                if indicator in user_message.lower():
                    # Extract potential topic (simplified)
                    words = user_message.split()
                    try:
                        indicator_index = [w.lower() for w in words].index(indicator)
                        if indicator_index + 1 < len(words):
                            potential_topic = " ".join(words[indicator_index:indicator_index+5])
                            session_data.setdefault("topics_explored", set()).add(potential_topic)
                            self.agent.set_data(DATA_NAME_RESEARCH_SESSION, session_data)
                    except ValueError:
                        pass


def get_research_session(agent: Agent) -> dict:
    """Get current research session data"""
    return agent.get_data(DATA_NAME_RESEARCH_SESSION) or {}

def is_research_session_active(agent: Agent) -> bool:
    """Check if research session is currently active"""
    session_data = get_research_session(agent)
    return session_data.get("active", False)

def get_research_topic(agent: Agent) -> str:
    """Get current research topic"""
    return agent.get_data(DATA_NAME_RESEARCH_TOPIC) or ""

def update_research_session(agent: Agent, updates: dict):
    """Update research session data"""
    session_data = get_research_session(agent)
    session_data.update(updates)
    agent.set_data(DATA_NAME_RESEARCH_SESSION, session_data)