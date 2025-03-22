from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
import uuid
import json
import time

class TeamAgent(Tool):
    """
    TeamAgent tool that integrates with the agent zero framework to manage
    collaborative agent teams.
    """
    
    async def execute(self, action="", team_id="", **kwargs):
        """
        Execute the TeamAgent tool with better integration with agent.py.
        
        Args:
            action: Action to perform (create, add_agent, assign_task, message, get_results)
            team_id: ID of the team (except for 'create' action)
            **kwargs: Additional arguments based on the action
        """
        # Parameter validation and normalization
        if not action and "action" in kwargs:
            action = kwargs.pop("action")
            self.log.update(progress=f"Normalized action parameter from kwargs: {action}")
            
        # Initialize teams data structure if not present
        if not self.agent.get_data("teams"):
            self.agent.set_data("teams", {})
            
        # Use active team if not explicitly provided
        if not team_id and action != "create" and self.agent.get_data("active_team_id"):
            team_id = self.agent.get_data("active_team_id")
            self.log.update(progress=f"Using active team ID: {team_id}")
            
        # Handle different actions
        if action == "create":
            return await self._create_team(**kwargs)
        # Handle actions with better logging
        try:
            if action == "create":
                return await self._create_team(**kwargs)
            elif action == "add_agent":
                self.log.update(progress=f"Adding agent to team {team_id}...")
                return await self._add_agent(team_id, **kwargs)
            elif action == "assign_task":
                self.log.update(progress=f"Assigning task to agent in team {team_id}...")
                return await self._assign_task(team_id, **kwargs)
            elif action == "execute_task":
                self.log.update(progress=f"Executing task in team {team_id}...")
                return await self._execute_task(team_id, **kwargs)
            elif action == "message":
                self.log.update(progress=f"Sending message in team {team_id}...")
                return await self._send_message(team_id, **kwargs)
            elif action == "get_results":
                self.log.update(progress=f"Getting results from team {team_id}...")
                return await self._get_results(team_id, **kwargs)
            elif action == "team_status":
                self.log.update(progress=f"Getting status for team {team_id}...")
                return await self._team_status(team_id, **kwargs)
            elif action == "integrate_results":
                self.log.update(progress=f"Integrating results from team {team_id}...")
                return await self._integrate_results(team_id, **kwargs)
            else:
                self.log.update(error=f"Unknown action: {action}")
                return Response(
                    message=self._format_response({
                        "error": f"Unknown action: {action}",
                        "available_actions": [
                            "create", "add_agent", "assign_task", 
                            "execute_task", "message", "get_results", 
                            "team_status", "integrate_results"
                        ]
                    }),
                    break_loop=False
                )
        except Exception as e:
            # Log the error and return a formatted response
            error_message = f"Error executing {action}: {str(e)}"
            self.log.update(error=error_message)
            
            return Response(
                message=self._format_response({
                    "error": error_message,
                    "action_attempted": action,
                    "next_step": "Check parameters and try again"
                }),
                break_loop=False
            )
        else:
            return Response(
                message=self._format_response({
                    "error": f"Unknown action: {action}",
                    "available_actions": [
                        "create", "add_agent", "assign_task", 
                        "execute_task", "message", "get_results", 
                        "team_status", "integrate_results"
                    ]
                }),
                break_loop=False
            )
            
    async def _create_team(self, name="Team", goal="Collaborate on a task", **kwargs):
        """Create a new team with a team leader agent"""
        team_id = f"team_{str(uuid.uuid4())[:8]}"
        
        # Create team leader agent - use the same number as the current agent 
        # to avoid numbering issues when creating subordinates
        team_leader = Agent(self.agent.number, self.agent.config, self.agent.context)
        team_leader.set_data("role", "team_leader")
        team_leader.set_data("team_id", team_id)
        team_leader.set_data("team_name", name)
        team_leader.set_data("team_goal", goal)
        team_leader.set_data("team_members", {})
        team_leader.set_data("tasks", {})
        team_leader.set_data("created_at", time.time())
        
        # Store team in agent's data
        teams = self.agent.get_data("teams")
        teams[team_id] = {
            "id": team_id,
            "name": name,
            "goal": goal,
            "leader_agent": team_leader,
            "created_at": time.time()
        }
        self.agent.set_data("teams", teams)
        
        # Set as the active team
        self.agent.set_data("active_team_id", team_id)
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "name": name,
                "goal": goal,
                "status": "created",
                "next_step": "Add specialized agents with the add_agent action"
            }),
            break_loop=False
        )
    
    async def _add_agent(self, team_id, role="member", skills=None, **kwargs):
        """Add a specialized agent to the team"""
        if skills is None:
            skills = []
            
        # Get team data
        teams = self.agent.get_data("teams")
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()) if teams else []
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        agent_id = f"agent_{str(uuid.uuid4())[:6]}"
        
        # Create a new agent instance - ensure we're using the next sequential number
        # Correcting the agent numbering to avoid skips
        new_agent = Agent(self.agent.number + 1, self.agent.config, self.agent.context)
        
        # Set agent properties
        new_agent.set_data("role", role)
        new_agent.set_data("skills", skills)
        new_agent.set_data("team_id", team_id)
        new_agent.set_data("agent_id", agent_id)
        new_agent.set_data("created_at", time.time())
        
        # Establish superior-subordinate relationship
        new_agent.set_data(Agent.DATA_NAME_SUPERIOR, team_leader)
        
        # Update team members registry
        team_members = team_leader.get_data("team_members") or {}
        team_members[agent_id] = {
            "role": role,
            "skills": skills,
            "agent": new_agent
        }
        team_leader.set_data("team_members", team_members)
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "agent_id": agent_id,
                "role": role,
                "status": "added",
                "next_step": "Assign a task to this agent with the assign_task action"
            }),
            break_loop=False
        )
    
    async def _assign_task(self, team_id, agent_id="", task="", context="", depends_on=None, **kwargs):
        """Assign a task to a team member"""
        if depends_on is None:
            depends_on = []
            
        # Get team data
        teams = self.agent.get_data("teams")
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()) if teams else []
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        # Get team members
        team_members = team_leader.get_data("team_members") or {}
        if not agent_id or agent_id not in team_members:
            return Response(
                message=self._format_response({
                    "error": f"Agent {agent_id} not found in team {team_id}",
                    "available_agents": list(team_members.keys()) if team_members else []
                }),
                break_loop=False
            )
        
        if not task:
            return Response(
                message=self._format_response({
                    "error": "Task description is required"
                }),
                break_loop=False
            )
        
        # Create task ID
        task_id = f"task_{str(uuid.uuid4())[:6]}"
        
        # Create task
        task_data = {
            "id": task_id,
            "agent_id": agent_id,
            "description": task,
            "context": context,
            "depends_on": depends_on,
            "status": "assigned",
            "created_at": time.time(),
            "completed_at": None,
            "result": None
        }
        
        # Store task in team leader's data
        tasks = team_leader.get_data("tasks") or {}
        tasks[task_id] = task_data
        team_leader.set_data("tasks", tasks)
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "agent_id": agent_id,
                "task_id": task_id,
                "status": "assigned",
                "next_step": "Execute this task with the execute_task action"
            }),
            break_loop=False
        )
    
    async def _execute_task(self, team_id, task_id="", **kwargs):
        """Execute a task with a specified team member"""
        self.log.update(progress="Executing task in team...")
        
        # Get team data
        teams = self.agent.get_data("teams")
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()) if teams else []
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        # Get tasks
        tasks = team_leader.get_data("tasks") or {}
        if not task_id or task_id not in tasks:
            return Response(
                message=self._format_response({
                    "error": f"Task {task_id} not found in team {team_id}",
                    "available_tasks": list(tasks.keys()) if tasks else []
                }),
                break_loop=False
            )
        
        task = tasks[task_id]
        agent_id = task["agent_id"]
        
        # Get team members
        team_members = team_leader.get_data("team_members") or {}
        if agent_id not in team_members:
            return Response(
                message=self._format_response({
                    "error": f"Agent {agent_id} not found in team {team_id}"
                }),
                break_loop=False
            )
        
        agent_instance = team_members[agent_id]["agent"]
        agent_role = team_members[agent_id]["role"]
        agent_skills = team_members[agent_id]["skills"]
        
        # Check for dependency status
        if task.get("depends_on") and not task.get("dependencies_met", False):
            # Check if dependencies are satisfied
            dependencies_met = True
            pending_deps = []
            
            for dep_id in task.get("depends_on", []):
                if dep_id not in tasks or tasks.get(dep_id, {}).get("status") != "completed":
                    dependencies_met = False
                    pending_deps.append(dep_id)
            
            if not dependencies_met:
                return Response(
                    message=self._format_response({
                        "error": "Task dependencies not met",
                        "pending_dependencies": pending_deps
                    }),
                    break_loop=False
                )
            
            # Collect dependency results for context
            dependency_context = ""
            for dep_id in task.get("depends_on", []):
                dep_task = tasks.get(dep_id, {})
                if dep_task.get("status") == "completed" and dep_task.get("result"):
                    dep_agent_id = dep_task.get("agent_id", "")
                    dep_agent_role = "unknown"
                    
                    if dep_agent_id in team_members:
                        dep_agent_role = team_members[dep_agent_id].get("role", "")
                    
                    dependency_context += f"\n--- DEPENDENCY RESULT FROM {dep_agent_role.upper()} (TASK {dep_id}) ---\n"
                    dependency_context += f"{dep_task.get('description')}\n\n"
                    dependency_context += f"{dep_task.get('result', '')}\n"
                    dependency_context += f"--- END OF DEPENDENCY RESULT ---\n"
            
            # Add dependency results to task context
            if dependency_context:
                if task["context"]:
                    task["context"] += f"\n\nRESULTS FROM DEPENDENCY TASKS:\n{dependency_context}"
                else:
                    task["context"] = f"RESULTS FROM DEPENDENCY TASKS:\n{dependency_context}"
            
            # Mark dependencies as met
            task["dependencies_met"] = True
            tasks[task_id] = task
            team_leader.set_data("tasks", tasks)
        
        # Update task status
        task["status"] = "executing"
        tasks[task_id] = task
        team_leader.set_data("tasks", tasks)
        
        # Build prompt for the agent
        prompt = f"""You are a {agent_role} agent with skills in {', '.join(agent_skills) if agent_skills else 'general tasks'}.
You are part of the {team_data['name']} team with the goal: {team_data['goal']}.

YOUR TASK (ID: {task_id}):
{task['description']}

ADDITIONAL CONTEXT:
{task['context']}

IMPORTANT: You must respond using the exact response format below:

```json
{{
    "thoughts": [
        "Your first thought about the task",
        "Your analysis process",
        "Your conclusions"
    ],
    "tool_name": "response",
    "tool_args": {{
        "text": "Your complete task result here. Be thorough and detailed. Include all relevant information."
    }}
}}
```

The "text" field should contain your complete analysis with all details, findings, and recommendations.
Do not use any other format or tool - only the response tool as shown above."""
        
        # Execute task using call_subordinate pattern
        # Let the user know we're delegating to a team member
        self.log.update(progress=f"Delegating to {agent_role} agent...")
        
        try:
            # Execute task using call_subordinate pattern
            await agent_instance.hist_add_user_message(UserMessage(message=prompt, attachments=[]))
            result = await agent_instance.monologue()
            self.log.update(progress=f"Received response from {agent_role} agent")
        except Exception as e:
            self.log.update(error=f"Error executing task: {str(e)}")
            result = f"Error executing task: {str(e)}"
        
        # Update task with result
        task["status"] = "completed"
        task["completed_at"] = time.time()
        task["result"] = result
        tasks[task_id] = task
        team_leader.set_data("tasks", tasks)
        
        # Find dependent tasks that can now be executed
        dependent_tasks = []
        for t_id, t_data in tasks.items():
            if task_id in t_data.get("depends_on", []) and t_data["status"] == "assigned":
                dependent_tasks.append(t_id)
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "status": "completed",
                "result_summary": result[:200] + "..." if len(result) > 200 else result,
                "dependent_tasks": dependent_tasks,
                "next_step": "Get final results with get_results action or execute dependent tasks"
            }),
            break_loop=False
        )
    
    async def _send_message(self, team_id, from_agent="", to_agent="", content="", **kwargs):
        """Send a message from one agent to another"""
        # Get team data
        teams = self.agent.get_data("teams")
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()) if teams else []
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        # Get team members
        team_members = team_leader.get_data("team_members") or {}
        if not from_agent or from_agent not in team_members:
            return Response(
                message=self._format_response({
                    "error": f"Source agent {from_agent} not found",
                    "available_agents": list(team_members.keys()) if team_members else []
                }),
                break_loop=False
            )
        
        if not to_agent or to_agent not in team_members:
            return Response(
                message=self._format_response({
                    "error": f"Target agent {to_agent} not found",
                    "available_agents": list(team_members.keys()) if team_members else []
                }),
                break_loop=False
            )
        
        if not content:
            return Response(
                message=self._format_response({
                    "error": "Message content is required"
                }),
                break_loop=False
            )
        
        # Create message ID
        message_id = f"msg_{str(uuid.uuid4())[:6]}"
        
        # Get agent instances
        from_role = team_members[from_agent]["role"]
        to_agent_instance = team_members[to_agent]["agent"]
        
        # Format the message
        formatted_message = f"[MESSAGE from {from_role} agent]: {content}"
        
        # Store message in recipient's pending messages
        pending_messages = to_agent_instance.get_data("pending_messages") or []
        pending_messages.append(formatted_message)
        to_agent_instance.set_data("pending_messages", pending_messages)
        
        # Store message in team history
        messages = team_leader.get_data("messages") or []
        message = {
            "id": message_id,
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "timestamp": time.time()
        }
        messages.append(message)
        team_leader.set_data("messages", messages)
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "message_id": message_id,
                "from": from_agent,
                "to": to_agent,
                "status": "delivered",
                "next_step": "The message will be delivered when the recipient agent executes its next task"
            }),
            break_loop=False
        )
    
    async def _get_results(self, team_id, **kwargs):
        """Get results from all tasks in a team"""
        # Add additional logging for debugging
        self.log.update(progress=f"Retrieving results for team {team_id}...")
        
        # Get team data with better error checking
        teams = self.agent.get_data("teams") or {}
        if not team_id or team_id not in teams:
            available_teams = list(teams.keys())
            error_msg = f"Team {team_id} not found"
            self.log.update(error=error_msg)
            
            if available_teams:
                self.log.update(progress=f"Available teams: {', '.join(available_teams)}")
                
            return Response(
                message=self._format_response({
                    "error": error_msg,
                    "available_teams": available_teams,
                    "next_step": "Create a team first with the 'create' action or use a valid team_id"
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        # Get tasks and team members
        tasks = team_leader.get_data("tasks") or {}
        team_members = team_leader.get_data("team_members") or {}
        
        # Organize results by agent and task
        results = {}
        completed_tasks = 0
        total_tasks = len(tasks)
        
        for task_id, task_data in tasks.items():
            agent_id = task_data["agent_id"]
            if agent_id not in results:
                agent_role = team_members[agent_id]["role"] if agent_id in team_members else "unknown"
                results[agent_id] = {
                    "role": agent_role,
                    "tasks": {}
                }
            
            # Add task result
            task_status = task_data["status"]
            if task_status == "completed":
                completed_tasks += 1
                
            results[agent_id]["tasks"][task_id] = {
                "description": task_data["description"],
                "status": task_status,
                "result": task_data.get("result", None) if task_status == "completed" else None
            }
        
        # Determine completion status
        completion_status = f"{completed_tasks}/{total_tasks} tasks completed"
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "name": team_data["name"],
                "goal": team_data["goal"],
                "completion": completion_status,
                "results": results
            }),
            break_loop=False
        )
    
    def _find_agent_by_role(self, team_id, role):
        """Helper to find agent by role instead of ID"""
        teams = self.agent.get_data("teams") or {}
        if team_id not in teams:
            return None
            
        team_leader = teams[team_id]["leader_agent"]
        team_members = team_leader.get_data("team_members") or {}
        
        for agent_id, agent_data in team_members.items():
            if agent_data["role"].lower() == role.lower():
                return agent_id
                
        return None
    
    async def _team_status(self, team_id, **kwargs):
        """Get comprehensive team status"""
        # Add progress logging
        self.log.update(progress=f"Getting status for team {team_id}...")
        
        # Get team data with better error checking
        teams = self.agent.get_data("teams") or {}
        if not team_id or team_id not in teams:
            available_teams = list(teams.keys())
            error_msg = f"Team {team_id} not found"
            self.log.update(error=error_msg)
            
            if available_teams:
                self.log.update(progress=f"Available teams: {', '.join(available_teams)}")
                
            return Response(
                message=self._format_response({
                    "error": error_msg,
                    "available_teams": available_teams,
                    "next_step": "Create a team first with the 'create' action or use a valid team_id"
                }),
                break_loop=False
            )
        
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        
        # Get tasks and team members
        tasks = team_leader.get_data("tasks") or {}
        team_members = team_leader.get_data("team_members") or {}
        messages = team_leader.get_data("messages") or []
        
        # Calculate statistics
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks.values() if t["status"] == "completed")
        in_progress_tasks = sum(1 for t in tasks.values() if t["status"] == "executing")
        pending_tasks = total_tasks - completed_tasks - in_progress_tasks
        
        # Organize agent workloads
        agent_workloads = {}
        for agent_id, agent_data in team_members.items():
            agent_tasks = [t for t in tasks.values() if t["agent_id"] == agent_id]
            agent_workloads[agent_id] = {
                "role": agent_data["role"],
                "total_tasks": len(agent_tasks),
                "completed": sum(1 for t in agent_tasks if t["status"] == "completed"),
                "in_progress": sum(1 for t in agent_tasks if t["status"] == "executing"),
                "pending": sum(1 for t in agent_tasks if t["status"] == "assigned")
            }
        
        # Map of tasks to their dependencies
        task_dependencies = {}
        for task_id, task_data in tasks.items():
            deps = task_data.get("depends_on", [])
            if deps:
                task_dependencies[task_id] = {
                    "depends_on": deps,
                    "description": task_data.get("description", ""),
                    "status": task_data.get("status", "unknown")
                }
        
        # Find next tasks to execute based on dependencies
        next_tasks = []
        for task_id, task_data in tasks.items():
            if task_data["status"] == "assigned":
                dependencies_ready = True
                for dep_id in task_data.get("depends_on", []):
                    if dep_id not in tasks or tasks[dep_id]["status"] != "completed":
                        dependencies_ready = False
                        break
                if dependencies_ready:
                    next_tasks.append(task_id)
        
        self.log.update(progress="Team status analysis complete")
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "name": team_data["name"],
                "goal": team_data["goal"],
                "statistics": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "in_progress_tasks": in_progress_tasks,
                    "pending_tasks": pending_tasks,
                    "agent_count": len(team_members),
                    "message_count": len(messages)
                },
                "agents": agent_workloads,
                "task_dependencies": task_dependencies,
                "next_executable_tasks": next_tasks,
                "workflow_status": "complete" if pending_tasks == 0 and in_progress_tasks == 0 else "in_progress"
            }),
            break_loop=False
        )
    
    def _format_response(self, data):
        """Format the response as a JSON string according to agent zero's requirements"""
        thoughts = [
            "Processed team agent request",
            "Generated appropriate response"
        ]
        
        # Add helpful next_step if not present
        if "error" in data and "next_step" not in data:
            if "available_teams" in data and data["available_teams"]:
                data["next_step"] = f"Use a valid team_id from: {', '.join(data['available_teams'])}"
            else:
                data["next_step"] = "Create a team first with the 'create' action"
        
        # Add specific formatting guidance for get_results response
        if "results" in data and "error" not in data:
            data["next_step"] = "Format your response to the user as a properly formatted JSON message using the response tool. Synthesize the individual contributions into a cohesive final product."
        
        formatted_response = {
            "thoughts": thoughts,
            "tool_name": "team_agent",
            "tool_args": data
        }
        
        return json.dumps(formatted_response, indent=2)

    async def _integrate_results(self, team_id, **kwargs):
        """Integrate results from all team members into a final product"""
        # Get team data
        teams = self.agent.get_data("teams") or {}
        if not team_id or team_id not in teams:
            available_teams = list(teams.keys())
            error_msg = f"Team {team_id} not found"
            self.log.update(error=error_msg)
            
            if available_teams:
                self.log.update(progress=f"Available teams: {', '.join(available_teams)}")
                
            return Response(
                message=self._format_response({
                    "error": error_msg,
                    "available_teams": available_teams,
                    "next_step": "Create a team first with the 'create' action or use a valid team_id"
                }),
                break_loop=False
            )
            
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        tasks = team_leader.get_data("tasks") or {}
        team_members = team_leader.get_data("team_members") or {}
        
        # Collect all completed results
        completed_results = {}
        for task_id, task_data in tasks.items():
            if task_data["status"] == "completed":
                agent_id = task_data["agent_id"]
                if agent_id in team_members:
                    role = team_members[agent_id]["role"]
                    completed_results[role] = {
                        "task": task_data["description"],
                        "result": task_data["result"]
                    }
        
        if not completed_results:
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "error": "No completed tasks found to integrate",
                    "next_step": "Execute tasks first with the execute_task action before attempting integration"
                }),
                break_loop=False
            )
        
        # Create integration prompt for team leader
        integration_prompt = f"""
        As the leader of the {team_data['name']} team, your task is to integrate the following contributions 
        into a coherent final product that fulfills the team goal: {team_data['goal']}
        
        TEAM CONTRIBUTIONS:
        {json.dumps(completed_results, indent=2)}
        
        Synthesize these contributions into a single cohesive response.
        
        IMPORTANT: You must respond using the exact response format below:
        
        ```json
        {{
            "thoughts": [
                "Your thought process for integration",
                "How you combined the different contributions",
                "Your final evaluation of the integrated result"
            ],
            "tool_name": "response",
            "tool_args": {{
                "text": "Your complete integrated result here. Be thorough and properly formatted."
            }}
        }}
        ```
        """
        
        # Let team leader create the integrated result
        self.log.update(progress="Asking team leader to integrate results...")
        
        try:
            # Execute integration using call to team leader
            await team_leader.hist_add_user_message(UserMessage(message=integration_prompt, attachments=[]))
            integrated_result = await team_leader.monologue()
            self.log.update(progress="Received integrated response from team leader")
        except Exception as e:
            self.log.update(error=f"Error during integration: {str(e)}")
            integrated_result = f"Error during integration: {str(e)}"
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "status": "integrated",
                "integrated_result": integrated_result,
                "next_step": "Use the response tool to share these integrated results with the user"
            }),
            break_loop=False
        )