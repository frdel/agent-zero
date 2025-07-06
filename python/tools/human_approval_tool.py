"""
Human Approval Tool for Agent Zero
Handles human-in-the-loop workflows with confirmation and approval stages
"""

import json
import time
import asyncio
from typing import Dict, Any, List

from python.helpers.tool import Tool, Response


class HumanApprovalTool(Tool):
    """
    A tool for managing human approvals and confirmations in workflows.
    Demonstrates the human-in-the-loop pattern from LangGraph examples.
    """

    def __init__(self, agent, name: str, method: str | None, args: dict[str, str], message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Store pending approvals
        self.pending_approvals = {}
        self.approval_history = []

    async def execute(self, **kwargs) -> Response:
        """Execute the human approval tool"""
        try:
            action = self.args.get("action", "request_approval")
            
            if action == "request_approval":
                return await self._request_approval()
            elif action == "process_approval":
                return await self._process_approval()
            elif action == "list_pending":
                return await self._list_pending_approvals()
            elif action == "approval_status":
                return await self._get_approval_status()
            elif action == "create_checkpoint":
                return await self._create_approval_checkpoint()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available actions: request_approval, process_approval, list_pending, approval_status, create_checkpoint",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Human approval tool failed: {str(e)}",
                break_loop=False
            )

    async def _request_approval(self) -> Response:
        """Request human approval for a decision or action"""
        
        approval_type = self.args.get("approval_type", "general")
        content = self.args.get("content", "")
        urgency = self.args.get("urgency", "normal")
        
        # Generate unique approval ID
        approval_id = f"approval_{int(time.time() * 1000)}"
        
        # Store approval request
        approval_request = {
            "id": approval_id,
            "type": approval_type,
            "content": content,
            "urgency": urgency,
            "requested_at": int(time.time() * 1000),
            "status": "pending",
            "timeout": self.args.get("timeout", 300000)  # 5 minutes default
        }
        
        self.pending_approvals[approval_id] = approval_request
        
        # Create AG-UI approval interface
        approval_interface = {
            "type": "container",
            "properties": {
                "layout": "vertical",
                "class": "approval-request"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"## Human Approval Required",
                        "variant": "heading"
                    }
                },
                {
                    "type": "card",
                    "properties": {
                        "title": f"Approval Type: {approval_type.title()}",
                        "content": f"**Request ID:** {approval_id}\n\n**Content:**\n{content}\n\n**Urgency:** {urgency.upper()}"
                    }
                },
                {
                    "type": "container",
                    "properties": {
                        "layout": "horizontal",
                        "class": "approval-actions"
                    },
                    "children": [
                        {
                            "type": "button",
                            "properties": {
                                "label": "✅ Approve",
                                "variant": "success"
                            },
                            "events": {
                                "click": f"window.processApproval('{approval_id}', 'approved')"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "❌ Reject",
                                "variant": "danger"
                            },
                            "events": {
                                "click": f"window.processApproval('{approval_id}', 'rejected')"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "💬 Request Changes",
                                "variant": "warning"
                            },
                            "events": {
                                "click": f"window.requestChanges('{approval_id}')"
                            }
                        }
                    ]
                },
                {
                    "type": "textarea",
                    "id": f"feedback-{approval_id}",
                    "properties": {
                        "placeholder": "Optional feedback or comments...",
                        "rows": 3
                    }
                },
                {
                    "type": "progress",
                    "properties": {
                        "value": 0,
                        "max": 100,
                        "label": "Waiting for human response...",
                        "variant": "info",
                        "animated": True
                    }
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Human Approval Request",
            content=json.dumps({
                "ui_components": approval_interface,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0",
                "approval_data": approval_request
            })
        )
        
        return Response(
            message=f"🤝 Human approval requested!\n\n**ID:** {approval_id}\n**Type:** {approval_type}\n**Urgency:** {urgency}\n\nUse the interactive approval interface above to respond.",
            break_loop=True  # Pause workflow until approval received
        )

    async def _process_approval(self) -> Response:
        """Process a human approval response"""
        
        approval_id = self.args.get("approval_id")
        decision = self.args.get("decision", "approved")  # approved, rejected, changes_requested
        feedback = self.args.get("feedback", "")
        
        if not approval_id or approval_id not in self.pending_approvals:
            return Response(
                message=f"Approval ID {approval_id} not found",
                break_loop=False
            )
        
        # Update approval status
        approval = self.pending_approvals[approval_id]
        approval["status"] = decision
        approval["feedback"] = feedback
        approval["processed_at"] = int(time.time() * 1000)
        approval["processing_time"] = approval["processed_at"] - approval["requested_at"]
        
        # Move to history
        self.approval_history.append(approval)
        del self.pending_approvals[approval_id]
        
        # Create result interface
        result_interface = {
            "type": "container",
            "properties": {
                "layout": "vertical"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"## Approval Processed",
                        "variant": "heading"
                    }
                },
                {
                    "type": "card",
                    "properties": {
                        "title": f"Decision: {decision.title()}",
                        "content": f"**Request ID:** {approval_id}\n**Processing Time:** {approval['processing_time']}ms\n**Feedback:** {feedback or 'None provided'}"
                    }
                },
                {
                    "type": "progress",
                    "properties": {
                        "value": 100,
                        "max": 100,
                        "label": f"Approval {decision}",
                        "variant": "success" if decision == "approved" else "warning" if decision == "changes_requested" else "danger"
                    }
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Approval Decision",
            content=json.dumps({
                "ui_components": result_interface,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0",
                "approval_result": approval
            })
        )
        
        return Response(
            message=f"✅ Approval {approval_id} has been {decision}!\n\nProcessing time: {approval['processing_time']}ms\nFeedback: {feedback or 'None'}",
            break_loop=False
        )

    async def _list_pending_approvals(self) -> Response:
        """List all pending approval requests"""
        
        if not self.pending_approvals:
            return Response(
                message="No pending approvals",
                break_loop=False
            )
        
        # Create approval dashboard
        approval_list = []
        for approval_id, approval in self.pending_approvals.items():
            time_waiting = int(time.time() * 1000) - approval["requested_at"]
            approval_list.append({
                "type": "card",
                "properties": {
                    "title": f"{approval['type'].title()} - {approval_id}",
                    "content": f"**Content:** {approval['content'][:100]}...\n**Waiting:** {time_waiting}ms\n**Urgency:** {approval['urgency']}"
                }
            })
        
        dashboard = {
            "type": "container",
            "properties": {
                "layout": "vertical"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"## Pending Approvals ({len(self.pending_approvals)})",
                        "variant": "heading"
                    }
                }
            ] + approval_list
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Pending Approvals Dashboard",
            content=json.dumps({
                "ui_components": dashboard,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message=f"📋 {len(self.pending_approvals)} pending approvals listed above",
            break_loop=False
        )

    async def _get_approval_status(self) -> Response:
        """Get status of a specific approval"""
        
        approval_id = self.args.get("approval_id")
        
        # Check pending approvals
        if approval_id in self.pending_approvals:
            approval = self.pending_approvals[approval_id]
            status = "pending"
        else:
            # Check history
            approval = next((a for a in self.approval_history if a["id"] == approval_id), None)
            status = approval["status"] if approval else "not_found"
        
        if not approval:
            return Response(
                message=f"Approval {approval_id} not found",
                break_loop=False
            )
        
        # Create status display
        status_display = {
            "type": "card",
            "properties": {
                "title": f"Approval Status: {approval_id}",
                "content": f"```json\n{json.dumps(approval, indent=2)}\n```"
            }
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Approval Status",
            content=json.dumps({
                "ui_components": status_display,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message=f"📊 Status for {approval_id}: {status}",
            break_loop=False
        )

    async def _create_approval_checkpoint(self) -> Response:
        """Create a workflow checkpoint requiring approval"""
        
        checkpoint_name = self.args.get("checkpoint_name", "workflow_checkpoint")
        workflow_state = self.args.get("workflow_state", "{}")
        
        try:
            state_data = json.loads(workflow_state)
        except json.JSONDecodeError:
            state_data = {"raw_state": workflow_state}
        
        # Create checkpoint interface
        checkpoint_interface = {
            "type": "container",
            "properties": {
                "layout": "vertical"
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"## Workflow Checkpoint: {checkpoint_name}",
                        "variant": "heading"
                    }
                },
                {
                    "type": "card",
                    "properties": {
                        "title": "Current Workflow State",
                        "content": f"```json\n{json.dumps(state_data, indent=2)}\n```"
                    }
                },
                {
                    "type": "container",
                    "properties": {
                        "layout": "horizontal"
                    },
                    "children": [
                        {
                            "type": "button",
                            "properties": {
                                "label": "Continue Workflow",
                                "variant": "primary"
                            },
                            "events": {
                                "click": f"window.continueWorkflow('{checkpoint_name}')"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "Pause & Review",
                                "variant": "secondary"
                            },
                            "events": {
                                "click": f"window.pauseWorkflow('{checkpoint_name}')"
                            }
                        },
                        {
                            "type": "button",
                            "properties": {
                                "label": "Modify State",
                                "variant": "warning"
                            },
                            "events": {
                                "click": f"window.modifyWorkflowState('{checkpoint_name}')"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Log the AG-UI component - properly formatted for Agent Zero's web interface
        self.agent.context.log.log(
            type="ag_ui",
            heading="Workflow Checkpoint",
            content=json.dumps({
                "ui_components": checkpoint_interface,  # Agent Zero expects object, not string
                "type": "ag_ui",
                "protocol_version": "1.0",
                "checkpoint_data": {
                    "name": checkpoint_name,
                    "state": state_data,
                    "timestamp": int(time.time() * 1000)
                }
            })
        )
        
        return Response(
            message=f"🚦 Workflow checkpoint '{checkpoint_name}' created!\n\nUse the interface above to continue, pause, or modify the workflow state.",
            break_loop=True  # Pause until human decision
        )