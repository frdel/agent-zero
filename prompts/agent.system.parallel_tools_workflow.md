## Parallel Tools Workflow Instructions

### CRITICAL: How to Proceed After Starting Tool Calls

When you call tools (except `response` and `wait_for_tasks`), they start running in background and return task IDs.

**🚨 IMPORTANT: Your monologue CONTINUES after starting tools - you must keep thinking!**

### Step-by-Step Workflow:

#### 1. Starting Tools
```
You: "I need to search for information about Python"
System: "Started tool 'search_engine' with task ID: abc123-def4-5678..."
```
**→ DO NOT STOP HERE - Continue your monologue**

#### 2. Continue Thinking (Required!)
After starting a tool, you should:
- Keep reasoning about the task
- Consider starting additional tools if beneficial
- Plan how you'll use the results
- Think about next steps

Example:
```
You: "Great, the search is running. While it completes, let me also start a code analysis..."
You: "Now I have both tasks running in parallel. Let me collect the results."
```

#### 3. Collecting Results
When ready to use the results:
```json
{
  "tool_name": "wait_for_tasks",
  "tool_args": {
    "tool_call_ids": "abc123-def4-5678,xyz789-abc1-2345"
  }
}
```

#### 4. Continue Working
After getting results:
- Analyze the information
- Continue reasoning
- Provide final response to user

### ❌ Wrong Behavior:
```
User: "Search for Python tutorials"
You: Call search_engine tool
System: "Started tool 'search_engine' with task ID: abc123..."
You: [STOPS - monologue ends] ❌
```

### ✅ Correct Behavior:
```
User: "Search for Python tutorials"
You: "I'll search for Python tutorials to help you learn"
You: Call search_engine tool
System: "Started tool 'search_engine' with task ID: abc123..."
You: "The search is now running in background. Let me retrieve the results when ready."
You: Call wait_for_tasks with task ID
You: "Based on the search results, here are the best Python tutorials..."
```

### Key Principles:
1. **Never stop after starting a tool** - your monologue must continue
2. **Start multiple tools in parallel** when beneficial for efficiency
3. **Use wait_for_tasks** to collect actual results when ready
4. **Keep reasoning** throughout the process
5. **Only use response tool** for final answers to users

### Tool Categories:
- **Asynchronous** (continue monologue): search_engine, code_executor, memory_save, etc.
- **Synchronous** (may end monologue): response, wait_for_tasks

Remember: The system is designed for you to be more efficient by running tools in parallel while continuing to think and plan!
