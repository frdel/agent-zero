"""
Collaborative State Management for Agent Zero
Inspired by CopilotKit's state machine approach but designed for multi-user scenarios
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from threading import Lock


class StateType(Enum):
    """Types of collaborative states"""
    AGENT_PROGRESS = "agent_progress"
    RESEARCH_SESSION = "research_session"
    TOOL_EXECUTION = "tool_execution"
    USER_INTERACTION = "user_interaction"
    SHARED_CONTEXT = "shared_context"


class ProgressStatus(Enum):
    """Progress status for streaming indicators"""
    IDLE = "idle"
    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    WAITING_INPUT = "waiting_input"
    COMPLETING = "completing"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class ProgressState:
    """State for streaming progress indicators"""
    id: str
    user_id: str
    agent_id: str
    status: ProgressStatus
    current_step: str
    total_steps: int
    completed_steps: int
    progress_percentage: float
    message: str
    details: Dict[str, Any]
    timestamp: float
    estimated_completion: Optional[float] = None


@dataclass
class ResearchState:
    """State for collaborative research sessions"""
    id: str
    session_name: str
    participants: List[str]  # user_ids
    research_topic: str
    current_phase: str
    findings: List[Dict[str, Any]]
    shared_documents: List[str]
    active_agents: List[str]
    collaboration_mode: str  # "parallel", "sequential", "interactive"
    timestamp: float


@dataclass
class SharedContext:
    """Shared context between users and agents"""
    id: str
    context_type: str
    owner_id: str
    shared_with: List[str]
    data: Dict[str, Any]
    permissions: Dict[str, List[str]]  # user_id -> [read, write, execute]
    last_updated: float
    version: int


class CollaborativeStateManager:
    """
    Dynamic state manager for multi-user collaborative features
    """
    
    def __init__(self):
        self.states: Dict[str, Dict[str, Any]] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> state_ids
        self.lock = Lock()
        
    def create_progress_state(self, user_id: str, agent_id: str, 
                            total_steps: int, initial_message: str) -> str:
        """Create a new progress state for streaming indicators"""
        state_id = f"progress_{uuid.uuid4().hex[:8]}"
        
        progress_state = ProgressState(
            id=state_id,
            user_id=user_id,
            agent_id=agent_id,
            status=ProgressStatus.STARTING,
            current_step=initial_message,
            total_steps=total_steps,
            completed_steps=0,
            progress_percentage=0.0,
            message=initial_message,
            details={},
            timestamp=time.time()
        )
        
        with self.lock:
            self.states[state_id] = {
                "type": StateType.AGENT_PROGRESS,
                "data": asdict(progress_state)
            }
            
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(state_id)
        
        self._notify_subscribers(state_id, "created")
        return state_id
    
    def update_progress(self, state_id: str, completed_steps: int = None,
                       current_step: str = None, message: str = None,
                       status: ProgressStatus = None, details: Dict[str, Any] = None):
        """Update progress state for streaming indicators"""
        with self.lock:
            if state_id not in self.states:
                return False
            
            state_data = self.states[state_id]["data"]
            
            if completed_steps is not None:
                state_data["completed_steps"] = completed_steps
                state_data["progress_percentage"] = (completed_steps / state_data["total_steps"]) * 100
            
            if current_step is not None:
                state_data["current_step"] = current_step
            
            if message is not None:
                state_data["message"] = message
            
            if status is not None:
                state_data["status"] = status.value
            
            if details is not None:
                state_data["details"].update(details)
            
            state_data["timestamp"] = time.time()
            
            # Estimate completion time based on progress
            if state_data["completed_steps"] > 0:
                elapsed = time.time() - state_data["timestamp"]
                remaining_steps = state_data["total_steps"] - state_data["completed_steps"]
                avg_time_per_step = elapsed / state_data["completed_steps"]
                state_data["estimated_completion"] = time.time() + (remaining_steps * avg_time_per_step)
        
        self._notify_subscribers(state_id, "updated")
        return True
    
    def create_research_session(self, user_id: str, session_name: str, 
                              research_topic: str, collaboration_mode: str = "interactive") -> str:
        """Create a collaborative research session"""
        state_id = f"research_{uuid.uuid4().hex[:8]}"
        
        research_state = ResearchState(
            id=state_id,
            session_name=session_name,
            participants=[user_id],
            research_topic=research_topic,
            current_phase="initialization",
            findings=[],
            shared_documents=[],
            active_agents=[],
            collaboration_mode=collaboration_mode,
            timestamp=time.time()
        )
        
        with self.lock:
            self.states[state_id] = {
                "type": StateType.RESEARCH_SESSION,
                "data": asdict(research_state)
            }
            
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = []
            self.user_sessions[user_id].append(state_id)
        
        self._notify_subscribers(state_id, "created")
        return state_id
    
    def join_research_session(self, state_id: str, user_id: str) -> bool:
        """Add a user to an existing research session"""
        with self.lock:
            if state_id not in self.states:
                return False
            
            state_data = self.states[state_id]["data"]
            if user_id not in state_data["participants"]:
                state_data["participants"].append(user_id)
                
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = []
                self.user_sessions[user_id].append(state_id)
        
        self._notify_subscribers(state_id, "participant_joined")
        return True
    
    def add_research_finding(self, state_id: str, user_id: str, finding: Dict[str, Any]) -> bool:
        """Add a finding to a research session"""
        with self.lock:
            if state_id not in self.states:
                return False
            
            state_data = self.states[state_id]["data"]
            if user_id not in state_data["participants"]:
                return False
            
            finding_with_meta = {
                **finding,
                "added_by": user_id,
                "timestamp": time.time(),
                "id": uuid.uuid4().hex[:8]
            }
            
            state_data["findings"].append(finding_with_meta)
        
        self._notify_subscribers(state_id, "finding_added")
        return True
    
    def create_shared_context(self, owner_id: str, context_type: str, 
                            data: Dict[str, Any], shared_with: List[str] = None) -> str:
        """Create shared context for real-time state sharing"""
        state_id = f"context_{uuid.uuid4().hex[:8]}"
        
        shared_context = SharedContext(
            id=state_id,
            context_type=context_type,
            owner_id=owner_id,
            shared_with=shared_with or [],
            data=data,
            permissions={owner_id: ["read", "write", "execute"]},
            last_updated=time.time(),
            version=1
        )
        
        # Set default permissions for shared users
        for user_id in (shared_with or []):
            shared_context.permissions[user_id] = ["read"]
        
        with self.lock:
            self.states[state_id] = {
                "type": StateType.SHARED_CONTEXT,
                "data": asdict(shared_context)
            }
            
            # Add to all relevant user sessions
            all_users = [owner_id] + (shared_with or [])
            for user_id in all_users:
                if user_id not in self.user_sessions:
                    self.user_sessions[user_id] = []
                self.user_sessions[user_id].append(state_id)
        
        self._notify_subscribers(state_id, "created")
        return state_id
    
    def update_shared_context(self, state_id: str, user_id: str, 
                            updates: Dict[str, Any]) -> bool:
        """Update shared context with real-time synchronization"""
        with self.lock:
            if state_id not in self.states:
                return False
            
            state_data = self.states[state_id]["data"]
            
            # Check permissions
            user_permissions = state_data["permissions"].get(user_id, [])
            if "write" not in user_permissions:
                return False
            
            # Apply updates
            state_data["data"].update(updates)
            state_data["last_updated"] = time.time()
            state_data["version"] += 1
        
        self._notify_subscribers(state_id, "updated")
        return True
    
    def subscribe(self, state_id: str, callback: Callable):
        """Subscribe to state changes"""
        if state_id not in self.subscribers:
            self.subscribers[state_id] = []
        self.subscribers[state_id].append(callback)
    
    def unsubscribe(self, state_id: str, callback: Callable):
        """Unsubscribe from state changes"""
        if state_id in self.subscribers:
            self.subscribers[state_id].remove(callback)
    
    def get_state(self, state_id: str) -> Optional[Dict[str, Any]]:
        """Get current state"""
        return self.states.get(state_id)
    
    def get_user_states(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all states for a user"""
        user_state_ids = self.user_sessions.get(user_id, [])
        return [self.states[state_id] for state_id in user_state_ids if state_id in self.states]
    
    def _notify_subscribers(self, state_id: str, event_type: str):
        """Notify all subscribers of state changes"""
        if state_id in self.subscribers:
            state_data = self.states.get(state_id)
            for callback in self.subscribers[state_id]:
                try:
                    callback(state_id, event_type, state_data)
                except Exception as e:
                    print(f"Error in state subscriber callback: {e}")


# Global instance for the application
collaborative_state_manager = CollaborativeStateManager()
