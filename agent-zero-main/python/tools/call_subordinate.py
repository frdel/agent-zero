from agent import Agent
from typing import Any


def call_subordinate(agent: Agent, task_id: str) -> Any:
    data = agent.get_data(task_id)
    # Proceed with the task
    agent.set_data(task_id, "result")
    agent.append_message("Task completed.")
    return data
