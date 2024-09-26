from agent import Agent
from config import AgentConfig
from typing import Any


def manage_memory(agent: Agent, memory_action: str, data: Any) -> None:
    AgentConfig()  # Removed unused variable 'config'
    context = agent.context
    if memory_action == "add":
        context["memory"].append(data)
    elif memory_action == "retrieve":
        return context.get("memory", [])
    agent.read_prompt = "Memory action performed."
    agent.append_message("Memory updated.")
