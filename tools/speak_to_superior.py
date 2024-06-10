from agent import Agent
from tools.helpers import files

def execute(agent:Agent, message: str, **kwargs):
    agent.message_for_superior = message
    return files.read_file("./prompts/fw.msg_sent.md")