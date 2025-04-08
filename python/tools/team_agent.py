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
            elif action == "get_task_result":
                self.log.update(progress=f"Getting specific task result from team {team_id}...")
                return await self._get_task_result(team_id, **kwargs)
            else:
                self.log.update(error=f"Unknown action: {action}")
                return Response(
                    message=self._format_response({
                        "error": f"Unknown action: {action}",
                        "available_actions": [
                            "create", "add_agent", "assign_task", 
                            "execute_task", "message", "get_results", 
                            "team_status", "integrate_results", "get_task_result"
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
                        "team_status", "integrate_results", "get_task_result"
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
                "next_step": "Step 1: CREATE ALL TEAM AGENTS FIRST by using add_agent multiple times to create each specialized agent needed for the task. Only proceed to assigning tasks after all agents are created."
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
        
        next_step = f"Step 1 CONTINUE: ADD MORE AGENTS if needed to complete the team composition. You have {member_count} agent(s) so far. Once ALL needed agents are created, proceed to Step 2: ASSIGN TASKS to each agent using the assign_task action."
        
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
        
        # Get existing tasks to determine sequence number and auto-dependencies
        tasks = team_leader.get_data("tasks") or {}
        sequence_num = len(tasks) + 1  # Start from 1
        
        # If no dependencies were explicitly provided, automatically set the most recent task as a dependency
        if not depends_on and tasks:
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
            "auto_dependency": True if not kwargs.get("depends_on") and depends_on else False
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
        
        if agents_without_tasks:
            next_step = f"Step 2 CONTINUE: ASSIGN TASKS to remaining agents ({', '.join(agents_without_tasks)}). Only after ALL agents have assigned tasks, proceed to Step 3: EXECUTE TASKS using the execute_task action."
        else:
            next_step = "Step 3: EXECUTE ALL TASKS by using execute_task for each task in sequence. Start with tasks that have no dependencies."
        
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
                "auto_dependency": True if not kwargs.get("depends_on") and depends_on else False,
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

AVAILABLE TOOLS:
- knowledge_tool: For research and information gathering
- code_execution_tool: For computation, data processing, file operations
- response_tool: REQUIRED for your final output

TERMINAL & CODE EXECUTION GUIDELINES:

1. For code execution, select the appropriate runtime:
   - "terminal": Shell commands and system operations
   - "python": Python code execution
   - "nodejs": JavaScript code execution
   - "output": Wait for output from long-running processes
   - "reset": Kill a stuck or non-responsive process

2. HANDLING TERMINAL INTERACTIONS:
   - For ANY command requiring user input (Y/N prompts, etc.), use "terminal" runtime in your next step
   - When installation prompts appear, respond with follow-up "terminal" commands
   - If a command seems stuck or frozen, use "reset" runtime to kill the process
   - For long-running commands, use "output" runtime to wait for completion

3. PROGRESSIVE DEVELOPMENT:
   - Always develop incrementally, with small working steps
   - Test each component before integrating
   - If you encounter errors, try simplified approaches rather than repeating the same pattern
   - Don't get stuck in loops - if something fails twice, try a different approach

4. FILE OPERATIONS:
   - Always verify file existence with "ls" before operations
   - Use explicit paths for all file operations (prefer /root/ directory)
   - Files in /root/ PERSIST between calls and are accessible to the team
   - Document any files you create for other team members

TOOL USAGE:

For code execution:
```json
{{
    "thoughts": ["I need to process data or perform calculations"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "python",  // Options: "terminal", "nodejs", "output", "reset"
        "code": "import os\\n\\nprint('Current directory:', os.getcwd())"  // Always use explicit print()/console.log()
    }}
}}
```

For knowledge lookup:
```json
{{
    "thoughts": ["I need specific information"],
    "tool_name": "knowledge_tool",
    "tool_args": {{
        "question": "Focused question directly related to my task"
    }}
}}
```

For your final response:
```json
{{
    "thoughts": [
        "Analysis of approach and results",
        "Key findings and limitations"
    ],
    "tool_name": "response",
    "tool_args": {{
        "text": "Complete, well-structured deliverable with all necessary details"
    }}
}}
```

CORE TERMINAL PATTERNS:

1. CREATING FILES:
   ```json
   {{
       "thoughts": ["Creating a file with code"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "cat << 'EOF' > /root/filename.py\\n# Python code here\\ndef main():\\n    print('Hello')\\n\\nif __name__ == '__main__':\\n    main()\\nEOF"
       }}
   }}
   ```
   IMPORTANT: The 'EOF' marker MUST be at the start of a new line with NO SPACES to properly close heredoc.

2. DIRECTORY OPERATIONS:
   ```json
   {{
       "thoughts": ["Creating and checking directories"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "mkdir -p /root/myproject && ls -la /root/myproject"
       }}
   }}
   ```

3. INSTALLING PACKAGES:
   ```json
   {{
       "thoughts": ["Installing required packages"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "pip install numpy pandas matplotlib"
       }}
   }}
   ```

4. WAITING FOR OUTPUT:
   ```json
   {{
       "thoughts": ["Waiting for long-running process to complete"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "output"
       }}
   }}
   ```

5. RESETTING TERMINAL:
   ```json
   {{
       "thoughts": ["Terminal is stuck or unresponsive"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "reset"
       }}
   }}
   ```

EXECUTION WORKFLOW:

1. UNDERSTAND: Analyze the task requirements and how they relate to previous work
2. PLAN: Break down complex problems into smaller, manageable steps
3. IMPLEMENT: Develop incrementally, with frequent testing and validation
4. DOCUMENT: Ensure your solution is clear and can be integrated with the team's work
5. FINALIZE: Submit a comprehensive response with your complete solution

Remember: The response_tool is REQUIRED for your final output. Deliver your results using this tool.
"""
        
        # Execute task using call_subordinate pattern
        # Let the user know we're delegating to a team member
        self.log.update(progress=f"Delegating to {agent_role} agent...")
        
        # Log the full prompt being sent to the agent for debugging and transparency
        self.log.update(context=f"Task Context Being Passed:\n\n{prompt}")
        
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
        
        # Check for any pending tasks and provide warning
        pending_tasks = sum(1 for t in tasks.values() if t["status"] != "completed")
        pending_warning = ""
        if pending_tasks > 0:
            pending_warning = f"\n\nNOTE: There are still {pending_tasks} pending tasks in this team. This integration only includes completed tasks."

        # Enhanced integration prompt with better guidance
        integration_prompt = f"""
        As the leader of the {team_data['name']} team, your critical responsibility is to synthesize all team contributions 
        into a cohesive, polished final product that fulfills our goal: {team_data['goal']}

        COMPLETED TEAM CONTRIBUTIONS:
        {json.dumps(completed_results, indent=2)}
        {pending_warning}

        INTEGRATION OBJECTIVE:
        Transform these separate contributions into a seamless, unified deliverable that achieves our team goal and meets the user's needs.

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
        
        # Create appropriate next steps based on task status
        if pending_tasks > 0:
            next_step = f"Step 5: DELIVER FINAL PRODUCT - Summarize and present integrated results to the user using the response tool. To get a more complete result, consider completing the remaining {pending_tasks} tasks first."
        else:
            next_step = "Step 5: DELIVER FINAL PRODUCT - Summarize and present these integrated results to the user as a comprehensive deliverable using the response tool. Use the text field to provide the complete answer that addresses the original request."
        
        return Response(
            message=self._format_response({
                "team_id": team_id,
                "status": "integrated",
                "integrated_result": integrated_result,
                "pending_tasks": pending_tasks,
                "next_step": next_step
            }),
            break_loop=False
        )