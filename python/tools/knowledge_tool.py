import os
import concurrent.futures

from agent import Agent
from python.helpers import tavily_search
from python.helpers import duckduckgo_search
from . import memory_tool
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle

class Knowledge(Tool):
    def execute(self, question="", **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Schedule the functions to be run in parallel

            # Tavily search, if API provided
            if os.getenv("API_KEY_TAVILY"):
                tavily = executor.submit(tavily_search.tavily_search, question, os.getenv("API_KEY_TAVILY"))
            else:
                PrintStyle.hint("No API key provided for Tavily. Skipping Tavily search.")
                tavily = None

            # DuckDuckGo search
            duckduckgo = executor.submit(duckduckgo_search.search, question)

            # Memory search
            future_memory = executor.submit(memory_tool.search, self.agent, question)

            # Wait for all functions to complete
            tavily_result = (tavily.result() if tavily else "") or ""
            duckduckgo_result = duckduckgo.result()
            memory_result = future_memory.result()

        msg = files.read_file(
            "prompts/tool.knowledge.response.md",
            online_sources=tavily_result + "\n\n" + str(duckduckgo_result),
            memory=memory_result
        )

        if self.agent.handle_intervention(msg):
            pass  # wait for intervention and handle it, if paused

        return Response(message=msg, break_loop=False)