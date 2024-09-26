from agent import Agent


def mark_task_done(agent: Agent, task_id: str) -> None:
    agent.set_data(task_id, "done")
    context = agent.context  # Example usage or remove if not needed
    agent.append_message(f"Task {task_id} marked as done.")
    # Assuming 'agent_name' is an attribute of Agent
    if hasattr(agent, "agent_name"):
        agent.append_message(f"Agent Name: {agent.agent_name}")
    else:
        agent.append_message("Agent name not defined.")
