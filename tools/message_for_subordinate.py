from agent import Agent

def execute(agent:Agent, message: str, reset: str = "false", **kwargs):
    if agent.subordinate is None or reset.lower() == "true":
        agent.subordinate = Agent(superior=agent, system_prompt=agent.system_prompt, tools_prompt=agent.tools_prompt, number=agent.number+1)
    return agent.subordinate.message_loop(message)