from agent import Agent
from . import online_knowledge_tool
from . import memory_tool
import concurrent.futures



from tools.helpers.tool import Tool, Response
from tools.helpers import files

class Knowledge(Tool):
    def execute(self, question="", **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Schedule the two functions to be run in parallel
            future_online = executor.submit(online_knowledge_tool.process_question, question)
            future_memory = executor.submit(memory_tool.search, self.agent, question)

            # Wait for both functions to complete
            online_result = future_online.result()
            memory_result = future_memory.result()

        result = f"# Online sources:\n{online_result}\n\n# Memory:\n{memory_result}"
        return Response(message=result, break_loop=False)