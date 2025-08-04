### wait_for_tasks

#### Description
The `wait_for_tasks` tool allows you to retrieve results from tool calls that are running in parallel in isolated temporary contexts. When you execute tools other than `wait_for_tasks`, they run asynchronously in their own temporary contexts and return a task ID immediately. Use this tool to collect the actual results.

#### Usage
```json
{
  "tool_name": "wait_for_tasks",
  "tool_args": {
    "tool_call_ids": "task-id-1,task-id-2,task-id-3"
  }
}
```

#### Parameters
- **tool_call_ids** (required): Comma-separated list of task IDs to wait for and retrieve results from

#### Behavior
- This tool executes synchronously in the current context (along with the `response` tool)
- All other tools execute in isolated temporary contexts that are auto-cleaned
- It will wait for the specified tasks to complete if they are still running
- Returns the results of all specified tasks (results are preserved even after context cleanup)
- Tasks that are already completed will return their cached results immediately
- Tasks that don't exist will be reported as "not found"
- Temporary contexts are automatically cleaned up after tool execution

#### Example Workflow
1. Execute multiple tools in parallel:
   ```json
   {"tool_name": "code_executor", "tool_args": {"code": "print('Task 1')"}}
   ```
   → Returns: "Task started with ID: abc123..."

2. Execute another tool:
   ```json
   {"tool_name": "search_engine", "tool_args": {"query": "python asyncio"}}
   ```
   → Returns: "Task started with ID: def456..."

3. Retrieve all results:
   ```json
   {"tool_name": "wait_for_tasks", "tool_args": {"tool_call_ids": "abc123,def456"}}
   ```
   → Returns results from both tasks

#### Critical Workflow Instructions
- **After starting any tool**: CONTINUE YOUR MONOLOGUE - don't stop thinking
- **Your role continues**: The system expects you to keep reasoning and planning
- **When to collect**: Use `wait_for_tasks` when you're ready to use the results
- **Multiple tasks**: You can start several tools, then collect all results together
- **Keep working**: After getting results, continue analysis and provide final response

#### Important Notes
- Always use `wait_for_tasks` to get actual tool results
- Task IDs are UUIDs generated automatically
- You can wait for multiple tasks at once for efficiency
- Tasks are tracked in the system prompt under "Tasks in Progress"
- Each tool runs in its own isolated temporary context (including subordinate agents)
- Contexts are automatically cleaned up - only results are preserved
- This prevents context pollution and ensures clean execution environments

#### Expected Agent Behavior After Tool Start
1. **Tool starts** → You see "Started tool 'X' with task ID: abc123"
2. **KEEP THINKING** → Continue your monologue, don't stop here
3. **Plan next steps** → Consider starting more tools or preparing for results
4. **Collect when ready** → Use wait_for_tasks to retrieve actual results
5. **Continue working** → Analyze results and provide final answer
