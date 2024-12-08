import os
import asyncio
from typing import cast
from python.helpers import memory, perplexity_search, duckduckgo_search, searxng_search
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error

class Knowledge(Tool):
    async def execute(self, question="", **kwargs):
        # Create tasks for all search methods
        tasks = [
            self.perplexity_search(question),
            self.searxng(question),
            self.duckduckgo_search(question),
            self.mem_search(question)
        ]

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        perplexity_result, searxng_results, duckduckgo_result, memory_result = results

        # Handle exceptions and format results
        perplexity_result = self.format_result(perplexity_result, "Perplexity")
        searxng_results = self.format_result(searxng_results, "SearXNG")
        duckduckgo_result = self.format_result(duckduckgo_result, "DuckDuckGo")
        memory_result = self.format_result(memory_result, "Memory")
        online_sources = ((perplexity_result + "\n\n") if perplexity_result else "")
        online_sources += ((searxng_results + "\n\n") if searxng_results else "")
        online_sources += str(duckduckgo_result)
        msg = self.agent.read_prompt("tool.knowledge.response.md", 
                                        online_sources = online_sources,
                                        memory = memory_result)

        await self.agent.handle_intervention(msg)  # wait for intervention and handle it, if paused

        return Response(message=msg, break_loop=False)

    async def perplexity_search(self, question):
        if os.getenv("API_KEY_PERPLEXITY"):
            return await asyncio.to_thread(perplexity_search.perplexity_search, question)
        else:
            self.print("No API key provided for Perplexity. Skipping Perplexity search.")
            return None

    async def searxng(self, question):
        if os.getenv("SEARXNG_BASE_URL"):
            search_categories = os.getenv("SEARXNG_SEARCH_CATEGORIES")
            if search_categories is not None:
                searches = searxng_search.parse_categories_settings(search_categories)
            else:
                searches = searxng_search.parse_categories_settings("general:5,news:3")
            
            cats = []
            for category in searches:
                cats.append(category.category.capitalize())
            self.print(f"Initialized searXNG search for categories: {', '.join(cats)}")

            self.print("Waiting search results...")
            results = await searxng_search.search(queries=[question],
                                                    base_url=os.getenv('SEARXNG_BASE_URL', 'http://localhost:8080'),
                                                    category_limits=searches)
            self.print(f"Received {len(results)} search results.")

            markdown = searxng_search.to_markdown(results, question)
            return markdown
        else:
            self.print("No API key provided for SearXNG. Skipping SearXNG search.", False)
            return None
    
    async def duckduckgo_search(self, question):
        return await asyncio.to_thread(duckduckgo_search.search, question)

    def print(self, msg, is_error: bool = False):
        if is_error:
            PrintStyle.error(msg)
            self.agent.context.log.log(type="error", content=msg)
        else:
            PrintStyle.hint(msg)
            self.agent.context.log.log(type="info", content=msg)


    async def mem_search(self, question: str):
        db = await memory.Memory.get(self.agent)
        docs = await db.search_similarity_threshold(query=question, limit=5, threshold=0.5)
        text = memory.Memory.format_docs_plain(docs)
        return "\n\n".join(text)

    def format_result(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"
        return result if result else ""