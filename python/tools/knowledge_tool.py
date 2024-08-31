import os
from agent import Agent
from python.helpers import perplexity_search
from python.helpers import duckduckgo_search

from . import memory_tool
import concurrent.futures

from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle
from python.helpers.log import Log

class Knowledge(Tool):
    def execute(self, question="", **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Schedule the two functions to be run in parallel

            # perplexity search, if API key provided
            if os.getenv("API_KEY_PERPLEXITY"):
                perplexity = executor.submit(perplexity_search.perplexity_search, question)
            else: 
                PrintStyle.hint("No API key provided for Perplexity. Skipping Perplexity search.")
                Log(type="hint", content="No API key provided for Perplexity. Skipping Perplexity search.")
                perplexity = None
                

            # duckduckgo search
            duckduckgo = executor.submit(duckduckgo_search.search, question)

            # memory search
            future_memory = executor.submit(memory_tool.search, self.agent, question)

            # Wait for both functions to complete
            try:
                perplexity_result = (perplexity.result() if perplexity else "") or ""
            except Exception as e:
                perplexity_result = "Perplexity search failed: " + str(e)

            try:
                duckduckgo_result = duckduckgo.result()
            except Exception as e:
                duckduckgo_result = "DuckDuckGo search failed: " + str(e)

            try:
                memory_result = future_memory.result()
            except Exception as e:
                memory_result = "Memory search failed: " + str(e)

        msg = self.agent.read_prompt("tool.knowledge.response.md", 
                              online_sources = ((perplexity_result + "\n\n") if perplexity else "") + str(duckduckgo_result),
                              memory = memory_result )

        if self.agent.handle_intervention(msg): pass # wait for intervention and handle it, if paused

        return Response(message=msg, break_loop=False)
