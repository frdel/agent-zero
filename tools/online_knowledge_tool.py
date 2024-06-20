from agent import Agent
from tools.helpers import perplexity_search
from tools.helpers.tool import Tool, Response

class Unknown(Tool):
    def execute(self):
        return Response(
            message=process_question(self.content),
            stop_tool_processing=True,
            break_loop=False,
        )

def process_question(question):
    return str(perplexity_search.perplexity_search(question))