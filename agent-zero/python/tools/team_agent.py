from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
import asyncio
import uuid
import json
import time
from typing import Dict, List, Any, Optional

# Create a global teams registry to ensure persistence across instances
GLOBAL_TEAMS_REGISTRY = {}
GLOBAL_AGENT_INSTANCES = {}
# Track action history and context for better continuity
GLOBAL_TEAM_CONTEXT = {}

class TeamAgent(Tool):
    """
    Tool for creating a team of agents that can collaborate on tasks.
    
    Simpler than the full collaborative framework, but maintains core collaboration features.
    """
    
    def __init__(self, agent=None, name=None, args=None, message=None, **kwargs):
        """Initialize the TeamAgent tool."""
        super().__init__(agent, name, args, message, **kwargs)
        # Use the global registry instead of instance-specific storage
        global GLOBAL_TEAMS_REGISTRY, GLOBAL_AGENT_INSTANCES, GLOBAL_TEAM_CONTEXT
        if not hasattr(self, 'teams'):
            self.teams = GLOBAL_TEAMS_REGISTRY
        if not hasattr(self, 'agent_instances'):
            self.agent_instances = GLOBAL_AGENT_INSTANCES
        if not hasattr(self, 'team_context'):
            self.team_context = GLOBAL_TEAM_CONTEXT
    
    async def execute(self, action="", team_id="", **kwargs):
        """
        Execute the TeamAgent tool.
        
        Args:
            action: Action to perform (create, add_agent, assign_task, message, get_results)
            team_id: ID of the team (except for 'create' action)
            **kwargs: Additional arguments based on the action
            
        Returns:
            Response: Tool response
        """
        global GLOBAL_TEAMS_REGISTRY, GLOBAL_AGENT_INSTANCES, GLOBAL_TEAM_CONTEXT
        
        try:
            # Log all incoming parameters for debugging
            debug_info = f"Action: {action}, Team ID: {team_id}, Args: {json.dumps(kwargs)}"
            PrintStyle(font_color="blue", padding=True).print(f"🔍 DEBUG: {debug_info}")
            PrintStyle(font_color="blue").print(f"🔍 Available teams: {list(self.teams.keys())}")
            
            # Check if we should use a persistent team_id from context
            if not team_id and action != "create" and self.team_context.get("active_team_id"):
                team_id = self.team_context.get("active_team_id")
                PrintStyle(font_color="green").print(
                    f"📌 Using persistent team_id from context: {team_id}"
                )
            
            # Track context for the current action
            current_context = {
                "action": action,
                "team_id": team_id,
                "timestamp": time.time(),
                "params": kwargs
            }
            
            # Start constructing a helpful "next steps" guide for responses
            next_steps = []
            available_context = {}
            
            # Handle different actions
            if action == "create":
                # Create a new team
                team_name = kwargs.get("name", "Team")
                team_goal = kwargs.get("goal", "Collaborate on a task")
                
                team_id = f"team_{str(uuid.uuid4())[:8]}"
                self.teams[team_id] = {
                    "id": team_id,
                    "name": team_name,
                    "goal": team_goal,
                    "agents": {},
                    "tasks": {},
                    "messages": [],
                    "created_at": time.time()
                }
                
                # Initialize team context
                self.team_context[team_id] = {
                    "active_team_id": team_id,
                    "name": team_name,
                    "goal": team_goal,
                    "action_history": [],
                    "agent_ids": [],
                    "task_ids": []
                }
                
                # Set as the active team
                self.team_context["active_team_id"] = team_id
                
                # Verify team was added to registry
                PrintStyle(font_color="green", padding=True).print(
                    f"✅ Team created: {team_id} (Total teams: {len(self.teams)})"
                )
                
                # Update global registry explicitly
                GLOBAL_TEAMS_REGISTRY.update(self.teams)
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                # Record action in history
                if team_id in self.team_context:
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # After creating the team, suggest next steps
                next_steps = [
                    "Now add team members with the 'add_agent' action",
                    f"Use team_id: {team_id} in your next commands",
                    "Example: Add a researcher with {'action': 'add_agent', 'team_id': '" + team_id + "', 'role': 'researcher'}"
                ]
                
                # Add available context for easier next steps
                available_context = {
                    "active_team": team_id,
                    "team_name": team_name,
                    "last_action": "create",
                    "next_step": "add_agent"
                }
                
                # Return enhanced response with clear next steps
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "name": team_name,
                    "goal": team_goal,
                    "status": "created",
                    "next_steps": next_steps,
                    "context": available_context
                }, indent=2), break_loop=False)
            
            # All other actions require a valid team_id
            if not team_id:
                # Show recent teams if available
                recent_teams = []
                if "active_team_id" in self.team_context:
                    recent_teams.append(self.team_context["active_team_id"])
                
                # Provide clear guidance on what's missing
                next_steps = [
                    "You need to specify a team_id",
                    "Create a new team first with {'action': 'create'} if you don't have one",
                    f"Or use one of these available teams: {list(self.teams.keys())}"
                ]
                
                return Response(message=json.dumps({
                    "error": "Missing team_id parameter",
                    "hint": "Provide a team_id from a previous create action",
                    "available_teams": list(self.teams.keys()),
                    "recent_teams": recent_teams,
                    "next_steps": next_steps
                }, indent=2), break_loop=False)
                
            # Check if team exists in the registry
            if team_id not in self.teams:
                # Better error reporting with available teams
                available_teams = list(self.teams.keys())
                return Response(message=json.dumps({
                    "error": f"Team {team_id} not found",
                    "hint": f"Available teams: {available_teams if available_teams else 'None. Create a team first with the create action'}",
                    "next": "Use the create action to make a new team"
                }, indent=2), break_loop=False)
            
            # Set this as the active team in context
            self.team_context["active_team_id"] = team_id
            
            if action == "add_agent":
                # Add an agent to the team
                role = kwargs.get("role", "member")
                skills = kwargs.get("skills", [])
                
                agent_id = f"agent_{str(uuid.uuid4())[:6]}"
                
                # Create a new agent instance
                new_agent = Agent(self.agent.number + 1, self.agent.config, self.agent.context)
                
                # Set superior-subordinate relationship
                new_agent.set_data(Agent.DATA_NAME_SUPERIOR, self.agent)
                
                # Set role information for the agent
                new_agent.set_data("role", role)
                new_agent.set_data("skills", skills)
                new_agent.set_data("team_id", team_id)
                new_agent.set_data("agent_id", agent_id)
                
                # Store agent information
                self.teams[team_id]["agents"][agent_id] = {
                    "id": agent_id,
                    "role": role,
                    "skills": skills,
                    "tasks": []
                }
                
                # Store agent instance in global registry
                self.agent_instances[agent_id] = new_agent
                GLOBAL_AGENT_INSTANCES.update(self.agent_instances)
                
                # Update team context with the new agent
                if team_id in self.team_context:
                    self.team_context[team_id]["agent_ids"].append(agent_id)
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global context
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                PrintStyle(font_color="green", padding=True).print(
                    f"✅ Agent added: {agent_id} with role {role} to team {team_id}"
                )
                
                # After adding agent, suggest next steps
                next_steps = [
                    f"Now assign a task to this agent with 'assign_task'",
                    f"Use agent_id: {agent_id} in your next command",
                    f"Example: {{'action': 'assign_task', 'team_id': '{team_id}', 'agent_id': '{agent_id}', 'task': 'Research topic X'}}"
                ]
                
                # Add available context for easier next steps
                available_context = {
                    "active_team": team_id,
                    "team_name": self.teams[team_id]["name"],
                    "last_action": "add_agent",
                    "agent_id": agent_id,
                    "agent_role": role,
                    "available_agents": list(self.teams[team_id]["agents"].keys()),
                    "next_step": "assign_task"
                }
                
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "agent_id": agent_id,
                    "role": role,
                    "status": "added",
                    "next_steps": next_steps,
                    "context": available_context
                }, indent=2), break_loop=False)
            
            elif action == "assign_task":
                # Assign a task to an agent
                agent_id = kwargs.get("agent_id", "")
                task = kwargs.get("task", "")
                context = kwargs.get("context", "")
                previous_task_id = kwargs.get("previous_task_id", "")
                # Add task dependency tracking
                depends_on = kwargs.get("depends_on", [])  # List of task IDs this task depends on
                
                if not agent_id or agent_id not in self.teams[team_id]["agents"]:
                    # List available agents for better error reporting
                    available_agents = list(self.teams[team_id]["agents"].keys())
                    return Response(message=json.dumps({
                        "error": f"Agent {agent_id} not found in team {team_id}",
                        "hint": f"Available agents: {available_agents if available_agents else 'None. Add agents first with the add_agent action'}",
                        "next": "Add the agent first with the 'add_agent' action"
                    }, indent=2), break_loop=False)
                
                if not task:
                    return Response(message=json.dumps({
                        "error": "Task description is required",
                        "hint": "Provide a task description in the 'task' parameter"
                    }, indent=2), break_loop=False)
                
                # Create task ID
                task_id = f"task_{str(uuid.uuid4())[:6]}"
                
                # If a previous task is specified, include its result in the context
                if previous_task_id and previous_task_id in self.teams[team_id]["tasks"]:
                    previous_task = self.teams[team_id]["tasks"][previous_task_id]
                    previous_agent_id = previous_task["agent_id"]
                    previous_agent_role = self.teams[team_id]["agents"][previous_agent_id]["role"]
                    
                    # Add previous task result to context
                    if previous_task["result"]:
                        if context:
                            context += "\n\n"
                        context += f"Previous task result from {previous_agent_role}:\n{previous_task['result']}"
                        
                        # Chain the response properly if both agents exist
                        await self._chain_response(
                            team_id, 
                            previous_agent_id, 
                            agent_id, 
                            previous_task["result"]
                        )
                
                # Check if dependencies are satisfied
                dependencies_met = all(
                    dep_id in self.teams[team_id]["tasks"] and 
                    self.teams[team_id]["tasks"].get(dep_id, {}).get("status") == "completed"
                    for dep_id in depends_on
                )
                
                initial_status = "assigned"
                if depends_on and not dependencies_met:
                    initial_status = "waiting_dependencies"
                    PrintStyle(font_color="yellow", padding=True).print(
                        f"⏳ Task {task_id} is waiting for dependencies to complete: {', '.join(depends_on)}"
                    )
                
                # Store task information
                self.teams[team_id]["tasks"][task_id] = {
                    "id": task_id,
                    "agent_id": agent_id,
                    "description": task,
                    "context": context,
                    "status": initial_status,
                    "result": None,
                    "depends_on": depends_on,
                    "dependencies_met": dependencies_met,
                    "created_at": time.time(),
                    "error": None
                }
                
                # Add task to agent's task list
                self.teams[team_id]["agents"][agent_id]["tasks"].append(task_id)
                
                # Update team context with the new task
                if team_id in self.team_context:
                    self.team_context[team_id]["task_ids"].append(task_id)
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global context
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                # Get the agent instance
                agent_instance = self.agent_instances.get(agent_id)
                
                if agent_instance:
                    # Format the prompt with team context
                    prompt = self._format_task_prompt(
                        team_id=team_id,
                        agent_id=agent_id,
                        task=task,
                        context=context,
                        task_id=task_id  # Pass task_id to the prompt formatter
                    )
                    
                    # Display agent activation message to the user 
                    agent_role = self.teams[team_id]["agents"][agent_id]["role"]
                    PrintStyle(bold=True, font_color="blue", padding=True).print(
                        f"📋 Assigning task to {agent_role} ({agent_id}): {task}"
                    )
                    
                    # Send the task to the agent
                    await agent_instance.hist_add_user_message(UserMessage(message=prompt, attachments=[]))
                    
                    # Update global registry
                    GLOBAL_TEAMS_REGISTRY.update(self.teams)
                    
                    status_message = "assigned"
                    if initial_status == "waiting_dependencies":
                        status_message = "waiting for dependencies"
                    
                    # After assigning task, suggest next steps
                    next_steps = [
                        f"Now execute this task with 'execute_task'",
                        f"Use task_id: {task_id} in your next command",
                        f"Example: {{'action': 'execute_task', 'team_id': '{team_id}', 'task_id': '{task_id}'}}"
                    ]
                    
                    # Add dependency info to next steps if applicable
                    if depends_on and not dependencies_met:
                        next_steps = [
                            f"This task depends on: {', '.join(depends_on)}",
                            "Execute those tasks first before running this one",
                            f"Example: {{'action': 'execute_task', 'team_id': '{team_id}', 'task_id': '{depends_on[0]}'}}"
                        ]
                    
                    # Add available context for easier next steps
                    available_context = {
                        "active_team": team_id,
                        "team_name": self.teams[team_id]["name"],
                        "last_action": "assign_task",
                        "agent_id": agent_id,
                        "agent_role": self.teams[team_id]["agents"][agent_id]["role"],
                        "task_id": task_id,
                        "dependencies": depends_on,
                        "dependencies_met": dependencies_met,
                        "next_step": "execute_task" if dependencies_met else "execute_dependency"
                    }
                    
                    # Instead of executing monologue right away, just return with the task assignment
                    # This keeps the interface more interactive
                    return Response(message=json.dumps({
                        "team_id": team_id,
                        "agent_id": agent_id,
                        "task_id": task_id,
                        "status": initial_status,
                        "dependencies": depends_on,
                        "dependencies_met": dependencies_met,
                        "next_steps": next_steps,
                        "context": available_context
                    }, indent=2), break_loop=False)
                else:
                    return Response(message=json.dumps({
                        "error": f"Agent instance for {agent_id} not found",
                        "hint": "This is an internal error, try adding the agent again"
                    }, indent=2), break_loop=False)
            
            elif action == "execute_task":
                # Execute a previously assigned task
                task_id = kwargs.get("task_id", "")
                # Add task resumption capability
                is_resuming = kwargs.get("resume", False)
                
                if not task_id or task_id not in self.teams[team_id]["tasks"]:
                    # List available tasks for better error reporting
                    available_tasks = list(self.teams[team_id]["tasks"].keys())
                    return Response(message=json.dumps({
                        "error": f"Task {task_id} not found in team {team_id}",
                        "hint": f"Available tasks: {available_tasks if available_tasks else 'None. Assign tasks first with the assign_task action'}",
                        "next": "Assign a task first with the 'assign_task' action"
                    }, indent=2), break_loop=False)
                
                task = self.teams[team_id]["tasks"][task_id]
                agent_id = task["agent_id"]
                agent_instance = self.agent_instances.get(agent_id)
                
                # Check for dependency status
                if task.get("depends_on") and not task.get("dependencies_met", False):
                    # Re-check if dependencies are now satisfied
                    dependencies_met = all(
                        dep_id in self.teams[team_id]["tasks"] and 
                        self.teams[team_id]["tasks"].get(dep_id, {}).get("status") == "completed"
                        for dep_id in task.get("depends_on", [])
                    )
                    
                    if not dependencies_met:
                        waiting_for = [
                            dep_id for dep_id in task.get("depends_on", [])
                            if not (dep_id in self.teams[team_id]["tasks"] and 
                                   self.teams[team_id]["tasks"].get(dep_id, {}).get("status") == "completed")
                        ]
                        return Response(message=json.dumps({
                            "error": f"Task {task_id} is still waiting for dependencies",
                            "waiting_for": waiting_for,
                            "hint": "Execute the dependent tasks first before running this one",
                            "next": f"Execute tasks: {', '.join(waiting_for)}"
                        }, indent=2), break_loop=False)
                    else:
                        # Dependencies are now met, update status
                        self.teams[team_id]["tasks"][task_id]["dependencies_met"] = True
                        self.teams[team_id]["tasks"][task_id]["status"] = "assigned"
                        PrintStyle(font_color="green", padding=True).print(
                            f"✅ Dependencies for task {task_id} are now satisfied, proceeding with execution"
                        )
                
                # Handle task resumption
                if is_resuming and task["status"] == "failed":
                    # Reset task status
                    self.teams[team_id]["tasks"][task_id]["status"] = "assigned"
                    self.teams[team_id]["tasks"][task_id]["error"] = None
                    PrintStyle(font_color="yellow", padding=True).print(
                        f"🔄 Resuming previously failed task: {task['description']}"
                    )
                
                if task["status"] not in ["assigned", "waiting_dependencies"]:
                    status = task["status"]
                    if status == "completed":
                        # Just return the previous result if already completed
                        return Response(message=json.dumps({
                            "team_id": team_id,
                            "agent_id": agent_id,
                            "task_id": task_id,
                            "status": "completed",
                            "agent_role": self.teams[team_id]["agents"][agent_id]["role"],
                            "task": task["description"],
                            "result": task["result"],
                            "note": "This task was already completed. Returning previous result.",
                            "context": {
                                "active_team": team_id,
                                "last_action": "execute_task",
                                "task_id": task_id,
                                "agent_id": agent_id,
                                "status": "completed"
                            }
                        }, indent=2), break_loop=False)
                    elif not is_resuming:
                        # If not resuming, prevent re-execution of tasks that aren't in assigned state
                        return Response(message=json.dumps({
                            "error": f"Task {task_id} has status '{status}' and cannot be executed",
                            "hint": f"Only tasks with 'assigned' status can be executed. Use 'resume=true' to retry failed tasks.",
                            "next": "Check task status with get_results or assign a new task"
                        }, indent=2), break_loop=False)
                
                if agent_instance:
                    agent_role = self.teams[team_id]["agents"][agent_id]["role"]
                    
                    # Display agent thinking message
                    PrintStyle(italic=True, font_color="cyan", padding=True).print(
                        f"🧠 {agent_role} ({agent_id}) is working on task: {task['description']}"
                    )
                    
                    # Add a clear visual separator to indicate agent transition in the UI
                    print("\n" + "="*80)
                    PrintStyle(bold=True, font_color="magenta", padding=True).print(
                        f"👤 AGENT TRANSITION: Now executing as {agent_role} (ID: {agent_id})"
                    )
                    PrintStyle(font_color="magenta").print(
                        f"📋 TASK #{task_id}: {task['description']}"
                    )
                    print("="*80 + "\n")
                    
                    # Save the original streaming agent
                    original_streaming_agent = None
                    if hasattr(self.agent.context, 'streaming_agent'):
                        original_streaming_agent = self.agent.context.streaming_agent
                    
                    try:
                        # Set the context's streaming_agent to this agent instance
                        # This ensures responses appear in the UI
                        if hasattr(self.agent.context, 'streaming_agent'):
                            # Set agent data for proper identification in UI
                            agent_instance.set_data("current_task_id", task_id)
                            agent_instance.set_data("current_team_id", team_id)
                            agent_instance.set_data("current_role", agent_role)
                            agent_instance.set_data("agent_number", agent_id.split("_")[1])  # Extract just the ID number
                            # Update the streaming agent
                            self.agent.context.streaming_agent = agent_instance
                        
                        # Run the agent's monologue directly, similar to call_subordinate
                        result = await agent_instance.monologue()
                        
                        # Update task with result
                        self.teams[team_id]["tasks"][task_id]["result"] = result
                        self.teams[team_id]["tasks"][task_id]["status"] = "completed"
                        
                        # Update team context with task completion
                        if team_id in self.team_context:
                            current_context["result"] = "completed"
                            self.team_context[team_id]["action_history"].append(current_context)
                        
                        # Add memory entry for task completion
                        if hasattr(self.agent, 'memory_save'):
                            memory_entry = f"Task {task_id} completed by {agent_role} ({agent_id}): {task['description']}\nResult: {result[:200]}..."
                            try:
                                await self.agent.memory_save(text=memory_entry, area="team_tasks")
                                PrintStyle(font_color="green").print(
                                    f"📝 Task result saved to memory with area='team_tasks'"
                                )
                            except Exception as mem_err:
                                PrintStyle(font_color="yellow").print(
                                    f"⚠️ Could not save task to memory: {str(mem_err)}"
                                )
                        
                        # Update global registry and context
                        GLOBAL_TEAMS_REGISTRY.update(self.teams)
                        GLOBAL_TEAM_CONTEXT.update(self.team_context)
                        
                        # Add a clear visual separator to indicate returning to main agent
                        print("\n" + "="*80)
                        PrintStyle(bold=True, font_color="green", padding=True).print(
                            f"✅ TASK COMPLETE: Returning to main agent"
                        )
                        print("="*80 + "\n")
                        
                        # Display agent completion message
                        PrintStyle(bold=True, font_color="green", padding=True).print(
                            f"✅ {agent_role} ({agent_id}) completed task: {task['description']}"
                        )
                        
                        # Check if any tasks were waiting on this one and update their status
                        dependent_tasks = [
                            t_id for t_id, t_info in self.teams[team_id]["tasks"].items()
                            if task_id in t_info.get("depends_on", []) and t_info["status"] == "waiting_dependencies"
                        ]
                        
                        if dependent_tasks:
                            for dep_task_id in dependent_tasks:
                                # Recheck all dependencies for this task
                                dependencies_met = all(
                                    dep_id in self.teams[team_id]["tasks"] and 
                                    self.teams[team_id]["tasks"].get(dep_id, {}).get("status") == "completed"
                                    for dep_id in self.teams[team_id]["tasks"][dep_task_id].get("depends_on", [])
                                )
                                
                                if dependencies_met:
                                    self.teams[team_id]["tasks"][dep_task_id]["dependencies_met"] = True
                                    self.teams[team_id]["tasks"][dep_task_id]["status"] = "assigned"
                                    PrintStyle(font_color="green").print(
                                        f"✅ Task {dep_task_id} dependencies are now satisfied and ready for execution"
                                    )
                        
                        return Response(message=json.dumps({
                            "team_id": team_id,
                            "agent_id": agent_id,
                            "task_id": task_id,
                            "status": "completed",
                            "agent_role": agent_role,
                            "task": task["description"],
                            "result": result,
                            "unlocked_tasks": dependent_tasks,
                            "context": {
                                "active_team": team_id,
                                "last_action": "execute_task",
                                "task_id": task_id,
                                "agent_id": agent_id,
                                "status": "completed"
                            }
                        }, indent=2), break_loop=False)
                    except asyncio.CancelledError as ce:
                        # Handle cancellation specially
                        self.teams[team_id]["tasks"][task_id]["status"] = "cancelled"
                        self.teams[team_id]["tasks"][task_id]["error"] = "Task was cancelled"
                        
                        # Update team context with task cancellation
                        if team_id in self.team_context:
                            current_context["result"] = "cancelled"
                            self.team_context[team_id]["action_history"].append(current_context)
                        
                        # Update global context
                        GLOBAL_TEAM_CONTEXT.update(self.team_context)
                        
                        # Add a clear visual separator to indicate returning to main agent after cancellation
                        print("\n" + "="*80)
                        PrintStyle(bold=True, font_color="yellow", padding=True).print(
                            f"⚠️ TASK CANCELLED: Returning to main agent"
                        )
                        print("="*80 + "\n")
                        
                        # Display agent cancellation message
                        PrintStyle(bold=True, font_color="yellow", padding=True).print(
                            f"⚠️ {agent_role} ({agent_id}) task was cancelled: {task['description']}"
                        )
                        
                        return Response(message=json.dumps({
                            "team_id": team_id,
                            "agent_id": agent_id,
                            "task_id": task_id,
                            "status": "cancelled",
                            "error": "Task was cancelled",
                            "context": {
                                "active_team": team_id,
                                "last_action": "execute_task",
                                "task_id": task_id,
                                "agent_id": agent_id,
                                "status": "cancelled"
                            }
                        }, indent=2), break_loop=False)
                    except Exception as e:
                        self.teams[team_id]["tasks"][task_id]["status"] = "failed"
                        self.teams[team_id]["tasks"][task_id]["error"] = str(e)
                        
                        # Update team context with task failure
                        if team_id in self.team_context:
                            current_context["result"] = "failed"
                            current_context["error"] = str(e)
                            self.team_context[team_id]["action_history"].append(current_context)
                        
                        # Add memory entry for task failure
                        if hasattr(self.agent, 'memory_save'):
                            memory_entry = f"Task {task_id} failed by {agent_role} ({agent_id}): {task['description']}\nError: {str(e)}"
                            try:
                                await self.agent.memory_save(text=memory_entry, area="team_tasks")
                                PrintStyle(font_color="yellow").print(
                                    f"📝 Task failure saved to memory with area='team_tasks'"
                                )
                            except Exception as mem_err:
                                PrintStyle(font_color="yellow").print(
                                    f"⚠️ Could not save task failure to memory: {str(mem_err)}"
                                )
                        
                        # Update global context
                        GLOBAL_TEAM_CONTEXT.update(self.team_context)
                        
                        # Add a clear visual separator to indicate returning to main agent after error
                        print("\n" + "="*80)
                        PrintStyle(bold=True, font_color="red", padding=True).print(
                            f"❌ TASK FAILED: Returning to main agent"
                        )
                        print("="*80 + "\n")
                        
                        # Display agent failure message
                        PrintStyle(bold=True, font_color="red", padding=True).print(
                            f"❌ {agent_role} ({agent_id}) failed task: {task['description']}"
                        )
                        
                        return Response(message=json.dumps({
                            "team_id": team_id,
                            "agent_id": agent_id,
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(e),
                            "context": {
                                "active_team": team_id,
                                "last_action": "execute_task",
                                "task_id": task_id,
                                "agent_id": agent_id,
                                "status": "failed"
                            },
                            "next": "You can retry this task with 'resume=true' parameter"
                        }, indent=2), break_loop=False)
                    finally:
                        # Reset the streaming agent back to the original agent
                        # This ensures we don't leave the UI in an inconsistent state
                        if hasattr(self.agent.context, 'streaming_agent') and original_streaming_agent:
                            self.agent.context.streaming_agent = original_streaming_agent
            
            elif action == "message":
                # Send a message between agents
                from_agent = kwargs.get("from", "")
                to_agent = kwargs.get("to", "")
                content = kwargs.get("content", "")
                
                if not from_agent or from_agent not in self.teams[team_id]["agents"]:
                    # List available agents for better error reporting
                    available_agents = list(self.teams[team_id]["agents"].keys())
                    return Response(message=json.dumps({
                        "error": f"Sender agent {from_agent} not found in team {team_id}",
                        "hint": f"Available agents: {available_agents}",
                        "next": "Specify a valid agent ID in the 'from' parameter"
                    }, indent=2), break_loop=False)
                
                if not to_agent or to_agent not in self.teams[team_id]["agents"]:
                    # List available agents for better error reporting
                    available_agents = list(self.teams[team_id]["agents"].keys())
                    return Response(message=json.dumps({
                        "error": f"Recipient agent {to_agent} not found in team {team_id}",
                        "hint": f"Available agents: {available_agents}",
                        "next": "Specify a valid agent ID in the 'to' parameter"
                    }, indent=2), break_loop=False)
                
                if not content:
                    return Response(message=json.dumps({
                        "error": "Message content is required",
                        "hint": "Provide message content in the 'content' parameter"
                    }, indent=2), break_loop=False)
                
                # Create message ID
                message_id = f"msg_{str(uuid.uuid4())[:6]}"
                
                # Get agent roles for display
                from_role = self.teams[team_id]["agents"][from_agent]["role"]
                to_role = self.teams[team_id]["agents"][to_agent]["role"]
                
                # Create a more visually distinct message UI
                PrintStyle(bold=True, font_color="purple", padding=True).print(
                    f"📨 MESSAGE SENT"
                )
                PrintStyle(font_color="purple").print(
                    f"📤 FROM: {from_role} (ID: {from_agent})"
                )
                PrintStyle(font_color="purple").print(
                    f"📥 TO: {to_role} (ID: {to_agent})"
                )
                PrintStyle(font_color="blue", padding=True).print(
                    f"💬 CONTENT: {content}"
                )
                
                # Store message
                message = {
                    "id": message_id,
                    "from": from_agent,
                    "to": to_agent,
                    "content": content,
                    "timestamp": time.time(),
                    "read": False
                }
                
                self.teams[team_id]["messages"].append(message)
                
                # Get recipient agent
                recipient = self.agent_instances.get(to_agent)
                
                if recipient:
                    # Format the message in a clearer way for the recipient
                    formatted_message = f"""## Message from {from_role}

{content}

---
From: {from_role} (Agent ID: {from_agent})
To: You as {to_role}
Time: {time.strftime('%H:%M:%S')}
"""
                    
                    # Store the message to be delivered when the agent executes its next task
                    if not recipient.get_data("pending_messages"):
                        recipient.set_data("pending_messages", [])
                    
                    pending_messages = recipient.get_data("pending_messages") or []
                    pending_messages.append(formatted_message)
                    recipient.set_data("pending_messages", pending_messages)
                
                # Update team context with messaging action
                if team_id in self.team_context:
                    current_context["message_id"] = message_id
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global registry and context
                GLOBAL_TEAMS_REGISTRY.update(self.teams)
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                # Add clear next steps for messaging
                next_steps = [
                    f"Message sent from {from_role} to {to_role}",
                    "The message will be delivered when the recipient runs their next task",
                    f"You can continue assigning/executing tasks or sending more messages"
                ]
                
                # Updated context and response
                available_context = {
                    "active_team": team_id,
                    "last_action": "message",
                    "from_agent": from_agent,
                    "from_role": from_role,
                    "to_agent": to_agent,
                    "to_role": to_role,
                    "message_id": message_id
                }
                
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "message_id": message_id,
                    "from": from_agent,
                    "from_role": from_role,
                    "to": to_agent,
                    "to_role": to_role,
                    "status": "sent",
                    "next_steps": next_steps,
                    "context": available_context
                }, indent=2), break_loop=False)
            
            elif action == "broadcast":
                # Broadcast a message to all agents
                from_agent = kwargs.get("from", "")
                content = kwargs.get("content", "")
                
                if not from_agent or from_agent not in self.teams[team_id]["agents"]:
                    # List available agents for better error reporting
                    available_agents = list(self.teams[team_id]["agents"].keys())
                    return Response(message=json.dumps({
                        "error": f"Sender agent {from_agent} not found in team {team_id}",
                        "hint": f"Available agents: {available_agents}",
                        "next": "Specify a valid agent ID in the 'from' parameter"
                    }, indent=2), break_loop=False)
                
                if not content:
                    return Response(message=json.dumps({
                        "error": "Message content is required",
                        "hint": "Provide message content in the 'content' parameter"
                    }, indent=2), break_loop=False)
                
                # Create message ID
                message_id = f"broadcast_{str(uuid.uuid4())[:6]}"
                
                # Get sender role
                from_role = self.teams[team_id]["agents"][from_agent]["role"]
                
                # Display broadcast message in the conversation
                PrintStyle(font_color="purple", padding=True).print(
                    f"📢 {from_role} ({from_agent}) BROADCAST: {content}"
                )
                
                # Format the message
                formatted_message = f"[BROADCAST from {from_role} agent]: {content}"
                
                # Prepare to deliver messages when agents execute their next tasks
                recipients = []
                for agent_id, agent_info in self.teams[team_id]["agents"].items():
                    if agent_id != from_agent:
                        recipient = self.agent_instances.get(agent_id)
                        if recipient:
                            # Store message to be delivered when the agent executes next
                            if not recipient.get_data("pending_messages"):
                                recipient.set_data("pending_messages", [])
                            
                            pending_messages = recipient.get_data("pending_messages") or []
                            pending_messages.append(formatted_message)
                            recipient.set_data("pending_messages", pending_messages)
                            
                            recipients.append(agent_id)
                
                # Store broadcast message
                message = {
                    "id": message_id,
                    "from": from_agent,
                    "to": "all",
                    "content": content,
                    "recipients": recipients,
                    "timestamp": time.time()
                }
                
                self.teams[team_id]["messages"].append(message)
                
                # Update team context with broadcast action
                if team_id in self.team_context:
                    current_context["message_id"] = message_id
                    current_context["recipients"] = recipients
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global registry and context
                GLOBAL_TEAMS_REGISTRY.update(self.teams)
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "message_id": message_id,
                    "from": from_agent,
                    "from_role": from_role,
                    "recipients": recipients,
                    "status": "broadcast_sent",
                    "next": "The broadcast will be delivered when recipient agents execute their next tasks",
                    "context": {
                        "active_team": team_id,
                        "last_action": "broadcast",
                        "from_agent": from_agent,
                        "recipients": recipients
                    }
                }, indent=2), break_loop=False)
            
            elif action == "get_results":
                # Get results of all tasks in the team
                results = {}
                
                for task_id, task in self.teams[team_id]["tasks"].items():
                    agent_id = task["agent_id"]
                    agent_role = self.teams[team_id]["agents"][agent_id]["role"]
                    
                    results[task_id] = {
                        "description": task["description"],
                        "agent": agent_id,
                        "role": agent_role,
                        "status": task["status"],
                        "result": task["result"]
                    }
                
                # Display summary of results
                PrintStyle(bold=True, font_color="green", padding=True).print(
                    f"📊 Team {self.teams[team_id]['name']} Results Summary:"
                )
                for task_id, result in results.items():
                    status_color = "green" if result["status"] == "completed" else "red"
                    PrintStyle(font_color=status_color).print(
                        f"  • {result['role']} - {result['description']}: {result['status']}"
                    )
                
                # Update team context with results action
                if team_id in self.team_context:
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global context
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "team_name": self.teams[team_id]["name"],
                    "goal": self.teams[team_id]["goal"],
                    "results": results,
                    "context": {
                        "active_team": team_id,
                        "last_action": "get_results",
                        "completed_tasks": [
                            task_id for task_id, result in results.items() 
                            if result["status"] == "completed"
                        ]
                    }
                }, indent=2), break_loop=False)
            
            elif action == "team_status":
                # Get comprehensive status of the entire team, including agents and tasks
                agent_statuses = {}
                task_statuses = {}
                message_count = len(self.teams[team_id]["messages"])
                team_info = self.teams[team_id]
                
                # Calculate stats
                total_tasks = len(team_info["tasks"])
                completed_tasks = sum(1 for t in team_info["tasks"].values() if t["status"] == "completed")
                failed_tasks = sum(1 for t in team_info["tasks"].values() if t["status"] == "failed")
                waiting_tasks = sum(1 for t in team_info["tasks"].values() if t["status"] == "waiting_dependencies")
                cancelled_tasks = sum(1 for t in team_info["tasks"].values() if t["status"] == "cancelled")
                assigned_tasks = sum(1 for t in team_info["tasks"].values() if t["status"] == "assigned")
                
                completion_percentage = 0
                if total_tasks > 0:
                    completion_percentage = int((completed_tasks / total_tasks) * 100)
                
                # Get agent statuses
                for agent_id, agent_info in team_info["agents"].items():
                    agent_role = agent_info["role"]
                    agent_tasks = [team_info["tasks"][t_id] for t_id in agent_info["tasks"] if t_id in team_info["tasks"]]
                    
                    # Calculate agent-specific stats
                    agent_total_tasks = len(agent_tasks)
                    agent_completed = sum(1 for t in agent_tasks if t["status"] == "completed")
                    agent_failed = sum(1 for t in agent_tasks if t["status"] == "failed")
                    agent_waiting = sum(1 for t in agent_tasks if t["status"] == "waiting_dependencies")
                    agent_assigned = sum(1 for t in agent_tasks if t["status"] == "assigned")
                    
                    # Get the agent's current active task if any
                    current_tasks = [t for t in agent_tasks if t["status"] == "assigned"]
                    current_task = current_tasks[0]["id"] if current_tasks else None
                    
                    agent_statuses[agent_id] = {
                        "role": agent_role,
                        "skills": agent_info["skills"],
                        "total_tasks": agent_total_tasks,
                        "completed_tasks": agent_completed,
                        "failed_tasks": agent_failed,
                        "waiting_tasks": agent_waiting,
                        "assigned_tasks": agent_assigned,
                        "current_task": current_task
                    }
                
                # Get task statuses with dependencies
                for task_id, task_info in team_info["tasks"].items():
                    agent_id = task_info["agent_id"]
                    agent_role = team_info["agents"][agent_id]["role"] if agent_id in team_info["agents"] else "Unknown"
                    
                    # Format dependent tasks info
                    dependencies = task_info.get("depends_on", [])
                    dependency_info = []
                    for dep_id in dependencies:
                        if dep_id in team_info["tasks"]:
                            dep_status = team_info["tasks"][dep_id]["status"]
                            dependency_info.append({
                                "task_id": dep_id,
                                "status": dep_status
                            })
                    
                    task_statuses[task_id] = {
                        "description": task_info["description"],
                        "agent": agent_id,
                        "role": agent_role,
                        "status": task_info["status"],
                        "created_at": task_info["created_at"],
                        "dependencies": dependency_info,
                        "dependencies_met": task_info.get("dependencies_met", True)
                    }
                
                # Display summary in console
                PrintStyle(bold=True, font_color="cyan", padding=True).print(
                    f"📊 Team {team_info['name']} Status Overview:"
                )
                PrintStyle(font_color="cyan").print(
                    f"  • Team progress: {completion_percentage}% ({completed_tasks}/{total_tasks} tasks completed)"
                )
                PrintStyle(font_color="cyan").print(
                    f"  • Agents: {len(team_info['agents'])} | Tasks: {total_tasks} | Messages: {message_count}"
                )
                PrintStyle(font_color="green").print(
                    f"  • Completed tasks: {completed_tasks}"
                )
                PrintStyle(font_color="yellow").print(
                    f"  • Waiting tasks: {waiting_tasks} | Assigned tasks: {assigned_tasks}"
                )
                PrintStyle(font_color="red").print(
                    f"  • Failed tasks: {failed_tasks} | Cancelled tasks: {cancelled_tasks}"
                )
                
                # Update team context
                if team_id in self.team_context:
                    self.team_context[team_id]["action_history"].append(current_context)
                
                # Update global context
                GLOBAL_TEAM_CONTEXT.update(self.team_context)
                
                return Response(message=json.dumps({
                    "team_id": team_id,
                    "team_name": team_info["name"],
                    "goal": team_info["goal"],
                    "created_at": team_info["created_at"],
                    "stats": {
                        "total_tasks": total_tasks,
                        "completed_tasks": completed_tasks,
                        "failed_tasks": failed_tasks,
                        "waiting_tasks": waiting_tasks,
                        "cancelled_tasks": cancelled_tasks,
                        "assigned_tasks": assigned_tasks,
                        "completion_percentage": completion_percentage,
                        "total_agents": len(team_info["agents"]),
                        "message_count": message_count
                    },
                    "agents": agent_statuses,
                    "tasks": task_statuses,
                    "context": {
                        "active_team": team_id,
                        "last_action": "team_status"
                    },
                    "next": "Use 'execute_task' on assigned tasks or assign new tasks to continue team progress"
                }, indent=2), break_loop=False)
            
            elif action == "get_context":
                # Return the current team context to help maintain state
                if team_id in self.team_context:
                    team_context = self.team_context[team_id]
                    # Limit history to last 5 actions to keep response size manageable
                    if "action_history" in team_context and len(team_context["action_history"]) > 5:
                        team_context["action_history"] = team_context["action_history"][-5:]
                    
                    return Response(message=json.dumps({
                        "team_id": team_id,
                        "team_name": self.teams[team_id]["name"] if team_id in self.teams else "",
                        "context": team_context,
                        "available_agents": list(self.teams[team_id]["agents"].keys()) if team_id in self.teams else [],
                        "available_tasks": list(self.teams[team_id]["tasks"].keys()) if team_id in self.teams else []
                    }, indent=2), break_loop=False)
                else:
                    return Response(message=json.dumps({
                        "error": f"No context found for team {team_id}",
                        "available_teams": list(self.teams.keys())
                    }, indent=2), break_loop=False)
            
            else:
                # Unknown action
                return Response(message=json.dumps({
                    "error": f"Unknown action: {action}",
                    "available_actions": ["create", "add_agent", "assign_task", "execute_task", "message", "broadcast", "get_results", "get_context", "team_status"],
                    "context": {
                        "active_team": self.team_context.get("active_team_id"),
                        "available_teams": list(self.teams.keys())
                    }
                }, indent=2), break_loop=False)
        
        except Exception as e:
            # Enhanced error handling
            import traceback
            error_trace = traceback.format_exc()
            PrintStyle(font_color="red", padding=True).print(
                f"❌ ERROR in TeamAgent: {str(e)}\n{error_trace}"
            )
            
            # Provide more helpful error recovery guidance
            next_steps = [
                "Check the error message and parameters",
                "Make sure team_id and other IDs are correct",
                "Try getting team status to see current state",
                f"Example: {{'action': 'team_status', 'team_id': '{team_id if team_id else 'your_team_id'}'}}"
            ]
            
            return Response(message=json.dumps({
                "error": f"Error executing TeamAgent: {str(e)}",
                "error_type": type(e).__name__,
                "available_teams": list(self.teams.keys()),
                "action_attempted": action,
                "team_id_used": team_id,
                "next_steps": next_steps,
                "context": {
                    "active_team": self.team_context.get("active_team_id"),
                    "available_teams": list(self.teams.keys())
                }
            }, indent=2), break_loop=False)
    
    async def _format_task_prompt(self, team_id: str, agent_id: str, task: str, context: str, task_id: str) -> str:
        """Format a task prompt for an agent."""
        team = self.teams[team_id]
        agent = team["agents"][agent_id]
        
        # Simplified prompt structure for smaller models
        prompt = f"# Task Assignment\n\n"
        prompt += f"You are the **{agent['role']}** in team '{team['name']}'.\n\n"
        
        # Add key identifiers at the top for easy reference
        prompt += f"## Reference IDs\n"
        prompt += f"- Task ID: {task_id}\n"
        prompt += f"- Team ID: {team_id}\n"
        prompt += f"- Your Agent ID: {agent_id}\n\n"
        
        # Clearly state goal and task
        prompt += f"## Team Goal\n{team['goal']}\n\n"
        prompt += f"## Your Task\n{task}\n\n"
        
        # Add context if provided
        if context:
            prompt += f"## Context Information\n{context}\n\n"
        
        # Add skills information
        if agent["skills"]:
            prompt += f"## Your Skills\n"
            for skill in agent["skills"]:
                prompt += f"- {skill}\n"
            prompt += "\n"
        
        # Add team members information for better coordination awareness
        if len(team["agents"]) > 1:
            prompt += "## Team Members\n"
            for member_id, member_info in team["agents"].items():
                if member_id != agent_id:
                    prompt += f"- {member_info['role']} (ID: {member_id}): {', '.join(member_info['skills'])}\n"
            prompt += "\n"
        
        # Add pending messages if any - keep at top level for visibility
        agent_instance = self.agent_instances.get(agent_id)
        if agent_instance:
            pending_messages = agent_instance.get_data("pending_messages") or []
            if pending_messages:
                prompt += "## Messages For You\n"
                for i, msg in enumerate(pending_messages):
                    prompt += f"{i+1}. {msg}\n"
                prompt += "\n"
                # Clear pending messages since they're now delivered
                agent_instance.set_data("pending_messages", [])
        
        # Add previous tasks in a more concise format
        previous_tasks = []
        for t_id in agent["tasks"]:
            if t_id in team["tasks"] and team["tasks"][t_id]["result"] and t_id != task_id:
                prev_task = team["tasks"][t_id]
                
                # Limit result to first 100 chars to keep prompts manageable
                result_summary = prev_task['result'][:100] + ("..." if len(prev_task['result']) > 100 else "")
                
                previous_tasks.append({
                    "id": t_id,
                    "description": prev_task["description"],
                    "result_summary": result_summary
                })
        
        if previous_tasks:
            prompt += "## Your Previous Tasks\n"
            for prev_task in previous_tasks:
                prompt += f"- Task {prev_task['id']}: {prev_task['description']}\n"
                prompt += f"  Result: {prev_task['result_summary']}\n"
            prompt += "\n"
        
        # Task dependency information - simplified
        depends_on = team["tasks"][task_id].get("depends_on", [])
        if depends_on:
            prompt += "## Dependencies\n"
            prompt += "This task depends on:\n"
            for dep_id in depends_on:
                if dep_id in team["tasks"]:
                    dep_task = team["tasks"][dep_id]
                    dep_agent_id = dep_task["agent_id"]
                    dep_agent_role = team["agents"][dep_agent_id]["role"] if dep_agent_id in team["agents"] else "Unknown"
                    prompt += f"- Task {dep_id} by {dep_agent_role}: {dep_task['description']}\n"
                    
                    # If completed, include brief result summary
                    if dep_task["status"] == "completed" and dep_task["result"]:
                        result_summary = dep_task['result'][:100] + ("..." if len(dep_task['result']) > 100 else "")
                        prompt += f"  Result: {result_summary}\n"
            prompt += "\n"
        
        # Add task completion instructions - simplified
        prompt += """## Instructions
1. Focus on your role as the {role}
2. Complete the assigned task
3. Provide a clear, detailed response
4. Reference team information when needed
"""
        
        return prompt

    async def _chain_response(self, team_id: str, from_agent_id: str, to_agent_id: str, response: str):
        """Chain a response from one agent to another, properly handling the relationship."""
        from_agent_instance = self.agent_instances.get(from_agent_id)
        to_agent_instance = self.agent_instances.get(to_agent_id)
        
        if not from_agent_instance or not to_agent_instance:
            return
        
        # Get agent roles for better logging
        from_role = self.teams[team_id]["agents"][from_agent_id]["role"]
        to_role = self.teams[team_id]["agents"][to_agent_id]["role"]
        
        # Create a more visually distinct handoff marker
        PrintStyle(bold=True, font_color="magenta", padding=True).print(
            f"🔄 AGENT HANDOFF: {from_role} → {to_role}"
        )
        PrintStyle(font_color="magenta").print(
            f"📎 FROM: {from_role} (ID: {from_agent_id})"
        )
        PrintStyle(font_color="magenta").print(
            f"📌 TO: {to_role} (ID: {to_agent_id})"
        )
        
        # Display a preview of the content being handed off
        content_preview = response[:100] + "..." if len(response) > 100 else response
        PrintStyle(font_color="blue", padding=True).print(
            f"💬 CONTENT PREVIEW: {content_preview}"
        )
        
        # Format the response for the receiving agent - use a simplified markdown format
        formatted_response = f"""## Response from {from_role}

The {from_role} has provided the following information for your task:

{response}

---
This information is directly relevant to your current task.
"""
        
        # Store as pending message using the enhanced format
        if not to_agent_instance.get_data("pending_messages"):
            to_agent_instance.set_data("pending_messages", [])
        pending_messages = to_agent_instance.get_data("pending_messages") or []
        pending_messages.append(formatted_response)
        to_agent_instance.set_data("pending_messages", pending_messages)
            
        return formatted_response