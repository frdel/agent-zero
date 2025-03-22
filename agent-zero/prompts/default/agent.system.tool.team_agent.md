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

workflow sequence:
1. create a team
2. add specialized agents with clear roles
3. assign specific tasks to agents
4. execute tasks one at a time
5. share results between agents
6. get final combined results

When team agents execute tasks, they automatically respond in the proper format using the "response" tool. Team management handles all communication between agents for you - you only need to use the actions shown above.