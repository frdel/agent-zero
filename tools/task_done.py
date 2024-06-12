from agent import Agent
from tools.helpers import files
from . import message_for_user

def execute(agent:Agent, message: str, **kwargs):
    # forward to message_for_user with no-timeout flag
    return message_for_user.execute(agent, message, response_required="true", timeout=0, **kwargs)