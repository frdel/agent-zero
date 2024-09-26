from agent import Agent
from config import AgentConfig
from typing import Any


def generate_response(agent: Agent, prompt: str) -> Any:
    config = AgentConfig()
    agent.set_data("last_prompt", prompt)
    context = agent.context
    # Response generation logic using config and context
    agent.append_message("Response generated.")
    return "response_text"
