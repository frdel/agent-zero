import asyncio
from python.helpers import dotenv, memory, perplexity_search, duckduckgo_search
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers.searxng import search as searxng

SEARCH_ENGINE_RESULTS = 10
class Knowledge(Tool):
    async def execute(self, question="", search_sites=[], **kwargs):
        # Run tasks concurrently
        tasks = [
            self.mem_search(question),
            self.searxng_search(question, search_sites)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        memory_result, searxng_result = results
        
        memory_result = self.format_result(memory_result, "Memory")
        searxng_result = self.format_result_searxng(searxng_result, "Search Engine")

        msg = self.agent.read_prompt(
            "tool.knowledge.response.md",
            online_sources=((searxng_result + "\n\n") if searxng_result else ""),
            memory=memory_result,
        )

        await self.agent.handle_intervention(msg)

        return Response(message=msg, break_loop=False)

    async def perplexity_search(self, question):
        if dotenv.get_dotenv_value("API_KEY_PERPLEXITY"):
            return await asyncio.to_thread(
                perplexity_search.perplexity_search, question
            )
        else:
            PrintStyle.hint(
                "No API key provided for Perplexity. Skipping Perplexity search."
            )
            self.agent.context.log.log(
                type="hint",
                content="No API key provided for Perplexity. Skipping Perplexity search.",
            )
            return None

    async def duckduckgo_search(self, question):
        return await asyncio.to_thread(duckduckgo_search.search, question)

    async def searxng_search(self, question, search_sites):
        return await searxng(question, search_sites)

    async def mem_search(self, question: str):
        db = await memory.Memory.get(self.agent)
        docs = await db.search_similarity_threshold(
            query=question, limit=5, threshold=0.5
        )
        text = memory.Memory.format_docs_plain(docs)
        return "\n\n".join(text)

    def format_result(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"
        return result if result else ""

    def format_result_searxng(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        outputs = []
        for item in result["results"]:
            outputs.append(f"{item['title']}\n{item['url']}\n{item['content']}")

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()
