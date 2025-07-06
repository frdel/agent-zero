"""
Workflow Manager for Agent Zero
Enables LangGraph-style state machine workflows with AG-UI integration
"""

import json
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict
from enum import Enum
import time
from abc import ABC, abstractmethod

from python.helpers.ag_ui_state import AGUIStateManager, get_global_state_manager
from python.helpers.tool import Tool, Response


class NodeType(Enum):
    START = "start"
    CHAT = "chat" 
    TOOL = "tool"
    CONDITION = "condition"
    END = "end"


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """Represents a node in a workflow graph"""
    id: str
    type: NodeType
    name: str
    handler: str  # Function name or tool name
    config: Dict[str, Any] = None
    position: Dict[str, int] = None  # For AG-UI canvas rendering
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.position is None:
            self.position = {"x": 0, "y": 0}


@dataclass 
class WorkflowEdge:
    """Represents an edge between workflow nodes"""
    id: str
    source: str
    target: str
    condition: Optional[str] = None  # JavaScript condition or Python expression
    label: Optional[str] = None


@dataclass
class WorkflowState:
    """Represents the current state of workflow execution"""
    workflow_id: str
    current_node: str
    state_data: Dict[str, Any]
    execution_history: List[str]
    status: ExecutionStatus
    timestamp: int


class WorkflowCommand:
    """Command object for workflow control flow"""
    def __init__(self, goto: str, update: Dict[str, Any] = None):
        self.goto = goto
        self.update = update or {}


class AbstractWorkflowHandler(ABC):
    """Abstract base class for workflow node handlers"""
    
    @abstractmethod
    async def execute(self, state: WorkflowState, config: Dict[str, Any]) -> WorkflowCommand:
        """Execute the workflow node and return next command"""
        pass


class ChatNodeHandler(AbstractWorkflowHandler):
    """Handler for chat-based workflow nodes"""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def execute(self, state: WorkflowState, config: Dict[str, Any]) -> WorkflowCommand:
        """Execute chat node with LLM integration"""
        try:
            # Get system prompt from config
            system_prompt = config.get("system_prompt", "You are a helpful assistant.")
            
            # Format prompt with current state
            if "document" in state.state_data:
                system_prompt += f"\n\nCurrent document: {state.state_data['document']}"
            
            # Use agent's LLM to process the conversation
            # This would integrate with Agent Zero's existing chat infrastructure
            # For now, return a simple command
            
            return WorkflowCommand(goto="end", update={
                "messages": state.state_data.get("messages", []) + [
                    {"role": "assistant", "content": "Chat processed"}
                ]
            })
            
        except Exception as e:
            return WorkflowCommand(goto="end", update={
                "error": str(e)
            })


class ToolNodeHandler(AbstractWorkflowHandler):
    """Handler for tool-based workflow nodes"""
    
    def __init__(self, agent):
        self.agent = agent
    
    async def execute(self, state: WorkflowState, config: Dict[str, Any]) -> WorkflowCommand:
        """Execute tool node"""
        try:
            tool_name = config.get("tool_name")
            tool_args = config.get("tool_args", {})
            
            # Find and execute tool
            # This would integrate with Agent Zero's existing tool system
            
            return WorkflowCommand(goto=config.get("next_node", "end"), update={
                f"{tool_name}_result": "Tool executed successfully"
            })
            
        except Exception as e:
            return WorkflowCommand(goto="end", update={
                "error": str(e)
            })


class ConditionNodeHandler(AbstractWorkflowHandler):
    """Handler for conditional workflow nodes"""
    
    async def execute(self, state: WorkflowState, config: Dict[str, Any]) -> WorkflowCommand:
        """Execute condition node and route based on result"""
        try:
            condition = config.get("condition")
            true_node = config.get("true_node", "end")
            false_node = config.get("false_node", "end")
            
            # Evaluate condition against current state
            # This is a simplified version - would need proper evaluation
            if self._evaluate_condition(condition, state.state_data):
                return WorkflowCommand(goto=true_node)
            else:
                return WorkflowCommand(goto=false_node)
                
        except Exception as e:
            return WorkflowCommand(goto="end", update={
                "error": str(e)
            })
    
    def _evaluate_condition(self, condition: str, state_data: Dict[str, Any]) -> bool:
        """Safely evaluate condition - simplified implementation"""
        # In production, this would use a safe expression evaluator
        return True  # Placeholder


