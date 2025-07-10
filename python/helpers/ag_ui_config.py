"""
AG-UI Agent Configuration System
Manages agent metadata, capabilities, and multi-agent coordination
"""

import json
import os
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime


class AgentCapability(Enum):
    """Standard agent capabilities for AG-UI protocol"""
    UI_GENERATION = "ui_generation"
    EVENT_HANDLING = "event_handling"
    STATE_MANAGEMENT = "state_management"
    MULTI_COMPONENT_SUPPORT = "multi_component_support"
    STREAMING_RESPONSES = "streaming_responses"
    REAL_TIME_COLLABORATION = "real_time_collaboration"
    TOOL_EXECUTION = "tool_execution"
    FORM_PROCESSING = "form_processing"
    FILE_HANDLING = "file_handling"
    MULTI_MODAL = "multi_modal"
    CANVAS_INTERACTION = "canvas_interaction"
    TABLE_OPERATIONS = "table_operations"


class AgentRole(Enum):
    """Agent roles in multi-agent systems"""
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    OBSERVER = "observer"
    EXECUTOR = "executor"
    VALIDATOR = "validator"


@dataclass
class AgentConfiguration:
    """Configuration for an AG-UI enabled agent"""
    agent_id: str
    name: str
    description: str
    version: str = "1.0.0"
    protocol_version: str = "1.0"
    framework: str = "agent_zero"
    
    # Capabilities
    capabilities: Set[AgentCapability] = field(default_factory=lambda: {
        AgentCapability.UI_GENERATION,
        AgentCapability.EVENT_HANDLING,
        AgentCapability.STATE_MANAGEMENT
    })
    
    # Multi-agent coordination
    role: AgentRole = AgentRole.EXECUTOR
    coordination_enabled: bool = True
    can_delegate: bool = True
    can_collaborate: bool = True
    
    # Component preferences
    preferred_components: List[str] = field(default_factory=lambda: [
        "button", "form", "card", "modal", "table"
    ])
    max_components_per_request: int = 10
    enable_streaming: bool = True
    
    # State management
    persist_state: bool = True
    state_ttl_minutes: int = 60
    share_state_with_agents: List[str] = field(default_factory=list)
    
    # Security settings
    allow_custom_html: bool = False
    allow_javascript_events: bool = True
    validate_all_inputs: bool = True
    sanitize_content: bool = True
    
    # Integration metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiAgentSession:
    """Represents a multi-agent collaboration session"""
    session_id: str
    coordinator_agent_id: str
    participant_agents: List[str]
    shared_state: Dict[str, Any] = field(default_factory=dict)
    session_metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True


