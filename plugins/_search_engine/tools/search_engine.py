import uuid

from helpers.tool import Tool, Response
from helpers.errors import handle_error
from helpers.searxng import search as searxng
from helpers.strings import truncate_text

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

    def get_log_object(self):
        return self.agent.context.log.log(
            type="search_engine",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        query = str(self.args.get("query") or "").strip()
        text = f"Searching: {truncate_text(query, 60)}" if query else "Searching"
        return f"icon://search {text}"
