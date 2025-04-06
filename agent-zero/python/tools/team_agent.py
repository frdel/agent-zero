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
- code_execution_tool: For computation, data processing, file operations, visualization
- response_tool: REQUIRED for your final output

TOOL USAGE:

For code execution (supports python, nodejs, terminal):
```json
{{
    "thoughts": ["I need to process data or perform calculations"],
    "tool_name": "code_execution_tool",
    "tool_args": {{
        "runtime": "python",  // Also: "terminal", "nodejs", "output" (wait for results), "reset" (if stuck)
        "code": "import os\\nimport json\\n\\n# Process data\\nresults = {{'key': 'value'}}\\n\\n# Save outputs to /root directory\\nwith open('/root/results.json', 'w') as f:\\n    json.dump(results, f, indent=2)\\n\\nprint('Results saved successfully')"  // Always use explicit print()/console.log()
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
        "Analysis of approach and process",
        "Key findings and deliverables"
    ],
    "tool_name": "response",
    "tool_args": {{
        "text": "Complete, well-structured deliverable with all necessary details"
    }}
}}
```

FILE OPERATIONS BEST PRACTICES:

When working with files in the /root/ directory:
1. CHECK: Always verify file existence first with terminal commands
   ```json
   {{
       "thoughts": ["I need to check if files exist"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "ls -la /root/"
       }}
   }}
   ```

2. CREATE/MODIFY: Use the terminal runtime with heredoc for reliable file creation
   ```json
   {{
       "thoughts": ["I need to save code to a file"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "cat << 'EOF' > /root/filename.py\\n# Your code here\\n\\ndef main():\\n    print('Hello')\\n\\nif __name__ == '__main__':\\n    main()\\nEOF"
       }}
   }}
   ```

3. VERIFY: Always confirm your file operations worked
   ```json
   {{
       "thoughts": ["Verifying the file was created properly"],
       "tool_name": "code_execution_tool", 
       "tool_args": {{
           "runtime": "terminal",
           "code": "cat /root/filename.py"
       }}
   }}
   ```

4. TEST: Execute your files to test functionality
   ```json
   {{
       "thoughts": ["Testing the script functionality"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\ntry:\\n    import filename\\n    # Run tests here\\nexcept Exception as e:\\n    print(f'Error: {{e}}')"
       }}
   }}
   ```

5. UNIFIED COMMAND EXECUTION: Combine commands with verification
   ```json
   {{
       "thoughts": ["Creating directory structure all at once"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "mkdir -p /root/myproject && ls -la /root/myproject && mkdir -p /root/myproject/subdir1 /root/myproject/subdir2 && ls -la /root/myproject"
       }}
   }}
   ```

6. ALTERNATIVE PATH STRATEGY: Use current directory as fallback
   ```json
   {{
       "thoughts": ["Using current directory as fallback"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "pwd && mkdir -p ./myproject/subdir1 ./myproject/subdir2 && ls -la ./myproject"
       }}
   }}
   ```

7. PYTHON-FIRST APPROACH: Use Python for critical file operations
   ```json
   {{
       "thoughts": ["Using Python for reliable directory creation"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import os\\n\\n# Create all directories at once\\nos.makedirs('/root/myproject/subdir1', exist_ok=True)\\nos.makedirs('/root/myproject/subdir2', exist_ok=True)\\n\\n# Verify\\nprint(f\"Created: {{os.path.exists('/root/myproject/subdir1')}}\")"
       }}
   }}
   ```

IMPORTANT: Files in /root/ PERSIST between tool invocations and are accessible to other team members. Always use complete file paths and document created files for your team.

EXPANDED FILE OPERATION EXAMPLES:

1. APPENDING to existing files:
   ```json
   {{
       "thoughts": ["I need to append to an existing file"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "cat << 'EOF' >> /root/existing_file.py\\n\\n# New content to append\\ndef new_function():\\n    return 'New functionality'\\nEOF"
       }}
   }}
   ```

2. READING specific lines from files:
   ```json
   {{
       "thoughts": ["I need to read specific lines from a file"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "sed -n '10,20p' /root/some_file.py"
       }}
   }}
   ```

3. SEARCHING in files:
   ```json
   {{
       "thoughts": ["I need to find specific content in files"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "grep -n 'function_name' /root/*.py"
       }}
   }}
   ```

4. RENAMING files:
   ```json
   {{
       "thoughts": ["I need to rename a file"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "mv /root/old_name.py /root/new_name.py && echo 'File renamed successfully'"
       }}
   }}
   ```

5. JSON file handling:
   ```json
   {{
       "thoughts": ["I need to update a JSON configuration file"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import json\\n\\n# Read existing JSON\\ntry:\\n    with open('/root/config.json', 'r') as f:\\n        config = json.load(f)\\nexcept FileNotFoundError:\\n    config = {{}}\\n\\n# Update configuration\\nconfig['new_setting'] = 'new_value'\\n\\n# Write back to file\\nwith open('/root/config.json', 'w') as f:\\n    json.dump(config, f, indent=2)\\n\\nprint(f'Updated config: {{config}}')"
       }}
   }}
   ```

