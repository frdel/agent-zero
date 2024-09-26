from agent import Agent
from config import AgentConfig
from typing import Any


def execute_code(agent: Agent, code: str) -> Any:
    config = AgentConfig()
    if config.code_exec_docker_enabled:
        context = agent.context  # Currently unused
        # Code execution within Docker
        agent.handle_intervention("Code execution started.")
        # Execution logic
    agent.append_message("Code executed.")
    return "execution_result"
