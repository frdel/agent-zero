from helpers.tool import Tool, Response
from helpers.errors import handle_error
from helpers.searxng import search as searxng

SEARCH_ENGINE_RESULTS = 10


class SearchEngine(Tool):
    async def execute(self, query="", **kwargs):


        searxng_result = await self.searxng_search(query)

        await self.agent.handle_intervention(
            searxng_result
        )  # wait for intervention and handle it, if paused

        return Response(message=searxng_result, break_loop=False)


    async def searxng_search(self, question):
        try:
            results = await searxng(question)
        except Exception as e:
            results = e
        return self.format_result_searxng(results, "Search Engine")

    def format_result_searxng(self, result, source):
        if isinstance(result, Exception):
            handle_error(result)
            return f"{source} search failed: {str(result)}"

        outputs = []
        for item in (result or {}).get("results", []):
            if not isinstance(item, dict):
                continue
            title = item.get("title", "")
            url = item.get("url", "")
            content = item.get("content", "")
            outputs.append(f"{title}\n{url}\n{content}")

        return "\n\n".join(outputs[:SEARCH_ENGINE_RESULTS]).strip()
