from agent import Agent
from typing import Any


def execute_tool(agent: Agent, tool_name: str, *args, **kwargs) -> Any:
    context = agent.context  # Example usage or remove if not needed
    max_length = agent.max_tool_response_length  # Example usage or remove if not needed
    prompt = agent.read_prompt  # Example usage or remove if not needed
    agent.append_message(f"Executing tool: {tool_name}")
    # Tool execution logic utilizing context, max_length, and prompt
    result = f"Executed {tool_name} with prompt '{prompt}' and max length {max_length}"
    return result
