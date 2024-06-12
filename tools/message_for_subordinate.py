from agent import Agent

def execute(agent:Agent, message: str, reset: str = "false", **kwargs):
    # create subordinate agent using the data object on this agent and set superior agent to his data object
    if agent.get_data("subordinate") is None or reset.lower().strip() == "true":
        subordinate = Agent(system_prompt=agent.system_prompt, tools_prompt=agent.tools_prompt, number=agent.number+1)
        subordinate.set_data("superior", agent)
        agent.set_data("subordinate", subordinate) 
    # run subordinate agent message loop
    return agent.get_data("subordinate").message_loop(message)