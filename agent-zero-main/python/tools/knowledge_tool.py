from agent import Agent


def add_knowledge(agent: Agent, knowledge: str) -> None:
    context = agent.context
    context.setdefault("knowledge", []).append(knowledge)
    agent.read_prompt = knowledge
    agent.handle_intervention("Knowledge added.")
    agent.append_message("Knowledge updated.")
