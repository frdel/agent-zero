# TeamAgent Tool

Create teams of specialized agents that collaborate on complex tasks.

## IMPORTANT: Always use format

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "create",
        "name": "Team Name",
        ...other parameters...
    }
}
```

## Workflow

1. **CREATE** a team
2. **ADD** specialized agents
3. **ASSIGN** tasks to agents
4. **EXECUTE** tasks
5. **MESSAGE** between agents
6. **GET** final results

## Available Actions

### create
Create a new team of agents.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "create",
        "name": "Research Team", 
        "goal": "Research quantum computing algorithms"
    }
}
```

### add_agent
Add an agent with a specific role to a team.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "add_agent",
        "team_id": "team_abcd1234",
        "role": "researcher",
        "skills": ["information gathering", "analysis"]
    }
}
```

### assign_task
Assign a task to an agent in the team. Optionally, specify dependencies on other tasks.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "assign_task",
        "team_id": "team_abcd1234",
        "agent_id": "agent_xyz789",
        "task": "Find the latest papers on quantum computing algorithms",
        "context": "Focus on papers from the last 2 years",
        "depends_on": ["task_123456", "task_789012"]  // Optional: List of tasks this depends on
    }
}
```

### execute_task
Run a previously assigned task and get the agent's response.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "execute_task",
        "team_id": "team_abcd1234",
        "task_id": "task_def456"
    }
}
```

### resume_task
Resume a failed task with same agent (includes the resume=true parameter).

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "execute_task",
        "team_id": "team_abcd1234",
        "task_id": "task_def456",
        "resume": true
    }
}
```

### message
Send a message from one agent to another.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "message",
        "team_id": "team_abcd1234",
        "from": "agent_xyz789",
        "to": "agent_abc123",
        "content": "I found 5 relevant papers on quantum algorithms"
    }
}
```

### broadcast
Send a message from one agent to all other agents.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "broadcast",
        "team_id": "team_abcd1234",
        "from": "agent_xyz789",
        "content": "Important update: focusing on quantum Fourier transform"
    }
}
```

### get_results
Get results from all tasks in the team.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "get_results",
        "team_id": "team_abcd1234"
    }
}
```

### team_status
Get comprehensive information about team progress, including task dependencies, agent workloads, and completion statistics.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "team_status",
        "team_id": "team_abcd1234"
    }
}
```

### get_context
Get current context and state information about the team to maintain continuity.

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "get_context",
        "team_id": "team_abcd1234"
    }
}
```

## Advanced Features

### Task Dependencies
Tasks can depend on other tasks, creating a workflow chain:

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "assign_task",
        "team_id": "team_abcd1234",
        "agent_id": "agent_abc123",
        "task": "Analyze research findings from initial data collection",
        "depends_on": ["task_data123"]  // This task will wait until task_data123 completes
    }
}
```

### Agent Self-Identification
Each agent knows its role and IDs:
- Agents receive their task_id, team_id, and agent_id in prompts
- Agents reference other team members by role and ID
- Task history is maintained with proper references

### Task Resumption
Failed tasks can be resumed:

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "execute_task",
        "team_id": "team_abcd1234",
        "task_id": "task_failed456",
        "resume": true
    }
}
```

## Complete Example: Research Team Workflow

```json
// 1. CREATE TEAM
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "create",
        "name": "AI Research Team",
        "goal": "Conduct comprehensive research on recent AI advancements"
    }
}
// Response will include: team_id and context information

// 2. ADD DATA COLLECTOR AGENT
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "add_agent",
        "team_id": "team_abcd1234",
        "role": "data_collector",
        "skills": ["web scraping", "information gathering", "source verification"]
    }
}
// Response includes: agent_id and updated context

// 3. ADD ANALYST AGENT
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "add_agent",
        "team_id": "team_abcd1234",
        "role": "analyst",
        "skills": ["data analysis", "pattern recognition", "critical thinking"]
    }
}

// 4. ASSIGN DATA COLLECTION TASK
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "assign_task",
        "team_id": "team_abcd1234",
        "agent_id": "agent_collector",
        "task": "Gather recent news and academic papers on transformer models",
        "context": "Focus on advancements from the last 6 months"
    }
}

// 5. EXECUTE DATA COLLECTION TASK
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "execute_task",
        "team_id": "team_abcd1234",
        "task_id": "task_collect123"
    }
}

// 6. ASSIGN ANALYSIS TASK (DEPENDENT ON DATA COLLECTION)
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "assign_task",
        "team_id": "team_abcd1234",
        "agent_id": "agent_analyst",
        "task": "Analyze collected data and identify key trends in transformer model architecture",
        "depends_on": ["task_collect123"]
    }
}

// 7. CHECK TEAM STATUS
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "team_status",
        "team_id": "team_abcd1234"
    }
}

// 8. EXECUTE ANALYSIS TASK
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "execute_task",
        "team_id": "team_abcd1234",
        "task_id": "task_analyze456"
    }
}

// 9. GET FINAL RESULTS
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "get_results",
        "team_id": "team_abcd1234"
    }
}
```

## Context Persistence

All responses include context information to help maintain state between actions:

```json
{
    "team_id": "team_abcd1234",
    "agent_id": "agent_xyz789",
    "status": "added",
    "context": {
        "active_team": "team_abcd1234",
        "last_action": "add_agent",
        "available_agents": ["agent_xyz789"]
    }
}
```

If you lose track of IDs or state, use the `get_context` action to retrieve the current state:

```json
{
    "tool_name": "team_agent",
    "tool_args": {
        "action": "get_context",
        "team_id": "team_abcd1234"
    }
}
```

## Tips for Success

1. **Always use `tool_name`: "team_agent"** for all commands
2. **Place action and parameters inside `tool_args`**
3. **Save IDs** from responses for use in subsequent commands
4. **Follow the workflow sequence**: Create → Add Agents → Assign Tasks → Execute Tasks → Get Results
5. **Use messages** to share information between agents
6. **Use task dependencies** for sequential workflows
7. **Monitor progress** with the team_status action
8. **Context is preserved** between actions - the system will remember the active team
9. **If you lose track** of team or agent IDs, use `get_context` to retrieve them
10. **Check error messages** for helpful hints when something goes wrong
