from agent import Agent
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

from agent import Agent
from tools.helpers.tool import Tool, Response
from tools.helpers import files
from tools.helpers.print_style import PrintStyle

class ResponseTool(Tool):

    def execute(self):
        # superior = self.agent.get_data("superior")
        # if superior:
        return Response(message=self.args["text"], break_loop=True)
        # else:

    def after_execution(self, response):
        pass # do add anything to the history or output

    
# def execute(agent:Agent, message: str, _tools, _tool_index, timeout=15, **kwargs):

#     # for models that like to use multiple tools in one response, we do a little trick to help the flow
#     # if there are tools producing output before this message or any other tools after this message, 
#     # this message will be sent as information only and will not stop the loop
#     # if this is the last tool in the iteration and no outputing tools we used before, we stop the loop
#     # and wait for user input
    

#     # tools called before this one that produce output
#     outputing_tools_before = filter_tools(
#             filters=[
#                 {"name":"memory_tool","action":"load"},
#                 {"name":"online_knowledge_tool"},
#                 {"name":"delegation"},
#                 ],
#             tools=_tools[:_tool_index]
#             )

#     # tools called after this one
#     other_tools_after = any(tool["name"] != kwargs["_name"] for tool in _tools[_tool_index:]) #are there other tools than messages used after this one?

#     agent.set_data("timeout", timeout) # set the timeout for response

#     #if there are other tools used, message is only for information, it does not stop the loop
#     if outputing_tools_before or other_tools_after:
#         return non_blocking_message(agent, message, timeout=timeout, **kwargs)
#     else: #if there are only messages used in this iteration, collect them into the loop result
#         return blocking_message(agent, message, timeout=timeout, **kwargs)

# def blocking_message(agent:Agent, message: str, timeout=15, **kwargs):
#     agent.add_result(message)
#     return files.read_file("./prompts/fw.msg_sent.md")

# def non_blocking_message(agent:Agent, message: str, timeout=15, **kwargs):
#     if agent.get_data("superior"): # add to superior messages if it is an agent
#         msg_for_user = files.read_file("./prompts/fw.msg_from_subordinate.md",name=agent.name,message=message)
#         agent.get_data("superior").append_message(msg_for_user, human=True)

#     # output to console
#     PrintStyle(font_color="white",background_color="#1D8348", bold=True, padding=True).print(f"{agent.name}: reponse:")        
#     PrintStyle(font_color="white").print(f"{message}")

#     return files.read_file("./prompts/fw.msg_info_sent.md") #return message o
    
# def filter_tools(filters, tools):
#     filtered_data = []
#     for data_item in tools:
#         if any(all(data_item.get(key) == value for key, value in filter_item.items()) for filter_item in filters):
#             filtered_data.append(data_item)
#     return filtered_data