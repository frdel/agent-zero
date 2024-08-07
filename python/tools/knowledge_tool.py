import os
import concurrent.futures
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers import perplexity_search, duckduckgo_search
from python.helpers.print_style import PrintStyle  # Retain new import from main branch
from . import memory_tool

class Knowledge(Tool):
    def execute(self, question="", **kwargs):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Schedule the different searches to be run in parallel
            if os.getenv("API_KEY_PERPLEXITY"):
                perplexity_future = executor.submit(perplexity_search.perplexity_search, question)
            else:
                PrintStyle.hint("No API key provided for Perplexity. Skipping Perplexity search.")
                perplexity_future = None

            duckduckgo_future = executor.submit(duckduckgo_search.search, question)
            memory_future = executor.submit(memory_tool.search, self.agent, question)
            wikipedia_future = executor.submit(fetch_wikipedia_content, question)

            # Collect the results
            perplexity_result = (perplexity_future.result() if perplexity_future else "") or ""
            duckduckgo_result = duckduckgo_future.result()
            memory_result = memory_future.result()
            wikipedia_result = wikipedia_future.result()

        msg = files.read_file(
            "prompts/tool.knowledge.response.md",
            online_sources=perplexity_result + "\n\n" + str(duckduckgo_result) + "\n\n" + wikipedia_result,
            memory=memory_result
        )

        if self.agent.handle_intervention(msg):  # wait for intervention and handle it, if paused
            pass

        return Response(message=msg, break_loop=False)

def fetch_wikipedia_content(query):
    try:
        import wikipedia
    except ImportError:
        return "Error: The 'wikipedia' library is not installed. Please install it using 'pip install wikipedia'."

    try:
        summary = wikipedia.summary(query)
        return summary
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options
        return f"Disambiguation Error: The query '{query}' may refer to multiple topics. Options include: {options[:3]}..."  # Limiting to the first 3 options for brevity
    except wikipedia.exceptions.PageError:
        return "Page not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"
