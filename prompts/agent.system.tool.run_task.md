### run_task Tool

## Description
The `run_task` tool is a wrapper that executes other tools in isolated background contexts. This allows you to run tools in parallel without blocking your main reasoning process. Use this tool when you want to start multiple operations simultaneously or when you need to continue thinking while a tool executes.

#### When to Use
- **Parallel Processing**: Start multiple tools simultaneously for efficiency
- **Long-Running Operations**: Execute time-consuming tools without blocking your reasoning
- **Concurrent Research**: Gather information from multiple sources at once
- **Workflow Optimization**: Continue planning while tools execute in background

#### Parameters
- `tool_name` (required): Name of the tool to execute (e.g., "search_engine", "code_exe")
- `method` (optional): Method to call on the tool (e.g., "search", "execute")
- `args` (required): JSON string containing arguments for the target tool
- `message` (optional): Message context for the tool execution

#### Usage Examples

##### Example 1: Parallel Web Search
```json
{
  "thoughts": [
    "I need to research multiple topics simultaneously for efficiency."
  ],
  "tool_name": "run_task",
  "tool_args": {
    "tool_name": "search_engine",
    "method": "search",
    "args": "{\"query\": \"machine learning algorithms comparison\"}"
  }
}
```

##### Example 2: Background Code Execution
```json
{
  "thoughts": [
    "I'll start this code execution in background while I prepare the next steps."
  ],
  "tool_name": "run_task",
  "tool_args": {
    "tool_name": "code_exe",
    "method": "execute",
    "args": "{\"language\": \"python\", \"code\": \"import time; time.sleep(5); print('Done')\"}"
  }
}
```

##### Example 3: Multiple Parallel Tasks
```json
{
  "thoughts": [
    "I'll start several research tasks in parallel for comprehensive analysis."
  ],
  "tool_name": "run_task",
  "tool_args": {
    "tool_name": "search_engine",
    "method": "search",
    "args": "{\"query\": \"AI safety research 2024\"}"
  }
}
```

#### Workflow Pattern

##### 1. Start Background Tasks
Use `run_task` to start tools in background, each returns a task ID:
```
Task 'search_engine:search' is now running in background with task ID: abc123...
```

##### 2. Continue Your Reasoning
After starting tasks, continue your monologue - don't wait immediately:
```
Now while that search is running, let me start another search...
```

##### 3. Start Additional Tasks (Optional)
Start more parallel tasks if needed:
```json
{
  "tool_name": "run_task",
  "tool_args": {
    "tool_name": "search_engine",
    "method": "search",
    "args": "{\"query\": \"related topic\"}"
  }
}
```

##### 4. Retrieve Results
Use `wait_for_tasks` to collect results:
```json
{
  "tool_name": "wait_for_tasks",
  "tool_args": {
    "tool_call_ids": "abc123,def456,ghi789"
  }
}
```

#### Important Notes

##### Background Execution
- Each task runs in an **isolated temporary context**
- Tasks are automatically cleaned up after completion
- No interference between parallel tasks or main context
- Results are preserved in main agent's storage

##### Error Handling
- Failed tasks store error information for later retrieval
- Background failures don't crash the main agent process
- Use `wait_for_tasks` to check task success/failure status

##### Performance Considerations
- Use parallel execution for independent operations
- Don't create excessive parallel tasks (recommend max 5-10 simultaneously)
- Consider task dependencies when planning parallel execution

#### Advantages Over Direct Tool Calls

##### Direct (Synchronous)
```json
{"tool_name": "search_engine", "tool_args": {"query": "test"}}
```
- Blocks until completion
- No parallelism possible
- Must wait before next action

##### Background (Asynchronous)
```json
{"tool_name": "run_task", "tool_args": {"tool_name": "search_engine", "args": "{\"query\": \"test\"}"}}
```
- Returns immediately with task ID
- Enables parallel execution
- Continue reasoning while tool runs
- Retrieve results when needed

#### Best Practices

1. **Plan First**: Identify which operations can run in parallel
2. **Start Tasks**: Use `run_task` to start background operations
3. **Continue Thinking**: Don't wait immediately - keep reasoning
4. **Batch Retrieval**: Collect multiple results with one `wait_for_tasks` call
5. **Handle Errors**: Check task success status in results

Use `run_task` whenever you want explicit control over parallel execution and need to optimize your workflow efficiency.
