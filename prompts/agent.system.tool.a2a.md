# A2A Communication Tool

## Description
The A2A (Agent-to-Agent) Communication tool enables direct peer-to-peer communication with other A2A-compliant agents across the network. Use this tool when you need to delegate tasks to, collaborate with, or gather information from other autonomous agents.

## When to Use
- Delegating specialized tasks to peer agents with specific capabilities
- Collaborating on complex problems that require multiple agent perspectives
- Gathering information or results from agents with domain expertise
- Distributing workload across a network of agents
- Accessing capabilities not available locally

## Arguments
- **peer_url** (required): The HTTPS URL of the target A2A-compliant agent
- **task_description** (required): Clear description of what you want the peer agent to do
- **interaction_type** (optional): Communication pattern - "polling" (default), "sse", or "webhook"
- **timeout** (optional): Maximum time to wait for response in seconds (default: 60)
- **auth_token** (optional): Authentication token for the peer agent if required
- **context** (optional): Additional context data to include with the task

## Interaction Types
1. **polling**: Submit task and periodically check for completion (most reliable)
2. **sse**: Real-time updates via Server-Sent Events (faster, requires streaming support)
3. **webhook**: Callback-based notifications (most efficient, requires webhook setup)

## Usage Examples

### Basic Task Delegation
```json
{
    "thoughts": ["Need to analyze financial data", "Found a specialized financial analysis agent"],
    "tool_name": "a2a_communication",
    "tool_args": {
        "peer_url": "https://finance-agent.example.com",
        "task_description": "Analyze the quarterly revenue data and identify trends",
        "interaction_type": "polling",
        "context": {
            "data_source": "Q3_2024_revenue.csv",
            "analysis_type": "trend_analysis"
        }
    }
}
```

### Collaborative Problem Solving
```json
{
    "thoughts": ["This coding problem requires expertise in quantum computing", "Delegating to quantum specialist agent"],
    "tool_name": "a2a_communication",
    "tool_args": {
        "peer_url": "https://quantum-dev.agents.ai",
        "task_description": "Implement a quantum circuit for Shor's algorithm optimization",
        "interaction_type": "sse",
        "timeout": 120,
        "context": {
            "problem_type": "quantum_algorithm",
            "optimization_target": "gate_count"
        }
    }
}
```

### Information Gathering
```json
{
    "thoughts": ["Need current market sentiment data", "Contacting market analysis agent"],
    "tool_name": "a2a_communication", 
    "tool_args": {
        "peer_url": "https://market-intel.trading-agents.com",
        "task_description": "Provide current market sentiment analysis for tech stocks",
        "interaction_type": "polling",
        "context": {
            "sectors": ["technology", "software"],
            "timeframe": "last_24_hours"
        }
    }
}
```

## Best Practices

1. **Clear Task Descriptions**: Be specific about what you want the peer agent to accomplish
2. **Appropriate Timeouts**: Set realistic timeouts based on task complexity
3. **Context Sharing**: Include relevant context to help the peer agent understand the task
4. **Error Handling**: Be prepared to handle cases where peer agents are unavailable
5. **Security**: Only communicate with trusted agents using HTTPS
6. **Capability Matching**: Verify peer agents have the required capabilities before delegating

## Error Handling
- Peer agent unavailable: Try alternative agents or handle locally
- Authentication failures: Check auth tokens and peer requirements
- Task failures: Analyze error messages and consider task reformulation
- Timeouts: Increase timeout or break task into smaller parts

## Security Considerations
- Always use HTTPS for peer communication
- Validate peer agent certificates and identity
- Never share sensitive data without proper authorization
- Use appropriate authentication tokens
- Be cautious with peer agent responses and validate outputs