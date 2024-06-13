from agent import Agent
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

def execute(agent:Agent, result: str, **kwargs):
    agent.set_data("timeout",0) # wait for user, no timeout
    agent.add_result(result) # add result data