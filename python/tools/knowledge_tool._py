import os
import asyncio
from python.helpers import dotenv, memory, perplexity_search, duckduckgo_search
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers.searxng import search as searxng
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD
from python.helpers.document_query import DocumentQueryHelper

SEARCH_ENGINE_RESULTS = 10


class Knowledge(Tool):
    async def execute(self, question="", **kwargs):
        # Create tasks for all three search methods
        tasks = [
            self.searxng_search(question),
            # self.perplexity_search(question),
            # self.duckduckgo_search(question),
            self.mem_search(question),
        ]

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # perplexity_result, duckduckgo_result, memory_result = results
        searxng_result, memory_result = results

        # enrich results with qa
        searxng_result = await self.searxng_document_qa(searxng_result, question)

        # Handle exceptions and format results
        # perplexity_result = self.format_result(perplexity_result, "Perplexity")
        # duckduckgo_result = self.format_result(duckduckgo_result, "DuckDuckGo")
        searxng_result = self.format_result_searxng(searxng_result, "Search Engine")
        memory_result = self.format_result(memory_result, "Memory")

        msg = self.agent.read_prompt(
            "fw.knowledge_tool.response.md",
            #   online_sources = ((perplexity_result + "\n\n") if perplexity_result else "") + str(duckduckgo_result),
            online_sources=((searxng_result + "\n\n") if searxng_result else ""),
            memory=memory_result,
        )

        await self.agent.handle_intervention(
            msg
        )  # wait for intervention and handle it, if paused

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

    async def searxng_search(self, question):
        return await searxng(question)

    async def searxng_document_qa(self, result, query):
        if isinstance(result, Exception) or not query or not result or not result["results"]:
            return result

        result["results"] = result["results"][:SEARCH_ENGINE_RESULTS]

        tasks = []
        helper = DocumentQueryHelper(self.agent)

        for index, item in enumerate(result["results"]):
            tasks.append(helper.document_qa(item["url"], [query]))

        task_results = list(await asyncio.gather(*tasks, return_exceptions=True))

        for index, item in enumerate(result["results"]):
            if isinstance(task_results[index], BaseException):
                continue
            found, qa = task_results[index]  # type: ignore
            if not found:
                continue
            result["results"][index]["qa"] = qa

        return result

    async def mem_search(self, question: str):
        db = await memory.Memory.get(self.agent)
        docs = await db.search_similarity_threshold(
            query=question, limit=5, threshold=DEFAULT_MEMORY_THRESHOLD
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
            if "qa" in item:
                outputs.append(
                    f"## Next Result\n"
                    f"*Title*: {item['title'].strip()}\n"
                    f"*URL*: {item['url'].strip()}\n"
                    f"*Search Engine Summary*:\n{item['content'].strip()}\n"
                    f"*Query Result*:\n{item['qa'].strip()}"
                )
            else:
                outputs.append(
                    f"## Next Result\n"
                    f"*Title*: {item['title'].strip()}\n"
                    f"*URL*: {item['url'].strip()}\n"
                    f"*Search Engine Summary*:\n{item['content'].strip()}"
                )

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()
