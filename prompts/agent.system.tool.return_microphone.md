# return_microphone

Use this tool to return the microphone to your superior agent along with your response/analysis that will be shared with ALL agents in the conversation.

This tool should be used when:
- You have completed the task given to you via the microphone
- You want to provide input/feedback to all agents in the conversation
- You have analysis or recommendations to share with the entire team

## Arguments
- **message** (required): Your response, analysis, or feedback to send back to all agents

## How it works
1. Your message gets added to the shared microphone messages queue
2. The microphone is returned to the superior agent
3. Your message will be injected into the system prompt of ALL agents in the conversation
4. Your message loop ends after using this tool

## Example usage
```json
{
    "tool_name": "return_microphone",
    "tool_args": {
        "message": "I found 3 potential security vulnerabilities in the code: SQL injection on line 45, XSS vulnerability in the user input handler, and missing authentication check in the admin endpoint. Here are the recommended fixes: ..."
    }
}
```

## Important Notes
- **Shared with All**: Your message will be visible to ALL agents in the conversation, not just your superior
- **Collaborative Input**: This enables multi-agent collaboration where your insights benefit the entire team
- **Microphone Required**: Only use this tool if you currently have the microphone (received via `pass_microphone`)
- **Message Loop End**: This tool will end your message loop, so make sure your message is complete
- **Team Context**: All agents will see your message in their next system prompt, enriching the collective understanding
