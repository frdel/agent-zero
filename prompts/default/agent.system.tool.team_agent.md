### team_agent:

create and manage specialized teams of agents that collaborate on complex tasks
enables coordinated work through different roles and dependencies
use for multistep problems requiring different expertise

usage:

```json
{
  "thoughts": [
    "I need to create a research team to investigate this complex problem"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "create",
    "name": "Research Team",
    "goal": "Research quantum computing algorithms"
  }
}
```

```json
{
  "thoughts": [
    "I need to add a researcher who can find information"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "add_agent",
    "team_id": "team_abcd1234",
    "role": "researcher",
    "skills": ["information gathering", "analysis"]
  }
}
```

```json
{
  "thoughts": [
    "I'll assign a task to the researcher agent"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "assign_task",
    "team_id": "team_abcd1234",
    "agent_id": "agent_xyz789",
    "task": "Find the 3 most recent papers on quantum computing algorithms",
    "context": "Focus on papers from the last 2 years"
  }
}
```

```json
{
  "thoughts": [
    "Time to execute the task I assigned"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "execute_task",
    "team_id": "team_abcd1234",
    "task_id": "task_def456"
  }
}
```

```json
{
  "thoughts": [
    "I should share information between agents"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "message",
    "team_id": "team_abcd1234",
    "from": "agent_xyz789",
    "to": "agent_abc123",
    "content": "I found 3 relevant papers on quantum algorithms"
  }
}
```

```json
{
  "thoughts": [
    "Let's get all the results from the team"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "get_results",
    "team_id": "team_abcd1234"
  }
}
```

```json
{
  "thoughts": [
    "I need to check the team's progress"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "team_status",
    "team_id": "team_abcd1234"
  }
}
```

```json
{
  "thoughts": [
    "I need to retrieve a specific task result to reference in my current work"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "get_task_result",
    "team_id": "team_abcd1234",
    "task_id": "task_def456"
  }
}
```

```json
{
  "thoughts": [
    "Now that I have all the results, I need to integrate them into a cohesive final product"
  ],
  "tool_name": "team_agent",
  "tool_args": {
    "action": "integrate_results",
    "team_id": "team_abcd1234"
  }
}
```

workflow sequence:
1. create a team
2. add specialized agents with clear roles
3. assign specific tasks to agents
4. execute tasks one at a time
5. share results between agents as needed
6. get all results with get_results
7. integrate results into a final product
8. respond to the user with the final integrated work

IMPORTANT: Follow this precise workflow for optimal results:

STEP 1: CREATE TEAM & ALL AGENTS
- First create the team with the 'create' action
- Then add ALL needed specialized agents with 'add_agent' before assigning any tasks
- Only proceed to task assignment after ALL required agents are created

STEP 2: ASSIGN ALL TASKS
- Assign tasks to EACH agent with the 'assign_task' action
- Make sure to specify the correct agent_id for each task
- Define dependencies between tasks if needed
- Only proceed to execution after ALL tasks are assigned

STEP 3: EXECUTE ALL TASKS
- Execute each task using 'execute_task' in dependency order
- Complete ALL tasks before proceeding to results integration
- Tasks with dependencies will automatically receive results from prerequisite tasks
- Use 'get_task_result' if you need to access specific task outputs during execution

STEP 4: COMPILE & SYNTHESIZE
- First gather all task results with 'get_results'
- Then synthesize into a complete product with 'integrate_results'
- Ensure the integrated result directly addresses the original goal

STEP 5: DELIVER FINAL PRODUCT
- Present the integrated results to the user in a comprehensive manner
- Use the response tool to provide the complete answer to the original request

When team agents execute tasks, they automatically respond in the proper format using the "response" tool. Team management handles all communication between agents for you - you only need to use the actions shown above.

COMMON ERRORS TO AVOID:
- Don't assign tasks without specifying which agent should perform them
- Don't execute tasks before all necessary agents are created
- Don't try to integrate results before all tasks are completed
- Don't mix task assignment with task execution - complete each phase fully