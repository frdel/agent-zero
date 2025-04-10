import os
import asyncio
import requests
from python.helpers import dotenv, memory, perplexity_search, duckduckgo_search
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers.searxng import search as searxng

SEARCH_ENGINE_RESULTS = 10
class Knowledge(Tool):
    async def execute(self, question="", **kwargs):
        # Create tasks for all three search methods
        tasks = [
            self.searxng_search(question),
            self.jina_search(question),
            self.mem_search(question),
        ]

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        searxng_result, jina_result, memory_result = results

        # Handle exceptions and format results
        searxng_result = self.format_result_searxng(searxng_result, "Search Engine")
        jina_result = self.format_result(jina_result, "Jina AI")
        memory_result = self.format_result(memory_result, "Memory")

        msg = self.agent.read_prompt(
            "tool.knowledge.response.md",
            online_sources=((searxng_result + "\n\n") if searxng_result else "") + ((jina_result + "\n\n") if jina_result else ""),
            memory=memory_result,
        )

        await self.agent.handle_intervention(
            msg
        )  # wait for intervention and handle it, if paused

        return Response(message=msg, break_loop=False)

    async def jina_search(self, question):
        try:
            url = "https://s.jina.ai/"
            headers = {
                "Authorization": f"Bearer {os.getenv('JINA_API_KEY')}",
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            payload = {
                "q": question,
                "num": SEARCH_ENGINE_RESULTS
            }
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            handle_error(e)
            return f"Jina AI search failed: {str(e)}"

    async def searxng_search(self, question):
        return await searxng(question)

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

        outputs = []
        for item in result.get("data", []):
            outputs.append(f"{item['title']}\n{item['url']}\n{item['content']}")

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()

    def format_result_searxng(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        outputs = []
        for item in result["results"]:
            outputs.append(f"{item['title']}\n{item['url']}\n{item['content']}")

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()
