from agent import Agent, UserMessage
from python.helpers.tool import Tool, Response
import uuid
import json
import time
import os

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
            
        # Enhanced handling for create action to include document status and separate planning
        if action == "create":
            # Determine project name for doc path
            project_name = kwargs.get("name", "project").replace(" ", "_").lower()
            doc_dir = "/root/team_task"
            doc_path = os.path.join(doc_dir, f"{project_name}.md")
            template_path = os.path.join(doc_dir, "template_project_name.md")
            
            # Log start of document check and planning phase
            self.log.update(progress=f"Starting planning phase for project: {project_name}...")
            
            # --- Step 1: Run Planning Phase ---
            # The planning phase now handles doc existence checks, reading, template use, and updates internally.
            # It returns a dictionary containing the planning summary and confirmed doc_path.
            planning_result = await self._team_planning_phase(**kwargs)
            
            # Extract planning details (handle potential errors if planning fails, though _team_planning_phase should manage its errors)
            planning_summary = planning_result.get("planning_summary", "Planning phase failed to generate summary.")
            # Use the doc_path confirmed/returned by the planning phase
            doc_path_from_planning = planning_result.get("doc_path", doc_path) # Fallback to original if needed
            planning_status = planning_result.get("status", "unknown")
            
            self.log.update(progress=f"Planning phase complete. Status: {planning_status}. Document at: {doc_path_from_planning}")
            
            # --- Step 2: Create the Team ---
            # Now that planning is done and the doc is handled, create the team structure.
            # Pass the confirmed doc_path to _create_team.
            self.log.update(progress="Creating team data structure...")
            # Pass kwargs and the confirmed doc_path
            create_response = await self._create_team(doc_path=doc_path_from_planning, **kwargs) 
            
            # Extract team_id from the create_response message (which should be JSON)
            team_id_from_create = None
            create_data = {}
            try:
                # Assuming create_response.message is a JSON string from _format_response
                create_data = json.loads(create_response.message)
                # Access the actual arguments passed to the tool via 'tool_args'
                team_id_from_create = create_data.get("tool_args", {}).get("team_id") 
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                self.log.update(error=f"Failed to parse team_id from _create_team response: {e}")
                # Handle error: maybe return an error response or log critical failure
                return Response(
                    message=self._format_response({
                        "error": "Failed to create team properly - could not extract team_id.",
                        "planning_summary": planning_summary,
                        "doc_path": doc_path_from_planning,
                        "next_step": "Internal error during team creation. Please report this issue."
                    }),
                    break_loop=True # Stop the loop on critical failure
                )
                
            # --- Step 3: Combine and Return ---
            # Combine planning info and creation info into one response for the user.
            self.log.update(progress=f"Team {team_id_from_create} created successfully.")
            return Response(
                message=self._format_response({
                    "status": "team_created",
                    "team_id": team_id_from_create, # Use the extracted team_id
                    "planning_summary": planning_summary, # Include the planning summary
                    "doc_path": doc_path_from_planning, # Use the confirmed doc path
                    "doc_status": "updated", # Indicate doc was handled in planning
                    "next_step": f"Team created with ID '{team_id_from_create}'. Planning document updated at '{doc_path_from_planning}'.\n\nNEXT: Use 'add_agent' with team_id '{team_id_from_create}' to add ALL necessary team members BEFORE assigning any tasks. Use the 'Role-Specific Task Assignment Guidance' from the planning summary when assigning tasks later."
                }),
                break_loop=False # Continue after successful creation
            )
            
        # Handle actions with better logging
        try:
            if action == "create":
                return await self._create_team(**kwargs)
            elif action == "add_agent":
                self.log.update(progress=f"Adding agent to team {team_id}...")
                return await self._add_agent(team_id, **kwargs)
            elif action == "assign_task":
                self.log.update(progress=f"Assigning task to agent in team {team_id}...")
                disable_auto_dependency = kwargs.pop("disable_auto_dependency", False)
                return await self._assign_task(team_id, disable_auto_dependency=disable_auto_dependency, **kwargs)
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
                # Explicitly extract step and review_summary from kwargs
                step = kwargs.pop("step", None)
                review_summary = kwargs.pop("review_summary", None)
                # Pass extracted parameters and remaining kwargs
                response = await self._integrate_results(team_id, step=step, review_summary=review_summary, **kwargs)
                if not isinstance(response, Response):
                    return Response(
                        message=self._format_response({
                            "team_id": team_id,
                            "error": "Integration did not return a valid Response object.",
                            "next_step": "Check the _integrate_results implementation."
                        }),
                        break_loop=False
                    )
                return response
            elif action == "get_task_result":
                self.log.update(progress=f"Getting specific task result from team {team_id}...")
                return await self._get_task_result(team_id, **kwargs)
            elif action == "delete_task":
                self.log.update(progress=f"Deleting task in team {team_id}...")
                return await self._delete_task(team_id, **kwargs)
            elif action == "update_task":
                self.log.update(progress=f"Updating task in team {team_id}...")
                return await self._update_task(team_id, **kwargs)
            else:
                self.log.update(error=f"Unknown action: {action}")
                return Response(
                    message=self._format_response({
                        "error": f"Unknown action: {action}",
                        "available_actions": [
                            "create", "add_agent", "assign_task", 
                            "execute_task", "message", "get_results", 
                            "team_status", "integrate_results", "get_task_result",
                            "delete_task", "update_task"
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
                        "team_status", "integrate_results", "get_task_result",
                        "delete_task", "update_task"
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
        
        # Retrieve the confirmed document path passed from the execute method
        doc_path = kwargs.get("doc_path", None) # Get doc_path from kwargs
        if not doc_path:
             # Fallback or log error if doc_path is missing - indicates an issue in the execute flow
             self.log.update(error=f"Critical: doc_path missing during _create_team for {team_id}")
             # Determine project name for fallback doc path calculation
             project_name = kwargs.get("name", "project").replace(" ", "_").lower()
             doc_dir = "/root/team_task" # Assuming this is the standard doc_dir
             doc_path = os.path.join(doc_dir, f"{project_name}.md")
             self.log.update(progress=f"Using fallback doc_path: {doc_path}")
             
        # Store team in agent's data
        teams = self.agent.get_data("teams") or {} # Ensure teams is initialized
        teams[team_id] = {
            "id": team_id,
            "name": name,
            "goal": goal,
            "leader_agent": team_leader,
            "created_at": time.time(),
            "doc_path": doc_path  # Store the confirmed document path
        }
        self.agent.set_data("teams", teams)
        
        # Set as the active team
        self.agent.set_data("active_team_id", team_id)
        
        # Return response containing the team_id and next steps
        # Note: The planning summary is handled in the main execute block
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "name": name,
                "goal": goal,
                "doc_path": doc_path, # Include doc_path for confirmation
                "status": "created", # Indicate team structure is created
                "next_step": "Team structure created. Follow instructions from the previous 'create' action response to add agents." # Simplified next_step, main guidance is in execute
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
        
        # Count existing team members
        member_count = len(team_members)
        
        next_step = f"Step 1 CONTINUE: ADD MORE AGENTS if needed to complete the team composition. You have {member_count} agent(s) so far. Once ALL needed agents are created, proceed to Step 2: ASSIGN TASKS to each agent using the assign_task action.\n\nIMPORTANT: Assign each agent their unique, role-appropriate task as defined in the 'Role-Specific Task Assignment Guidance' section of the planning summary. Do NOT assign the same review or implementation task to multiple agents. Each agent's task should leverage their specific expertise and responsibilities."
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "agent_id": agent_id,
                "role": role,
                "status": "added",
                "next_step": next_step
            }),
            break_loop=False
        )
    
    def _has_circular_dependency(self, tasks, start_task_id, new_depends_on):
        """Detect if adding new_depends_on to start_task_id would create a cycle"""
        visited = set()
        stack = list(new_depends_on)
        while stack:
            current = stack.pop()
            if current == start_task_id:
                return True
            if current in visited or current not in tasks:
                continue
            visited.add(current)
            stack.extend(tasks[current].get("depends_on", []))
        return False
    
    async def _assign_task(self, team_id, agent_id="", task="", context="", depends_on=None, disable_auto_dependency=False, **kwargs):
        """Assign a task to a team member.\n\nREMINDER: When assigning a task, use the unique, role-appropriate task for this agent as defined in the planning summary's 'Role-Specific Task Assignment Guidance' section. Avoid assigning the same generic review or implementation task to multiple agents."""
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
        
        # Get existing tasks to determine sequence number and auto-dependencies
        tasks = team_leader.get_data("tasks") or {}
        sequence_num = len(tasks) + 1  # Start from 1
        
        # If no dependencies were explicitly provided, automatically set the most recent task as a dependency
        if not disable_auto_dependency and not depends_on and tasks:
            # Find the most recent assigned or completed task by highest sequence number
            most_recent_task = None
            highest_seq = 0
            for task_id, task_data in tasks.items():
                task_seq = task_data.get("sequence_num", 0)
                if task_seq > highest_seq:
                    most_recent_task = task_id
                    highest_seq = task_seq
            if most_recent_task:
                depends_on = [most_recent_task]
                self.log.update(progress=f"Automatically set task dependency on prior task: {most_recent_task}")
        
        # Create task ID
        task_id = f"task_{str(uuid.uuid4())[:6]}"
        
        # Circular dependency check
        if self._has_circular_dependency(tasks, task_id, depends_on):
            return Response(
                message=self._format_response({
                    "error": f"Circular dependency detected: assigning these dependencies would create a cycle.",
                    "proposed_depends_on": depends_on,
                    "next_step": "Revise dependencies to avoid cycles. Use update_task to change dependencies, delete_task to remove problematic tasks, or use disable_auto_dependency: true in assign_task to prevent automatic dependencies."
                }),
                break_loop=False
            )
        
        # Create task
        task_data = {
            "id": task_id,
            "agent_id": agent_id,
            "description": task,
            "context": context,
            "depends_on": depends_on,
            "status": "assigned",
            "created_at": time.time(),
            "sequence_num": sequence_num,  # Add explicit sequence number
            "completed_at": None,
            "result": None,
            "auto_dependency": True if not disable_auto_dependency and depends_on else False
        }
        
        # Store task in team leader's data
        tasks[task_id] = task_data
        team_leader.set_data("tasks", tasks)
        
        # Get the agent's role for better context
        agent_role = team_members[agent_id]["role"] if agent_id in team_members else "unknown"
        
        # Create a task keywords summary
        task_keywords = " ".join(task.split()[:7]) + "..." if len(task.split()) > 7 else task
        
        # Prepare dependency info if any
        dependency_info = ""
        if depends_on:
            dependency_names = []
            for dep_id in depends_on:
                if dep_id in tasks:
                    dep_agent_id = tasks[dep_id].get("agent_id", "unknown")
                    dep_role = "unknown"
                    if dep_agent_id in team_members:
                        dep_role = team_members[dep_agent_id].get("role", "unknown")
                    dependency_names.append(f"{dep_id} ({dep_role})")
            
            if dependency_names:
                dependency_info = f", depends on: {', '.join(dependency_names)}"
        
        # Count remaining agents without tasks
        agents_without_tasks = []
        for aid, adata in team_members.items():
            if not any(t["agent_id"] == aid for t in tasks.values()):
                agents_without_tasks.append(f"{adata['role']} ({aid})")
        
        # Enhanced next_step with auto-dependency context
        auto_dep_note = ""
        if not disable_auto_dependency and not kwargs.get("depends_on") and tasks:
            auto_dep_note = " This task was automatically set to depend on the previous task. To prevent this in the future, use disable_auto_dependency: true in assign_task."
        elif disable_auto_dependency and not depends_on:
            auto_dep_note = " This task has no dependencies. If you want to automatically depend on the previous task, omit disable_auto_dependency or set it to false."
        if agents_without_tasks:
            next_step = f"Step 2 CONTINUE: ASSIGN TASKS to remaining agents ({', '.join(agents_without_tasks)}). Only after ALL agents have assigned tasks, proceed to Step 3: EXECUTE TASKS using the execute_task action. If you need to change or remove a task, use update_task or delete_task.{auto_dep_note}\n\nREMINDER: Use the unique, role-appropriate task for each agent as defined in the planning summary's 'Role-Specific Task Assignment Guidance' section. Avoid assigning the same generic review or implementation task to multiple agents."
        else:
            next_step = f"Step 3: EXECUTE ALL TASKS by using execute_task for each task in sequence. Start with tasks that have no dependencies. If you need to change or remove a task, use update_task or delete_task.{auto_dep_note}\n\nREMINDER: All agents should have unique, role-appropriate tasks as defined in the planning summary."
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "agent_id": agent_id,
                "task_id": task_id,
                "status": "assigned",
                "agent_role": agent_role,
                "task_description": task_keywords,
                "dependencies": depends_on if depends_on else [],
                "sequence_num": sequence_num,  # Include sequence number in response
                "has_context": bool(context),
                "auto_dependency": True if not disable_auto_dependency and depends_on else False,
                "next_step": next_step
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
        
        # Calculate team progress for context
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks.values() if t.get("status") == "completed")
        
        # Find dependent tasks for this task (tasks that depend on this one)
        dependent_tasks = []
        for t_id, t_data in tasks.items():
            if task_id in t_data.get("depends_on", []):
                if t_data["agent_id"] in team_members:
                    dependent_role = team_members[t_data["agent_id"]].get("role", "unknown")
                    dependent_tasks.append(f"{dependent_role} (Task {t_id}): {t_data['description'][:30]}...")
        
        # Create summary of completed tasks for context
        team_results_summary = []
        for t_id, t_data in tasks.items():
            if t_data["status"] == "completed" and t_id != task_id:
                # Skip direct dependencies as they will be included in full in the context
                if t_id in task.get("depends_on", []):
                    continue
                    
                if t_data["agent_id"] in team_members:
                    task_role = team_members[t_data["agent_id"]].get("role", "unknown")
                    # Extract a brief summary from the result (first 100 chars)
                    result_text = str(t_data.get("result", ""))
                    result_summary = result_text[:100] + "..." if len(result_text) > 100 else result_text
                    team_results_summary.append(f"{task_role} (Task {t_id}): {t_data['description'][:30]}... | Result summary: {result_summary}")
        
        # Format dependency information
        dependency_info = []
        auto_dependency_note = ""
        for dep_id in task.get("depends_on", []):
            if dep_id in tasks:
                dep_data = tasks[dep_id]
                if dep_data["agent_id"] in team_members:
                    dep_role = team_members[dep_data["agent_id"]].get("role", "unknown")
                    # Find if this was a sequence-based automatic dependency
                    if len(task.get("depends_on", [])) == 1 and dep_id in tasks:
                        # Check if the current task has an auto-dependency flag
                        if task.get("auto_dependency", False):
                            auto_dependency_note = f"\nNOTE: Your task automatically depends on the previous task ({dep_id}) due to sequential workflow."
                    dependency_info.append(f"{dep_role} (Task {dep_id}): {dep_data['description'][:30]}...")
        
        # Enhanced prompt with more comprehensive context
        prompt = f"""You are a {agent_role} with expertise in {', '.join(agent_skills) if agent_skills else 'general tasks'} on the {team_data['name']} team working toward: {team_data['goal']}.

CONTEXT:
- Team progress: {completed_tasks}/{total_tasks} tasks completed
- Your dependencies: {', '.join(dependency_info) if dependency_info else "None"}{auto_dependency_note}
- Tasks depending on yours: {', '.join(dependent_tasks) if dependent_tasks else "None"}
- Relevant completed work: 
{chr(10).join([f"  • {summary}" for summary in team_results_summary[:3]])}
{f"  • ...and {len(team_results_summary) - 3} more" if len(team_results_summary) > 3 else ""}

DEPENDENCY RESULTS:
{task['context']}

YOUR TASK (ID: {task_id}):
{task['description']}

WORKSPACE FUNDAMENTALS:
- Create complete, well-structured projects before execution
- Save all code to files with logical project structure
- Always verify file creation before trying to run files
- Use consistent file paths throughout your workflow

SESSION WORKFLOW:
- Session 0: File creation and editing ONLY
- Sessions 1+: Running and testing code ONLY
- Always reset sessions before running new code
- Use the input tool for interactive programs

ERROR HANDLING STRATEGY:
- If you encounter the same error twice when trying the same approach, switch to an alternative, more reliable method (such as using Python file I/O as described below). Document the fallback method used in your response.
- For library/package issues, try a different library or implement a minimal solution from scratch
- When installation fails despite multiple attempts, use a fallback implementation as specified in your task
- Document environment issues and your workaround strategy in your final response

PROJECT CREATION PATTERN:
1. Create directories and verify structure
2. Create all required files with explicit paths (using reliable methods below)
3. Verify all files exist before execution
4. Run code in separate sessions from creation
5. ALWAYS install packages AND run scripts with terminal runtime to maintain environment consistency

FILE EDITING STRATEGIES (Use Terminal First for Writes):

Reading Files:
- Use `cat /path/to/file` in the `terminal` runtime.

Writing/Overwriting Files (RECOMMENDED METHOD):
- Use `cat > /path/to/file << 'EOF' ... EOF` in the **terminal** runtime (session 0). This is generally the most reliable way to write or overwrite entire files, especially multi-line content or code, avoiding Python environment issues.
- **Formatting:** Ensure correct JSON escaping (`\n` for newlines) and that the final `EOF` is on its own line.
```json
{{
    "thoughts": ["Overwriting file with new content using terminal heredoc"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal",
        "session": 0,
        "code": "cat > /path/to/your/file.py << 'EOF'\n# Your full new file content here\nprint(\'Hello Overwritten World!\')\nEOF"
    }}
}}
```
- **Verification:** ALWAYS verify the write immediately using `cat /path/to/file` in a subsequent `terminal` call.
- **Troubleshooting:** If this command hangs (shows a `>` prompt and times out), it likely means the multi-line content or the final `EOF` was not transmitted correctly. Double-check formatting and escaping. If it hangs repeatedly, use the Python Fallback method.

Creating Empty Files or Simple Overwrites (Use with Caution):
- `echo "single line" > /path/to/file` or `touch /path/to/file` are acceptable for very simple cases but less reliable for complex content.

Python Fallback (Use if Terminal `cat > EOF` Hangs):
- Use this method **ONLY if the terminal `cat > EOF` method hangs repeatedly** (stuck on `>` prompt).
- Use the `python` runtime (session 0) with standard file I/O.
```json
{{
    "thoughts": ["Terminal file write failed/hung, falling back to Python file I/O"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "python",
        "session": 0,
        "code": "with open('/path/to/your/file.py', 'w') as f:\n    f.write(\'\'\'# Your full new file content here\nprint(\\\'Hello Python Fallback!\\\')\n\'\'\')\nprint('File written via Python.')"
    }}
}}
```

**Overall Edit Strategy:**
1.  Read the necessary context (`cat <file>`).
2.  Construct the *entire* new file content in memory.
3.  Write the *entire* new content using the **Terminal Heredoc** method first.
4.  **Verify** the write (`cat <file>`).
5.  If the terminal method **hangs** (stuck on `>`), retry using the **Python Fallback** method.
6.  Verify again.

*NEVER* use naive string/line replacements or partial edits, especially for code or structured files.

AVAILABLE TOOLS:
- knowledge_tool: For research and information gathering
- code_execution_tool: For computation, data processing, file operations (use 'terminal' runtime for commands and file ops; use 'python' runtime ONLY for executing Python logic or the file I/O fallback)
- input: For providing input to interactive programs
- response_tool: REQUIRED for your final output

TOOL USAGE EXAMPLES (Focus on Runtimes):

Checking File Content (Terminal):
```json
{{
    "thoughts": ["Checking the content of main.py"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal", // Use terminal to run cat
        "session": 0,
        "code": "cat project/src/main.py"
    }}
}}
```

Executing Python Code (Terminal):
```json
{{
    "thoughts": ["Testing code/imports"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal", // ALWAYS use terminal for running ANY Python code/scripts
        "session": 1,
        "code": "python -c 'import pandas; print(pandas.__version__)'"
    }}
}}
```

Installing Packages (Terminal):
```json
{{
    "thoughts": ["Installing required packages"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal", // Terminal for pip
        "session": 1,
        "code": "pip install pandas matplotlib"
    }}
}}
```

Running Scripts (Terminal):
```json
{{
    "thoughts": ["Reset session before running"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "reset",
        "session": 1
    }}
}}
```
```json
{{
    "thoughts": ["Running the created file"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal", // Terminal to execute the python script
        "session": 1,
        "code": "python project/src/main.py"
    }}
}}
```

Checking Environment (Terminal):
```json
{{
    "thoughts": ["Verifying Python environment"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "terminal", // Terminal for shell commands
        "session": 1,
        "code": "which python && python --version && pip list | grep pandas"
    }}
}}
```

Research (Knowledge Tool):
```json
{{
    "thoughts": ["Need information about X"],
    "tool_name": "knowledge_tool",
    "tool_args": {{
        "question": "Specific question about my task"
    }}
}}
```

Final Response (Response Tool - REQUIRED):
```json
{{
    "thoughts": ["Task complete, delivering results"],
    "tool_name": "response",
    "tool_args": {{
        "text": "Complete, well-structured deliverable with all necessary details"
    }}
}}
```

IMPORTANT: When executing terminal commands, monitor the output carefully for errors, especially `command not found`, `ModuleNotFoundError` or `ImportError`. If library imports fail after installation, verify that your terminal commands and Python code are using the same environment (`which python`).

EXECUTION STRATEGY:
1. UNDERSTAND the task requirements
2. PLAN your approach before writing any code
3. CREATE/EDIT files using reliable terminal methods (`cat`, `cat > EOF`)
4. TEST your implementation thoroughly (using `terminal` runtime for execution)
5. PIVOT quickly if you encounter repeated errors (try Python file I/O fallback for edits)
6. DELIVER using the response tool

Remember: The response_tool is REQUIRED for your final output. Avoid complex escaping; use heredocs or the Python fallback for multi-line strings.
"""
        
        # Execute task using call_subordinate pattern
        # Let the user know we're delegating to a team member
        self.log.update(progress=f"Delegating to {agent_role} agent...")
        
        # Log the full prompt being sent to the agent for debugging and transparency
        self.log.update(context=f"Task Context Being Passed:\n\n{prompt}")
        
        try:
            # Execute task using call_subordinate pattern
            agent_instance.hist_add_user_message(UserMessage(message=prompt, attachments=[]))
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
        
        # Count remaining tasks
        remaining_tasks = sum(1 for t in tasks.values() if t["status"] == "assigned")
        executable_tasks = sum(1 for t_id, t_data in tasks.items() 
                              if t_data["status"] == "assigned" and
                              all(dep_id not in t_data.get("depends_on", []) or
                                  tasks.get(dep_id, {}).get("status") == "completed"
                                  for dep_id in t_data.get("depends_on", [])))
        
        # Get list of executable tasks
        executable_task_list = []
        for t_id, t_data in tasks.items():
            if (t_data["status"] == "assigned" and
                all(dep_id not in t_data.get("depends_on", []) or
                    tasks.get(dep_id, {}).get("status") == "completed"
                    for dep_id in t_data.get("depends_on", []))):
                assigned_to = "unknown"
                if t_data["agent_id"] in team_members:
                    assigned_to = team_members[t_data["agent_id"]].get("role", "unknown")
                executable_task_list.append(f"{t_id} (assigned to {assigned_to})")
                
        if dependent_tasks:
            next_step = f"Step 3 CONTINUE: EXECUTE DEPENDENT TASKS that can now run: {', '.join(dependent_tasks)}. Execute ALL tasks before moving to the next step."
        elif remaining_tasks == 0:
            next_step = "Step 4: COMPILE AND SYNTHESIZE RESULTS using get_results action followed by integrate_results action to create a comprehensive final deliverable."
        elif executable_tasks > 0:
            next_step = f"Step 3 CONTINUE: EXECUTE REMAINING TASKS - {executable_tasks} tasks ready to execute: {', '.join(executable_task_list)}. Complete ALL tasks before proceeding."
        else:
            next_step = f"Step 3 CONTINUE: EXECUTE OTHER TASKS after their dependencies are met. {remaining_tasks} tasks remain. Complete ALL tasks before proceeding."
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "status": "completed",
                "result_summary": result[:200] + "..." if len(result) > 200 else result,
                "dependent_tasks": dependent_tasks,
                "remaining_tasks": remaining_tasks,
                "next_step": next_step
            }),
            break_loop=False
        )

    async def _get_task_result(self, team_id, task_id="", **kwargs):
        """Get the result of a specific task"""
        self.log.update(progress=f"Retrieving result for task {task_id} in team {team_id}...")
        
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
        
        # Get tasks and team members
        tasks = team_leader.get_data("tasks") or {}
        team_members = team_leader.get_data("team_members") or {}
        
        # Check if task exists
        if not task_id or task_id not in tasks:
            return Response(
                message=self._format_response({
                    "error": f"Task {task_id} not found in team {team_id}",
                    "available_tasks": list(tasks.keys()) if tasks else []
                }),
                break_loop=False
            )
        
        task_data = tasks[task_id]
        
        # Check if task is completed
        if task_data["status"] != "completed":
            return Response(
                message=self._format_response({
                    "error": f"Task {task_id} is not completed (current status: {task_data['status']})",
                    "task_id": task_id,
                    "status": task_data["status"],
                    "next_step": "Execute this task before trying to retrieve its result"
                }),
                break_loop=False
            )
        
        # Get agent information
        agent_id = task_data["agent_id"]
        agent_role = "unknown"
        if agent_id in team_members:
            agent_role = team_members[agent_id]["role"]
        
        # Return task result
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "agent_role": agent_role,
                "task_description": task_data["description"],
                "status": "completed",
                "completed_at": task_data.get("completed_at"),
                "result": task_data["result"],
                "next_step": "Use this result as input for other tasks or incorporate it into your workflow"
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
        
        # Provide appropriate next steps based on completion status
        if completed_tasks < total_tasks:
            pending_tasks = []
            for task_id, task_data in tasks.items():
                if task_data["status"] != "completed":
                    agent_id = task_data["agent_id"]
                    agent_role = "unknown"
                    if agent_id in team_members:
                        agent_role = team_members[agent_id]["role"]
                    pending_tasks.append(f"{task_id} (assigned to {agent_role})")
                    
            next_step = f"Step 3 INCOMPLETE: {total_tasks - completed_tasks} TASKS STILL PENDING. Complete these tasks first: {', '.join(pending_tasks)}. Only after ALL tasks are completed, use integrate_results to synthesize the final deliverable."
        else:
            next_step = "Step 4: SYNTHESIZE ALL INFORMATION using the integrate_results action to create a comprehensive final deliverable that addresses the original goal."
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "name": team_data["name"],
                "goal": team_data["goal"],
                "completion": completion_status,
                "results": results,
                "next_step": next_step
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
                
        # Add document context if applicable
        if "doc_path" in data and "doc_status" not in data:
            data["doc_status"] = "available" # Default status if path exists but status isn't specified
            
        # Add specific context for document operations
        if "status" in data:
            if data["status"] == "team_created":
                if "doc_path" in data:
                    thoughts.append(f"Team created with planning document at {data['doc_path']}")
            elif data["status"] == "integration_review":
                thoughts.append("Completed document review phase of integration")
            elif data["status"] == "integrated":
                thoughts.append("Completed document update and integration of team results")
                
        # Add specific formatting guidance for get_results response
        if "results" in data and "error" not in data and "next_step" not in data:
            data["next_step"] = "Format your response to the user as a properly formatted JSON message using the response tool. Synthesize the individual contributions into a cohesive final product that addresses the user's original request."
        
        # Add specific guidance for integration results
        if "integrated_result" in data and "error" not in data and "next_step" not in data:
            data["next_step"] = "Use the response tool to share these integrated results with the user in a format that directly addresses their original request. Consider using code_execution tool if specific file output is needed."
        
        # Add context and summary for non-error responses to help maintain task focus
        if "error" not in data and "team_id" in data:
            # Get team data to add context
            teams = self.agent.get_data("teams") or {}
            team_id = data["team_id"]
            
            if team_id in teams:
                team_data = teams[team_id]
                
                # Add team context if not already present
                if "name" not in data and "goal" not in data:
                    data["team_name"] = team_data.get("name", "Unknown Team")
                    data["team_goal"] = team_data.get("goal", "Unknown Goal")
                
                # Add progress summary if team leader exists
                if "leader_agent" in team_data:
                    team_leader = team_data["leader_agent"]
                    tasks = team_leader.get_data("tasks") or {}
                    team_members = team_leader.get_data("team_members") or {}
                    
                    # Add team composition summary with agent IDs
                    if team_members and "team_composition" not in data:
                        team_composition = []
                        for agent_id, member_data in team_members.items():
                            if isinstance(member_data, dict) and "role" in member_data:
                                team_composition.append(f"{member_data['role']} ({agent_id})")
                        
                        if team_composition:
                            data["team_composition"] = f"{len(team_composition)} members: {', '.join(team_composition)}"
                    
                    # Add task progress summary
                    if tasks and "task_progress" not in data:
                        total = len(tasks)
                        completed = sum(1 for t in tasks.values() if t.get("status") == "completed")
                        executing = sum(1 for t in tasks.values() if t.get("status") == "executing")
                        assigned = sum(1 for t in tasks.values() if t.get("status") == "assigned")
                        
                        data["task_progress"] = f"{completed}/{total} tasks completed, {executing} executing, {assigned} pending"
                    
                    # Add task details summary if relevant
                    if "task_id" in data and data["task_id"] in tasks:
                        task_data = tasks[data["task_id"]]
                        agent_id = task_data.get("agent_id", "unknown")
                        agent_role = "unknown"
                        if agent_id in team_members and isinstance(team_members[agent_id], dict):
                            agent_role = team_members[agent_id].get("role", "unknown")
                        
                        # Add a short task summary with keywords
                        description = task_data.get("description", "")
                        keywords = " ".join(description.split()[:5]) + "..." if len(description.split()) > 5 else description
                        
                        data["task_summary"] = f"Task {data['task_id']} assigned to {agent_role} ({agent_id}): {keywords}"
                    
                    # Add comprehensive ordered task list
                    if tasks:
                        # First try to sort by explicit sequence number, fall back to creation timestamp
                        sorted_tasks = sorted(tasks.items(), key=lambda x: (
                            x[1].get("sequence_num", float('inf')),  # Sort by sequence first
                            x[1].get("created_at", 0)                # Then by creation time
                        ))
                        
                        tasks_ordered = []
                        for task_id, task_data in sorted_tasks:
                            agent_id = task_data.get("agent_id", "unknown")
                            agent_role = "unknown"
                            if agent_id in team_members and isinstance(team_members[agent_id], dict):
                                agent_role = team_members[agent_id].get("role", "unknown")
                            
                            # Create a concise description
                            description = task_data.get("description", "")
                            short_desc = " ".join(description.split()[:6]) + "..." if len(description.split()) > 6 else description
                            
                            # Add dependencies info if any
                            deps_info = ""
                            if task_data.get("depends_on"):
                                deps_info = f" (depends on: {', '.join(task_data['depends_on'])})"
                            
                            # Format the task entry with status, sequence number, and indices
                            status = task_data.get("status", "unknown")
                            seq_num = task_data.get("sequence_num", "?")
                            task_entry = f"#{seq_num} {task_id} [{status}]: {agent_role} - {short_desc}{deps_info}"
                            tasks_ordered.append(task_entry)
                        
                        if tasks_ordered:
                            data["tasks_ordered"] = tasks_ordered
                    
                    # Add task overview if this is a team status response (keep this for backward compatibility)
                    if "task_overview" not in data and len(tasks) > 0 and "task_id" not in data:
                        task_overview = []
                        for task_id, task_data in tasks.items():
                            agent_id = task_data.get("agent_id", "unknown")
                            status = task_data.get("status", "unknown")
                            description = task_data.get("description", "")
                            short_desc = " ".join(description.split()[:3]) + "..." if len(description.split()) > 3 else description
                            
                            agent_role = "unknown"
                            if agent_id in team_members and isinstance(team_members[agent_id], dict):
                                agent_role = team_members[agent_id].get("role", "unknown")
                                
                            task_overview.append(f"{task_id} ({status}): {agent_role} - {short_desc}")
                        
                        if task_overview:
                            data["task_overview"] = task_overview[:5]  # Limit to 5 tasks to avoid clutter
                            if len(task_overview) > 5:
                                data["task_overview"].append(f"...and {len(task_overview) - 5} more tasks")
        
        formatted_response = {
            "thoughts": thoughts,
            "tool_name": "team_agent",
            "tool_args": data
        }
        
        return json.dumps(formatted_response, indent=2)

    async def _integrate_results(self, team_id, step=None, review_summary=None, **kwargs):
        """Integrate results from all team members into a final product, now as a two-step process: review, then edit/update.\\n\\nBEST PRACTICE: For all markdown or code section edits, always read the necessary context, construct the full updated content, and overwrite the file in one write operation using the terminal `cat > /path/to/file << 'EOF' ... EOF` method. After writing, read the file back (`cat /path/to/file`) to confirm the update. Do NOT use regex, partial, or line-by-line replacements—these are unreliable."""
        # Enhanced progress tracking
        progress_prefix = f"Team {team_id} Integration"
        self.log.update(progress=f"{progress_prefix}: Starting integration process... Step: {step if step else 'default (review -> edit)'}")

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

        # Calculate overall progress and pending tasks early
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks.values() if t["status"] == "completed")
        pending_tasks = total_tasks - completed_tasks # Define pending_tasks here
        progress_percentage = f"{completed_tasks}/{total_tasks} tasks completed ({int(completed_tasks/total_tasks*100) if total_tasks else 0}%)"
        self.log.update(progress=f"{progress_prefix}: {progress_percentage}")

        # Initialize pending_warning
        pending_warning = "" 
        if pending_tasks > 0:
            pending_warning = f"\\n\\nNOTE: There are still {pending_tasks} pending tasks in this team. This integration only includes completed tasks."

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

        # Check if there are any completed results to integrate
        if not completed_results:
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "error": "No completed tasks found to integrate",
                    "next_step": "Execute tasks first with the execute_task action before attempting integration"
                }),
                break_loop=False
            )

        # Retrieve stored doc_path, with fallback
        doc_path = team_data.get("doc_path")
        if not doc_path:
            # Fallback calculation if doc_path wasn't stored
            project_name_fallback = team_data.get("name", "project").replace(" ", "_").lower()
            doc_dir = "/root/team_task" 
            doc_path = os.path.join(doc_dir, f"{project_name_fallback}.md")
            # Store it back for future use
            team_data["doc_path"] = doc_path
            teams[team_id] = team_data 
            self.agent.set_data("teams", teams) # Ensure teams data is updated in the agent
            self.log.update(progress=f"{progress_prefix}: doc_path was not found, using fallback and storing: {doc_path}")
        else:
            self.log.update(progress=f"{progress_prefix}: Using stored doc_path: {doc_path}")

        # --- Step Execution Logic --- 

        if step == "review":
            # Execute only the review step
            return await self._integrate_review_step(
                team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, 
                pending_tasks, progress_percentage
            )
        elif step == "edit":
            # Execute only the edit step (requires review_summary)
            if not review_summary:
                return Response(
                    message=self._format_response({
                        "team_id": team_id,
                        "error": "Missing review_summary for edit step.",
                        "next_step": "Run the 'review' step first to generate a review_summary, then pass it to the 'edit' step."
                    }),
                    break_loop=False
                )
            return await self._integrate_edit_step(
                team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, 
                review_summary, completed_results, pending_tasks, progress_percentage, pending_warning
            )
        elif step is None:
            # Default: Execute both steps sequentially
            self.log.update(progress=f"{progress_prefix}: Running default two-step integration (review -> edit)...")
            
            # Step 1: Review
            review_response = await self._integrate_review_step(
                team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, 
                pending_tasks, progress_percentage
            )
            
            # Check review response for errors
            try:
                review_data = json.loads(review_response.message)
                if "error" in review_data.get("tool_args", {}):
                    self.log.update(error=f"{progress_prefix}: Error during review step: {review_data['tool_args']['error']}")
                    return review_response # Return the error response from review step
                extracted_review_summary = review_data.get("tool_args", {}).get("review_summary")
                if not extracted_review_summary:
                     self.log.update(error=f"{progress_prefix}: Failed to extract review_summary from review step response.")
                     return Response(
                        message=self._format_response({
                            "team_id": team_id,
                            "error": "Internal error: Could not extract review summary after review step.",
                            "next_step": "Review step completed but summary was missing. Please report this issue."
                        }),
                        break_loop=False
                    )
            except (json.JSONDecodeError, AttributeError, TypeError) as e:
                self.log.update(error=f"{progress_prefix}: Failed to parse review step response: {e}")
                return Response(
                    message=self._format_response({
                        "team_id": team_id,
                        "error": f"Internal error parsing review step response: {e}",
                        "next_step": "The review step failed unexpectedly. Please report this issue."
                    }),
                    break_loop=False
                )
            
            self.log.update(progress=f"{progress_prefix}: Review step completed successfully. Proceeding to edit step.")
            
            # Step 2: Edit (using extracted summary)
            return await self._integrate_edit_step(
                team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, 
                extracted_review_summary, completed_results, pending_tasks, progress_percentage, pending_warning
            )
        else:
            # Invalid step value
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "error": f"Invalid step value: '{step}'. Must be 'review', 'edit', or omitted for default flow.",
                    "next_step": "Provide a valid step parameter or omit it."
                }),
                break_loop=False
            )

    async def _delete_task(self, team_id, task_id, **kwargs):
        """Delete a task from the team and remove it from dependencies of other tasks"""
        teams = self.agent.get_data("teams") or {}
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()),
                    "next_step": "Create a team first with the 'create' action or use a valid team_id"
                }),
                break_loop=False
            )
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        tasks = team_leader.get_data("tasks") or {}
        if not task_id or task_id not in tasks:
            return Response(
                message=self._format_response({
                    "error": f"Task {task_id} not found in team {team_id}",
                    "available_tasks": list(tasks.keys()),
                    "next_step": "Provide a valid task_id to delete"
                }),
                break_loop=False
            )
        # Remove the task
        del tasks[task_id]
        # Remove this task from any other task's depends_on list
        for t in tasks.values():
            if "depends_on" in t and task_id in t["depends_on"]:
                t["depends_on"] = [dep for dep in t["depends_on"] if dep != task_id]
        team_leader.set_data("tasks", tasks)
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "task_id": task_id,
                "status": "deleted",
                "next_step": "Task deleted. Review remaining tasks and dependencies. Use assign_task to add new tasks or update_task to modify existing ones."
            }),
            break_loop=False
        )

    async def _update_task(self, team_id, task_id, **kwargs):
        """Update properties of a task (description, depends_on, context, etc.)"""
        teams = self.agent.get_data("teams") or {}
        if not team_id or team_id not in teams:
            return Response(
                message=self._format_response({
                    "error": f"Team {team_id} not found",
                    "available_teams": list(teams.keys()),
                    "next_step": "Create a team first with the 'create' action or use a valid team_id"
                }),
                break_loop=False
            )
        team_data = teams[team_id]
        team_leader = team_data["leader_agent"]
        tasks = team_leader.get_data("tasks") or {}
        if not task_id or task_id not in tasks:
            return Response(
                message=self._format_response({
                    "error": f"Task {task_id} not found in team {team_id}",
                    "available_tasks": list(tasks.keys()),
                    "next_step": "Provide a valid task_id to update"
                }),
                break_loop=False
            )
        task = tasks[task_id]
        updated_fields = []
        # Circular dependency check if depends_on is being updated
        if "depends_on" in kwargs:
            if self._has_circular_dependency(tasks, task_id, kwargs["depends_on"]):
                return Response(
                    message=self._format_response({
                        "error": f"Circular dependency detected: updating these dependencies would create a cycle.",
                        "proposed_depends_on": kwargs["depends_on"],
                        "next_step": "Revise dependencies to avoid cycles."
                    }),
                    break_loop=False
                )
        # Update allowed fields
        for field in ["description", "depends_on", "context"]:
            if field in kwargs:
                task[field] = kwargs[field]
                updated_fields.append(field)
        tasks[task_id] = task
        team_leader.set_data("tasks", tasks)
        if updated_fields:
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "task_id": task_id,
                    "status": "updated",
                    "updated_fields": updated_fields,
                    "next_step": f"Task updated: {', '.join(updated_fields)}. Review dependencies and proceed as needed. You can use update_task again to make further changes or delete_task to remove this task."
                }),
                break_loop=False
            )
        else:
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "task_id": task_id,
                    "status": "no_changes",
                    "next_step": "No updatable fields provided. Specify at least one of: description, depends_on, context. Use update_task to modify a task or delete_task to remove it."
                }),
                break_loop=False
            )

    async def _team_planning_phase(self, prior_doc="", **kwargs):
        """Step-by-step team planning phase before agent creation, agent-driven doc management"""
        # Initialize progress tracking
        self.log.update(progress="Starting team planning phase...")
        
        planning_context = {}
        user_goal = kwargs.get("goal", "")
        user_name = kwargs.get("name", "Project")
        project_name = user_name.replace(" ", "_").lower()
        doc_dir = "/root/team_task"
        doc_path = os.path.join(doc_dir, f"{project_name}.md")
        template_path = os.path.join(doc_dir, "template_project_name.md")
        
        # Create team leader instance for planning
        team_leader = Agent(self.agent.number, self.agent.config, self.agent.context)
        
        # Step 1: Document check
        self.log.update(progress="Planning Step 1/7: Checking for existing planning document...")
        doc_check_prompt = (
            f"START OF TEAM PLANNING PHASE.\\n"
            f"Step 1: Initial Document Check (Perform ONCE)\\n"
            f"This is the very first step. Check if the file {doc_path} exists using `ls {doc_path}`.\\n"
            f"- If it exists: Read the entire file using `cat {doc_path}` and provide a structured summary of its sections and key content.\\n"
            f"- If it does NOT exist: State that clearly. Create it by copying the template at {template_path} using the reliable `cat > {doc_path} << \\'EOF\\' ... EOF` method, reading the template content first with `cat {template_path}`. Then, read the *newly created* file back using `cat {doc_path}` and summarize it.\\n"
            f"CRITICAL: Use the specified terminal commands (`ls`, `cat`, `cat > EOF`). After summarizing or creating the file THIS ONE TIME, you MUST immediately proceed to Step 2 (Project File Review). Do NOT repeat Step 1. Your output for Step 1 is just the summary. Now, continue to Step 2."
        )
        # The agent should summarize and then continue, not loop.
        team_leader.hist_add_user_message(UserMessage(message=doc_check_prompt, attachments=[]))
        doc_check_summary = await team_leader.monologue()
        planning_context["doc_check_summary"] = doc_check_summary
        self.log.update(progress="Planning Step 1/7: Document check complete: " + doc_check_summary[:100] + "...") # Add log here
        
        # Step 2: Project file review (as before, but reference doc)
        self.log.update(progress="Planning Step 2/7: Reviewing project files...") # Add log here
        file_review_prompt = (
            f"Step 2: Project File Review\\n"
            f"User's project goal: {user_goal}\\n"
            f"Team/Project name: {user_name}\n"
            "- List all directories in /root/.\n"
            "- Infer the most relevant project directory from the user's goal or prompt.\n"
            "- Review the contents of that directory. If it contains mostly subdirectories, look one level deeper.\n"
            "- Summarize the directory structure and the most relevant files (not just the first level).\n"
            "- Always state which directories and files you are reviewing in your output.\n"
            f"If a directory path is mentioned (e.g., /root/chess/), use it as the primary context for file review. "
            f"If the directory does not exist or is empty, propose a logical structure for the project under /root/[project_name]. "
        )
        team_leader.hist_add_user_message(UserMessage(message=file_review_prompt, attachments=[]))
        file_review = await team_leader.monologue()
        planning_context["file_review"] = file_review
        self.log.update(progress="Planning Step 2/7: Project file review complete.") # Add log here
        
        # Step 3: Goal/challenge inference
        self.log.update(progress="Planning Step 3/7: Inferring goal and challenges...") # Add log here
        goal_prompt = (
            "Step 3: Project Goal and Challenges\\n"
            "Based on the files and any available project description, summarize what you believe is the main project goal and any key challenges."
        )
        team_leader.hist_add_user_message(UserMessage(message=goal_prompt, attachments=[]))
        goal_summary = await team_leader.monologue()
        planning_context["goal_summary"] = goal_summary
        self.log.update(progress="Planning Step 3/7: Goal inference complete.") # Add log here
        
        # Step 4: Role/skill suggestion
        self.log.update(progress="Planning Step 4/7: Suggesting team roles...") # Add log here
        roles_prompt = (
            "Step 4: Team Roles and Skills\\n"
            "Given the project's structure and goal, suggest the roles and skills needed for the team. For each role, briefly state its purpose."
        )
        team_leader.hist_add_user_message(UserMessage(message=roles_prompt, attachments=[]))
        roles_suggestion = await team_leader.monologue()
        planning_context["roles_suggestion"] = roles_suggestion
        self.log.update(progress="Planning Step 4/7: Role suggestion complete.") # Add log here
        
        # Step 4a: Role-specific task assignment guidance
        self.log.update(progress="Planning Step 4a/7: Generating role-specific task guidance...") # Add log here
        role_task_prompt = (
            "Step 4a: Role-Specific Task Assignment Guidance\\n"
            "For each team role identified, create a unique, role-appropriate task that leverages the agent's expertise. "
            "Do NOT assign the same generic task to all agents. Instead, tailor each task to the agent's role and responsibilities. "
            "Provide a brief description of the task for each role."
        )
        team_leader.hist_add_user_message(UserMessage(message=role_task_prompt, attachments=[]))
        role_task_guidance = await team_leader.monologue()
        planning_context["role_task_guidance"] = role_task_guidance
        self.log.update(progress="Planning Step 4a/7: Task guidance generation complete.") # Add log here
        
        # Step 5: High-level task breakdown
        self.log.update(progress="Planning Step 5/7: Breaking down tasks...") # Add log here
        tasks_prompt = (
            "Step 5: High-Level Task Breakdown\\n"
            "Propose a high-level breakdown of main tasks (and possible subtasks) that the team should complete to achieve the project goal."
        )
        team_leader.hist_add_user_message(UserMessage(message=tasks_prompt, attachments=[]))
        task_breakdown = await team_leader.monologue()
        planning_context["task_breakdown"] = task_breakdown
        self.log.update(progress="Planning Step 5/7: Task breakdown complete.") # Add log here
        
        # Step 6: Clarifications/questions
        self.log.update(progress="Planning Step 6/7: Identifying clarifications...") # Add log here
        clarifications_prompt = (
            "Step 6: Clarifications or Questions\\n"
            "List any questions or missing information that would help you plan more effectively."
        )
        team_leader.hist_add_user_message(UserMessage(message=clarifications_prompt, attachments=[]))
        clarifications = await team_leader.monologue()
        planning_context["clarifications"] = clarifications
        self.log.update(progress="Planning Step 6/7: Clarification identification complete.") # Add log here
        
        # Step 7: Update doc with planning summary
        self.log.update(progress=f"Planning Step 7/7: Updating planning document at {doc_path}...") # Add log here
        # Construct the final planning summary string first
        planning_summary_content = (
            f"{doc_check_summary}\\n\\n" # Use the summary from step 1 # Escaped newline
            f"## Project File Review\\n{file_review}\\n\\n" # Escaped newline
            f"## Project Goal and Challenges\\n{goal_summary}\\n\\n" # Escaped newline
            f"## Team Roles and Skills\\n{roles_suggestion}\\n\\n" # Escaped newline
            f"## Role-Specific Task Assignment Guidance\\n{role_task_guidance}\\n\\n" # Escaped newline
            f"## High-Level Task Breakdown\\n{task_breakdown}\\n\\n" # Escaped newline
            f"## Clarifications or Questions\\n{clarifications}\\n" # Escaped newline
        )

        # Use the reliable full-overwrite method to update the document's overview section
        # Escape backticks and dollar signs within the heredoc content if they were potentially present
        escaped_planning_summary_content = planning_summary_content.replace('`', '\\`').replace('$', '\\$')

        doc_update_prompt = (
            f"Step 7: Update Planning Document ({doc_path})\\n"
            f"Task: Read the entire document at '{doc_path}' using `cat {doc_path}`. Find the '## Project Overview' section. Replace the content *under* this header with the new planning summary provided below. If the section doesn't exist, add it at an appropriate place (e.g., after the guide). Construct the full, updated markdown content *in memory* first.\\n"
            f"Then, overwrite the file at '{doc_path}' in ONE single write operation using the terminal heredoc method: `cat > {doc_path} << \\'EOF\\'\\n[Your FULL reconstructed file content]\\nEOF`.\\n"
            f"After writing, read the file back using `cat {doc_path}` to confirm the '## Project Overview' section contains the new summary.\\n"
            f"CRITICAL: Use the specified `cat` and `cat > EOF` commands. Do NOT use partial replacements or other runtimes.\\n"
            f"\\n--- New Project Overview Content (to be inserted) ---\\n{escaped_planning_summary_content}\\n--- End New Content ---" # Use the escaped content
        )

        team_leader.hist_add_user_message(UserMessage(message=doc_update_prompt, attachments=[]))
        doc_update_confirmation = await team_leader.monologue() # This should contain confirmation from the agent
        planning_context["doc_update_confirmation"] = doc_update_confirmation
        self.log.update(progress=f"Planning Step 7/7: Document update requested. Confirmation: {doc_update_confirmation[:100]}...") # Add log here
        
        # Final step with comprehensive log update
        self.log.update(progress=f"Planning phase complete. Planning document updated at {doc_path}") # Add final log here
        
        # Compose the complete planning summary for return
        # This includes the initial doc check summary and the confirmation from the update step
        final_planning_summary = (
            f"{doc_check_summary}\\n\\n" # Include initial doc check summary
            f"--- Planning Summary ---\\n"
            f"Project File Review:\\n{file_review}\\n\\n"
            f"Project Goal and Challenges:\\n{goal_summary}\\n\\n"
            f"Team Roles and Skills:\\n{roles_suggestion}\\n\\n"
            f"Role-Specific Task Assignment Guidance:\\n{role_task_guidance}\\n\\n"
            f"High-Level Task Breakdown:\\n{task_breakdown}\\n\\n"
            f"Clarifications or Questions:\\n{clarifications}\\n\\n"
            f"--- Document Update Confirmation ---\\n{doc_update_confirmation}\\n" # Include update confirmation
        )
        
        # Return planning summary along with confirmed doc_path and status
        return {
            "planning_summary": final_planning_summary, # Return the combined summary
            "doc_path": doc_path, # Return the confirmed doc_path used
            "status": "planning_complete" # Indicate planning is done
        }

    async def _integrate_review_step(self, team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, pending_tasks, progress_percentage):
        """Handles the 'review' step of the integration process."""
        self.log.update(progress=f"{progress_prefix} - STEP 1/2: Starting document review...")
        review_doc_prompt = (
            f"Integration Step 1: Review Planning/Results Document\\n" # Escaped newline
            f"Read the current planning/results document at {doc_path} using `cat {doc_path}`. Summarize its contents, especially the Project Overview and any previous Integration Review sections.\\n" # Escaped newline
            f"Then review the current project directory and files using `ls -R` or similar terminal commands. Validate that all expected deliverables are present and organized. Summarize results, check for gaps, and provide recommendations.\\n" # Escaped newline
            f"Your response should include:\\n" # Escaped newline
            f"- Directory/file review (list and describe key files and structure using terminal commands)\\n" # Escaped newline
            f"- Checklist of deliverables (what was expected, what is present, what is missing)\\n" # Escaped newline
            f"- Summary of results (from all completed tasks)\\n" # Escaped newline
            f"- Recommendations for improvement or next steps\\n" # Escaped newline
            f"Always state which directories and files you are reviewing in your output."
        )
        team_leader.hist_add_user_message(UserMessage(message=review_doc_prompt, attachments=[]))
        review_response = await team_leader.monologue()

        self.log.update(progress=f"{progress_prefix} - STEP 1/2: Document review complete.")

        return Response(
            message=self._format_response({
                "team_id": team_id,
                "status": "integration_review",
                "review_summary": review_response,
                "pending_tasks": pending_tasks, # Use the calculated value
                "team_progress": progress_percentage, # Add progress
                "doc_path": doc_path, # Add doc path
                "team_name": team_data.get("name", "Unknown"), # Add team name
                "team_goal": team_data.get("goal", "Unknown"), # Add team goal
                "next_step": "Step 2: Use the 'edit' step to update the document and synthesize the final integration based on this review. Pass the review_summary as input."
            }),
            break_loop=False
        )

    async def _integrate_edit_step(self, team_id, team_data, team_leader, tasks, team_members, doc_path, progress_prefix, review_summary, completed_results, pending_tasks, progress_percentage, pending_warning):
        """Handles the 'edit' step of the integration process."""
        self.log.update(progress=f"{progress_prefix} - STEP 2/2: Starting document update...")
        if not review_summary:
            return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "error": "Missing review_summary for edit step.",
                    "next_step": "Run the 'review' step first to generate a review_summary, then pass it to the 'edit' step."
                }),
                break_loop=False
            )

        # Ensure doc_path is valid before proceeding
        if not doc_path: # Check if doc_path is None or empty after potential fallback
             return Response(
                message=self._format_response({
                    "team_id": team_id,
                    "error": "Document path could not be determined for editing.",
                    "next_step": "Verify team data and naming conventions."
                }),
                break_loop=False
            )

        # Update Integration Review section
        def update_markdown_section(file_path, section_header, new_content):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except FileNotFoundError:
                lines = []
            start_idx = None
            end_idx = None
            for i, line in enumerate(lines):
                if line.strip() == section_header:
                    start_idx = i
                    for j in range(i+1, len(lines)):
                        if lines[j].startswith('## ') and lines[j].strip() != section_header:
                            end_idx = j
                            break
                    if end_idx is None:
                        end_idx = len(lines)
                    break
            section_block = [section_header + '\\n', new_content.strip() + '\\n'] # Escaped newlines
            if start_idx is not None:
                new_lines = lines[:start_idx] + section_block + lines[end_idx:]
            else:
                if lines and not lines[-1].endswith('\\n'): # Escaped newline
                    lines[-1] += '\\n' # Escaped newline
                new_lines = lines + ['\\n'] + section_block # Escaped newline
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

        update_markdown_section(doc_path, '## Integration Review', review_summary)
        # Note: doc_update_confirmation below gets overwritten by the monologue call
        # This initial string serves mainly as a placeholder in case the monologue fails.
        doc_update_confirmation_initial = f"Integration Review section updated in {doc_path}."

        # Prompt the agent to review and update the entire document
        doc_update_prompt = (
            f"Integration Step 2: Update Planning/Results Document\\n" # Escaped newline
            f"Read the entire document at {doc_path}. Review all sections, especially Project Overview and Integration Review. "
            f"Update the document to reflect the latest results, recommendations, and integration review. "
            f"Save the updated document, ensuring all sections are well-structured and up to date. Confirm the update."
        )
        team_leader.hist_add_user_message(UserMessage(message=doc_update_prompt, attachments=[]))
        doc_update_confirmation = await team_leader.monologue()

        # Enhanced integration prompt with better guidance
        integration_prompt = f'''
        As the leader of the {team_data['name']} team, your critical responsibility is to synthesize all team contributions
        into a cohesive, polished final product that fulfills our goal: {team_data['goal']}

        COMPLETED TEAM CONTRIBUTIONS:
        {json.dumps(completed_results, indent=2)}
        {pending_warning} # Use the initialized pending_warning

        INTEGRATION REVIEW:
        {review_summary}

        DOCUMENT UPDATE CONFIRMATION:
        {doc_update_confirmation}

        INTEGRATION OBJECTIVE:
        Transform these separate contributions into a seamless, unified deliverable that achieves our team goal and meets the user\\'s needs.

        YOUR INTEGRATION ROLE:
        1. Identify the key insights and valuable content from each contribution
        2. Resolve any inconsistencies or conflicts between contributions
        3. Establish a logical flow and structure for the integrated result
        4. Ensure all critical information is included without unnecessary repetition
        5. Maintain a consistent voice, style, and level of technical detail
        6. Verify that the final product directly addresses the original goal

        INTEGRATION METHODOLOGY:
        - Begin with a high-level synthesis plan
        - Extract core content from each contribution
        - Create a unified structure that builds logically
        - Fill gaps and eliminate redundancies
        - Add transitions to create seamless flow between sections
        - Review for completeness, coherence, and alignment with the goal

        QUALITY CRITERIA FOR FINAL DELIVERABLE:
        - Comprehensiveness: Covers all essential aspects of the topic
        - Coherence: Presents a unified perspective rather than disjointed views
        - Clarity: Communicates ideas in a clear, accessible manner
        - Conciseness: Avoids unnecessary repetition while maintaining completeness
        - Alignment: Directly addresses the original goal
        - Readability: Well-structured with appropriate transitions and flow

        OUTPUT FORMAT REQUIREMENTS:
        You MUST respond using the exact JSON format below to ensure proper delivery to the user:

        ```json
        {{
            "thoughts": [
                "Your integration strategy and approach",
                "How you synthesized the different contributions",
                "Your assessment of the integrated final product"
            ],
            "tool_name": "response",
            "tool_args": {{
                "text": "Your complete integrated result here. This should be comprehensive, cohesive, and directly address the team goal."
            }}
        }}
        ```

        The "text" field must contain the complete integrated final product, ready for delivery to the user.
        '''
        self.log.update(progress=f"{progress_prefix} - STEP 2/2: Document update complete. Integration in progress...")
        try:
            team_leader.hist_add_user_message(UserMessage(message=integration_prompt, attachments=[]))
            integrated_result = await team_leader.monologue()
            self.log.update(progress=f"{progress_prefix}: Integration complete.") # Update log here
        except Exception as e:
            self.log.update(error=f"Error during integration: {str(e)}")
            integrated_result = f"Error during integration: {str(e)}"

        if pending_tasks > 0: # Use the calculated value
            next_step = f"Step 3: DELIVER FINAL PRODUCT - Summarize and present integrated results to the user using the response tool. To get a more complete result, consider completing the remaining {pending_tasks} tasks first."
        else:
            next_step = "Step 3: DELIVER FINAL PRODUCT - Summarize and present these integrated results to the user as a comprehensive deliverable using the response tool. Use the text field to provide the complete answer that addresses the original request."

        return Response(
            message=self._format_response({
                "team_id": team_id,
                "status": "integrated",
                "team_name": team_data.get("name", "Unknown"), # Add team name
                "team_goal": team_data.get("goal", "Unknown"), # Add team goal
                "team_progress": progress_percentage, # Add progress
                "doc_path": doc_path, # Add doc path
                "document_status": "updated", # Add doc status
                "integrated_result": integrated_result,
                "pending_tasks": pending_tasks, # Use the calculated value
                "next_step": next_step
            }),
            break_loop=False
        )