class WorkflowEngine:
    """Main workflow execution engine"""
    
    def __init__(self, agent):
        self.agent = agent
        self.state_manager = get_global_state_manager()
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.handlers = {
            NodeType.CHAT: ChatNodeHandler(agent),
            NodeType.TOOL: ToolNodeHandler(agent),
            NodeType.CONDITION: ConditionNodeHandler()
        }
    
    def register_workflow(self, workflow_id: str, nodes: List[WorkflowNode], 
                         edges: List[WorkflowEdge], initial_state: Dict[str, Any] = None):
        """Register a new workflow"""
        self.workflows[workflow_id] = {
            "nodes": {node.id: node for node in nodes},
            "edges": edges,
            "initial_state": initial_state or {}
        }
    
    async def execute_workflow(self, workflow_id: str, input_data: Dict[str, Any] = None) -> WorkflowState:
        """Execute a workflow from start to completion"""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        
        # Initialize workflow state
        state = WorkflowState(
            workflow_id=workflow_id,
            current_node="start",
            state_data={**workflow["initial_state"], **(input_data or {})},
            execution_history=[],
            status=ExecutionStatus.RUNNING,
            timestamp=int(time.time() * 1000)
        )
        
        # Store initial state
        self.state_manager.set_component_state(f"workflow_{workflow_id}", asdict(state))
        
        try:
            while state.current_node != "end" and state.status == ExecutionStatus.RUNNING:
                # Execute current node
                command = await self._execute_node(state, workflow)
                
                # Update state based on command
                if command.update:
                    state.state_data.update(command.update)
                
                # Record execution history
                state.execution_history.append(state.current_node)
                
                # Move to next node
                state.current_node = command.goto
                state.timestamp = int(time.time() * 1000)
                
                # Update stored state for AG-UI synchronization
                self.state_manager.set_component_state(f"workflow_{workflow_id}", asdict(state))
                
                # Emit AG-UI events for real-time updates
                await self._emit_workflow_event("NODE_EXECUTED", state)
            
            # Mark as completed
            state.status = ExecutionStatus.COMPLETED
            self.state_manager.set_component_state(f"workflow_{workflow_id}", asdict(state))
            
            return state
            
        except Exception as e:
            state.status = ExecutionStatus.FAILED
            state.state_data["error"] = str(e)
            self.state_manager.set_component_state(f"workflow_{workflow_id}", asdict(state))
            raise
    
    async def _execute_node(self, state: WorkflowState, workflow: Dict[str, Any]) -> WorkflowCommand:
        """Execute a single workflow node"""
        node = workflow["nodes"].get(state.current_node)
        if not node:
            return WorkflowCommand(goto="end", update={"error": f"Node {state.current_node} not found"})
        
        # Handle special nodes
        if node.type == NodeType.START:
            # Find first edge from start node
            next_node = self._find_next_node(state.current_node, workflow["edges"])
            return WorkflowCommand(goto=next_node)
        
        if node.type == NodeType.END:
            return WorkflowCommand(goto="end")
        
        # Execute handler for node type
        handler = self.handlers.get(node.type)
        if not handler:
            return WorkflowCommand(goto="end", update={"error": f"No handler for node type {node.type}"})
        
        return await handler.execute(state, node.config)
    
    def _find_next_node(self, current_node: str, edges: List[WorkflowEdge]) -> str:
        """Find the next node to execute based on edges"""
        for edge in edges:
            if edge.source == current_node:
                return edge.target
        return "end"
    
    async def _emit_workflow_event(self, event_type: str, state: WorkflowState):
        """Emit workflow event for AG-UI integration"""
        event_data = {
            "type": event_type,
            "workflow_id": state.workflow_id,
            "current_node": state.current_node,
            "state_data": state.state_data,
            "timestamp": state.timestamp
        }
        
        # This would integrate with Agent Zero's logging system
        if hasattr(self.agent, 'context') and hasattr(self.agent.context, 'log'):
            self.agent.context.log.log(
                type="workflow_event",
                heading=f"Workflow Event: {event_type}",
                content=json.dumps(event_data, indent=2)
            )
    
    def get_workflow_canvas_data(self, workflow_id: str) -> Dict[str, Any]:
        """Generate AG-UI canvas data for workflow visualization"""
        if workflow_id not in self.workflows:
            return {}
        
        workflow = self.workflows[workflow_id]
        
        # Convert nodes to canvas format
        canvas_nodes = []
        for node in workflow["nodes"].values():
            canvas_nodes.append({
                "id": node.id,
                "label": node.name,
                "position": node.position
            })
        
        # Convert edges to canvas format
        canvas_edges = []
        for edge in workflow["edges"]:
            canvas_edges.append({
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label or ""
            })
        
        return {
            "nodes": canvas_nodes,
            "edges": canvas_edges
        }


