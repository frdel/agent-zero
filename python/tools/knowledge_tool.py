import asyncio
from python.helpers import memory
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers.searxng import search as searxng
from typing import List, Dict

SEARCH_ENGINE_RESULTS = 20

class Knowledge(Tool):
    async def execute(self, question: str = "", search_sites: List[str] = [], **kwargs):
        # Run tasks concurrently
        tasks = [
            self.mem_search(question),
            self.searxng_search(question, search_sites)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        memory_result, searxng_result = results

        # Format results
        memory_result = self.format_result(memory_result, "Memory")
        searxng_result = self.format_result_searxng(searxng_result, "Search Engine")

        # Prepare response
        response_data = {
            "online_sources": searxng_result if searxng_result else "",
            "memory": memory_result if memory_result else "",
            "citations": self.format_citations(searxng_result)
        }

        msg = self.agent.read_prompt(
            "tool.knowledge.response.md",
            **response_data
        )

        await self.agent.handle_intervention(msg)
        return Response(message=msg, break_loop=False)

    async def searxng_search(self, question: str, search_sites: List[str]):
        return await searxng(question, search_sites)

    async def mem_search(self, question: str):
        db = await memory.Memory.get(self.agent)
        docs = await db.search_similarity_threshold(
            query=question, limit=5, threshold=0.5
        )
        text = memory.Memory.format_docs_plain(docs)
        return "\n\n".join(text)

    def format_result(self, result, source: str):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"
        return result if result else ""

    def format_result_searxng(self, result, source: str):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        # Handle empty or invalid results
        if not isinstance(result, dict) or "results" not in result:
            return ""

        # Check for search error
        if "error" in result:
            handle_error(result["error"])
            return f"{source} search failed: {result['error']}"

        # Handle empty results list
        if not result["results"]:
            return "No results found"

        outputs = []
        for item in result["results"]:
            try:
                formatted_result = f"""
Source: {item.get('title', 'Untitled')}
URL: {item.get('url', 'No URL available')}
Content:
{item.get('content', 'No content available')}
"""
                outputs.append(formatted_result)
            except Exception as e:
                handle_error(e)
                continue

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip() if outputs else "No valid results found"

    def format_citations(self, search_result: str) -> List[str]:
        if not search_result:
            return []
            
        citations = []
        current_citation = {}
        
        for line in search_result.split("\n"):
            if line.startswith("Source:"):
                if current_citation:
                    citations.append(self.format_citation(current_citation))
                current_citation = {"title": line.split(":")[1].strip()}
            elif line.startswith("URL:"):
                current_citation["url"] = line.split(":")[1].strip()
                
        if current_citation:
            citations.append(self.format_citation(current_citation))
            
        return citations

    def format_citation(self, citation: Dict[str, str]) -> str:
        return f"{citation.get('title', '')} - {citation.get('url', '')}"
