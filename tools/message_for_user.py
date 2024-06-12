from agent import Agent
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

def execute(agent:Agent, message: str, response_required: str = "false", timeout=15, **kwargs):

    agent.set_data("timeout", timeout) # set the no-timeout flag
    
    if response_required.lower().strip() == "true":
        agent.stop_loop = True
        agent.loop_result = message

        return files.read_file("./prompts/fw.msg_sent.md")
        
    else:
        if agent.get_data("superior"): # add to superior messages if it is an agent
            files.read_file("./prompts/fw.msg_from_subordinate.md",name=agent.name,message=message)
            agent.get_data("superior").append_message(message, human=True)

        # output to console
        PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.name}: reponse:")        
        PrintStyle(font_color="white").print(f"{message}")

        return files.read_file("./prompts/fw.msg_info_sent.md")
    