COMPREHENSIVE TESTING PROTOCOLS:

1. UNIT TESTING: Test individual functions
   ```json
   {{
       "thoughts": ["Testing individual functions"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\n# Import the module to test\\nimport my_module\\n\\ndef test_function():\\n    # Define test cases\\n    test_cases = [\\n        {{\\n            'input': 5,\\n            'expected': 25,\\n            'description': 'Testing with positive integer'\\n        }},\\n        {{\\n            'input': -3,\\n            'expected': 9,\\n            'description': 'Testing with negative integer'\\n        }},\\n        {{\\n            'input': 0,\\n            'expected': 0,\\n            'description': 'Testing with zero'\\n        }}\\n    ]\\n    \\n    # Run tests\\n    for tc in test_cases:\\n        result = my_module.square(tc['input'])\\n        if result == tc['expected']:\\n            print(f\"PASS: {{tc['description']}} - Got {{result}}\")\\n        else:\\n            print(f\"FAIL: {{tc['description']}} - Expected {{tc['expected']}}, Got {{result}}\")\\n\\ntest_function()"
       }}
   }}
   ```

2. INTEGRATION TESTING: Test interaction between components
   ```json
   {{
       "thoughts": ["Testing integration between components"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\n# Import modules to test integration\\nfrom data_processor import process_data\\nfrom data_validator import validate_data\\n\\n# Test data\\ntest_input = [1, 2, 'invalid', 3]\\n\\nprint(f\"Input: {{test_input}}\")\\n\\ntry:\\n    # Test the integration flow\\n    print(\"Step 1: Validating data...\")\\n    validated_data = validate_data(test_input)\\n    print(f\"Validation result: {{validated_data}}\")\\n    \\n    print(\"Step 2: Processing validated data...\")\\n    processed_data = process_data(validated_data)\\n    print(f\"Processing result: {{processed_data}}\")\\n    \\n    print(\"✅ Integration test passed!\")\\nexcept Exception as e:\\n    print(f\"❌ Integration test failed: {{e}}\")"
       }}
   }}
   ```

3. ERROR HANDLING TESTS: Verify proper error handling
   ```json
   {{
       "thoughts": ["Testing error handling"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\n# Import the module to test\\nimport file_handler\\n\\n# Test error handling\\ndef test_error_handling():\\n    # Test cases for error conditions\\n    error_tests = [\\n        {{\\n            'test': lambda: file_handler.read_file('nonexistent_file.txt'),\\n            'expected_error': FileNotFoundError,\\n            'description': 'Reading nonexistent file'\\n        }},\\n        {{\\n            'test': lambda: file_handler.parse_json('invalid_json.txt'),\\n            'expected_error': json.JSONDecodeError,\\n            'description': 'Parsing invalid JSON'\\n        }}\\n    ]\\n    \\n    # Run error tests\\n    for test in error_tests:\\n        try:\\n            result = test['test']()\\n            print(f\"FAIL: {{test['description']}} - Expected {{test['expected_error'].__name__}} but no error occurred\")\\n        except Exception as e:\\n            if isinstance(e, test['expected_error']):\\n                print(f\"PASS: {{test['description']}} - Correctly raised {{type(e).__name__}}\")\\n            else:\\n                print(f\"FAIL: {{test['description']}} - Expected {{test['expected_error'].__name__}} but got {{type(e).__name__}}\")\\n\\ntest_error_handling()"
       }}
   }}
   ```

4. FUNCTIONAL TESTING: End-to-end workflow testing
   ```json
   {{
       "thoughts": ["Testing complete workflow"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\n# Import the main module that orchestrates the workflow\\nimport workflow\\n\\n# Sample input for workflow\\ninput_data = {{\\n    'user_id': 123,\\n    'parameters': {{\\n        'start_date': '2023-01-01',\\n        'end_date': '2023-01-31',\\n        'type': 'report'\\n    }}\\n}}\\n\\nprint(\"Starting functional test of complete workflow...\")\\nprint(f\"Input: {{input_data}}\")\\n\\ntry:\\n    # Run the entire workflow\\n    result = workflow.run(input_data)\\n    \\n    # Check expected output format\\n    required_keys = ['status', 'result', 'timestamp']\\n    missing_keys = [key for key in required_keys if key not in result]\\n    \\n    if missing_keys:\\n        print(f\"❌ Test failed: Missing required keys: {{missing_keys}}\")\\n    else:\\n        print(f\"✅ Workflow executed successfully with result:\\n{{result}}\\n\\nAll required keys present in output.\")\\nexcept Exception as e:\\n    print(f\"❌ Workflow test failed with error: {{e}}\")"
       }}
   }}
   ```

