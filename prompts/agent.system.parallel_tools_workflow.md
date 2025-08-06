# Parallel Tools Workflow Instructions

## Key Concept: Explicit Parallel Execution with run_task
You now have full control over which tools run in parallel. Use the `run_task` wrapper tool to execute any tool in the background. All tools execute synchronously by default unless wrapped with `run_task`.

## Important Workflow Rules

### **1. Understanding Parallel Execution**
- **Direct tool calls** (like `search_engine:search`) execute synchronously (blocking)
- **Wrapped tool calls** (like `run_task` with `search_engine`) execute in background
- Background tasks run in isolated temporary contexts that auto-clean up
- You receive a **task ID** immediately for background tasks
- **IMPORTANT**: after starting a background task, CONTINUE your monologue - don't stop thinking

### **2. Two Execution Methods**

#### Synchronous (Direct) Execution
```json
{
  "tool_name": "search_engine",
  "tool_args": {"query": "test"}
}
```
- Blocks until completion
- Returns actual result immediately
- Use for simple, quick operations

#### Asynchronous (Background) Execution
```json
{
  "tool_name": "run_task",
  "tool_args": {
    "tool_name": "search_engine",
    "method": "search",
    "args": "{\"query\": \"test\"}"
  }
}
```
- Returns task ID immediately
- Runs in isolated background context
- Use for parallel/long-running operations

### **3. When to Use Each Method**

#### Use Direct Execution For:
- Quick, simple operations
- Single tool calls where you need immediate results
- Final tools like `response`

#### Use Background Execution (`run_task`) For:
- Multiple parallel research tasks
- Long-running operations (code execution, complex searches)
- When you want to continue thinking while tool runs
- Gathering information from multiple sources simultaneously

### **4. Correct Parallel Workflow Example**

```
Agent: "I need comprehensive research on this topic."

🔧 run_task(tool_name="search_engine", method="search", args='{"query": "topic A"}')
→ Returns: "Task 'search_engine:search' running with ID: abc123..."

Agent: "While that search runs, let me start researching related aspects."

🔧 run_task(tool_name="search_engine", method="search", args='{"query": "topic B"}')
→ Returns: "Task 'search_engine:search' running with ID: def456..."

Agent: "I'll also check for code examples in parallel."

🔧 run_task(tool_name="code_exe", method="execute", args='{"language": "python", "code": "example_code"}')
→ Returns: "Task 'code_exe:execute' running with ID: ghi789..."

Agent: "Now I'll collect all the results."

🔧 wait_for_tasks(tool_call_ids="abc123,def456,ghi789")
→ Returns: Full results from all three tasks

Agent: "Based on the comprehensive research and code execution results..."

🔧 response(message="Here's my complete analysis...")
```

### **5. Wrong vs Right Behavior**

#### ❌ Wrong: Stopping After Background Task Start
```
Agent: "I'll search for information"
🔧 run_task(tool_name="search_engine", args='{"query": "test"}')
→ Returns: "Task running with ID: abc123..."
[AGENT STOPS - WRONG!]
```

#### ✅ Right: Continuing After Background Task Start
```
Agent: "I'll search for information"
🔧 run_task(tool_name="search_engine", args='{"query": "test"}')
→ Returns: "Task running with ID: abc123..."
Agent: "While that runs, let me also check documentation"
🔧 run_task(tool_name="search_engine", args='{"query": "documentation"}')
→ Returns: "Task running with ID: def456..."
Agent: "Now I'll retrieve both results"
🔧 wait_for_tasks(tool_call_ids="abc123,def456")
```

### **6. Mixed Execution Strategy**
You can combine both approaches:

```
Agent: "Let me start some background research while I do quick analysis"

🔧 run_task(tool_name="search_engine", args='{"query": "complex topic"}')
→ Background task started: abc123

Agent: "While that runs, let me do a quick calculation"

🔧 code_exe(language="python", code="2 + 2")
→ Immediate result: 4

Agent: "Now let me get the background research"

🔧 wait_for_tasks(tool_call_ids="abc123")
→ Retrieved background results
```

## Critical Success Rules

### **Rule 1: Choose Execution Method Wisely**
- Use `run_task` for parallel/long operations
- Use direct calls for immediate needs

### **Rule 2: Continue Your Monologue**
After starting background tasks, **keep thinking and planning**. Don't wait immediately.

### **Rule 3: Use Parallel Execution for Efficiency**
Start multiple independent background tasks simultaneously.

### **Rule 4: Batch Result Collection**
Collect multiple task results in one `wait_for_tasks` call when possible.

### **Rule 5: Plan Your Workflow**
Think about which operations can run in parallel before starting them.

## Tool Reference

### Core Tools for Parallel Workflow:
- **`run_task`** - Wraps any tool for background execution
- **`wait_for_tasks`** - Collects results from background tasks
- **`response`** - Provides final answer (always synchronous)

**Remember**: You now have explicit control over parallel execution. Use `run_task` when you want background execution, and direct tool calls when you need immediate results!
