"""
Collaborative Tools for Agent Zero
Implements streaming progress, research mode, and real-time state sharing
"""

import json
import time
from typing import Dict, Any, List, Optional
from python.helpers.tool import Tool, Response
from python.helpers.collaborative_state import (
    collaborative_state_manager, 
    ProgressStatus, 
    StateType
)


class StreamingProgressTool(Tool):
    """
    Tool for creating and managing streaming progress indicators
    """
    
    async def execute(self, **kwargs) -> Response:
        """Execute streaming progress operations"""
        try:
            action = self.args.get("action", "create")
            
            if action == "create":
                return await self._create_progress()
            elif action == "update":
                return await self._update_progress()
            elif action == "complete":
                return await self._complete_progress()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: create, update, complete",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Streaming progress failed: {str(e)}",
                break_loop=False
            )
    
    async def _create_progress(self) -> Response:
        """Create a new streaming progress indicator"""
        user_id = self.args.get("user_id", "default_user")
        agent_id = self.args.get("agent_id", self.agent.agent_name)
        total_steps = self.args.get("total_steps", 5)
        initial_message = self.args.get("message", "Starting task...")
        
        # Create progress state
        progress_id = collaborative_state_manager.create_progress_state(
            user_id=user_id,
            agent_id=agent_id,
            total_steps=total_steps,
            initial_message=initial_message
        )
        
        # Generate AG-UI progress component
        progress_component = {
            "type": "container",
            "id": f"progress-{progress_id}",
            "properties": {
                "layout": "vertical",
                "progress_id": progress_id
            },
            "children": [
                {
                    "type": "text",
                    "properties": {
                        "content": f"**{initial_message}**",
                        "variant": "large"
                    }
                },
                {
                    "type": "progress",
                    "id": f"progress-bar-{progress_id}",
                    "properties": {
                        "value": 0,
                        "max": 100,
                        "label": "0%",
                        "variant": "primary"
                    }
                },
                {
                    "type": "text",
                    "id": f"progress-status-{progress_id}",
                    "properties": {
                        "content": f"Step 0 of {total_steps}",
                        "variant": "small"
                    }
                }
            ]
        }
        
        # Add real-time update script
        update_script = f"""
        <script>
        // Real-time progress updates for {progress_id}
        (function() {{
            const progressBar = document.getElementById('progress-bar-{progress_id}');
            const statusText = document.getElementById('progress-status-{progress_id}');
            
            // WebSocket or polling for real-time updates
            function updateProgress() {{
                fetch('/api/collaborative_state/{progress_id}')
                    .then(response => response.json())
                    .then(data => {{
                        if (data && data.data) {{
                            const progress = data.data;
                            if (progressBar) {{
                                progressBar.value = progress.progress_percentage;
                                progressBar.textContent = Math.round(progress.progress_percentage) + '%';
                            }}
                            if (statusText) {{
                                statusText.textContent = `Step ${{progress.completed_steps}} of ${{progress.total_steps}}: ${{progress.current_step}}`;
                            }}
                            
                            // Continue polling if not completed
                            if (progress.status !== 'completed' && progress.status !== 'error') {{
                                setTimeout(updateProgress, 1000);
                            }}
                        }}
                    }})
                    .catch(error => console.error('Progress update failed:', error));
            }}
            
            // Start polling
            setTimeout(updateProgress, 1000);
        }})();
        </script>
        """
        
        # Log as AG-UI component
        self.agent.context.log.log(
            type="ag_ui",
            heading="Streaming Progress Started",
            content=json.dumps(progress_component)
        )
        
        # Add update script
        self.agent.context.log.log(
            type="ag_ui",
            heading="Progress Updates",
            content=json.dumps({
                "ui_components": update_script,
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )
        
        return Response(
            message=f"✅ Streaming progress created: {progress_id}\\n\\nUse `update_progress('{progress_id}', step, message)` to update progress.",
            break_loop=False
        )
    
    async def _update_progress(self) -> Response:
        """Update existing progress"""
        progress_id = self.args.get("progress_id")
        completed_steps = self.args.get("completed_steps")
        current_step = self.args.get("current_step")
        message = self.args.get("message")
        status = self.args.get("status")
        
        if not progress_id:
            return Response(
                message="progress_id is required for update",
                break_loop=False
            )
        
        # Parse status if provided
        progress_status = None
        if status:
            try:
                progress_status = ProgressStatus(status)
            except ValueError:
                pass
        
        # Update the progress state
        success = collaborative_state_manager.update_progress(
            state_id=progress_id,
            completed_steps=completed_steps,
            current_step=current_step,
            message=message,
            status=progress_status
        )
        
        if success:
            return Response(
                message=f"✅ Progress updated: {progress_id}",
                break_loop=False
            )
        else:
            return Response(
                message=f"❌ Failed to update progress: {progress_id}",
                break_loop=False
            )
    
    async def _complete_progress(self) -> Response:
        """Complete progress indicator"""
        progress_id = self.args.get("progress_id")
        final_message = self.args.get("message", "Task completed successfully!")
        
        if not progress_id:
            return Response(
                message="progress_id is required for completion",
                break_loop=False
            )
        
        # Get current state to determine total steps
        state = collaborative_state_manager.get_state(progress_id)
        if not state:
            return Response(
                message=f"Progress state not found: {progress_id}",
                break_loop=False
            )
        
        total_steps = state["data"]["total_steps"]
        
        # Complete the progress
        collaborative_state_manager.update_progress(
            state_id=progress_id,
            completed_steps=total_steps,
            current_step=final_message,
            message=final_message,
            status=ProgressStatus.COMPLETED
        )
        
        return Response(
            message=f"✅ Progress completed: {progress_id}",
            break_loop=False
        )


class CollaborativeResearchTool(Tool):
    """
    Tool for collaborative research sessions
    """
    
    async def execute(self, **kwargs) -> Response:
        """Execute collaborative research operations"""
        try:
            action = self.args.get("action", "create")
            
            if action == "create":
                return await self._create_research_session()
            elif action == "join":
                return await self._join_research_session()
            elif action == "add_finding":
                return await self._add_finding()
            elif action == "get_session":
                return await self._get_research_session()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: create, join, add_finding, get_session",
                    break_loop=False
                )
                
        except Exception as e:
            return Response(
                message=f"Collaborative research failed: {str(e)}",
                break_loop=False
            )
    
    async def _create_research_session(self) -> Response:
        """Create a new collaborative research session"""
        user_id = self.args.get("user_id", "default_user")
        session_name = self.args.get("session_name", "Research Session")
        research_topic = self.args.get("research_topic", "General Research")
        collaboration_mode = self.args.get("collaboration_mode", "interactive")
        
        # Create research session
        session_id = collaborative_state_manager.create_research_session(
            user_id=user_id,
            session_name=session_name,
            research_topic=research_topic,
            collaboration_mode=collaboration_mode
        )
        
        # Generate AG-UI research interface
        research_component = {
            "type": "container",
            "id": f"research-{session_id}",
            "properties": {
                "layout": "vertical",
                "session_id": session_id
            },
            "children": [
                {
                    "type": "card",
                    "properties": {
                        "title": f"🔬 {session_name}",
                        "content": f"**Topic:** {research_topic}\\n**Mode:** {collaboration_mode}\\n**Session ID:** {session_id}"
                    }
                },
                {
                    "type": "container",
                    "id": f"research-findings-{session_id}",
                    "properties": {
                        "layout": "vertical"
                    },
                    "children": [
                        {
                            "type": "text",
                            "properties": {
                                "content": "**Research Findings:**",
                                "variant": "large"
                            }
                        },
                        {
                            "type": "text",
                            "id": f"findings-list-{session_id}",
                            "properties": {
                                "content": "*No findings yet. Start researching!*",
                                "variant": "small"
                            }
                        }
                    ]
                },
                {
                    "type": "button",
                    "properties": {
                        "label": "Add Finding",
                        "variant": "primary"
                    },
                    "events": {
                        "click": f"prompt('Enter your finding:').then(finding => {{ if(finding) fetch('/api/research_finding', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{session_id: '{session_id}', finding: finding}}) }}); }})"
                    }
                }
            ]
        }
        
        # Log as AG-UI component
        self.agent.context.log.log(
            type="ag_ui",
            heading="Collaborative Research Session",
            content=json.dumps(research_component)
        )
        
        return Response(
            message=f"✅ Research session created: {session_id}\\n\\n**Topic:** {research_topic}\\n**Share this ID with collaborators:** `{session_id}`",
            break_loop=False
        )
    
    async def _add_finding(self) -> Response:
        """Add a finding to research session"""
        session_id = self.args.get("session_id")
        user_id = self.args.get("user_id", "default_user")
        finding_text = self.args.get("finding")
        source = self.args.get("source", "manual")
        confidence = self.args.get("confidence", "medium")
        
        if not session_id or not finding_text:
            return Response(
                message="session_id and finding are required",
                break_loop=False
            )
        
        finding = {
            "text": finding_text,
            "source": source,
            "confidence": confidence,
            "type": "text"
        }
        
        success = collaborative_state_manager.add_research_finding(
            state_id=session_id,
            user_id=user_id,
            finding=finding
        )
        
        if success:
            return Response(
                message=f"✅ Finding added to research session: {session_id}",
                break_loop=False
            )
        else:
            return Response(
                message=f"❌ Failed to add finding to session: {session_id}",
                break_loop=False
            )


# Helper functions for easy use in agent code
def create_progress(agent, total_steps: int, message: str = "Starting task...") -> str:
    """Helper to create streaming progress indicator"""
    tool = StreamingProgressTool(agent=agent, args={
        "action": "create",
        "total_steps": total_steps,
        "message": message
    })
    response = tool.execute()
    # Extract progress_id from response (simplified)
    return f"progress_{int(time.time())}"

def update_progress(progress_id: str, step: int, message: str):
    """Helper to update progress"""
    collaborative_state_manager.update_progress(
        state_id=progress_id,
        completed_steps=step,
        current_step=message,
        message=message
    )

def complete_progress(progress_id: str, message: str = "Task completed!"):
    """Helper to complete progress"""
    collaborative_state_manager.update_progress(
        state_id=progress_id,
        status=ProgressStatus.COMPLETED,
        message=message
    )


class RealTimeStateTool(Tool):
    """
    Tool for real-time state sharing between users and agents
    """

    async def execute(self, **kwargs) -> Response:
        """Execute real-time state operations"""
        try:
            action = self.args.get("action", "create")

            if action == "create":
                return await self._create_shared_context()
            elif action == "update":
                return await self._update_shared_context()
            elif action == "get":
                return await self._get_shared_context()
            elif action == "share":
                return await self._share_context()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available: create, update, get, share",
                    break_loop=False
                )

        except Exception as e:
            return Response(
                message=f"Real-time state failed: {str(e)}",
                break_loop=False
            )

    async def _create_shared_context(self) -> Response:
        """Create shared context for real-time collaboration"""
        owner_id = self.args.get("owner_id", "default_user")
        context_type = self.args.get("context_type", "general")
        data = self.args.get("data", {})
        shared_with = self.args.get("shared_with", [])

        # Create shared context
        context_id = collaborative_state_manager.create_shared_context(
            owner_id=owner_id,
            context_type=context_type,
            data=data,
            shared_with=shared_with
        )

        # Generate AG-UI real-time interface
        realtime_component = {
            "type": "container",
            "id": f"realtime-{context_id}",
            "properties": {
                "layout": "vertical",
                "context_id": context_id
            },
            "children": [
                {
                    "type": "card",
                    "properties": {
                        "title": f"🔄 Real-time Context: {context_type}",
                        "content": f"**Context ID:** {context_id}\\n**Shared with:** {len(shared_with)} users"
                    }
                },
                {
                    "type": "text",
                    "id": f"context-data-{context_id}",
                    "properties": {
                        "content": f"```json\\n{json.dumps(data, indent=2)}\\n```",
                        "variant": "small"
                    }
                }
            ]
        }

        # Add real-time sync script
        sync_script = f"""
        <script>
        // Real-time context sync for {context_id}
        (function() {{
            const contextData = document.getElementById('context-data-{context_id}');
            let lastVersion = 1;

            function syncContext() {{
                fetch('/api/collaborative_state/{context_id}')
                    .then(response => response.json())
                    .then(data => {{
                        if (data && data.data && data.data.version > lastVersion) {{
                            lastVersion = data.data.version;
                            if (contextData) {{
                                contextData.innerHTML = '<pre><code>' + JSON.stringify(data.data.data, null, 2) + '</code></pre>';
                            }}
                        }}
                        // Continue syncing
                        setTimeout(syncContext, 2000);
                    }})
                    .catch(error => {{
                        console.error('Context sync failed:', error);
                        setTimeout(syncContext, 5000); // Retry after error
                    }});
            }}

            // Start syncing
            setTimeout(syncContext, 2000);
        }})();
        </script>
        """

        # Log components
        self.agent.context.log.log(
            type="ag_ui",
            heading="Real-time Shared Context",
            content=json.dumps(realtime_component)
        )

        self.agent.context.log.log(
            type="ag_ui",
            heading="Real-time Sync",
            content=json.dumps({
                "ui_components": sync_script,
                "type": "ag_ui",
                "protocol_version": "1.0"
            })
        )

        return Response(
            message=f"✅ Real-time context created: {context_id}\\n\\n**Type:** {context_type}\\n**Shared with:** {shared_with}",
            break_loop=False
        )

    async def _update_shared_context(self) -> Response:
        """Update shared context with real-time sync"""
        context_id = self.args.get("context_id")
        user_id = self.args.get("user_id", "default_user")
        updates = self.args.get("updates", {})

        if not context_id:
            return Response(
                message="context_id is required for update",
                break_loop=False
            )

        success = collaborative_state_manager.update_shared_context(
            state_id=context_id,
            user_id=user_id,
            updates=updates
        )

        if success:
            return Response(
                message=f"✅ Shared context updated: {context_id}",
                break_loop=False
            )
        else:
            return Response(
                message=f"❌ Failed to update context (check permissions): {context_id}",
                break_loop=False
            )


# Integration helpers for Agent Zero
def start_collaborative_task(agent, task_name: str, total_steps: int,
                           shared_context: Dict[str, Any] = None) -> Dict[str, str]:
    """
    Start a collaborative task with progress tracking and shared context
    Returns dict with progress_id and context_id
    """
    # Create progress indicator
    progress_tool = StreamingProgressTool(agent=agent, args={
        "action": "create",
        "total_steps": total_steps,
        "message": f"Starting {task_name}..."
    })
    progress_response = progress_tool.execute()
    progress_id = f"progress_{int(time.time())}"  # Simplified

    # Create shared context if provided
    context_id = None
    if shared_context:
        context_tool = RealTimeStateTool(agent=agent, args={
            "action": "create",
            "context_type": "task_context",
            "data": shared_context
        })
        context_response = context_tool.execute()
        context_id = f"context_{int(time.time())}"  # Simplified

    return {
        "progress_id": progress_id,
        "context_id": context_id,
        "task_name": task_name
    }
