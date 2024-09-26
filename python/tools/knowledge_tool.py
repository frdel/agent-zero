import os
from python.helpers import perplexity_search
from python.helpers import duckduckgo_search
from . import memory_tool
import concurrent.futures
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error

class Knowledge(Tool):
    async def execute(self, question="", **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Schedule the two functions to be run in parallel

            # perplexity search, if API key provided
            if os.getenv("API_KEY_PERPLEXITY"):
                perplexity = executor.submit(perplexity_search.perplexity_search, question)
            else: 
                PrintStyle.hint("No API key provided for Perplexity. Skipping Perplexity search.")
                self.agent.context.log.log(type="hint", content="No API key provided for Perplexity. Skipping Perplexity search.")
                perplexity = None
                

            # duckduckgo search
            duckduckgo = executor.submit(duckduckgo_search.search, question)

            # manual memory search
            future_memory_man = executor.submit(memory_tool.search, self.agent, question)

            # Wait for both functions to complete
            try:
                perplexity_result = (perplexity.result() if perplexity else "") or ""
            except Exception as e:
                handle_error(e)
                perplexity_result = "Perplexity search failed: " + str(e)

            try:
                duckduckgo_result = duckduckgo.result()
            except Exception as e:
                handle_error(e)
                duckduckgo_result = "DuckDuckGo search failed: " + str(e)

            try:
                memory_result = future_memory_man.result()
            except Exception as e:
                handle_error(e)
                memory_result = "Memory search failed: " + str(e)

        msg = self.agent.read_prompt("tool.knowledge.response.md", 
                              online_sources = ((perplexity_result + "\n\n") if perplexity else "") + str(duckduckgo_result),
                              memory = memory_result )

        await self.agent.handle_intervention(msg) # wait for intervention and handle it, if paused

        return Response(message=msg, break_loop=False)
