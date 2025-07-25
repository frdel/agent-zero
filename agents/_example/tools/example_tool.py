from python.helpers.tool import Tool, Response

# this is an example tool class
# don't forget to include instructions in the system prompt by creating 
#   agent.system.tool.example_tool.md file in prompts directory of your agent
# see /python/tools folder for all default tools

class ExampleTool(Tool):
    async def execute(self, **kwargs):

        # parameters
        test_input = kwargs.get("test_input", "")

        # do something
        print("Example tool executed with test_input: " + test_input)

        # return response
        return Response(
            message="This is an example tool response, test_input: " + test_input, # response for the agent
            break_loop=False, # stop the message chain if true
        )
