

from urllib.parse import urlparse
import os
import mimetypes
from typing import List

from python.helpers.tool import Tool, Response
from python.helpers.document_query import DocumentQueryHelper, DocumentQueryStore
from python.helpers import memory
from python.helpers.print_style import PrintStyle
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter


class KnowledgeIndex(Tool):
    async def execute(self, uri: str = "", url: str = "", path: str = "", owner: str | None = None, **kwargs):
        # Resolve source URI
        source_uri = uri or url or path or self.args.get("uri") or self.args.get("url") or self.args.get("path") or ""
        if not source_uri:
            return Response(message="No 'uri' provided (accepts uri/url/path)", break_loop=False)

        # Always index into main area
        area = memory.Memory.Area.MAIN.value

        # Determine owner: explicit > profile-based default
        resolved_owner = (owner or self.args.get("owner") or "").strip()
        if not resolved_owner:
            profile = self.agent.config.profile or ""
            resolved_owner = profile if profile and profile != "default" else "default"

        # Fetch content using DocumentQueryHelper (no indexing into its store)
        helper = DocumentQueryHelper(self.agent)
        try:
            content = await helper.document_get_content(source_uri, add_to_db=False)
        except Exception as e:
            return Response(message=f"Failed to fetch document: {e}", break_loop=False)

        # Split content into chunks similar to DocumentQueryStore defaults
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=DocumentQueryStore.DEFAULT_CHUNK_SIZE,
            chunk_overlap=DocumentQueryStore.DEFAULT_CHUNK_OVERLAP,
        )
        chunks = splitter.split_text(content or "")
        if not chunks:
            return Response(message="No content extracted from document", break_loop=False)

        # Build metadata
        parsed = urlparse(source_uri)
        source_path = source_uri
        source_file = os.path.basename(parsed.path or source_uri)
        file_type = (mimetypes.guess_type(source_file)[0] or "").split("/")[-1] if source_file else ""

        base_metadata = {
            "area": area,
            "owner": resolved_owner,
            "knowledge_source": True,
            "source_file": source_file,
            "source_path": source_path,
            "file_type": file_type,
            "document_uri": DocumentQueryStore.normalize_uri(source_uri),
        }

        # Create Documents
        docs: List[Document] = []
        total = len(chunks)
        for idx, chunk in enumerate(chunks):
            md = base_metadata.copy()
            md["chunk_index"] = idx
            md["total_chunks"] = total
            docs.append(Document(page_content=chunk, metadata=md))

        # Insert into knowledge memory
        db = await memory.Memory.get(self.agent)
        try:
            ids = await db.insert_documents(docs)
        except Exception as e:
            return Response(message=f"Failed to index knowledge: {e}", break_loop=False)

        msg = (
            f"Indexed knowledge from '{source_uri}'\n"
            f"Chunks: {len(ids)} | Area: {area} | Owner: {resolved_owner}"
        )
        PrintStyle.standard(msg)
        return Response(message=msg, break_loop=False)
