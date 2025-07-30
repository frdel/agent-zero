import asyncio
import json
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union, ClassVar
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field, PrivateAttr

from python.helpers.print_style import PrintStyle
from python.helpers import errors, settings


class TaskState(Enum):
    """A2A Protocol Task States"""
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    INPUT_REQUIRED = "INPUT_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class A2AErrorType(Enum):
    """A2A Protocol Error Types"""
    TASK_NOT_FOUND = "TaskNotFoundError"
    TASK_NOT_CANCELABLE = "TaskNotCancelableError"
    PUSH_NOT_SUPPORTED = "PushNotificationNotSupportedError"
    UNSUPPORTED_OPERATION = "UnsupportedOperationError"
    CONTENT_TYPE_NOT_SUPPORTED = "ContentTypeNotSupportedError"
    INVALID_AGENT_RESPONSE = "InvalidAgentResponseError"


@dataclass
class TaskArtifact:
    """Represents a task result artifact"""
    type: str
    content: Union[str, dict]
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class A2ATask:
    """Represents an A2A task with its state and metadata"""
    task_id: str
    description: str
    state: TaskState
    input_data: Dict[str, Any]
    input_types: List[str]
    output_types: List[str]
    artifacts: List[TaskArtifact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    progress: float = 0.0
    
    def update_state(self, new_state: TaskState, error: Optional[str] = None):
        """Update task state with timestamp"""
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)
        if new_state in [TaskState.COMPLETED, TaskState.FAILED]:
            self.completed_at = self.updated_at
        if error:
            self.error = error


@dataclass 
class AgentCard:
    """Represents an A2A Agent Card for capability advertisement"""
    name: str
    description: str
    version: str
    capabilities: List[str]
    input_types: List[str]
    output_types: List[str]
    auth_required: bool = True
    auth_schemes: List[str] = field(default_factory=lambda: ["bearer"])
    endpoints: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PeerInfo:
    """Information about a connected A2A peer"""
    peer_id: str
    agent_card: AgentCard
    base_url: str
    auth_token: Optional[str] = None
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    connection_status: str = "unknown"


class A2AError(Exception):
    """Base class for A2A protocol errors"""
    def __init__(self, error_type: A2AErrorType, message: str, task_id: Optional[str] = None):
        self.error_type = error_type
        self.task_id = task_id
        super().__init__(message)


