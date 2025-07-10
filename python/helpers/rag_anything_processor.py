import os
import json
import asyncio
import tempfile
import base64
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

from agent import Agent
from python.helpers.print_style import PrintStyle
from python.helpers.rag_anything_memory import RAGAnythingMemory
from python.helpers.rag_anything_models import RAGAnythingModelAdapter


class RAGAnythingProcessor:
    """
    Document processing pipeline that integrates RAG-Anything's multimodal capabilities
    with Agent Zero's memory and model systems
    """
    
    def __init__(self, agent: Agent, progress_callback: Optional[Callable] = None):
        self.agent = agent
        self.progress_callback = progress_callback or (lambda x: None)
        self.memory_handler = RAGAnythingMemory(agent)
        self.model_adapter = RAGAnythingModelAdapter(agent)
        self.working_dir = None
        self.rag_anything = None
    
    def _report_progress(self, message: str):
        """Report progress to callback and log"""
        self.progress_callback(message)
        PrintStyle(font_color="#85C1E9", padding=False).print(f"RAG-Anything: {message}")
    
    async def initialize_rag_anything(self, config: Dict[str, Any] = None) -> bool:
        """
        Initialize RAG-Anything with Agent Zero's model functions
        
        Args:
            config: Optional configuration override
            
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Import RAG-Anything (this will be installed via requirements)
            try:
                from rag_anything import RAGAnything
            except ImportError:
                self._report_progress("RAG-Anything package not found. Please install rag-anything.")
                return False
            
            self._report_progress("Initializing RAG-Anything...")
            
            # Get model functions from adapter
            model_functions = self.model_adapter.get_model_functions()
            
            # Set up working directory
            if not self.working_dir:
                settings = self._get_rag_anything_settings()
                self.working_dir = settings.get("working_dir", tempfile.mkdtemp(prefix="rag_anything_"))
                os.makedirs(self.working_dir, exist_ok=True)
            
            # Default configuration
            default_config = {
                "working_dir": self.working_dir,
                "image_processing": True,
                "table_processing": True,
                "equation_processing": True,
                "context_window": 2000,
                "batch_size": 10,
                "mineru_config": None
            }
            
            # Override with provided config
            if config:
                default_config.update(config)
            
            # Initialize RAG-Anything
            self.rag_anything = RAGAnything(
                llm_model_func=model_functions["llm_model_func"],
                vision_model_func=model_functions["vision_model_func"],
                embedding_func=model_functions["embedding_func"],
                working_dir=self.working_dir,
                **default_config
            )
            
            self._report_progress("RAG-Anything initialized successfully")
            return True
            
        except Exception as e:
            self._report_progress(f"Failed to initialize RAG-Anything: {e}")
            PrintStyle(font_color="red", padding=True).print(f"RAG-Anything initialization error: {e}")
            return False
    
    async def process_document(
        self,
        document_path: str,
        extract_images: bool = True,
        extract_tables: bool = True,
        extract_equations: bool = True,
        store_in_memory: bool = True
    ) -> Dict[str, Any]:
        """
        Process a document using RAG-Anything and optionally store in memory
        
        Args:
            document_path: Path to the document to process
            extract_images: Whether to extract and process images
            extract_tables: Whether to extract and process tables
            extract_equations: Whether to extract and process equations
            store_in_memory: Whether to store results in Agent Zero's memory
            
        Returns:
            Dictionary containing processed content and metadata
        """
        if not self.rag_anything:
            if not await self.initialize_rag_anything():
                return {"error": "Failed to initialize RAG-Anything"}
        
        try:
            self._report_progress(f"Processing document: {document_path}")
            
            # Validate document exists
            if not os.path.exists(document_path):
                return {"error": f"Document not found: {document_path}"}
            
            # Process document with RAG-Anything
            processing_options = {
                "extract_images": extract_images,
                "extract_tables": extract_tables,
                "extract_equations": extract_equations
            }
            
            self._report_progress("Extracting multimodal content...")
            
            # Use actual RAG-Anything processing
            extracted_content = await self._process_with_rag_anything(
                document_path, processing_options
            )
            
            # Prepare results
            results = {
                "document_path": document_path,
                "processed_at": str(asyncio.get_event_loop().time()),
                "processing_options": processing_options,
                "extracted_content": extracted_content,
                "content_summary": self._generate_content_summary(extracted_content)
            }
            
            # Store in memory if requested
            if store_in_memory and extracted_content:
                self._report_progress("Storing content in memory...")
                stored_ids = await self.memory_handler.store_document_content(
                    document_path=document_path,
                    extracted_content=extracted_content,
                    processing_metadata={
                        "processing_options": processing_options,
                        "processed_at": results["processed_at"]
                    }
                )
                results["stored_ids"] = stored_ids
                results["stored_count"] = len(stored_ids)
            
            self._report_progress(f"Document processing completed: {len(extracted_content)} content types extracted")
            return results
            
        except Exception as e:
            error_msg = f"Error processing document {document_path}: {e}"
            self._report_progress(error_msg)
            PrintStyle(font_color="red", padding=True).print(error_msg)
            return {"error": error_msg}
    
    async def query_document(
        self,
        query: str,
        document_path: str = None,
        content_types: List[str] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Query processed document content using semantic search
        
        Args:
            query: Search query
            document_path: Optional specific document to search
            content_types: Optional filter by content types
            limit: Maximum number of results
            
        Returns:
            Dictionary containing search results
        """
        try:
            self._report_progress(f"Searching for: {query}")
            
            # Search in memory
            if document_path:
                # Search specific document
                all_content = await self.memory_handler.get_content_by_document(document_path)
                # Filter by content types if specified
                if content_types:
                    filtered_content = [
                        doc for doc in all_content 
                        if doc.metadata.get('content_type') in content_types
                    ]
                else:
                    filtered_content = all_content
                
                # Rank by relevance (simplified - would use proper similarity in production)
                results = filtered_content[:limit]
            else:
                # Search across all content
                results = await self.memory_handler.search_multimodal_content(
                    query=query,
                    content_types=content_types,
                    limit=limit
                )
            
            # Format results
            formatted_results = []
            for doc in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "content_type": doc.metadata.get('content_type', 'unknown'),
                    "document_path": doc.metadata.get('document_path', ''),
                    "timestamp": doc.metadata.get('timestamp', '')
                })
            
            return {
                "query": query,
                "results_count": len(formatted_results),
                "results": formatted_results
            }
            
        except Exception as e:
            error_msg = f"Error querying content: {e}"
            self._report_progress(error_msg)
            return {"error": error_msg}
    
    async def batch_process_documents(
        self,
        document_paths: List[str],
        **processing_options
    ) -> Dict[str, Any]:
        """
        Process multiple documents in batch
        
        Args:
            document_paths: List of document paths to process
            **processing_options: Options passed to process_document
            
        Returns:
            Dictionary containing batch processing results
        """
        self._report_progress(f"Starting batch processing of {len(document_paths)} documents")
        
        results = {
            "total_documents": len(document_paths),
            "successful": 0,
            "failed": 0,
            "results": {},
            "errors": {}
        }
        
        for i, doc_path in enumerate(document_paths):
            self._report_progress(f"Processing document {i+1}/{len(document_paths)}: {doc_path}")
            
            try:
                result = await self.process_document(doc_path, **processing_options)
                
                if "error" in result:
                    results["failed"] += 1
                    results["errors"][doc_path] = result["error"]
                else:
                    results["successful"] += 1
                    results["results"][doc_path] = result
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"][doc_path] = str(e)
        
        self._report_progress(f"Batch processing completed: {results['successful']} successful, {results['failed']} failed")
        return results
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about processed content
        """
        return await self.memory_handler.get_content_statistics()
    
    def _get_rag_anything_settings(self) -> Dict[str, Any]:
        """Get RAG-Anything settings from Agent Zero configuration"""
        try:
            from python.helpers.settings import get_settings
            settings = get_settings()
            
            return {
                "working_dir": settings.get("rag_anything_working_dir", "") or tempfile.mkdtemp(prefix="rag_anything_"),
                "image_processing": settings.get("rag_anything_image_processing", True),
                "table_processing": settings.get("rag_anything_table_processing", True),
                "equation_processing": settings.get("rag_anything_equation_processing", True),
                "context_window": settings.get("rag_anything_context_window", 2000),
                "batch_size": settings.get("rag_anything_batch_size", 10),
                "mineru_config_path": settings.get("mineru_config_path", "")
            }
        except Exception as e:
            self._report_progress(f"Warning: Could not load settings, using defaults: {e}")
            return {
                "working_dir": tempfile.mkdtemp(prefix="rag_anything_"),
                "image_processing": True,
                "table_processing": True,
                "equation_processing": True,
                "context_window": 2000,
                "batch_size": 10,
                "mineru_config_path": ""
            }
    
    async def _process_with_rag_anything(
        self,
        document_path: str,
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process document using actual RAG-Anything library
        """
        try:
            # Process the document with RAG-Anything
            processing_result = await self.rag_anything.process_document(
                document_path=document_path,
                extract_images=options.get("extract_images", True),
                extract_tables=options.get("extract_tables", True),
                extract_equations=options.get("extract_equations", True)
            )
            
            # Structure the results according to our expected format
            extracted_content = {}
            
            # Extract text content
            if "text" in processing_result:
                extracted_content["text"] = processing_result["text"]
            
            # Extract images with context
            if "images" in processing_result and options.get("extract_images", True):
                extracted_content["images"] = []
                for img in processing_result["images"]:
                    extracted_content["images"].append({
                        "content": img.get("content", ""),
                        "description": img.get("description", ""),
                        "context": img.get("context", ""),
                        "bbox": img.get("bbox", {}),
                        "page_number": img.get("page_number", 0)
                    })
            
            # Extract tables with context
            if "tables" in processing_result and options.get("extract_tables", True):
                extracted_content["tables"] = []
                for table in processing_result["tables"]:
                    extracted_content["tables"].append({
                        "content": table.get("content", ""),
                        "description": table.get("description", ""),
                        "context": table.get("context", ""),
                        "bbox": table.get("bbox", {}),
                        "page_number": table.get("page_number", 0)
                    })
            
            # Extract equations with context
            if "equations" in processing_result and options.get("extract_equations", True):
                extracted_content["equations"] = []
                for eq in processing_result["equations"]:
                    extracted_content["equations"].append({
                        "content": eq.get("content", ""),
                        "description": eq.get("description", ""),
                        "context": eq.get("context", ""),
                        "bbox": eq.get("bbox", {}),
                        "page_number": eq.get("page_number", 0)
                    })
            
            return extracted_content
            
        except Exception as e:
            self._report_progress(f"Error in RAG-Anything processing: {e}")
            # Fallback to basic text extraction if RAG-Anything fails
            return {"text": f"Error processing {document_path}: {e}"}
    
    def _generate_content_summary(self, extracted_content: Dict[str, Any]) -> Dict[str, int]:
        """Generate a summary of extracted content counts"""
        summary = {}
        
        for content_type, content_data in extracted_content.items():
            if isinstance(content_data, list):
                summary[content_type] = len(content_data)
            elif isinstance(content_data, str):
                summary[content_type] = 1
            else:
                summary[content_type] = 0
        
        return summary