class AGUIConfigManager:
    """Manages AG-UI agent configurations and multi-agent coordination"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.join(os.path.dirname(__file__), "..", "..", "config", "ag_ui")
        self.configurations: Dict[str, AgentConfiguration] = {}
        self.active_sessions: Dict[str, MultiAgentSession] = {}
        self.agent_registry: Dict[str, Dict[str, Any]] = {}
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load existing configurations
        self._load_configurations()
    
    def register_agent(self, config: AgentConfiguration) -> bool:
        """Register an agent with the AG-UI system"""
        try:
            self.configurations[config.agent_id] = config
            
            # Add to agent registry
            self.agent_registry[config.agent_id] = {
                "name": config.name,
                "capabilities": [cap.value for cap in config.capabilities],
                "role": config.role.value,
                "active": True,
                "last_seen": datetime.now().isoformat(),
                "metadata": config.metadata
            }
            
            # Save configuration
            self._save_configuration(config)
            return True
            
        except Exception as e:
            print(f"Error registering agent {config.agent_id}: {e}")
            return False
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent from the AG-UI system"""
        try:
            if agent_id in self.configurations:
                del self.configurations[agent_id]
            
            if agent_id in self.agent_registry:
                self.agent_registry[agent_id]["active"] = False
            
            # Remove from active sessions
            for session in self.active_sessions.values():
                if agent_id in session.participant_agents:
                    session.participant_agents.remove(agent_id)
                if session.coordinator_agent_id == agent_id:
                    session.active = False
            
            return True
            
        except Exception as e:
            print(f"Error unregistering agent {agent_id}: {e}")
            return False
    
    def get_agent_config(self, agent_id: str) -> Optional[AgentConfiguration]:
        """Get configuration for a specific agent"""
        return self.configurations.get(agent_id)
    
    def update_agent_config(self, agent_id: str, updates: Dict[str, Any]) -> bool:
        """Update agent configuration"""
        try:
            config = self.configurations.get(agent_id)
            if not config:
                return False
            
            # Update configuration fields
            for key, value in updates.items():
                if hasattr(config, key):
                    if key == "capabilities" and isinstance(value, list):
                        config.capabilities = {AgentCapability(cap) for cap in value}
                    elif key == "role" and isinstance(value, str):
                        config.role = AgentRole(value)
                    else:
                        setattr(config, key, value)
            
            # Save updated configuration
            self._save_configuration(config)
            return True
            
        except Exception as e:
            print(f"Error updating agent config {agent_id}: {e}")
            return False
    
    def find_agents_by_capability(self, capability: AgentCapability) -> List[str]:
        """Find agents that have a specific capability"""
        matching_agents = []
        for agent_id, config in self.configurations.items():
            if capability in config.capabilities and self.agent_registry.get(agent_id, {}).get("active", False):
                matching_agents.append(agent_id)
        return matching_agents
    
    def find_agents_by_role(self, role: AgentRole) -> List[str]:
        """Find agents that have a specific role"""
        matching_agents = []
        for agent_id, config in self.configurations.items():
            if config.role == role and self.agent_registry.get(agent_id, {}).get("active", False):
                matching_agents.append(agent_id)
        return matching_agents
    
    def create_collaboration_session(self, coordinator_agent_id: str, participant_agents: List[str], session_metadata: Dict[str, Any] = None) -> str:
        """Create a new multi-agent collaboration session"""
        import uuid
        session_id = str(uuid.uuid4())
        
        session = MultiAgentSession(
            session_id=session_id,
            coordinator_agent_id=coordinator_agent_id,
            participant_agents=participant_agents,
            session_metadata=session_metadata or {}
        )
        
        self.active_sessions[session_id] = session
        return session_id
    
    def get_collaboration_session(self, session_id: str) -> Optional[MultiAgentSession]:
        """Get collaboration session by ID"""
        return self.active_sessions.get(session_id)
    
    def add_agent_to_session(self, session_id: str, agent_id: str) -> bool:
        """Add agent to collaboration session"""
        session = self.active_sessions.get(session_id)
        if session and agent_id not in session.participant_agents:
            session.participant_agents.append(agent_id)
            return True
        return False
    
    def remove_agent_from_session(self, session_id: str, agent_id: str) -> bool:
        """Remove agent from collaboration session"""
        session = self.active_sessions.get(session_id)
        if session and agent_id in session.participant_agents:
            session.participant_agents.remove(agent_id)
            return True
        return False
    
    def end_collaboration_session(self, session_id: str) -> bool:
        """End a collaboration session"""
        session = self.active_sessions.get(session_id)
        if session:
            session.active = False
            return True
        return False
    
    def get_agent_capabilities_matrix(self) -> Dict[str, List[str]]:
        """Get a matrix of agents and their capabilities"""
        matrix = {}
        for agent_id, config in self.configurations.items():
            if self.agent_registry.get(agent_id, {}).get("active", False):
                matrix[agent_id] = [cap.value for cap in config.capabilities]
        return matrix
    
    def suggest_delegation_targets(self, required_capability: AgentCapability, exclude_agents: List[str] = None) -> List[Dict[str, Any]]:
        """Suggest agents that can handle delegation for a specific capability"""
        exclude_agents = exclude_agents or []
        suggestions = []
        
        for agent_id in self.find_agents_by_capability(required_capability):
            if agent_id not in exclude_agents:
                config = self.configurations[agent_id]
                if config.can_delegate:
                    suggestions.append({
                        "agent_id": agent_id,
                        "name": config.name,
                        "role": config.role.value,
                        "capabilities": [cap.value for cap in config.capabilities],
                        "load_score": len(config.capabilities)  # Simple load metric
                    })
        
        # Sort by load score (fewer capabilities = less loaded)
        suggestions.sort(key=lambda x: x["load_score"])
        return suggestions
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status and metrics"""
        active_agents = sum(1 for agent in self.agent_registry.values() if agent.get("active", False))
        active_sessions = sum(1 for session in self.active_sessions.values() if session.active)
        
        capability_distribution = {}
        for capability in AgentCapability:
            capability_distribution[capability.value] = len(self.find_agents_by_capability(capability))
        
        return {
            "total_registered_agents": len(self.configurations),
            "active_agents": active_agents,
            "active_collaboration_sessions": active_sessions,
            "capability_distribution": capability_distribution,
            "system_health": "healthy" if active_agents > 0 else "no_active_agents"
        }
    
    def _load_configurations(self):
        """Load configurations from disk"""
        try:
            config_file = os.path.join(self.config_dir, "agents.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                for agent_data in data.get("agents", []):
                    config = self._dict_to_config(agent_data)
                    self.configurations[config.agent_id] = config
                    
                self.agent_registry = data.get("registry", {})
                
        except Exception as e:
            print(f"Error loading configurations: {e}")
    
    def _save_configuration(self, config: AgentConfiguration):
        """Save configuration to disk"""
        try:
            config_file = os.path.join(self.config_dir, "agents.json")
            
            # Load existing data
            data = {"agents": [], "registry": {}}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    data = json.load(f)
            
            # Update or add agent configuration
            agent_data = self._config_to_dict(config)
            agents = data.get("agents", [])
            
            # Remove existing config for this agent
            agents = [a for a in agents if a.get("agent_id") != config.agent_id]
            agents.append(agent_data)
            
            data["agents"] = agents
            data["registry"] = self.agent_registry
            
            # Save to file
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def _config_to_dict(self, config: AgentConfiguration) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        data = asdict(config)
        data["capabilities"] = [cap.value for cap in config.capabilities]
        data["role"] = config.role.value
        return data
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AgentConfiguration:
        """Convert dictionary to configuration"""
        # Convert capabilities
        capabilities = {AgentCapability(cap) for cap in data.get("capabilities", [])}
        data["capabilities"] = capabilities
        
        # Convert role
        data["role"] = AgentRole(data.get("role", "executor"))
        
        return AgentConfiguration(**data)


# Global configuration manager instance
_global_config_manager = None


def get_global_config_manager() -> AGUIConfigManager:
    """Get or create global configuration manager instance"""
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = AGUIConfigManager()
    return _global_config_manager


def create_default_agent_config(agent_id: str, name: str, description: str) -> AgentConfiguration:
    """Create a default agent configuration"""
    return AgentConfiguration(
        agent_id=agent_id,
        name=name,
        description=description,
        capabilities={
            AgentCapability.UI_GENERATION,
            AgentCapability.EVENT_HANDLING,
            AgentCapability.STATE_MANAGEMENT,
            AgentCapability.MULTI_COMPONENT_SUPPORT
        },
        role=AgentRole.EXECUTOR,
        metadata={
            "created_at": datetime.now().isoformat(),
            "framework": "agent_zero",
            "ag_ui_version": "1.0"
        }
    )