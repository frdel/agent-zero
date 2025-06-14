import mimetypes
import os
import asyncio
import aiohttp
import json

os.environ["USER_AGENT"] = "@mixedbread-ai/unstructured"  # noqa E402
from langchain_unstructured import UnstructuredLoader  # noqa E402

from urllib.parse import urlparse
from typing import Sequence, List, Optional, Tuple
from datetime import datetime

from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_community.document_loaders.pdf import PyMuPDFLoader
from langchain_community.document_transformers import MarkdownifyTransformer
from langchain_community.document_loaders.parsers.images import TesseractBlobParser

from langchain_core.documents import Document
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage
from langchain.storage import LocalFileStore, InMemoryStore
from langchain.embeddings import CacheBackedEmbeddings

from langchain_community.vectorstores import FAISS
import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores.utils import (
    DistanceStrategy,
)
from langchain_core.embeddings import Embeddings

from python.helpers.print_style import PrintStyle
from python.helpers import files #, rfc_files
rfc_files = files # TODO: fix

from agent import Agent
import models

from langchain.text_splitter import RecursiveCharacterTextSplitter


class DocumentQueryStore:
    """
    FAISS Store for document query results.
    Manages documents identified by URI for storage, retrieval, and searching.
    """

    # Default chunking parameters
    DEFAULT_CHUNK_SIZE = 1000
    DEFAULT_CHUNK_OVERLAP = 100

    # Cache for initialized stores
    _stores: dict[str, "DocumentQueryStore"] = {}

    @staticmethod
    async def get(agent: Agent):
        """Get or create a DocumentQueryStore instance for the specified agent."""
        if not agent or not agent.config:
            raise ValueError("Agent and agent config must be provided")

        memory_subdir = agent.config.memory_subdir or "default"
        store_key = f"{memory_subdir}/document_query"

        if store_key not in DocumentQueryStore._stores:
            # Initialize embeddings model from agent config
            embeddings_model = agent.get_embedding_model()

            # Initialize store
            store = DocumentQueryStore(agent, embeddings_model, memory_subdir)
            DocumentQueryStore._stores[store_key] = store
            return store
        else:
            return DocumentQueryStore._stores[store_key]

    @staticmethod
    async def reload(agent: Agent):
        """Reload the DocumentQueryStore for the specified agent."""
        memory_subdir = agent.config.memory_subdir or "default"
        store_key = f"{memory_subdir}/document_query"

        if store_key in DocumentQueryStore._stores:
            del DocumentQueryStore._stores[store_key]

        return await DocumentQueryStore.get(agent)

    def __init__(
        self,
        agent: Agent,
        embeddings_model: Embeddings,
        memory_subdir: str,
    ):
        """Initialize a DocumentQueryStore instance."""
        self.agent = agent
        self.memory_subdir = memory_subdir

        # Get directory paths
        db_dir = self._get_db_dir()
        em_dir = os.path.join(db_dir, "embeddings")

        # Create directories
        os.makedirs(db_dir, exist_ok=True)
        os.makedirs(em_dir, exist_ok=True)

        # Setup embeddings cache
        store = LocalFileStore(em_dir)
        self.embeddings = CacheBackedEmbeddings.from_bytes_store(
            embeddings_model,
            store,
            namespace=f"document_query_{getattr(embeddings_model, 'model', getattr(embeddings_model, 'model_name', 'default'))}"
        )

        # Initialize vector store
        index_path = os.path.join(db_dir, "index.faiss")
        docstore_path = os.path.join(db_dir, "docstore.json")

        if os.path.exists(index_path) and os.path.exists(docstore_path):
            PrintStyle.standard(f"Loading existing vector store from {db_dir}")
            try:
                self.vectorstore = FAISS.load_local(
                    folder_path=db_dir,
                    embeddings=self.embeddings,
                    allow_dangerous_deserialization=True,
                    distance_strategy=DistanceStrategy.COSINE,
                )
            except Exception as e:
                PrintStyle.error(f"Error loading vector store: {str(e)}")
                self._initialize_new_vectorstore()
        else:
            PrintStyle.standard(f"Creating new vector store in '{db_dir}'")
            self._initialize_new_vectorstore()

    def _initialize_new_vectorstore(self):
        """Initialize a new vector store."""
        dimension = len(self.embeddings.embed_query("test"))
        index = faiss.IndexFlatIP(dimension)
        self.vectorstore = FAISS(
            embedding_function=self.embeddings,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
            distance_strategy=DistanceStrategy.COSINE,
        )

    def _get_db_dir(self) -> str:
        """Get the absolute path to the database directory."""
        return files.get_abs_path("memory", self.memory_subdir, "document_query")

    def _save_vectorstore(self):
        """Save the vector store to disk."""
        db_dir = self._get_db_dir()
        PrintStyle.standard(f"Saving vector store to {db_dir}")
        self.vectorstore.save_local(folder_path=db_dir)
        PrintStyle.standard(f"Vector store saved with {len(self.vectorstore.index_to_docstore_id)} documents")

    @staticmethod
    def _normalize_uri(uri: str) -> str:
        """
        Normalize a document URI to ensure consistent lookup.

        Args:
            uri: The URI to normalize

        Returns:
            Normalized URI
        """
        # Convert to lowercase
        normalized = uri.lower()

        # Parse the URL to get scheme
        parsed = urlparse(normalized)
        scheme = parsed.scheme or "file"

        # Normalize based on scheme
        if scheme == "file":
            if not normalized.startswith("file:"):
                normalized = "file:" + normalized
            if normalized.startswith("file://"):
                normalized = normalized.replace("file://", "file:")
        elif scheme in ["http", "https"]:
            # Always use https for web URLs
            normalized = normalized.replace("http://", "https://")

        return normalized

    async def add_document(self, text: str, document_uri: str, metadata: dict | None = None) -> bool:
        """
        Add a document to the store with the given URI.

        Args:
            text: The document text content
            document_uri: The URI that uniquely identifies this document
            metadata: Optional metadata for the document

        Returns:
            True if successful, False otherwise
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        # Delete existing document if it exists to avoid duplicates
        await self.delete_document(document_uri)

        # Initialize metadata
        doc_metadata = metadata or {}
        doc_metadata["document_uri"] = document_uri
        doc_metadata["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.DEFAULT_CHUNK_SIZE,
            chunk_overlap=self.DEFAULT_CHUNK_OVERLAP
        )
        chunks = text_splitter.split_text(text)

        # Create documents
        docs = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = doc_metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)
            docs.append(Document(page_content=chunk, metadata=chunk_metadata))

        if not docs:
            PrintStyle.error(f"No chunks created for document: {document_uri}")
            return False

        # Apply rate limiter
        try:
            docs_text = "".join(chunk.page_content for chunk in docs)
            await self.agent.rate_limiter(
                model_config=self.agent.config.embeddings_model,
                input=docs_text
            )

            # Add documents to vector store
            self.vectorstore.add_documents(documents=docs)
            self._save_vectorstore()
            PrintStyle.standard(f"Added document '{document_uri}' with {len(docs)} chunks")
            return True
        except Exception as e:
            PrintStyle.error(f"Error adding document '{document_uri}': {str(e)}")
            return False

    async def get_document(self, document_uri: str) -> Optional[Document]:
        """
        Retrieve a document by its URI.

        Args:
            document_uri: The URI of the document to retrieve

        Returns:
            The complete document if found, None otherwise
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        # Get all chunks for this document
        docs = await self._get_document_chunks(document_uri)
        if not docs:
            PrintStyle.error(f"Document not found: {document_uri}")
            return None

        # Combine chunks into a single document
        chunks = sorted(docs, key=lambda x: x.metadata.get("chunk_index", 0))
        full_content = "\n".join(chunk.page_content for chunk in chunks)

        # Use metadata from first chunk
        metadata = chunks[0].metadata.copy()
        metadata.pop("chunk_index", None)
        metadata.pop("total_chunks", None)

        return Document(page_content=full_content, metadata=metadata)

    async def _get_document_chunks(self, document_uri: str) -> List[Document]:
        """
        Get all chunks for a document.

        Args:
            document_uri: The URI of the document

        Returns:
            List of document chunks
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        # Access docstore directly
        chunks = []
        for doc_id, doc in self.vectorstore.docstore._dict.items():  # type: ignore
            if isinstance(doc.metadata, dict) and doc.metadata.get("document_uri") == document_uri:
                chunks.append(doc)

        PrintStyle.standard(f"Found {len(chunks)} chunks for document: {document_uri}")
        return chunks

    async def document_exists(self, document_uri: str) -> bool:
        """
        Check if a document exists in the store.

        Args:
            document_uri: The URI of the document to check

        Returns:
            True if the document exists, False otherwise
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        chunks = await self._get_document_chunks(document_uri)
        return len(chunks) > 0

    async def delete_document(self, document_uri: str) -> bool:
        """
        Delete a document from the store.

        Args:
            document_uri: The URI of the document to delete

        Returns:
            True if deleted, False if not found
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        chunks = await self._get_document_chunks(document_uri)
        if not chunks:
            return False

        # Collect IDs to delete
        ids_to_delete = []
        for chunk in chunks:
            for doc_id, doc_ref in self.vectorstore.docstore._dict.items():  # type: ignore
                if doc_ref == chunk:
                    ids_to_delete.append(doc_id)

        # Delete from vector store
        if ids_to_delete:
            self.vectorstore.delete(ids_to_delete)
            self._save_vectorstore()
            PrintStyle.standard(f"Deleted document '{document_uri}' with {len(ids_to_delete)} chunks")
            return True

        return False

    async def expire_documents(self, older_than_days: float) -> int:
        """
        Delete documents older than the specified number of days.

        Args:
            older_than_days: Number of days (can be fractional) before current time

        Returns:
            Number of documents deleted
        """
        if older_than_days <= 0:
            return 0

        # Calculate cutoff timestamp
        cutoff_date = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)

        # Find expired documents
        expired_uris = set()

        # Check all documents in the store
        for doc_id, doc in self.vectorstore.docstore._dict.items():  # type: ignore
            if not isinstance(doc.metadata, dict):
                continue

            # Only process each document once (first chunk)
            if doc.metadata.get("chunk_index", 0) != 0:
                continue

            doc_uri = doc.metadata.get("document_uri")
            if not doc_uri:
                continue

            try:
                # Check timestamp
                timestamp_str = doc.metadata.get("timestamp")
                if not timestamp_str:
                    continue

                doc_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S").timestamp()
                if doc_timestamp < cutoff_date:
                    expired_uris.add(doc_uri)
            except (ValueError, TypeError):
                # Skip documents with invalid timestamps
                continue

        # Delete expired documents
        deleted_count = 0
        for uri in expired_uris:
            if await self.delete_document(uri):
                deleted_count += 1

        PrintStyle.standard(f"Expired {deleted_count} documents older than {older_than_days} days")
        return deleted_count

    async def search_documents(self, query: str, limit: int = 10, threshold: float = 0.5) -> List[Document]:
        """
        Search for documents similar to the query across the entire store.

        Args:
            query: The search query string
            limit: Maximum number of results to return
            threshold: Minimum similarity score threshold (0-1)

        Returns:
            List of matching documents
        """
        # Handle empty query
        if not query:
            PrintStyle.standard("Empty search query, returning empty results")
            return []

        # Apply rate limiter
        await self.agent.rate_limiter(
            model_config=self.agent.config.embeddings_model,
            input=query
        )

        # Perform search
        try:
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=limit,
                score_threshold=threshold
            )

            # Extract documents from results (which are (doc, score) pairs)
            docs = [doc for doc, score in results]
            PrintStyle.standard(f"Search '{query}' returned {len(docs)} results")
            return docs
        except Exception as e:
            PrintStyle.error(f"Error searching documents: {str(e)}")
            return []

    async def search_document(self, document_uri: str, query: str, limit: int = 10, threshold: float = 0.5) -> List[Document]:
        """
        Search for content within a specific document.

        Args:
            document_uri: The URI of the document to search within
            query: The search query string
            limit: Maximum number of results to return
            threshold: Minimum similarity score threshold (0-1)

        Returns:
            List of matching document chunks
        """
        # Normalize the URI
        document_uri = self._normalize_uri(document_uri)

        # Handle empty query
        if not query:
            PrintStyle.standard("Empty search query, returning empty results")
            return []

        # Check if document exists
        if not await self.document_exists(document_uri):
            PrintStyle.error(f"Document not found: {document_uri}")
            return []

        # Apply rate limiter
        await self.agent.rate_limiter(
            model_config=self.agent.config.embeddings_model,
            input=query
        )

        # Perform search with document filter
        try:
            # Create metadata filter function
            def filter_fn(doc_metadata):
                return doc_metadata.get("document_uri") == document_uri

            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=limit,
                score_threshold=threshold,
                filter=filter_fn
            )

            # Extract documents from results
            docs = [doc for doc, score in results]
            PrintStyle.standard(f"Search '{query}' in document '{document_uri}' returned {len(docs)} results")

            # Try with lower threshold if no results
            if not docs and threshold > 0.3:
                PrintStyle.standard("No results found, trying with lower threshold (0.3)")
                results = self.vectorstore.similarity_search_with_score(
                    query=query,
                    k=limit,
                    score_threshold=0.3,
                    filter=filter_fn
                )
                docs = [doc for doc, score in results]
                PrintStyle.standard(f"Retry search returned {len(docs)} results")

            return docs
        except Exception as e:
            PrintStyle.error(f"Error searching within document: {str(e)}")
            return []

    async def list_documents(self) -> List[str]:
        """
        Get a list of all document URIs in the store.

        Returns:
            List of document URIs
        """
        # Extract unique URIs
        uris = set()
        for doc in self.vectorstore.docstore._dict.values():  # type: ignore
            if isinstance(doc.metadata, dict):
                uri = doc.metadata.get("document_uri")
                if uri:
                    uris.add(uri)

        return sorted(list(uris))


class DocumentQueryHelper:

    def __init__(self, agent: Agent):
        self.agent = agent
        self.store: DocumentQueryStore = asyncio.run(DocumentQueryStore.get(agent))

    async def document_qa(self, document_uri: str, questions: Sequence[str]) -> Tuple[bool, str]:
        _ = await self.document_get_content(document_uri)
        content = ""
        for question in questions:
            human_content = f'Search Query: "{question}"'
            system_content = self.agent.parse_prompt("fw.document_query.optmimize_query.md")

            optimized_query = await self.agent.call_utility_model(
                system=system_content,
                message=human_content
            )

            chunks = await self.store.search_document(
                document_uri=document_uri,
                query=str(optimized_query),
                limit=10000,
                threshold=0.66
            )
            content += "\n\n----\n\n".join([chunk.page_content for chunk in chunks]) + "\n\n----\n\n"

        if not content:
            content = f"!!! No content found for document: {document_uri} matching queries: {json.dumps(questions)}"
            return False, content

        questions_str = "\n".join([f" *  {question}" for question in questions])

        qa_system_message = self.agent.parse_prompt("fw.document_query.system_prompt.md")
        qa_user_message = f"# Document:\n{content}\n\n# Queries:\n{questions_str}"

        ai_response = await self.agent.call_chat_model(
            prompt=ChatPromptTemplate.from_messages([
                SystemMessage(content=qa_system_message),
                HumanMessage(content=qa_user_message),
            ])
        )

        return True, str(ai_response)

    async def document_get_content(self, document_uri: str) -> str:
        url = urlparse(document_uri)
        scheme = url.scheme or "file"
        mimetype, encoding = mimetypes.guess_type(document_uri)
        mimetype = mimetype or "application/octet-stream"

        if mimetype == "application/octet-stream":
            if url.scheme in ["http", "https"]:
                response: aiohttp.ClientResponse | None = None
                retries = 0
                last_error = ""
                while not response and retries < 3:
                    try:
                        async with aiohttp.ClientSession() as session:
                            response = await session.head(document_uri, timeout=aiohttp.ClientTimeout(total=2.0), allow_redirects=True)
                            if response.status > 399:
                                raise Exception(response.status)
                            break
                    except Exception as e:
                        await asyncio.sleep(1)
                        last_error = str(e)
                    retries += 1

                if not response:
                    raise ValueError(f"DocumentQueryHelper::document_get_content: Document fetch error: {document_uri} ({last_error})")

                mimetype = response.headers["content-type"]
                if "content-length" in response.headers:
                    content_length = float(response.headers["content-length"]) / 1024 / 1024  # MB
                    if content_length > 50.0:
                        raise ValueError(f"Document content length exceeds max. 50MB: {content_length} MB ({document_uri})")
                if mimetype and '; charset=' in mimetype:
                    mimetype = mimetype.split('; charset=')[0]

        if scheme == "file":
            try:
                document_uri = os.path.abspath(url.path)
            except Exception as e:
                raise ValueError(f"Invalid document path '{url.path}'") from e

        if encoding:
            raise ValueError(f"Compressed documents are unsupported '{encoding}' ({document_uri})")

        if mimetype == "application/octet-stream":
            raise ValueError(f"Unsupported document mimetype '{mimetype}' ({document_uri})")

        # Use the store's normalization method
        document_uri_norm = self.store._normalize_uri(document_uri)

        await self.store.expire_documents(7)
        exists = await self.store.document_exists(document_uri_norm)
        document_content = ""
        if not exists:
            if mimetype.startswith("image/"):
                document_content = self.handle_image_document(document_uri, scheme)
            elif mimetype == "text/html":
                document_content = self.handle_html_document(document_uri, scheme)
            elif mimetype.startswith("text/") or mimetype == "application/json":
                document_content = self.handle_text_document(document_uri, scheme)
            elif mimetype == "application/pdf":
                document_content = self.handle_pdf_document(document_uri, scheme)
            else:
                document_content = self.handle_unstructured_document(document_uri, scheme)
            await self.store.add_document(document_content, document_uri_norm)
        else:
            doc = await self.store.get_document(document_uri_norm)
            if doc:
                document_content = doc.page_content
            else:
                raise ValueError(f"DocumentQueryHelper::document_get_content: Document not found: {document_uri_norm}")
        return document_content

    def handle_image_document(self, document: str, scheme: str) -> str:
        return self.handle_unstructured_document(document, scheme)

    def handle_html_document(self, document: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            loader = AsyncHtmlLoader(web_path=document)
            parts: list[Document] = loader.load()
        elif scheme == "file":
            # Use RFC file operations instead of TextLoader
            file_content_bytes = rfc_files.read_file_bin(document)
            file_content = file_content_bytes.decode('utf-8')
            # Create Document manually since we're not using TextLoader
            parts = [Document(page_content=file_content, metadata={"source": document})]
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        return "\n".join([element.page_content for element in MarkdownifyTransformer().transform_documents(parts)])

    def handle_text_document(self, document: str, scheme: str) -> str:
        if scheme in ["http", "https"]:
            loader = AsyncHtmlLoader(web_path=document)
            elements: list[Document] = loader.load()
        elif scheme == "file":
            # Use RFC file operations instead of TextLoader
            file_content_bytes = rfc_files.read_file_bin(document)
            file_content = file_content_bytes.decode('utf-8')
            # Create Document manually since we're not using TextLoader
            elements = [Document(page_content=file_content, metadata={"source": document})]
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        return "\n".join([element.page_content for element in elements])

    def handle_pdf_document(self, document: str, scheme: str) -> str:
        temp_file_path = ""
        if scheme == "file":
            # Use RFC file operations to read the PDF file as binary
            file_content_bytes = rfc_files.read_file_bin(document)
            # Create a temporary file for PyMuPDFLoader since it needs a file path
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(file_content_bytes)
                temp_file_path = temp_file.name
        elif scheme in ["http", "https"]:
            # download the file from the web url to a temporary file using python libraries for downloading
            import requests
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                response = requests.get(document, timeout=10.0)
                if response.status_code != 200:
                    raise ValueError(f"DocumentQueryHelper::handle_pdf_document: Failed to download PDF from {document}: {response.status_code}")
                temp_file.write(response.content)
                temp_file_path = temp_file.name
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        if not os.path.exists(temp_file_path):
            raise ValueError(f"DocumentQueryHelper::handle_pdf_document: Temporary file not found: {temp_file_path}")

        try:
            try:
                loader = PyMuPDFLoader(
                    temp_file_path,
                    mode="single",
                    extract_tables="markdown",
                    extract_images=True,
                    images_inner_format="text",
                    images_parser=TesseractBlobParser(),
                    pages_delimiter="\n",
                )
                elements: list[Document] = loader.load()
                contents = "\n".join([element.page_content for element in elements])
            except Exception as e:
                PrintStyle.error(f"DocumentQueryHelper::handle_pdf_document: Error loading with PyMuPDF: {e}")
                contents = ""

            if not contents:
                import pdf2image
                import pytesseract

                PrintStyle.debug(f"DocumentQueryHelper::handle_pdf_document: FALLBACK Converting PDF to images: {temp_file_path}")

                # Convert PDF to images
                pages = pdf2image.convert_from_path(temp_file_path) # type: ignore
                for page in pages:
                    contents += pytesseract.image_to_string(page) + "\n\n"

            return contents
        finally:
            os.unlink(temp_file_path)

    def handle_unstructured_document(self, document: str, scheme: str) -> str:
        elements: list[Document] = []
        if scheme in ["http", "https"]:
            # loader = UnstructuredURLLoader(urls=[document], mode="single")
            loader = UnstructuredLoader(
                web_url=document,
                mode="single",
                partition_via_api=False,
                # chunking_strategy="by_page",
                strategy="hi_res",
            )
            elements = loader.load()
        elif scheme == "file":
            # Use RFC file operations to read the file as binary
            file_content_bytes = rfc_files.read_file_bin(document)
            # Create a temporary file for UnstructuredLoader since it needs a file path
            import tempfile
            import os
            # Get file extension to preserve it for proper processing
            _, ext = os.path.splitext(document)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(file_content_bytes)
                temp_file_path = temp_file.name

            try:
                loader = UnstructuredLoader(
                    file_path=temp_file_path,
                    mode="single",
                    partition_via_api=False,
                    # chunking_strategy="by_page",
                    strategy="hi_res",
                )
                elements = loader.load()
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
        else:
            raise ValueError(f"Unsupported scheme: {scheme}")

        return "\n".join([element.page_content for element in elements])
