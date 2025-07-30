# pass_microphone

Use this tool to pass the microphone to a subordinate agent, allowing them to provide input that will be injected into the system prompt of ALL agents in the conversation.

This is useful when you want to:
- Delegate a specific task to a subordinate and get their direct input
- Have a subordinate analyze something and provide feedback
- Allow a subordinate to contribute to the conversation flow
- Share subordinate insights with all agents in the conversation

## Arguments
- **message** (required): The message/task to send to the subordinate agent
- **agent_profile** (optional): The profile/persona to assign to the subordinate agent (e.g., "developer", "researcher", "hacker")

## How it works
1. The subordinate agent receives your message and processes it
2. They can use the `return_microphone` tool to send their response back
3. Their response gets injected into the system prompt of ALL agents in the conversation
4. All agents continue with the subordinate's input as shared context

## Example usage
```json
{
    "tool_name": "pass_microphone",
    "tool_args": {
        "message": "Please analyze this code for potential security vulnerabilities",
        "agent_profile": "hacker"
    }
}
```

## Important Notes
- **Shared Context**: The subordinate's response will be visible to ALL agents in the conversation
- **Collaborative**: This enables true multi-agent collaboration with shared insights
- **Superior Control**: Only superior agents can pass the microphone
- **Context Enrichment**: All agents benefit from the subordinate's specialized analysis