class WorkflowTool(Tool):
    """Agent Zero tool for executing workflows"""
    
    def __init__(self, agent, name: str, method: str | None, args: dict[str, str], message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        self.workflow_engine = WorkflowEngine(agent)
    
    async def execute(self, **kwargs) -> Response:
        """Execute workflow tool"""
        try:
            workflow_id = self.args.get("workflow_id")
            action = self.args.get("action", "execute")  # execute, create, visualize
            
            if action == "execute":
                input_data = json.loads(self.args.get("input_data", "{}"))
                state = await self.workflow_engine.execute_workflow(workflow_id, input_data)
                
                return Response(
                    message=f"Workflow {workflow_id} executed successfully. Final state: {state.state_data}",
                    break_loop=False
                )
            
            elif action == "visualize":
                canvas_data = self.workflow_engine.get_workflow_canvas_data(workflow_id)
                
                # Generate AG-UI canvas component
                canvas_spec = {
                    "type": "canvas",
                    "properties": {
                        "nodes": canvas_data["nodes"],
                        "edges": canvas_data["edges"],
                        "width": "100%",
                        "height": "400px"
                    }
                }
                
                # This would use the existing AG-UI tool to render the canvas
                return Response(
                    message=f"Workflow visualization for {workflow_id}: {json.dumps(canvas_spec)}",
                    break_loop=False
                )
            
            else:
                return Response(
                    message=f"Unknown workflow action: {action}",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Workflow execution failed: {str(e)}",
                break_loop=False
            )


# Integration helper functions
def create_document_workflow(agent) -> str:
    """Create a document editing workflow similar to the LangGraph example"""
    workflow_id = f"document_workflow_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="chat_node", 
            type=NodeType.CHAT,
            name="Chat Node",
            handler="chat_handler",
            config={
                "system_prompt": "You are a helpful assistant for writing documents. To write the document, you MUST use the write_document tool.",
                "tools": ["write_document", "confirm_changes"]
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler", 
            position={"x": 500, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_chat", "start", "chat_node"),
        WorkflowEdge("chat_to_end", "chat_node", "end")
    ]
    
    initial_state = {
        "document": None,
        "messages": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_agentic_chat_workflow(agent) -> str:
    """Create a simple agentic chat workflow using ReAct pattern"""
    workflow_id = f"agentic_chat_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="chat_node",
            type=NodeType.CHAT,
            name="Agentic Chat",
            handler="chat_handler",
            config={
                "system_prompt": "You are a helpful assistant.",
                "tools": ["*"],  # All available tools
                "parallel_tool_calls": False,
                "model": "gpt-4o"
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 500, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_chat", "start", "chat_node"),
        WorkflowEdge("chat_to_end", "chat_node", "end")
    ]
    
    initial_state = {
        "messages": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_recipe_workflow(agent) -> str:
    """Create a recipe improvement workflow"""
    workflow_id = f"recipe_workflow_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="analyze_recipe",
            type=NodeType.CHAT,
            name="Analyze Recipe", 
            handler="chat_handler",
            config={
                "system_prompt": "Analyze the current recipe and identify areas for improvement.",
                "tools": ["analyze_nutrition", "suggest_improvements"]
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="improve_recipe",
            type=NodeType.CHAT,
            name="Improve Recipe",
            handler="chat_handler", 
            config={
                "system_prompt": "Improve the recipe based on analysis and user preferences.",
                "tools": ["update_recipe", "validate_recipe"]
            },
            position={"x": 500, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End", 
            handler="end_handler",
            position={"x": 700, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_analyze", "start", "analyze_recipe"),
        WorkflowEdge("analyze_to_improve", "analyze_recipe", "improve_recipe"),
        WorkflowEdge("improve_to_end", "improve_recipe", "end")
    ]
    
    initial_state = {
        "recipe": {
            "title": "",
            "ingredients": [],
            "instructions": [],
            "skill_level": "intermediate",
            "cooking_time": "30 min"
        },
        "preferences": []
    }
    
    engine = WorkflowEngine(agent) 
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_multi_agent_workflow(agent) -> str:
    """Create a multi-agent collaborative workflow"""
    workflow_id = f"multi_agent_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="coordinator",
            type=NodeType.CHAT,
            name="Coordinator",
            handler="chat_handler",
            config={
                "system_prompt": "You are a coordinator that delegates tasks to specialist agents.",
                "tools": ["call_subordinate", "delegate_task"]
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="specialist_decision",
            type=NodeType.CONDITION,
            name="Route to Specialist",
            handler="condition_handler",
            config={
                "condition": "task_type == 'code'",
                "true_node": "code_specialist",
                "false_node": "general_specialist"
            },
            position={"x": 500, "y": 100}
        ),
        WorkflowNode(
            id="code_specialist",
            type=NodeType.CHAT,
            name="Code Specialist",
            handler="chat_handler",
            config={
                "system_prompt": "You are a coding specialist. Focus on code-related tasks.",
                "tools": ["code_execution_tool", "code_analysis"]
            },
            position={"x": 700, "y": 50}
        ),
        WorkflowNode(
            id="general_specialist",
            type=NodeType.CHAT,
            name="General Specialist",
            handler="chat_handler",
            config={
                "system_prompt": "You are a general assistant for non-coding tasks.",
                "tools": ["search_engine", "document_query"]
            },
            position={"x": 700, "y": 150}
        ),
        WorkflowNode(
            id="consolidate",
            type=NodeType.CHAT,
            name="Consolidate Results",
            handler="chat_handler",
            config={
                "system_prompt": "Consolidate results from specialist agents and provide final response.",
                "tools": ["response"]
            },
            position={"x": 900, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 1100, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_coordinator", "start", "coordinator"),
        WorkflowEdge("coordinator_to_decision", "coordinator", "specialist_decision"),
        WorkflowEdge("decision_to_code", "specialist_decision", "code_specialist"),
        WorkflowEdge("decision_to_general", "specialist_decision", "general_specialist"),
        WorkflowEdge("code_to_consolidate", "code_specialist", "consolidate"),
        WorkflowEdge("general_to_consolidate", "general_specialist", "consolidate"),
        WorkflowEdge("consolidate_to_end", "consolidate", "end")
    ]
    
    initial_state = {
        "task": "",
        "task_type": "general",
        "specialist_results": [],
        "messages": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_data_analysis_workflow(agent) -> str:
    """Create a data analysis workflow with visualization"""
    workflow_id = f"data_analysis_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="data_ingestion",
            type=NodeType.TOOL,
            name="Data Ingestion",
            handler="tool_handler",
            config={
                "tool_name": "data_loader",
                "tool_args": {"source": "user_upload"}
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="data_validation",
            type=NodeType.CONDITION,
            name="Validate Data",
            handler="condition_handler",
            config={
                "condition": "data_valid == True",
                "true_node": "analyze_data",
                "false_node": "data_error"
            },
            position={"x": 500, "y": 100}
        ),
        WorkflowNode(
            id="analyze_data",
            type=NodeType.CHAT,
            name="Analyze Data",
            handler="chat_handler",
            config={
                "system_prompt": "Analyze the provided data and generate insights.",
                "tools": ["statistical_analysis", "pattern_detection"]
            },
            position={"x": 700, "y": 100}
        ),
        WorkflowNode(
            id="create_visualization",
            type=NodeType.TOOL,
            name="Create Visualization",
            handler="tool_handler",
            config={
                "tool_name": "ag_ui_tool",
                "tool_args": {
                    "component_type": "chart",
                    "chart_type": "dynamic"
                }
            },
            position={"x": 900, "y": 100}
        ),
        WorkflowNode(
            id="data_error",
            type=NodeType.CHAT,
            name="Handle Data Error",
            handler="chat_handler",
            config={
                "system_prompt": "Handle data validation errors and provide feedback.",
                "tools": ["error_reporting"]
            },
            position={"x": 500, "y": 200}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 1100, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_ingestion", "start", "data_ingestion"),
        WorkflowEdge("ingestion_to_validation", "data_ingestion", "data_validation"),
        WorkflowEdge("validation_to_analysis", "data_validation", "analyze_data"),
        WorkflowEdge("validation_to_error", "data_validation", "data_error"),
        WorkflowEdge("analysis_to_visualization", "analyze_data", "create_visualization"),
        WorkflowEdge("visualization_to_end", "create_visualization", "end"),
        WorkflowEdge("error_to_end", "data_error", "end")
    ]
    
    initial_state = {
        "data": None,
        "data_valid": False,
        "analysis_results": {},
        "visualization_config": {},
        "messages": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_generative_ui_workflow(agent) -> str:
    """Create a tool-based generative UI workflow (like haiku + images generation)"""
    workflow_id = f"generative_ui_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="chat_node",
            type=NodeType.CHAT,
            name="Generative Chat",
            handler="chat_handler",
            config={
                "system_prompt": """You assist the user in generating creative content.
                Use available tools to generate structured content like haiku, poems, stories, or other creative works.
                When generating content, also select relevant images, media, or visual elements to enhance the user experience.
                Stream tool calls to provide real-time feedback as content is being generated.""",
                "tools": ["generate_haiku", "generate_story", "generate_poem", "select_images", "create_gallery"],
                "emit_intermediate_state": True,
                "parallel_tool_calls": False
            },
            position={"x": 300, "y": 100}
        ),
        WorkflowNode(
            id="render_content",
            type=NodeType.TOOL,
            name="Render Generated Content",
            handler="tool_handler",
            config={
                "tool_name": "ag_ui_tool",
                "tool_args": {
                    "component_type": "container",
                    "layout": "creative_showcase"
                }
            },
            position={"x": 500, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 700, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_chat", "start", "chat_node"),
        WorkflowEdge("chat_to_render", "chat_node", "render_content"),
        WorkflowEdge("render_to_end", "render_content", "end")
    ]
    
    initial_state = {
        "generated_content": {},
        "selected_media": [],
        "content_type": "haiku",
        "theme": "",
        "messages": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_enhanced_document_workflow(agent) -> str:
    """Create an enhanced document editing workflow with confirmation and streaming"""
    workflow_id = f"enhanced_document_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="start_flow",
            type=NodeType.CONDITION,
            name="Route to Chat",
            handler="condition_handler",
            config={
                "condition": "True",  # Always route to chat
                "true_node": "chat_node",
                "false_node": "end"
            },
            position={"x": 250, "y": 100}
        ),
        WorkflowNode(
            id="chat_node",
            type=NodeType.CHAT,
            name="Document Chat",
            handler="chat_handler",
            config={
                "system_prompt": """You are a helpful assistant for writing documents. 
                To write the document, you MUST use the write_document tool.
                You MUST write the full document, even when changing only a few words.
                When you wrote the document, DO NOT repeat it as a message. 
                Just briefly summarize the changes you made. 2 sentences max.""",
                "tools": ["write_document", "confirm_changes"],
                "emit_intermediate_state": [{
                    "state_key": "document",
                    "tool": "write_document", 
                    "tool_argument": "document"
                }],
                "parallel_tool_calls": False
            },
            position={"x": 400, "y": 100}
        ),
        WorkflowNode(
            id="process_tool_calls",
            type=NodeType.CONDITION,
            name="Process Tool Calls",
            handler="condition_handler",
            config={
                "condition": "tool_call_name == 'write_document'",
                "true_node": "handle_document_write",
                "false_node": "end"
            },
            position={"x": 550, "y": 100}
        ),
        WorkflowNode(
            id="handle_document_write",
            type=NodeType.TOOL,
            name="Handle Document Write",
            handler="tool_handler",
            config={
                "tool_name": "document_processor",
                "tool_args": {
                    "action": "process_write",
                    "add_confirmation": True
                }
            },
            position={"x": 700, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 850, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_flow", "start", "start_flow"),
        WorkflowEdge("flow_to_chat", "start_flow", "chat_node"),
        WorkflowEdge("chat_to_process", "chat_node", "process_tool_calls"),
        WorkflowEdge("process_to_handle", "process_tool_calls", "handle_document_write"),
        WorkflowEdge("process_to_end", "process_tool_calls", "end"),
        WorkflowEdge("handle_to_end", "handle_document_write", "end"),
        WorkflowEdge("flow_to_end", "start_flow", "end")
    ]
    
    initial_state = {
        "document": None,
        "messages": [],
        "tool_calls": [],
        "confirmations": []
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_human_in_loop_workflow(agent) -> str:
    """Create a human-in-the-loop workflow with multiple confirmation stages"""
    workflow_id = f"human_in_loop_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="start_flow",
            type=NodeType.TOOL,
            name="Initialize Flow",
            handler="tool_handler",
            config={
                "tool_name": "flow_initializer",
                "delay": 2000,  # 2 second delay
                "next_node": "buffer_node"
            },
            position={"x": 250, "y": 100}
        ),
        WorkflowNode(
            id="buffer_node",
            type=NodeType.CHAT,
            name="Process Request",
            handler="chat_handler",
            config={
                "system_prompt": """You are a helpful assistant that answers user's questions. 
                Make sure the response is concise and to the point. 
                The response format should strictly be in markdown format.""",
                "tools": [],
                "model": "gpt-4o-mini",
                "delay": 1000,  # 1 second delay
                "parallel_tool_calls": False
            },
            position={"x": 400, "y": 100}
        ),
        WorkflowNode(
            id="confirming_response_node",
            type=NodeType.TOOL,
            name="Confirm Response",
            handler="tool_handler",
            config={
                "tool_name": "human_confirmation",
                "confirmation_type": "response_review",
                "delay": 2000,  # 2 second delay
                "next_node": "reporting_node"
            },
            position={"x": 550, "y": 100}
        ),
        WorkflowNode(
            id="reporting_node",
            type=NodeType.TOOL,
            name="Generate Report",
            handler="tool_handler",
            config={
                "tool_name": "report_generator",
                "delay": 2000,  # 2 second delay
                "final_step": True
            },
            position={"x": 700, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 850, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_flow", "start", "start_flow"),
        WorkflowEdge("flow_to_buffer", "start_flow", "buffer_node"),
        WorkflowEdge("buffer_to_confirm", "buffer_node", "confirming_response_node"),
        WorkflowEdge("confirm_to_report", "confirming_response_node", "reporting_node"),
        WorkflowEdge("report_to_end", "reporting_node", "end")
    ]
    
    initial_state = {
        "messages": [],
        "confirmations": [],
        "reports": [],
        "human_interventions": [],
        "current_stage": "initializing"
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id


def create_approval_workflow(agent) -> str:
    """Create a workflow with multiple approval checkpoints"""
    workflow_id = f"approval_workflow_{uuid.uuid4().hex[:8]}"
    
    nodes = [
        WorkflowNode(
            id="start",
            type=NodeType.START,
            name="Start",
            handler="start_handler",
            position={"x": 100, "y": 100}
        ),
        WorkflowNode(
            id="draft_generation",
            type=NodeType.CHAT,
            name="Generate Draft",
            handler="chat_handler",
            config={
                "system_prompt": "Generate a draft response or solution based on the user's request.",
                "tools": ["draft_generator", "content_analyzer"]
            },
            position={"x": 250, "y": 100}
        ),
        WorkflowNode(
            id="first_approval",
            type=NodeType.CONDITION,
            name="First Approval Check",
            handler="condition_handler",
            config={
                "condition": "user_approved == True",
                "true_node": "refinement",
                "false_node": "revision_needed",
                "requires_human_input": True,
                "approval_type": "draft_review"
            },
            position={"x": 400, "y": 100}
        ),
        WorkflowNode(
            id="revision_needed",
            type=NodeType.CHAT,
            name="Handle Revisions",
            handler="chat_handler",
            config={
                "system_prompt": "Based on user feedback, revise the draft to address their concerns.",
                "tools": ["revision_handler", "feedback_processor"]
            },
            position={"x": 400, "y": 200}
        ),
        WorkflowNode(
            id="refinement",
            type=NodeType.CHAT,
            name="Refine Content",
            handler="chat_handler",
            config={
                "system_prompt": "Refine and polish the approved draft for final presentation.",
                "tools": ["content_refiner", "quality_checker"]
            },
            position={"x": 550, "y": 100}
        ),
        WorkflowNode(
            id="final_approval",
            type=NodeType.CONDITION,
            name="Final Approval",
            handler="condition_handler",
            config={
                "condition": "final_approved == True",
                "true_node": "delivery",
                "false_node": "revision_needed",
                "requires_human_input": True,
                "approval_type": "final_review"
            },
            position={"x": 700, "y": 100}
        ),
        WorkflowNode(
            id="delivery",
            type=NodeType.TOOL,
            name="Deliver Result",
            handler="tool_handler",
            config={
                "tool_name": "result_delivery",
                "delivery_format": "comprehensive"
            },
            position={"x": 850, "y": 100}
        ),
        WorkflowNode(
            id="end",
            type=NodeType.END,
            name="End",
            handler="end_handler",
            position={"x": 1000, "y": 100}
        )
    ]
    
    edges = [
        WorkflowEdge("start_to_draft", "start", "draft_generation"),
        WorkflowEdge("draft_to_first_approval", "draft_generation", "first_approval"),
        WorkflowEdge("first_approval_to_refinement", "first_approval", "refinement"),
        WorkflowEdge("first_approval_to_revision", "first_approval", "revision_needed"),
        WorkflowEdge("revision_to_first_approval", "revision_needed", "first_approval"),
        WorkflowEdge("refinement_to_final_approval", "refinement", "final_approval"),
        WorkflowEdge("final_approval_to_delivery", "final_approval", "delivery"),
        WorkflowEdge("final_approval_to_revision", "final_approval", "revision_needed"),
        WorkflowEdge("delivery_to_end", "delivery", "end")
    ]
    
    initial_state = {
        "messages": [],
        "draft_content": "",
        "user_feedback": [],
        "approval_status": {
            "first_approval": "pending",
            "final_approval": "pending"
        },
        "revision_count": 0,
        "current_stage": "drafting"
    }
    
    engine = WorkflowEngine(agent)
    engine.register_workflow(workflow_id, nodes, edges, initial_state)
    
    return workflow_id