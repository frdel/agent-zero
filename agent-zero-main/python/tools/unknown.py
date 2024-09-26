from agent import Agent
from typing import Any


def unknown_action(agent: Agent) -> Any:
    prompt = agent.read_prompt
    # Handle unknown action
    agent.append_message("Unknown action handled.")
    return "unknown_result"
