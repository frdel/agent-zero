from agent import Agent
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

def execute(agent:Agent, message: str, **kwargs):

    # output to console
    PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.name}: reponse:")        
    PrintStyle(font_color="white").print(f"{message}") 

    if agent.superior: # add to superior messages if it is an agent
        files.read_file("./prompts/fw.msg_from_subordinate.md",name=agent.name,message=message)
        agent.superior.append_message(message, human=True)

    return files.read_file("./prompts/fw.msg_info_sent.md")
    
