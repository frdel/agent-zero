import asyncio
import uuid
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from helpers.tool import Tool, Response
from helpers.strings import truncate_text
from plugins._document_query.helpers.document_query import DocumentQueryHelper


class DocumentQueryTool(Tool):

    async def execute(self, **kwargs):
        document_uri = kwargs.get("document")
        document_uris = []

        if isinstance(document_uri, list):
            document_uris = document_uri
        elif isinstance(document_uri, str):
            document_uris = [document_uri]

        if not document_uris:
            return Response(
                message=self.agent.read_prompt("fw.document_query.document_missing.md"),
                break_loop=False,
            )

        queries = (
            kwargs["queries"]
            if "queries" in kwargs
            else [kwargs["query"]]
            if ("query" in kwargs and kwargs["query"])
            else []
        )
        try:
            progress = []

            def progress_callback(msg):
                progress.append(msg)
                self.log.update(progress="\n".join(progress))

            helper = DocumentQueryHelper(
                self.agent, progress_callback, stream_callback=self._stream_answer
            )
            if not queries:
                gather_timeout = helper.config.get("gather_timeout", 120)
                try:
                    contents = await asyncio.wait_for(
                        asyncio.gather(
                            *[helper.document_get_content(uri) for uri in document_uris]
                        ),
                        timeout=gather_timeout,
                    )
                except asyncio.TimeoutError:
                    return Response(
                        message=self.agent.read_prompt(
                            "fw.document_query.timeout.md", gather_timeout=gather_timeout
                        ),
                        break_loop=False,
                    )
                content = "\n\n---\n\n".join(contents)
            else:
                _, content = await helper.document_qa(document_uris, queries)
            return Response(message=content, break_loop=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return Response(
                message=self.agent.read_prompt("fw.document_query.error.md", error=e),
                break_loop=False,
            )

    def _stream_answer(self, text: str):
        self.log.update(content=text)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="document_query",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        verb = "Querying" if _has_queries(self.args) else "Reading"
        uris = self.args.get("document") if isinstance(self.args.get("document"), list) else [self.args.get("document")]
        names = [_document_name(uri) for uri in uris]
        names = [name for name in names if name]
        if not names:
            return f"icon://manage_search {verb}" # missing document is a tool error
        head = truncate_text(names[0], 60)
        if len(names) > 1:
            return f"icon://manage_search {verb}: {head} + {len(names) - 1} more"
        return f"icon://manage_search {verb}: {head}"


def _has_queries(args: dict) -> bool:
    queries = args.get("queries") if "queries" in args else [args.get("query")] if args.get("query") else []
    if isinstance(queries, str):
        queries = [queries]
    return any(str(query or "").strip() for query in queries or [])


def _document_name(document):
    if not isinstance(document, str):
        return ""
    path = urlparse(document).path
    return PurePosixPath(unquote(path)).name