5. DATA VALIDATION TESTING: Verify input/output formats
   ```json
   {{
       "thoughts": ["Testing data validation"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "import sys\\nsys.path.append('/root')\\n\\n# Import validation module\\nfrom data_validator import validate\\n\\n# Test cases with both valid and invalid data\\ntest_cases = [\\n    {{\\n        'data': {{\\n            'name': 'Test User',\\n            'email': 'test@example.com',\\n            'age': 25\\n        }},\\n        'expected_valid': True,\\n        'description': 'Valid complete user data'\\n    }},\\n    {{\\n        'data': {{\\n            'name': 'Test User',\\n            'email': 'invalid-email'\\n        }},\\n        'expected_valid': False, \\n        'description': 'Invalid email format'\\n    }},\\n    {{\\n        'data': {{\\n            'name': '',\\n            'email': 'test@example.com'\\n        }},\\n        'expected_valid': False,\\n        'description': 'Empty required field'\\n    }}\\n]\\n\\n# Run validation tests\\nfor tc in test_cases:\\n    print(f\"Testing: {{tc['description']}}\\n  Input: {{tc['data']}}\")\\n    \\n    try:\\n        validation_result = validate(tc['data'])\\n        is_valid = validation_result.get('valid', False)\\n        \\n        if is_valid == tc['expected_valid']:\\n            print(f\"  ✅ PASS: Validation returned {{is_valid}} as expected\")\\n        else:\\n            print(f\"  ❌ FAIL: Expected {{tc['expected_valid']}} but got {{is_valid}}\")\\n        \\n        if 'errors' in validation_result and not is_valid:\\n            print(f\"  Validation errors: {{validation_result['errors']}}\")\\n            \\n    except Exception as e:\\n        print(f\"  ❌ FAIL: Validation threw unexpected exception: {{e}}\")\\n    \\n    print(\"\")"
       }}
   }}
   ```

CODE EXECUTION BEST PRACTICES:

1. HEREDOC FORMATTING: Use the correct syntax for heredoc file creation
   ```json
   {{
       "thoughts": ["Creating a Python file with proper heredoc syntax"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "terminal",
           "code": "cat << 'EOF' > /root/example.py\\n# Python code here\\n\\ndef function():\\n    print('Success')\\n\\nfunction()\\nEOF"
       }}
   }}
   ```
   IMPORTANT: Note that the 'EOF' marker MUST be at the start of a new line with NO SPACES before it to properly close the heredoc.

2. STRING ESCAPING: Handle nested quotes properly
   ```json
   {{
       "thoughts": ["Handling nested quotes in strings"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "# Single quotes inside double quotes\\nprint(\"This contains 'single quotes'\")\\n\\n# Double quotes inside single quotes\\nprint('This contains \"double quotes\"')\\n\\n# Alternative for complex strings\\nmultiline = '''\\nThis string has both 'single' and \"double\" quotes\\nand spans multiple lines\\n'''\\nprint(multiline)"
       }}
   }}
   ```

3. PYTHON INDENTATION: Maintain consistent indentation (4 spaces recommended)
   ```json
   {{
       "thoughts": ["Using proper Python indentation"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "def outer_function():\\n    # 4 spaces for first level indent\\n    print('First level indent')\\n    \\n    def inner_function():\\n        # 8 spaces for second level indent\\n        print('Second level indent')\\n        \\n        for i in range(3):\\n            # 12 spaces for third level indent\\n            print(f'Third level indent: {{i}}')\\n    \\n    inner_function()\\n\\nouter_function()"
       }}
   }}
   ```

4. INCREMENTAL DEVELOPMENT: Develop and test in small steps
   ```json
   {{
       "thoughts": ["Developing incrementally"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "# Step 1: Define basic structure\\ndef process_data(data):\\n    # TODO: Implement processing\\n    return data\\n\\n# Test simple case first\\ntest_data = ['item1', 'item2']\\nprint(f'Initial test: {{process_data(test_data)}}')"
       }}
   }}
   ```
   
   ```json
   {{
       "thoughts": ["Extending functionality after testing basics"],
       "tool_name": "code_execution_tool",
       "tool_args": {{
           "runtime": "python",
           "code": "# Step 2: Implement actual processing\\ndef process_data(data):\\n    # Now implementing the actual logic\\n    return [item.upper() for item in data]\\n\\n# Test again with the same data\\ntest_data = ['item1', 'item2']\\nprint(f'Enhanced test: {{process_data(test_data)}}')"
       }}
   }}
   ```

EXECUTION WORKFLOW:

For tasks involving code and files, follow this sequence:
1. UNDERSTAND the task requirements and how it relates to previous work
2. CHECK for existing files relevant to your task
3. DEVELOP your solution incrementally
4. SAVE your complete solution to the appropriate file
5. VERIFY your solution works as expected
6. DOCUMENT your work clearly for other team members

Remember: Your work should build upon previous tasks and enable subsequent tasks.

EXECUTION APPROACH:
1. Analyze requirements thoroughly
2. Use appropriate tools for research and computation
3. Structure your output for clarity and team integration
4. Include any limitations or uncertainties in your approach
5. Ensure your final response is comprehensive and directly addresses the task

REQUIRED RESPONSE FORMAT:
```json
{{
    "thoughts": [
        "Initial analysis and approach",
        "Implementation process and methods",
        "Quality assessment and limitations"
    ],
    "tool_name": "response",
    "tool_args": {{
        "text": "Your complete, detailed deliverable formatted appropriately for team integration"
    }}
}}
```"""
        
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