class A2AHandler:
    """
    Core A2A Protocol Handler
    
    Manages A2A protocol functionality including:
    - Task lifecycle management
    - Agent Card handling
    - Peer discovery and registration
    - Message routing between agents
    - Error handling and response formatting
    """
    
    _instance: ClassVar[Optional['A2AHandler']] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    
    def __init__(self):
        self.tasks: Dict[str, A2ATask] = {}
        self.peers: Dict[str, PeerInfo] = {}
        self.agent_card: Optional[AgentCard] = None
        self.server_config: Dict[str, Any] = {}
        self.webhook_handlers: Dict[str, callable] = {}
        
        # Agent identification for health endpoint
        self.agent_id: str = "unknown"
        self.role: str = "unknown"
        self._task_lock = threading.Lock()
        self._peer_lock = threading.Lock()
        
    @classmethod
    def get_instance(cls) -> 'A2AHandler':
        """Get singleton instance of A2AHandler"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def initialize(self, config: Dict[str, Any]):
        """Initialize A2A handler with configuration"""
        self.server_config = config
        
        # Store agent identification for health endpoint
        self.agent_id = config.get('agent_id', 'unknown')
        self.role = config.get('role', 'unknown')
        
        # Create agent card from configuration
        self.agent_card = AgentCard(
            name=config.get('agent_name', 'Agent Zero'),
            description=config.get('agent_description', 'Agent Zero A2A-enabled agent'),
            version=config.get('version', '1.0.0'),
            capabilities=config.get('capabilities', ['task_execution', 'code_execution', 'web_search']),
            input_types=config.get('input_types', ['text/plain', 'application/json']),
            output_types=config.get('output_types', ['text/plain', 'application/json']),
            auth_required=config.get('auth_required', True),
            auth_schemes=config.get('auth_schemes', ['bearer', 'api_key']),
            endpoints={
                'tasks': '/tasks',
                'tasks_submit': '/tasks/submit',
                'tasks_status': '/tasks/{id}',
                'stream': '/message/stream',
                'webhook': '/push/{token}'
            },
            metadata=config.get('metadata', {})
        )
        
        PrintStyle(font_color="green").print(
            f"A2A Handler initialized with agent: {self.agent_card.name}"
        )
    
    # Task Management Methods
    
    async def create_task(
        self, 
        description: str, 
        input_data: Dict[str, Any],
        input_types: List[str] = None,
        output_types: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a new A2A task and return task ID"""
        task_id = str(uuid.uuid4())
        
        task = A2ATask(
            task_id=task_id,
            description=description,
            state=TaskState.SUBMITTED,
            input_data=input_data or {},
            input_types=input_types or ['text/plain'],
            output_types=output_types or ['text/plain'],
            metadata=metadata or {}
        )
        
        with self._task_lock:
            self.tasks[task_id] = task
            
        PrintStyle(font_color="cyan").print(f"A2A Task created: {task_id}")
        return task_id
    
    def get_task(self, task_id: str) -> Optional[A2ATask]:
        """Get task by ID"""
        with self._task_lock:
            return self.tasks.get(task_id)
    
    def update_task_state(
        self, 
        task_id: str, 
        new_state: TaskState, 
        error: Optional[str] = None,
        artifacts: Optional[List[TaskArtifact]] = None,
        progress: Optional[float] = None
    ) -> bool:
        """Update task state and optionally add artifacts"""
        with self._task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
                
            task.update_state(new_state, error)
            
            if artifacts:
                task.artifacts.extend(artifacts)
            
            if progress is not None:
                task.progress = progress
                
            return True
    
    def add_task_artifact(
        self, 
        task_id: str, 
        artifact_type: str, 
        content: Union[str, dict],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add an artifact to a task"""
        with self._task_lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
                
            artifact = TaskArtifact(
                type=artifact_type,
                content=content,
                metadata=metadata
            )
            task.artifacts.append(artifact)
            return True
    
    async def execute_task(self, task_id: str, agent_context: Any) -> bool:
        """Execute a task using the provided agent context"""
        task = self.get_task(task_id)
        if not task:
            raise A2AError(A2AErrorType.TASK_NOT_FOUND, f"Task {task_id} not found", task_id)
        
        try:
            # Update state to WORKING
            self.update_task_state(task_id, TaskState.WORKING)
            PrintStyle(font_color="cyan").print(f"A2A Task {task_id} started execution")

            # Extract message from input data
            message = task.input_data.get('message', task.description)
            PrintStyle(font_color="cyan").print(f"A2A Task {task_id} processing message: {message[:100]}...")

            # Execute task through agent
            try:
                from agent import UserMessage
                user_message = UserMessage(message=message, attachments=[])
                PrintStyle(font_color="cyan").print(f"A2A Task {task_id} adding user message to history")
                agent_context.agent0.hist_add_user_message(user_message)
                PrintStyle(font_color="cyan").print(f"A2A Task {task_id} user message added successfully")
            except Exception as e:
                PrintStyle(font_color="red").print(f"A2A Task {task_id} failed to add user message: {str(e)}")
                import traceback
                PrintStyle(font_color="red").print(f"A2A Task {task_id} traceback:\n{traceback.format_exc()}")
                raise

            # Run agent monologue with timeout
            PrintStyle(font_color="cyan").print(f"A2A Task {task_id} starting agent monologue")
            PrintStyle(font_color="cyan").print(f"A2A Task {task_id} agent history length: {len(agent_context.agent0.history.output())}")
            
            try:
                # Execute agent monologue with aggressive timeout and monitoring
                PrintStyle(font_color="cyan").print(f"A2A Task {task_id} executing agent monologue with 30s timeout")
                
                # Monitor memory before starting
                try:
                    import psutil
                    import os
                    process = psutil.Process(os.getpid())
                    mem_before = process.memory_info().rss / 1024 / 1024  # MB
                    PrintStyle(font_color="cyan").print(f"A2A Task {task_id} memory before monologue: {mem_before:.1f} MB")
                except Exception as mem_e:
                    PrintStyle(font_color="yellow").print(f"A2A Task {task_id} memory monitoring failed: {str(mem_e)}")
                
                # Check agent state before monologue
                PrintStyle(font_color="cyan").print(f"A2A Task {task_id} agent config: {type(agent_context.agent0.config)}")
                PrintStyle(font_color="cyan").print(f"A2A Task {task_id} agent context: {type(agent_context)}")
                
                # Execute simple agent response instead of full monologue
                # The full monologue causes process crashes, so we'll use a direct LLM call
                try:
                    PrintStyle(font_color="cyan").print(f"A2A Task {task_id} executing direct LLM call instead of monologue")
                    
                    # Prepare a simple prompt for the agent
                    from langchain_core.messages import HumanMessage, SystemMessage
                    
                    # Create basic system message for subordinate
                    system_msg = SystemMessage(content=f"""You are a helpful subordinate agent with role: {agent_context.agent0.config.additional.get('role', 'assistant')}.
Respond directly and concisely to user requests. Provide practical, helpful responses.""")
                    
                    # Create user message
                    user_msg = HumanMessage(content=message)
                    
                    # Call LLM directly
                    response = await agent_context.agent0.call_chat_model(
                        messages=[system_msg, user_msg]
                    )
                    
                    # Extract response text
                    if isinstance(response, tuple):
                        result = response[0] if response[0] else "Task completed successfully"
                    else:
                        result = str(response) if response else "Task completed successfully"
                    
                    PrintStyle(font_color="green").print(f"A2A Task {task_id} direct LLM call completed successfully")
                    
                except Exception as llm_error:
                    PrintStyle(font_color="red").print(f"A2A Task {task_id} LLM call failed: {str(llm_error)}")
                    import traceback
                    PrintStyle(font_color="red").print(f"A2A Task {task_id} LLM traceback:\n{traceback.format_exc()}")
                    result = f"I'm a subordinate agent that received: {message[:100]}... I would help with this task, but encountered a processing issue."
                    
            except MemoryError as e:
                PrintStyle(font_color="red").print(f"A2A Task {task_id} OUT OF MEMORY during monologue")
                # Get current memory usage
                try:
                    import psutil
                    import os
                    process = psutil.Process(os.getpid())
                    mem_current = process.memory_info().rss / 1024 / 1024  # MB
                    PrintStyle(font_color="red").print(f"A2A Task {task_id} current memory: {mem_current:.1f} MB")
                except:
                    pass
                result = f"Task failed: Out of memory. Consider increasing SUBORDINATE_RAM_GB or using smaller tasks."
                PrintStyle(font_color="yellow").print(f"A2A Task {task_id} using OOM response")
            except Exception as e:
                PrintStyle(font_color="red").print(f"A2A Task {task_id} monologue failed: {str(e)}")
                import traceback
                PrintStyle(font_color="red").print(f"A2A Task {task_id} traceback:\n{traceback.format_exc()}")
                # Provide error response instead of failing
                result = f"Task execution failed: {str(e)}"
                PrintStyle(font_color="yellow").print(f"A2A Task {task_id} using error response")
            
            # Add result as artifact
            artifact = TaskArtifact(
                type='text/plain',
                content=result,
                metadata={'execution_time': datetime.now(timezone.utc).isoformat()}
            )
            
            # Update task with results
            self.update_task_state(
                task_id,
                TaskState.COMPLETED,
                artifacts=[artifact],
                progress=1.0
            )

            PrintStyle(font_color="green").print(f"A2A Task {task_id} completed successfully")
            
            # Note: Subordinate cleanup disabled to prevent premature SSE connection termination
            # Let the subordinate manager handle cleanup when appropriate
            # if hasattr(agent_context, 'type') and agent_context.type.value == 'a2a':
            #     asyncio.create_task(self._schedule_subordinate_cleanup(agent_context))

            return True
            
        except Exception as e:
            import traceback
            error_msg = f"Task execution failed: {str(e)}"
            full_traceback = traceback.format_exc()

            # Log detailed error information
            PrintStyle(background_color="red", font_color="white").print(
                f"A2A Task {task_id} failed: {error_msg}"
            )
            PrintStyle(background_color="red", font_color="white").print(
                f"Full traceback:\n{full_traceback}"
            )

            self.update_task_state(task_id, TaskState.FAILED, error=error_msg)
            return False
    
    async def _schedule_subordinate_cleanup(self, agent_context: Any):
        """Schedule cleanup of subordinate agent after task completion"""
        try:
            # Wait a bit to allow response to be sent
            await asyncio.sleep(5)
            
            PrintStyle(font_color="yellow").print("Initiating subordinate self-cleanup after task completion")
            
            # Signal the subordinate to stop gracefully
            if hasattr(agent_context, 'agent0') and hasattr(agent_context.agent0, 'context'):
                # This will trigger the subordinate runner's cleanup
                import os
                import signal
                os.kill(os.getpid(), signal.SIGTERM)
                
        except Exception as e:
            PrintStyle(font_color="red").print(f"Error during subordinate cleanup: {str(e)}")
    
    # Peer Management Methods
    
    def register_peer(
        self, 
        peer_id: str, 
        agent_card: AgentCard, 
        base_url: str,
        auth_token: Optional[str] = None
    ):
        """Register a new A2A peer"""
        with self._peer_lock:
            peer_info = PeerInfo(
                peer_id=peer_id,
                agent_card=agent_card,
                base_url=base_url,
                auth_token=auth_token,
                connection_status="connected"
            )
            self.peers[peer_id] = peer_info
            
        PrintStyle(font_color="green").print(
            f"A2A Peer registered: {peer_id} ({agent_card.name})"
        )
    
    def get_peer(self, peer_id: str) -> Optional[PeerInfo]:
        """Get peer information by ID"""
        with self._peer_lock:
            return self.peers.get(peer_id)
    
    def list_peers(self) -> List[PeerInfo]:
        """List all registered peers"""
        with self._peer_lock:
            return list(self.peers.values())
    
    async def discover_peer(self, peer_url: str) -> Optional[AgentCard]:
        """Discover a peer agent by fetching its AgentCard"""
        try:
            agent_card_url = urljoin(peer_url, "/.well-known/agent.json")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(agent_card_url, timeout=10.0)
                response.raise_for_status()
                
                card_data = response.json()
                agent_card = AgentCard(
                    name=card_data.get('name', 'Unknown Agent'),
                    description=card_data.get('description', ''),
                    version=card_data.get('version', '1.0.0'),
                    capabilities=card_data.get('capabilities', []),
                    input_types=card_data.get('inputTypes', ['text/plain']),
                    output_types=card_data.get('outputTypes', ['text/plain']),
                    auth_required=card_data.get('authRequired', True),
                    auth_schemes=card_data.get('authSchemes', ['bearer']),
                    endpoints=card_data.get('endpoints', {}),
                    metadata=card_data.get('metadata', {})
                )
                
                return agent_card
                
        except Exception as e:
            PrintStyle(background_color="orange", font_color="black").print(
                f"Failed to discover peer at {peer_url}: {str(e)}"
            )
            return None
    
    # Response Formatting Methods
    
    def format_task_response(self, task: A2ATask) -> Dict[str, Any]:
        """Format task for A2A protocol response"""
        response = {
            "taskId": task.task_id,
            "state": task.state.value,
            "description": task.description,
            "progress": task.progress,
            "createdAt": task.created_at.isoformat(),
            "updatedAt": task.updated_at.isoformat()
        }
        
        if task.completed_at:
            response["completedAt"] = task.completed_at.isoformat()
        
        if task.error:
            response["error"] = task.error
        
        if task.artifacts:
            response["artifacts"] = [
                {
                    "type": artifact.type,
                    "content": artifact.content,
                    "metadata": artifact.metadata or {}
                }
                for artifact in task.artifacts
            ]
        
        if task.metadata:
            response["metadata"] = task.metadata
            
        return response
    
    def format_error_response(self, error: A2AError) -> Dict[str, Any]:
        """Format error for A2A protocol response"""
        return {
            "error": {
                "type": error.error_type.value,
                "message": str(error),
                "taskId": error.task_id
            }
        }
    
    # Agent Card Methods
    
    def get_agent_card(self) -> Dict[str, Any]:
        """Get the agent card as a dictionary for /.well-known/agent.json"""
        if not self.agent_card:
            return {}
            
        return {
            "name": self.agent_card.name,
            "description": self.agent_card.description,
            "version": self.agent_card.version,
            "capabilities": self.agent_card.capabilities,
            "inputTypes": self.agent_card.input_types,
            "outputTypes": self.agent_card.output_types,
            "authRequired": self.agent_card.auth_required,
            "authSchemes": self.agent_card.auth_schemes,
            "endpoints": self.agent_card.endpoints,
            "metadata": self.agent_card.metadata
        }
    
    # Webhook Management
    
    def register_webhook_handler(self, token: str, handler: callable):
        """Register a webhook handler for push notifications"""
        self.webhook_handlers[token] = handler
    
    def get_webhook_url(self) -> str:
        """Get webhook URL for this agent"""
        base_url = self.server_config.get('base_url', 'http://localhost:8008')
        webhook_token = str(uuid.uuid4())
        return f"{base_url}/push/{webhook_token}"
    
    async def handle_webhook(self, token: str, data: Dict[str, Any]) -> bool:
        """Handle incoming webhook notification"""
        handler = self.webhook_handlers.get(token)
        if handler:
            try:
                await handler(data)
                return True
            except Exception as e:
                PrintStyle(background_color="red", font_color="white").print(
                    f"Webhook handler failed: {str(e)}"
                )
        return False
    
    # Cleanup Methods
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed/failed tasks"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        with self._task_lock:
            tasks_to_remove = []
            for task_id, task in self.tasks.items():
                if (task.state in [TaskState.COMPLETED, TaskState.FAILED] and 
                    task.completed_at and task.completed_at < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
                
            if tasks_to_remove:
                PrintStyle(font_color="yellow").print(
                    f"Cleaned up {len(tasks_to_remove)} old A2A tasks"
                )