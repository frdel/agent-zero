# A2A Subordinate Tool

## Description
The A2A Subordinate tool enables spawning and communicating with subordinate agents as independent A2A processes. This provides true multi-agent collaboration with parallel processing, direct user interaction, and scalable agent networks.

## When to Use A2A Subordinates
- Breaking down complex tasks into specialized subtasks
- Requiring parallel processing across multiple agents
- Need for specialized expertise (coding, analysis, research, etc.)
- User wants to interact directly with subordinate agents
- Building scalable multi-agent workflows
- Distributing workload across multiple processes

## Comparison: A2A Subordinates vs External A2A Peers

### Use A2A Subordinates When:
✅ Task needs specialized roles within your control  
✅ Breaking down YOUR task into parallel subtasks  
✅ User should be able to talk directly to specialists  
✅ Need multiple agents working simultaneously  
✅ Require agent hierarchy and lifecycle management  

### Use External A2A Communication When:
✅ Collaborating with independent agents you don't control  
✅ Accessing specialized external services/capabilities  
✅ Cross-organization agent communication  
✅ Using agents with unique data sources  

## Arguments
- **message** (required): Task/message to send to subordinate
- **role** (required): Subordinate role/specialty (e.g., "coder", "analyst", "researcher", "tester")
- **prompt_profile** (optional): Prompt profile for subordinate behavior (default: "default")
- **reset** (optional): "true" to spawn new subordinate, "false" to use existing (default: "false")
- **capabilities** (optional): List of capabilities the subordinate should have
- **context** (optional): Additional context data to share with subordinate
- **timeout** (optional): Maximum response time in seconds (default: 60)

## Available Subordinate Roles

### Specialized Roles
- **coder**: Software development, debugging, code review
- **analyst**: Data analysis, visualization, statistical analysis
- **researcher**: Information gathering, web research, summarization
- **tester**: Testing, validation, quality assurance
- **writer**: Content creation, documentation, editing
- **assistant**: General assistance, task coordination

### Custom Roles
You can use any role name - the subordinate will be optimized for that specialty.

## Usage Examples

### Basic Task Delegation
```json
{
    "thoughts": ["This coding task is complex", "I'll delegate to a coder subordinate"],
    "tool_name": "a2a_subordinate",
    "tool_args": {
        "message": "Write a Python function to parse CSV data and generate summary statistics",
        "role": "coder",
        "reset": "true"
    }
}
```

### Parallel Processing
```json
{
    "thoughts": ["I need both data analysis and visualization", "I'll spawn two subordinates to work in parallel"],
    "tool_name": "a2a_subordinate", 
    "tool_args": {
        "message": "Analyze the sales data for trends and patterns",
        "role": "analyst",
        "reset": "true",
        "context": {
            "data_file": "sales_q4_2024.csv",
            "focus": "trend_analysis"
        }
    }
}
```

### Continuing with Existing Subordinate
```json
{
    "thoughts": ["The coder needs to fix the issue I found", "I'll continue with the existing coder subordinate"],
    "tool_name": "a2a_subordinate",
    "tool_args": {
        "message": "Fix the bug in the CSV parser function - it's not handling empty cells correctly",
        "role": "coder",
        "reset": "false"
    }
}
```

### Research Task with Specific Capabilities
```json
{
    "thoughts": ["I need comprehensive market research", "A researcher with web search capabilities would be perfect"],
    "tool_name": "a2a_subordinate",
    "tool_args": {
        "message": "Research the current state of AI agent frameworks and their market adoption",
        "role": "researcher", 
        "capabilities": ["web_search", "information_gathering", "summarization", "report_generation"],
        "context": {
            "research_depth": "comprehensive",
            "focus_areas": ["technical_capabilities", "market_adoption", "competitive_landscape"]
        }
    }
}
```

## Advanced Features

### Context Sharing
The subordinate automatically receives:
- Parent agent information
- Relevant conversation history
- Shared context data you provide
- Parent context ID for cross-reference

### Parallel Execution
Multiple subordinates can work simultaneously:
```json
// First subordinate
{
    "tool_name": "a2a_subordinate",
    "tool_args": {
        "message": "Analyze the financial data",
        "role": "financial_analyst",
        "reset": "true"
    }
}

// Immediately spawn second subordinate (parallel processing)
{
    "tool_name": "a2a_subordinate", 
    "tool_args": {
        "message": "Create data visualizations",
        "role": "data_visualizer",
        "reset": "true"
    }
}
```

### Direct User Interaction
Once spawned, users can communicate directly with subordinates:
- Subordinates appear in the agent list
- Users can send messages to specific subordinates
- Subordinates can respond directly to users
- Maintains conversation history

## Best Practices

1. **Clear Role Definition**: Choose specific, descriptive roles for better specialization
2. **Appropriate Task Scope**: Delegate substantial subtasks, not tiny operations
3. **Context Sharing**: Provide relevant context to help subordinates understand the task
4. **Parallel Processing**: Use multiple subordinates for independent tasks
5. **Reset Strategy**: Use reset="true" for new tasks, reset="false" for continuing work
6. **Resource Management**: Monitor active subordinates to avoid resource exhaustion

## Subordinate Management

### List Active Subordinates
```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "list"
    }
}
```

### Check Subordinate Status
```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "status",
        "role": "coder"
    }
}
```

### Shutdown Subordinate
```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "shutdown", 
        "role": "researcher"
    }
}
```

## Error Handling
- **Port allocation errors**: Automatically finds available ports
- **Subordinate startup failures**: Detailed error messages and cleanup
- **Communication timeouts**: Configurable timeout settings
- **Process crashes**: Automatic detection and restart options
- **Resource limits**: Prevents spawning too many subordinates

## Security Considerations
- Subordinates run as separate processes for isolation
- No authentication required between parent and subordinates (local communication)
- Subordinates inherit parent's security context
- Automatic cleanup on parent shutdown

## Performance Notes
- Each subordinate uses additional memory and CPU
- Network communication overhead (local HTTP)
- Consider subordinate limits based on system resources
- Monitor system performance with multiple active subordinates

The A2A Subordinate tool enables sophisticated multi-agent workflows while maintaining the simplicity of Agent Zero's tool-based architecture.