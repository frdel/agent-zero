from python.helpers.tool import Tool, Response
from python.helpers.document_query import DocumentQueryHelper


class DocumentQueryTool(Tool):

    async def execute(self, **kwargs):
        document_uri = kwargs["document"] or None
        queries = kwargs["queries"] if "queries" in kwargs else [kwargs["query"]] if ("query" in kwargs and kwargs["query"]) else []
        if not isinstance(document_uri, str) or not document_uri:
            return Response(message="Error: no document provided", break_loop=False)
        try:

            progress = []

            # logging callback
            def progress_callback(msg):
                progress.append(msg)
                self.log.update(progress="\n".join(progress))
            
            helper = DocumentQueryHelper(self.agent, progress_callback)
            if not queries:
                content = await helper.document_get_content(document_uri)
            else:
                _, content = await helper.document_qa(document_uri, queries)
            return Response(message=content, break_loop=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return Response(message=f"Error processing document: {e}", break_loop=False)
