from agent import Agent
from tools.helpers import files

def execute(agent:Agent, message: str, **kwargs):
    agent.stop_loop = True
    agent.loop_result = message
    return files.read_file("./prompts/fw.msg_sent.md")