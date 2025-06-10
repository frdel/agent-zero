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
        if not question:
            question = kwargs.get("query", "")
            if not question:
                return Response(message="No question provided", break_loop=False)

        # Create tasks for all search methods
        tasks = [
            self.searxng_search(question),
            # self.perplexity_search(question),
            # self.duckduckgo_search(question),
            self.mem_search_enhanced(question),
        ]

        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # perplexity_result, duckduckgo_result, memory_result = results
        searxng_result, memory_result = results

        # enrich results with qa
        searxng_result = await self.searxng_document_qa(searxng_result, question)

        # Handle exceptions and format results
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

    async def mem_search_enhanced(self, question: str):
        """
        Enhanced memory search with knowledge source awareness.
        Separates and prioritizes knowledge sources vs conversation memories.
        """
        try:
            db = await memory.Memory.get(self.agent)

            # Search for knowledge sources (knowledge_source=True)
            knowledge_docs = await db.search_similarity_threshold(
                query=question, limit=5, threshold=DEFAULT_MEMORY_THRESHOLD,
                filter="knowledge_source == True"
            )

            # Search for conversation memories (field doesn't exist or is not True)
            conversation_docs = await db.search_similarity_threshold(
                query=question, limit=5, threshold=DEFAULT_MEMORY_THRESHOLD,
                filter="not knowledge_source if 'knowledge_source' in locals() else True"
            )

            # Combine and fallback to lower threshold if needed
            all_docs = knowledge_docs + conversation_docs
            threshold_note = ""

            # If no results with default threshold, try with lower threshold
            if not all_docs:
                lower_threshold = DEFAULT_MEMORY_THRESHOLD * 0.8
                knowledge_docs = await db.search_similarity_threshold(
                    query=question, limit=5, threshold=lower_threshold,
                    filter="knowledge_source == True"
                )
                conversation_docs = await db.search_similarity_threshold(
                    query=question, limit=5, threshold=lower_threshold,
                    filter="not knowledge_source if 'knowledge_source' in locals() else True"
                )
                all_docs = knowledge_docs + conversation_docs
                if all_docs:
                    threshold_note = f" (threshold: {lower_threshold})"

            if not all_docs:
                return await self._get_memory_diagnostics(db, question)

            # Separate knowledge sources from conversation memories
            knowledge_sources = knowledge_docs
            conversation_memories = conversation_docs
            result_parts = []

            # Add search summary
            result_parts.append(f"## 🔍 Search Results for: '{question}'")
            result_parts.append(f"**Found:** {len(knowledge_sources)} knowledge sources, {len(conversation_memories)} conversation memories{threshold_note}")

            # Show knowledge sources
            if knowledge_sources:
                result_parts.append("")
                result_parts.append("## 📚 Knowledge Sources:")
                for index, doc in enumerate(knowledge_sources):
                    source_file = doc.metadata.get('source_file', 'Unknown source')
                    file_type = doc.metadata.get('file_type', '').upper()
                    area = doc.metadata.get('area', 'main').upper()

                    result_parts.append(f"**Source:** {source_file} ({file_type}) [{area}]")
                    result_parts.append(f"**Content:** {doc.page_content}")
                    if index < len(knowledge_sources) - 1:
                        result_parts.append("-" * 80)

            # Show conversation memories
            if conversation_memories:
                if knowledge_sources:
                    result_parts.append("")
                result_parts.append("## 💭 Related Experience:")
                for index, doc in enumerate(conversation_memories):
                    timestamp = doc.metadata.get('timestamp', 'Unknown time')
                    area = doc.metadata.get('area', 'main').upper()
                    consolidation_action = doc.metadata.get('consolidation_action', '')

                    metadata_info = f"{timestamp} [{area}]"
                    if consolidation_action:
                        metadata_info += f" (consolidated: {consolidation_action})"

                    result_parts.append(f"**Experience:** {metadata_info}")
                    result_parts.append(f"**Content:** {doc.page_content}")
                    if index < len(conversation_memories) - 1:
                        result_parts.append("-" * 80)

            return "\n".join(result_parts)

        except Exception as e:
            handle_error(e)
            return f"Memory search failed: {str(e)}"

    async def _get_memory_diagnostics(self, db, query: str):
        """Provide memory diagnostics when no search results are found."""
        try:
            # Get sample of all documents to see what's in memory
            sample_docs = await db.search_similarity_threshold(
                query="test", limit=20, threshold=0.0
            )

            if not sample_docs:
                return f"## 🔍 No Results for: '{query}'\n**Memory database appears to be empty.**"

            # Analyze what's in memory
            area_counts: dict[str, int] = {}
            knowledge_count = 0

            for doc in sample_docs:
                area = doc.metadata.get('area', 'unknown')
                area_counts[area] = area_counts.get(area, 0) + 1
                if doc.metadata.get('knowledge_source', False):
                    knowledge_count += 1

            result_parts = [
                f"## 🔍 No Results for: '{query}'",
                f"**Database contains:** {len(sample_docs)} total documents",
                f"**Areas:** {', '.join([f'{area.upper()}: {count}' for area, count in area_counts.items()])}",
                f"**Knowledge sources:** {knowledge_count} documents",
                "",
                "**Suggestions:**",
                "- Try different or more general search terms",
                "- Check if the information was recently memorized",
                f"- Current search threshold: {DEFAULT_MEMORY_THRESHOLD}"
            ]

            return "\n".join(result_parts)

        except Exception as e:
            return f"Memory diagnostics failed: {str(e)}"

    def format_result(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"
        return result if result else ""

    def format_result_searxng(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        if not result or "results" not in result:
            return ""

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
