import mimetypes
import os
from urllib.parse import urlparse
from typing import Sequence, cast
import requests

from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_community.document_loaders.pdf import PyMuPDFLoader
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_community.document_loaders.parsers.images import TesseractBlobParser

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel

os.environ["USER_AGENT"] = "@mixedbread-ai/unstructured"  # noqa E402
from langchain_unstructured import UnstructuredLoader  # noqa E402

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class DocumentQueryTool(Tool):

    async def execute(self, **kwargs):
        document_uri = kwargs["document"] or None
        queries = kwargs["queries"] if "queries" in kwargs else [kwargs["query"]] if ("query" in kwargs and kwargs["query"]) else []
        if not isinstance(document_uri, str) or not document_uri:
            return Response(message="Error: no document provided", break_loop=False)
        try:
            content = await self._document_get_content(document_uri)
            if content and queries:
                content = await self._document_qa(content, queries)
            return Response(message=content, break_loop=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return Response(message=f"Error processing document: {e}", break_loop=False)

    async def _document_qa(self, content: str, questions: Sequence[str]) -> str:
        questions_str = "\n".join([f" *  {question}" for question in questions])
        llm: BaseChatModel = self.agent.get_chat_model()
        qa_system_message = self.agent.parse_prompt("fw.document_query.system_prompt.md")
        qa_user_message = "# Document:\n{content}\n\n# Queries:\n{queries}"
        ai_response: AIMessage = cast(AIMessage, await llm.ainvoke(
            [
                SystemMessage(content=qa_system_message),
                HumanMessage(content=qa_user_message.format(content=content, queries=questions_str)),
            ]
        ))
        return str(ai_response.text())

    async def _document_get_content(self, document_uri: str) -> str:
        url = urlparse(document_uri)
        scheme = url.scheme or "file"
        mimetype, encoding = mimetypes.guess_type(document_uri)
        mimetype = mimetype or "application/octet-stream"

        if mimetype == "application/octet-stream":
            if url.scheme in ["http", "https"]:
                response: requests.Response = requests.Session().head(document_uri, timeout=2.0, allow_redirects=True)
                mimetype = response.headers["content-type"]
                if "content-length" in response.headers:
                    content_length = float(response.headers["content-length"]) / 1024 / 1024  # MB
                    if content_length > 25.0:
                        raise ValueError(f"Document content length exceeds max. 25MB: {content_length} MB ({document_uri})")
                if mimetype and '; charset=' in mimetype:
                    mimetype = mimetype.split('; charset=')[0]

        if scheme == "file":
            try:
                document_uri = os.path.abspath(url.path)
            except Exception as e:
                raise ValueError(f"Invalid document path '{url.path}'") from e

        PrintStyle(font_color="green", padding=True).print(
            f"DocumentQueryTool::Document: {document_uri} {encoding} {mimetype}"
        )

        if encoding:
            raise ValueError(f"Compressed documents are unsupported '{encoding}' ({document_uri})")

        if mimetype == "application/octet-stream":
            raise ValueError(f"Unsupported document mimetype '{mimetype}' ({document_uri})")

        if mimetype.startswith("image/"):
            return self.handle_image_document(document_uri, scheme)
        elif mimetype == "text/html":
            return self.handle_html_document(document_uri, scheme)
        elif mimetype.startswith("text/") or mimetype == "application/json":
            return self.handle_text_document(document_uri, scheme)
        elif mimetype == "application/pdf":
            return self.handle_pdf_document(document_uri, scheme)
        else:
            return self.handle_unstructured_document(document_uri, scheme)

    def handle_image_document(self, document: str, scheme: str) -> str:
        return self.handle_unstructured_document(document, scheme)

    def handle_html_document(self, document: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            loader = AsyncHtmlLoader(web_path=document)
        elif scheme == "file":
            loader = TextLoader(file_path=document)
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        parts: list[Document] = loader.load()
        return "\n".join([element.page_content for element in MarkdownifyTransformer().transform_documents(parts)])

    def handle_text_document(self, document: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            loader = AsyncHtmlLoader(web_path=document)
        elif scheme == "file":
            loader = TextLoader(file_path=document)
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        elements: list[Document] = loader.load()
        return "\n".join([element.page_content for element in elements])

    def handle_pdf_document(self, document: str, scheme: str) -> str:
        if scheme not in ["file", "http", "https"]:
            raise ValueError(f"Unsupported scheme: {scheme}")

        loader = PyMuPDFLoader(
            document,
            mode="single",
            extract_tables="markdown",
            extract_images=True,
            images_inner_format="text",
            images_parser=TesseractBlobParser(),
            pages_delimiter="\n",
        )

        elements: list[Document] = loader.load()
        return "\n".join([element.page_content for element in elements])

    def handle_unstructured_document(self, document: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            # loader = UnstructuredURLLoader(urls=[document], mode="single")
            loader = UnstructuredLoader(
                web_url=document,
                mode="single",
                partition_via_api=False,
                # chunking_strategy="by_page",
                strategy="hi_res",
            )
        elif scheme == "file":
            loader = UnstructuredLoader(
                file_path=document,
                mode="single",
                partition_via_api=False,
                # chunking_strategy="by_page",
                strategy="hi_res",
            )
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        elements: list[Document] = loader.load()
        return "\n".join([element.page_content for element in elements])
