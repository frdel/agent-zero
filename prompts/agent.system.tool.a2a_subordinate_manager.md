# A2A Subordinate Manager Tool

## Description
The A2A Subordinate Manager tool provides comprehensive management capabilities for A2A subordinate agents. This tool allows you to monitor, control, and organize your subordinate agent infrastructure.

## When to Use
- Monitor active subordinate agents
- Check subordinate health and status
- Manage subordinate lifecycle (shutdown, restart)
- View agent hierarchy and relationships
- Debug subordinate communication issues
- Resource management and cleanup

## Arguments
- **action** (required): Management action to perform
  - `"list"`: List all active subordinates
  - `"status"`: Get detailed status of specific subordinate
  - `"shutdown"`: Shutdown a specific subordinate
  - `"hierarchy"`: Show agent hierarchy visualization
- **role** (optional): Subordinate role for role-specific actions (required for "status" and "shutdown")

## Available Actions

### List Active Subordinates
Shows all currently running subordinate agents with basic information.

```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "list"
    }
}
```

**Returns:**
- Agent roles and IDs
- Connection URLs
- Current status
- Available capabilities
- Last contact time

### Check Subordinate Status
Get detailed information about a specific subordinate agent.

```json
{
    "tool_name": "a2a_subordinate_manager", 
    "tool_args": {
        "action": "status",
        "role": "coder"
    }
}
```

**Returns:**
- Full agent details (ID, URL, port, process ID)
- Spawn and contact timestamps
- Detailed capability list
- Current operational status
- Process health information

### Shutdown Subordinate
Gracefully shutdown a specific subordinate agent.

```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "shutdown",
        "role": "researcher"
    }
}
```

**Returns:**
- Success/failure status
- Cleanup confirmation
- Resource release information

### View Agent Hierarchy
Display the current agent hierarchy and relationships.

```json
{
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "hierarchy"
    }
}
```

**Returns:**
- Tree structure of agent relationships
- Parent-child mappings
- Status of each agent in hierarchy
- Visual hierarchy representation

## Usage Examples

### Basic Monitoring Workflow
```json
{
    "thoughts": ["Let me check what subordinates are currently active"],
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "list"
    }
}
```

### Detailed Troubleshooting
```json
{
    "thoughts": ["The coder subordinate seems unresponsive", "Let me check its detailed status"],
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "status",
        "role": "coder"
    }
}
```

### Resource Cleanup
```json
{
    "thoughts": ["The research task is complete", "I should shutdown the researcher to free resources"],
    "tool_name": "a2a_subordinate_manager",
    "tool_args": {
        "action": "shutdown",
        "role": "researcher"
    }
}
```

### Architecture Overview
```json
{
    "thoughts": ["I want to understand the current agent structure"],
    "tool_name": "a2a_subordinate_manager", 
    "tool_args": {
        "action": "hierarchy"
    }
}
```

## Best Practices

### Regular Monitoring
- Check subordinate status periodically during long-running tasks
- Monitor resource usage with multiple active subordinates
- Verify subordinate health after communication errors

### Resource Management
- Shutdown completed subordinates to free system resources
- Limit concurrent subordinates based on system capacity
- Monitor port allocation and network connections

### Troubleshooting
- Use detailed status when subordinates become unresponsive
- Check hierarchy to understand agent relationships
- Verify process health and communication channels

### Cleanup
- Shutdown subordinates when tasks are complete
- Clear inactive subordinates before spawning new ones
- Maintain a clean subordinate pool for optimal performance

## Error Handling
- **No subordinates**: Returns empty list with appropriate message
- **Invalid role**: Error message for non-existent subordinate roles
- **Communication failures**: Reports connection and process issues
- **Permission errors**: Handles cases where shutdown may fail

## Security Notes
- Management operations only affect subordinates you spawned
- No cross-agent interference or unauthorized access
- Secure cleanup ensures no orphaned processes
- Local-only communication prevents external exploitation

## Performance Considerations
- Listing subordinates is lightweight and fast
- Status checks involve network communication overhead
- Shutdown operations may take time for graceful cleanup
- Hierarchy views scale with number of active agents

The A2A Subordinate Manager tool provides essential infrastructure management for sophisticated multi-agent workflows while maintaining security and performance.