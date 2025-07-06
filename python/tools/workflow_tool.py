"""
Workflow Tool for Agent Zero
Enables creation, execution, and management of LangGraph-style workflows
"""

import json
import asyncio
from typing import Dict, Any, List

from python.helpers.tool import Tool, Response
from python.helpers.workflow_manager import (
    WorkflowEngine, 
    create_agentic_chat_workflow,
    create_document_workflow,
    create_recipe_workflow,
    create_multi_agent_workflow,
    create_data_analysis_workflow,
    create_generative_ui_workflow,
    create_enhanced_document_workflow,
    create_human_in_loop_workflow,
    create_approval_workflow
)


class WorkflowTool(Tool):
    """
    A tool for managing and executing Agent Zero workflows.
    Supports LangGraph-style state machine patterns with AG-UI integration.
    """

    def __init__(self, agent, name: str, method: str | None, args: dict[str, str], message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        self.workflow_engine = WorkflowEngine(agent)
        
        # Available workflow templates
        self.workflow_templates = {
            "agentic_chat": create_agentic_chat_workflow,
            "document_editing": create_document_workflow,
            "enhanced_document": create_enhanced_document_workflow,
            "generative_ui": create_generative_ui_workflow,
            "recipe_management": create_recipe_workflow,
            "multi_agent": create_multi_agent_workflow,
            "data_analysis": create_data_analysis_workflow,
            "human_in_loop": create_human_in_loop_workflow,
            "approval_workflow": create_approval_workflow
        }

    async def execute(self, **kwargs) -> Response:
        """Execute the workflow tool"""
        try:
            action = self.args.get("action", "list")
            
            if action == "list":
                return await self._list_workflows()
            elif action == "create":
                return await self._create_workflow()
            elif action == "execute":
                return await self._execute_workflow()
            elif action == "visualize":
                return await self._visualize_workflow()
            elif action == "status":
                return await self._get_workflow_status()
            elif action == "delete":
                return await self._delete_workflow()
            else:
                return Response(
                    message=f"Unknown workflow action: {action}. Available actions: list, create, execute, visualize, status, delete",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Workflow tool execution failed: {str(e)}",
                break_loop=False
            )

    async def _list_workflows(self) -> Response:
        """List available workflow templates and created workflows"""
        
        # Available templates
        templates_info = []
        for template_name, template_func in self.workflow_templates.items():
            templates_info.append({
                "name": template_name,
                "description": template_func.__doc__ or "No description available"
            })
        
        # Created workflows
        created_workflows = list(self.workflow_engine.workflows.keys())
        
        response_data = {
            "available_templates": templates_info,
            "created_workflows": created_workflows,
            "total_templates": len(templates_info),
            "total_workflows": len(created_workflows)
        }
        
        # Generate AG-UI component to display the information
        workflow_list_spec = {
            "type": "container",
            "properties": {
                "layout": "vertical",
                "class": "workflow-dashboard"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": "# Workflow Management Dashboard",
                        "variant": "heading"
                    }
                },
                {
                    "type": "card",
                    "properties": {
                        "title": "Available Workflow Templates",
                        "content": self._format_templates_content(templates_info)
                    }
                },
                {
                    "type": "card", 
                    "properties": {
                        "title": "Created Workflows",
                        "content": self._format_workflows_content(created_workflows)
                    }
                },
                {
                    "type": "button",
                    "properties": {
                        "label": "Create New Workflow",
                        "variant": "primary"
                    },
                    "events": {
                        "click": "window.showWorkflowCreator()"
                    }
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Workflow Dashboard",
            content=json.dumps({
                "ui_components": workflow_list_spec,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message=f"📊 Workflow Dashboard Created!\n\n**Available Templates:** {len(templates_info)}\n**Created Workflows:** {len(created_workflows)}\n\nUse the interactive dashboard above to manage workflows.",
            break_loop=False
        )

    async def _create_workflow(self) -> Response:
        """Create a new workflow from template"""
        template_name = self.args.get("template", "agentic_chat")
        
        if template_name not in self.workflow_templates:
            return Response(
                message=f"Unknown template: {template_name}. Available templates: {list(self.workflow_templates.keys())}",
                break_loop=False
            )
        
        try:
            # Create workflow from template
            template_func = self.workflow_templates[template_name]
            workflow_id = template_func(self.agent)
            
            # Get workflow data for visualization
            canvas_data = self.workflow_engine.get_workflow_canvas_data(workflow_id)
            
            # Generate AG-UI canvas to show the created workflow
            canvas_spec = {
                "type": "container",
                "properties": {
                    "layout": "vertical"
                },
                "children": [
                    {
                        "type": "text",
                        "properties": {
                            "content": f"## Workflow Created: {workflow_id}",
                            "variant": "heading"
                        }
                    },
                    {
                        "type": "canvas",
                        "properties": {
                            "nodes": canvas_data.get("nodes", []),
                            "edges": canvas_data.get("edges", []),
                            "width": "100%",
                            "height": "400px"
                        }
                    },
                    {
                        "type": "container",
                        "properties": {
                            "layout": "horizontal",
                            "class": "workflow-actions"
                        },
                        "children": [
                            {
                                "type": "button",
                                "properties": {
                                    "label": "Execute Workflow",
                                    "variant": "primary"
                                },
                                "events": {
                                    "click": f"window.executeWorkflow('{workflow_id}')"
                                }
                            },
                            {
                                "type": "button",
                                "properties": {
                                    "label": "Edit Workflow",
                                    "variant": "secondary"
                                },
                                "events": {
                                    "click": f"window.editWorkflow('{workflow_id}')"
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Log the AG-UI component - properly formatted for Agent Zero's web interface
            self.agent.context.log.log(
                type="ag_ui",
                heading="Workflow Created",
                content=json.dumps({
                    "ui_components": canvas_spec,  # Agent Zero expects object, not string
                    "type": "ag_ui",
                    "protocol_version": "1.0"
                })
            )
            
            return Response(
                message=f"✅ Workflow created successfully!\n\n**ID:** {workflow_id}\n**Template:** {template_name}\n**Nodes:** {len(canvas_data.get('nodes', []))}\n**Edges:** {len(canvas_data.get('edges', []))}\n\nUse the interactive visualization above to execute or edit the workflow.",
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Failed to create workflow: {str(e)}",
                break_loop=False
            )

    async def _execute_workflow(self) -> Response:
        """Execute an existing workflow"""
        workflow_id = self.args.get("workflow_id")
        if not workflow_id:
            return Response(
                message="workflow_id is required for execution",
                break_loop=False
            )
        
        input_data_str = self.args.get("input_data", "{}")
        try:
            input_data = json.loads(input_data_str)
        except json.JSONDecodeError:
            return Response(
                message=f"Invalid input_data JSON: {input_data_str}",
                break_loop=False
            )
        
        try:
            # Execute workflow
            final_state = await self.workflow_engine.execute_workflow(workflow_id, input_data)
            
            # Create progress visualization
            progress_spec = {
                "type": "container",
                "properties": {
                    "layout": "vertical"
                },
                "children": [
                    {
                        "type": "text",
                        "properties": {
                            "content": f"## Workflow Execution: {workflow_id}",
                            "variant": "heading"
                        }
                    },
                    {
                        "type": "progress",
                        "properties": {
                            "value": 100,
                            "max": 100,
                            "label": f"Status: {final_state.status.value}",
                            "variant": "success" if final_state.status.name == "COMPLETED" else "error"
                        }
                    },
                    {
                        "type": "card",
                        "properties": {
                            "title": "Execution History",
                            "content": " → ".join(final_state.execution_history)
                        }
                    },
                    {
                        "type": "card",
                        "properties": {
                            "title": "Final State Data",
                            "content": f"```json\n{json.dumps(final_state.state_data, indent=2)}\n```"
                        }
                    }
                ]
            }
            
            # Log the AG-UI component - properly formatted for Agent Zero's web interface
            self.agent.context.log.log(
                type="ag_ui",
                heading="Workflow Execution Results",
                content=json.dumps({
                    "ui_components": progress_spec,  # Agent Zero expects object, not string
                    "type": "ag_ui",
                    "protocol_version": "1.0"
                })
            )
            
            return Response(
                message=f"🚀 Workflow executed successfully!\n\n**Status:** {final_state.status.value}\n**Steps:** {len(final_state.execution_history)}\n**Current Node:** {final_state.current_node}\n\nSee the interactive results above for detailed execution information.",
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Workflow execution failed: {str(e)}",
                break_loop=False
            )

    async def _visualize_workflow(self) -> Response:
        """Visualize an existing workflow"""
        workflow_id = self.args.get("workflow_id")
        if not workflow_id:
            return Response(
                message="workflow_id is required for visualization",
                break_loop=False
            )
        
        try:
            canvas_data = self.workflow_engine.get_workflow_canvas_data(workflow_id)
            
            # Generate interactive canvas visualization
            canvas_spec = {
                "type": "container",
                "properties": {
                    "layout": "vertical"
                },
                "children": [
                    {
                        "type": "text",
                        "properties": {
                            "content": f"## Workflow Visualization: {workflow_id}",
                            "variant": "heading"
                        }
                    },
                    {
                        "type": "canvas",
                        "properties": {
                            "nodes": canvas_data.get("nodes", []),
                            "edges": canvas_data.get("edges", []),
                            "width": "100%",
                            "height": "500px"
                        }
                    },
                    {
                        "type": "card",
                        "properties": {
                            "title": "Workflow Statistics",
                            "content": f"**Nodes:** {len(canvas_data.get('nodes', []))}\n**Edges:** {len(canvas_data.get('edges', []))}\n**Type:** Graph-based workflow"
                        }
                    }
                ]
            }
            
            # Log the AG-UI component - properly formatted for Agent Zero's web interface
            self.agent.context.log.log(
                type="ag_ui",
                heading="Workflow Visualization",
                content=json.dumps({
                    "ui_components": canvas_spec,  # Agent Zero expects object, not string
                    "type": "ag_ui",
                    "protocol_version": "1.0"
                })
            )
            
            return Response(
                message=f"📊 Workflow visualization generated for {workflow_id}!\n\nUse the interactive canvas above to explore the workflow structure.",
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Failed to visualize workflow: {str(e)}",
                break_loop=False
            )

    async def _get_workflow_status(self) -> Response:
        """Get status of a workflow"""
        workflow_id = self.args.get("workflow_id")
        if not workflow_id:
            return Response(
                message="workflow_id is required for status check",
                break_loop=False
            )
        
        try:
            # Get workflow state from state manager
            state_data = self.workflow_engine.state_manager.get_component_state(f"workflow_{workflow_id}")
            
            if not state_data:
                return Response(
                    message=f"No execution state found for workflow {workflow_id}",
                    break_loop=False
                )
            
            # Create status display
            status_spec = {
                "type": "card",
                "properties": {
                    "title": f"Workflow Status: {workflow_id}",
                    "content": f"```json\n{json.dumps(state_data, indent=2)}\n```"
                }
            }
            
            # Log the AG-UI component - properly formatted for Agent Zero's web interface
            self.agent.context.log.log(
                type="ag_ui",
                heading="Workflow Status",
                content=json.dumps({
                    "ui_components": status_spec,  # Agent Zero expects object, not string
                    "type": "ag_ui",
                    "protocol_version": "1.0"
                })
            )
            
            return Response(
                message=f"📋 Status retrieved for workflow {workflow_id}",
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Failed to get workflow status: {str(e)}",
                break_loop=False
            )

    async def _delete_workflow(self) -> Response:
        """Delete a workflow"""
        workflow_id = self.args.get("workflow_id")
        if not workflow_id:
            return Response(
                message="workflow_id is required for deletion",
                break_loop=False
            )
        
        try:
            if workflow_id in self.workflow_engine.workflows:
                del self.workflow_engine.workflows[workflow_id]
                
                # Clean up state
                self.workflow_engine.state_manager.delete_component_state(f"workflow_{workflow_id}")
                
                return Response(
                    message=f"🗑️ Workflow {workflow_id} deleted successfully",
                    break_loop=False
                )
            else:
                return Response(
                    message=f"Workflow {workflow_id} not found",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Failed to delete workflow: {str(e)}",
                break_loop=False
            )

    def _format_templates_content(self, templates: List[Dict[str, str]]) -> str:
        """Format template information for display"""
        content = ""
        for template in templates:
            content += f"**{template['name']}**\n{template['description']}\n\n"
        return content

    def _format_workflows_content(self, workflows: List[str]) -> str:
        """Format workflow list for display"""
        if not workflows:
            return "No workflows created yet."
        
        content = ""
        for workflow in workflows:
            content += f"• {workflow}\n"
        return content