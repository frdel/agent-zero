"""
AG-UI State Management System
Implements bidirectional state synchronization between agents and clients
"""

import json
import threading
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class StateEvent:
    """Represents a state change event"""
    type: str  # STATE_SNAPSHOT, STATE_DELTA
    agent_id: str
    component_id: Optional[str]
    state_data: Dict[str, Any]
    timestamp: int
    sequence_id: int


class AGUIStateManager:
    """
    Manages bidirectional state synchronization for AG-UI protocol.
    Supports multi-agent collaboration and state persistence.
    """
    
    def __init__(self, agent_id: str = "agent_zero"):
        self.agent_id = agent_id
        self.state_store: Dict[str, Dict[str, Any]] = {}
        self.component_states: Dict[str, Dict[str, Any]] = {}
        self.state_history: List[StateEvent] = []
        self.subscribers: Dict[str, List[Callable]] = {}
        self.sequence_counter = 0
        self.lock = threading.Lock()
        
        # Multi-agent collaboration
        self.connected_agents: Dict[str, Dict[str, Any]] = {}
        self.shared_state: Dict[str, Any] = {}
        
    def register_agent(self, agent_id: str, metadata: Dict[str, Any] = None):
        """Register an agent for multi-agent collaboration"""
        with self.lock:
            self.connected_agents[agent_id] = {
                "metadata": metadata or {},
                "last_seen": self._get_timestamp(),
                "active": True
            }
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent from collaboration"""
        with self.lock:
            if agent_id in self.connected_agents:
                self.connected_agents[agent_id]["active"] = False
    
    def set_component_state(self, component_id: str, state: Dict[str, Any], emit_event: bool = True):
        """Set state for a specific component"""
        with self.lock:
            old_state = self.component_states.get(component_id, {})
            self.component_states[component_id] = state
            
            if emit_event:
                # Create state delta
                delta = self._calculate_state_delta(old_state, state)
                self._emit_state_event("STATE_DELTA", component_id, delta)
    
    def get_component_state(self, component_id: str) -> Dict[str, Any]:
        """Get state for a specific component"""
        return self.component_states.get(component_id, {})
    
    def update_component_state(self, component_id: str, updates: Dict[str, Any]):
        """Update specific fields in component state"""
        with self.lock:
            current_state = self.component_states.get(component_id, {})
            current_state.update(updates)
            self.set_component_state(component_id, current_state)

    def delete_component_state(self, component_id: str) -> bool:
        """Delete state for a specific component"""
        with self.lock:
            if component_id in self.component_states:
                del self.component_states[component_id]
                self._emit_state_event("STATE_DELETED", component_id, {})
                return True
            return False

    def get_all_component_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all component states"""
        return self.component_states.copy()

    def clear_component_states_by_prefix(self, prefix: str) -> int:
        """Clear component states with a specific prefix"""
        with self.lock:
            to_delete = [cid for cid in self.component_states.keys() if cid.startswith(prefix)]
            for component_id in to_delete:
                del self.component_states[component_id]
                self._emit_state_event("STATE_DELETED", component_id, {})
            return len(to_delete)

    def clear_all_component_states(self) -> int:
        """Clear all component states"""
        with self.lock:
            count = len(self.component_states)
            self.component_states.clear()
            self._emit_state_event("ALL_STATES_CLEARED", None, {"cleared_count": count})
            return count
    
    def set_global_state(self, key: str, value: Any):
        """Set global state value"""
        with self.lock:
            old_value = self.state_store.get(key)
            self.state_store[key] = value
            
            # Emit state delta for global state change
            delta = {key: {"old": old_value, "new": value}}
            self._emit_state_event("STATE_DELTA", None, delta)
    
    def get_global_state(self, key: str = None) -> Any:
        """Get global state value(s)"""
        if key is None:
            return self.state_store.copy()
        return self.state_store.get(key)
    
    def set_shared_state(self, key: str, value: Any, agent_id: str = None):
        """Set shared state for multi-agent collaboration"""
        with self.lock:
            if agent_id is None:
                agent_id = self.agent_id
                
            self.shared_state[key] = {
                "value": value,
                "owner": agent_id,
                "timestamp": self._get_timestamp()
            }
            
            # Notify all connected agents
            self._broadcast_shared_state_change(key, value, agent_id)
    
    def get_shared_state(self, key: str = None) -> Any:
        """Get shared state value(s)"""
        if key is None:
            return {k: v["value"] for k, v in self.shared_state.items()}
        
        shared_item = self.shared_state.get(key)
        return shared_item["value"] if shared_item else None
    
    def subscribe_to_state_changes(self, event_type: str, callback: Callable):
        """Subscribe to state change events"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def unsubscribe_from_state_changes(self, event_type: str, callback: Callable):
        """Unsubscribe from state change events"""
        if event_type in self.subscribers:
            self.subscribers[event_type].remove(callback)
    
    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get complete state snapshot for AG-UI protocol"""
        return {
            "type": "STATE_SNAPSHOT",
            "agent_id": self.agent_id,
            "timestamp": self._get_timestamp(),
            "global_state": self.state_store.copy(),
            "component_states": self.component_states.copy(),
            "shared_state": self.get_shared_state(),
            "connected_agents": list(self.connected_agents.keys())
        }
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any]):
        """Restore state from snapshot"""
        with self.lock:
            if "global_state" in snapshot:
                self.state_store = snapshot["global_state"].copy()
            if "component_states" in snapshot:
                self.component_states = snapshot["component_states"].copy()
            if "shared_state" in snapshot:
                for key, value in snapshot["shared_state"].items():
                    self.shared_state[key] = {
                        "value": value,
                        "owner": snapshot.get("agent_id", "unknown"),
                        "timestamp": self._get_timestamp()
                    }
    
    def get_state_history(self, limit: int = 100) -> List[StateEvent]:
        """Get recent state change history"""
        return self.state_history[-limit:]
    
    def clear_state(self, component_id: str = None):
        """Clear state for component or all state"""
        with self.lock:
            if component_id:
                self.component_states.pop(component_id, None)
                self._emit_state_event("STATE_DELTA", component_id, {})
            else:
                self.state_store.clear()
                self.component_states.clear()
                self._emit_state_event("STATE_SNAPSHOT", None, {})
    
    def _emit_state_event(self, event_type: str, component_id: Optional[str], state_data: Dict[str, Any]):
        """Emit state change event"""
        event = StateEvent(
            type=event_type,
            agent_id=self.agent_id,
            component_id=component_id,
            state_data=state_data,
            timestamp=self._get_timestamp(),
            sequence_id=self._get_next_sequence_id()
        )
        
        self.state_history.append(event)
        
        # Notify subscribers
        for callback in self.subscribers.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                print(f"Error in state event callback: {e}")
    
    def _calculate_state_delta(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate state delta between old and new state"""
        delta = {}
        
        # Find changed and new keys
        for key, value in new_state.items():
            if key not in old_state or old_state[key] != value:
                delta[key] = {"old": old_state.get(key), "new": value}
        
        # Find removed keys
        for key in old_state:
            if key not in new_state:
                delta[key] = {"old": old_state[key], "new": None}
        
        return delta
    
    def _broadcast_shared_state_change(self, key: str, value: Any, owner_agent_id: str):
        """Broadcast shared state change to all connected agents"""
        # This would typically send events to other agent instances
        # For now, we'll emit a local event
        self._emit_state_event("SHARED_STATE_CHANGE", None, {
            "key": key,
            "value": value,
            "owner": owner_agent_id
        })
    
    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds"""
        return int(time.time() * 1000)
    
    def _get_next_sequence_id(self) -> int:
        """Get next sequence ID for event ordering"""
        self.sequence_counter += 1
        return self.sequence_counter
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state manager to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "state_store": self.state_store,
            "component_states": self.component_states,
            "shared_state": self.shared_state,
            "connected_agents": self.connected_agents,
            "timestamp": self._get_timestamp()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AGUIStateManager":
        """Create state manager from dictionary"""
        manager = cls(data.get("agent_id", "agent_zero"))
        manager.state_store = data.get("state_store", {})
        manager.component_states = data.get("component_states", {})
        manager.shared_state = data.get("shared_state", {})
        manager.connected_agents = data.get("connected_agents", {})
        return manager


# Global state manager instance
_global_state_manager = None


def get_global_state_manager() -> AGUIStateManager:
    """Get or create global state manager instance"""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = AGUIStateManager()
    return _global_state_manager


def create_agent_state_manager(agent_id: str) -> AGUIStateManager:
    """Create a new state manager for a specific agent"""
    return AGUIStateManager(agent_id)