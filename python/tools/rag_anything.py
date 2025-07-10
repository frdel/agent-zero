import json
import os
from typing import Dict, List, Any
from pathlib import Path

from python.helpers.tool import Tool, Response
from python.helpers.rag_anything_processor import RAGAnythingProcessor
from python.helpers.rag_anything_memory import RAGAnythingMemory
from python.helpers.rag_anything_models import validate_model_setup
from python.helpers.print_style import PrintStyle


class RAGAnythingTool(Tool):
    """
    RAG-Anything integration tool for Agent Zero
    Provides multimodal document processing and retrieval capabilities
    
    Supports the following operations:
    - process: Process documents to extract multimodal content
    - query: Search processed content using semantic similarity
    - status: Get processing statistics and system status
    - batch: Process multiple documents in batch
    """

    def __init__(self, agent, name: str, method: str | None, args: dict, message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        self.processor = None
        self.memory_handler = None

    async def execute(self, **kwargs) -> Response:
        """Execute RAG-Anything tool based on the method specified"""
        
        # Initialize processor and memory handler
        if not self.processor:
            progress_callback = lambda msg: self.log.update(progress=f"\n{msg}")
            self.processor = RAGAnythingProcessor(self.agent, progress_callback)
            self.memory_handler = RAGAnythingMemory(self.agent)

        try:
            # Validate model setup
            is_valid, issues = validate_model_setup(self.agent)
            if not is_valid:
                return Response(
                    message=f"Model setup issues detected:\n" + "\n".join(f"- {issue}" for issue in issues),
                    break_loop=False
                )

            # Route to appropriate method
            if self.method == "process" or not self.method:
                return await self._process_document()
            elif self.method == "query":
                return await self._query_content()
            elif self.method == "status":
                return await self._get_status()
            elif self.method == "batch":
                return await self._batch_process()
            elif self.method == "delete":
                return await self._delete_content()
            else:
                return Response(
                    message=f"Unknown method '{self.method}'. Available methods: process, query, status, batch, delete",
                    break_loop=False
                )

        except Exception as e:
            error_msg = f"Error in RAG-Anything tool: {e}"
            PrintStyle(font_color="red", padding=True).print(error_msg)
            return Response(message=error_msg, break_loop=False)

    async def _process_document(self) -> Response:
        """Process a document using RAG-Anything"""
        
        # Get required document path
        document_path = self.args.get("document_path") or self.args.get("document") or self.args.get("path")
        if not document_path:
            return Response(
                message="Error: document_path is required for processing",
                break_loop=False
            )

        # Validate document exists
        if not os.path.exists(document_path):
            return Response(
                message=f"Error: Document not found at path: {document_path}",
                break_loop=False
            )

        # Get processing options
        extract_images = self.args.get("extract_images", True)
        extract_tables = self.args.get("extract_tables", True)  
        extract_equations = self.args.get("extract_equations", True)
        store_in_memory = self.args.get("store_in_memory", True)

        # Convert string boolean values
        if isinstance(extract_images, str):
            extract_images = extract_images.lower() in ('true', '1', 'yes', 'on')
        if isinstance(extract_tables, str):
            extract_tables = extract_tables.lower() in ('true', '1', 'yes', 'on')
        if isinstance(extract_equations, str):
            extract_equations = extract_equations.lower() in ('true', '1', 'yes', 'on')
        if isinstance(store_in_memory, str):
            store_in_memory = store_in_memory.lower() in ('true', '1', 'yes', 'on')

        # Process document
        result = await self.processor.process_document(
            document_path=document_path,
            extract_images=extract_images,
            extract_tables=extract_tables,
            extract_equations=extract_equations,
            store_in_memory=store_in_memory
        )

        if "error" in result:
            return Response(message=result["error"], break_loop=False)

        # Format response
        response_parts = [
            f"Document processed successfully: {document_path}",
            f"Content extracted: {result.get('content_summary', {})}"
        ]

        if store_in_memory and "stored_count" in result:
            response_parts.append(f"Stored {result['stored_count']} items in memory")

        if "extracted_content" in result:
            content = result["extracted_content"]
            if "text" in content:
                response_parts.append(f"Text content preview: {content['text'][:200]}...")
            
            for content_type in ["images", "tables", "equations"]:
                if content_type in content and content[content_type]:
                    count = len(content[content_type])
                    response_parts.append(f"Found {count} {content_type}")

        return Response(message="\n".join(response_parts), break_loop=False)

    async def _query_content(self) -> Response:
        """Query processed content using semantic search"""
        
        # Get required query
        query = self.args.get("query")
        if not query:
            return Response(
                message="Error: query is required for searching content",
                break_loop=False
            )

        # Get optional parameters
        document_path = self.args.get("document_path") or self.args.get("document")
        content_types_str = self.args.get("content_types", "")
        limit = int(self.args.get("limit", 10))

        # Parse content types
        content_types = None
        if content_types_str:
            content_types = [ct.strip() for ct in content_types_str.split(",")]

        # Perform query
        result = await self.processor.query_document(
            query=query,
            document_path=document_path,
            content_types=content_types,
            limit=limit
        )

        if "error" in result:
            return Response(message=result["error"], break_loop=False)

        # Format response
        results_count = result.get("results_count", 0)
        if results_count == 0:
            return Response(
                message=f"No results found for query: {query}",
                break_loop=False
            )

        response_parts = [
            f"Found {results_count} results for query: {query}",
            ""
        ]

        for i, item in enumerate(result.get("results", [])[:5], 1):  # Show top 5
            content_type = item.get("content_type", "unknown")
            document = item.get("document_path", "unknown")
            content = item.get("content", "")[:300]  # Truncate content
            
            response_parts.append(f"{i}. [{content_type}] from {Path(document).name}")
            response_parts.append(f"   {content}...")
            response_parts.append("")

        if results_count > 5:
            response_parts.append(f"... and {results_count - 5} more results")

        return Response(message="\n".join(response_parts), break_loop=False)

    async def _get_status(self) -> Response:
        """Get RAG-Anything system status and statistics"""
        
        try:
            # Get processing statistics
            stats = await self.processor.get_processing_statistics()
            
            # Validate model setup
            is_valid, issues = validate_model_setup(self.agent)
            
            # Format response
            response_parts = [
                "RAG-Anything System Status:",
                "",
                f"Model setup: {'✓ Valid' if is_valid else '⚠ Issues detected'}",
            ]
            
            if issues:
                response_parts.append("Issues:")
                for issue in issues:
                    response_parts.append(f"  - {issue}")
                response_parts.append("")
            
            response_parts.extend([
                "Content Statistics:",
                f"  Total items: {stats.get('total_items', 0)}",
                f"  Unique documents: {stats.get('unique_documents', 0)}",
                ""
            ])
            
            content_types = stats.get('content_types', {})
            if content_types:
                response_parts.append("Content by type:")
                for content_type, count in content_types.items():
                    response_parts.append(f"  {content_type}: {count}")
                response_parts.append("")
            
            documents = stats.get('documents', [])
            if documents:
                response_parts.append("Processed documents:")
                for doc in documents[:10]:  # Show first 10
                    response_parts.append(f"  - {Path(doc).name}")
                if len(documents) > 10:
                    response_parts.append(f"  ... and {len(documents) - 10} more")

            return Response(message="\n".join(response_parts), break_loop=False)

        except Exception as e:
            return Response(message=f"Error getting status: {e}", break_loop=False)

    async def _batch_process(self) -> Response:
        """Process multiple documents in batch"""
        
        # Get document paths
        documents_str = self.args.get("documents") or self.args.get("document_paths")
        if not documents_str:
            return Response(
                message="Error: documents parameter is required for batch processing (comma-separated paths)",
                break_loop=False
            )

        # Parse document paths
        document_paths = [path.strip() for path in documents_str.split(",")]
        
        # Validate paths exist
        valid_paths = []
        invalid_paths = []
        for path in document_paths:
            if os.path.exists(path):
                valid_paths.append(path)
            else:
                invalid_paths.append(path)

        if invalid_paths:
            return Response(
                message=f"Error: These document paths do not exist:\n" + "\n".join(f"- {path}" for path in invalid_paths),
                break_loop=False
            )

        # Get processing options
        processing_options = {
            "extract_images": self.args.get("extract_images", True),
            "extract_tables": self.args.get("extract_tables", True),
            "extract_equations": self.args.get("extract_equations", True),
            "store_in_memory": self.args.get("store_in_memory", True)
        }

        # Convert string boolean values
        for key, value in processing_options.items():
            if isinstance(value, str):
                processing_options[key] = value.lower() in ('true', '1', 'yes', 'on')

        # Process documents
        result = await self.processor.batch_process_documents(
            document_paths=valid_paths,
            **processing_options
        )

        # Format response
        total = result.get("total_documents", 0)
        successful = result.get("successful", 0)
        failed = result.get("failed", 0)

        response_parts = [
            f"Batch processing completed:",
            f"  Total documents: {total}",
            f"  Successful: {successful}",
            f"  Failed: {failed}",
            ""
        ]

        if failed > 0:
            response_parts.append("Failed documents:")
            errors = result.get("errors", {})
            for doc_path, error in errors.items():
                response_parts.append(f"  - {Path(doc_path).name}: {error}")
            response_parts.append("")

        if successful > 0:
            response_parts.append("Successfully processed:")
            results = result.get("results", {})
            for doc_path in results.keys():
                response_parts.append(f"  - {Path(doc_path).name}")

        return Response(message="\n".join(response_parts), break_loop=False)

    async def _delete_content(self) -> Response:
        """Delete processed content for a document"""
        
        document_path = self.args.get("document_path") or self.args.get("document")
        if not document_path:
            return Response(
                message="Error: document_path is required for deletion",
                break_loop=False
            )

        # Delete content
        deleted_count = await self.memory_handler.delete_document_content(document_path)

        return Response(
            message=f"Deleted {deleted_count} items for document: {document_path}",
            break_loop=False
        )