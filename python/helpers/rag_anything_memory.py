import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
from langchain_core.documents import Document

from agent import Agent
from python.helpers.memory import Memory
from python.helpers.print_style import PrintStyle


class RAGAnythingMemory:
    """
    Extended memory system supporting RAG-Anything multimodal content
    Handles storage and retrieval of images, tables, equations with context
    """
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.memory = None
        self.rag_anything_area = Memory.Area.RAG_ANYTHING.value
    
    async def initialize(self):
        """Initialize the memory system"""
        if not self.memory:
            self.memory = await Memory.get(self.agent)
    
    async def store_multimodal_content(
        self,
        content_type: str,
        content_data: str,
        metadata: Dict[str, Any],
        surrounding_context: str = "",
        document_path: str = ""
    ) -> str:
        """
        Store multimodal content with appropriate metadata
        
        Args:
            content_type: Type of content ('image', 'table', 'equation', 'text')
            content_data: The actual content (base64 for images, markdown for tables, etc.)
            metadata: Additional metadata about the content
            surrounding_context: Text context around the multimodal content
            document_path: Path to the source document
            
        Returns:
            The ID of the stored content
        """
        await self.initialize()
        
        # Prepare document content
        full_content = f"Content Type: {content_type}\n"
        if surrounding_context:
            full_content += f"Context: {surrounding_context}\n"
        full_content += f"Content: {content_data}"
        
        # Prepare metadata
        enhanced_metadata = {
            "content_type": content_type,
            "document_path": document_path,
            "area": self.rag_anything_area,
            "timestamp": datetime.now().isoformat(),
            **metadata
        }
        
        # Create document
        doc = Document(
            page_content=full_content,
            metadata=enhanced_metadata
        )
        
        # Store document
        doc_ids = await self.memory.insert_documents([doc])
        return doc_ids[0]
    
    async def store_document_content(
        self,
        document_path: str,
        extracted_content: Dict[str, Any],
        processing_metadata: Dict[str, Any] = None
    ) -> List[str]:
        """
        Store processed document content from RAG-Anything
        
        Args:
            document_path: Path to the processed document
            extracted_content: Content extracted by RAG-Anything
            processing_metadata: Metadata about the processing
            
        Returns:
            List of document IDs that were stored
        """
        await self.initialize()
        
        stored_ids = []
        processing_metadata = processing_metadata or {}
        
        # Store text content
        if 'text' in extracted_content:
            text_id = await self.store_multimodal_content(
                content_type="text",
                content_data=extracted_content['text'],
                metadata={
                    "extraction_method": "rag_anything",
                    **processing_metadata
                },
                document_path=document_path
            )
            stored_ids.append(text_id)
        
        # Store images with context
        if 'images' in extracted_content:
            for i, image_data in enumerate(extracted_content['images']):
                image_id = await self.store_multimodal_content(
                    content_type="image",
                    content_data=image_data.get('content', ''),
                    metadata={
                        "image_index": i,
                        "image_description": image_data.get('description', ''),
                        "extraction_method": "rag_anything",
                        **processing_metadata
                    },
                    surrounding_context=image_data.get('context', ''),
                    document_path=document_path
                )
                stored_ids.append(image_id)
        
        # Store tables with context
        if 'tables' in extracted_content:
            for i, table_data in enumerate(extracted_content['tables']):
                table_id = await self.store_multimodal_content(
                    content_type="table",
                    content_data=table_data.get('content', ''),
                    metadata={
                        "table_index": i,
                        "table_description": table_data.get('description', ''),
                        "extraction_method": "rag_anything",
                        **processing_metadata
                    },
                    surrounding_context=table_data.get('context', ''),
                    document_path=document_path
                )
                stored_ids.append(table_id)
        
        # Store equations with context
        if 'equations' in extracted_content:
            for i, equation_data in enumerate(extracted_content['equations']):
                equation_id = await self.store_multimodal_content(
                    content_type="equation",
                    content_data=equation_data.get('content', ''),
                    metadata={
                        "equation_index": i,
                        "equation_description": equation_data.get('description', ''),
                        "extraction_method": "rag_anything",
                        **processing_metadata
                    },
                    surrounding_context=equation_data.get('context', ''),
                    document_path=document_path
                )
                stored_ids.append(equation_id)
        
        return stored_ids
    
    async def search_multimodal_content(
        self,
        query: str,
        content_types: List[str] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Document]:
        """
        Search for multimodal content using similarity search
        
        Args:
            query: Search query
            content_types: Filter by content types ('image', 'table', 'equation', 'text')
            limit: Maximum number of results
            threshold: Similarity threshold
            
        Returns:
            List of matching documents
        """
        await self.initialize()
        
        # Build filter for RAG-Anything content
        filter_conditions = [f"area == '{self.rag_anything_area}'"]
        
        if content_types:
            content_type_filter = " or ".join([f"content_type == '{ct}'" for ct in content_types])
            filter_conditions.append(f"({content_type_filter})")
        
        filter_str = " and ".join(filter_conditions)
        
        # Perform similarity search
        results = await self.memory.search_similarity_threshold(
            query=query,
            limit=limit,
            threshold=threshold,
            filter=filter_str
        )
        
        return results
    
    async def get_content_by_document(self, document_path: str) -> List[Document]:
        """
        Get all stored content for a specific document
        
        Args:
            document_path: Path to the document
            
        Returns:
            List of stored content for the document
        """
        await self.initialize()
        
        filter_str = f"area == '{self.rag_anything_area}' and document_path == '{document_path}'"
        
        # Search with a very broad query to get all content
        results = await self.memory.search_similarity_threshold(
            query="document content",
            limit=1000,  # High limit to get all content
            threshold=0.0,  # Very low threshold to match everything
            filter=filter_str
        )
        
        return results
    
    async def delete_document_content(self, document_path: str) -> int:
        """
        Delete all stored content for a specific document
        
        Args:
            document_path: Path to the document
            
        Returns:
            Number of documents deleted
        """
        await self.initialize()
        
        filter_str = f"area == '{self.rag_anything_area}' and document_path == '{document_path}'"
        
        # Delete documents matching the filter
        removed_docs = await self.memory.delete_documents_by_query(
            query="document content",
            threshold=0.0,  # Very low threshold to match everything with the filter
            filter=filter_str
        )
        
        return len(removed_docs)
    
    async def get_content_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored RAG-Anything content
        
        Returns:
            Dictionary with content statistics
        """
        await self.initialize()
        
        # Get all RAG-Anything content
        all_content = await self.search_multimodal_content(
            query="content",
            limit=10000,
            threshold=0.0
        )
        
        stats = {
            "total_items": len(all_content),
            "content_types": {},
            "documents": set(),
            "extraction_methods": {}
        }
        
        for doc in all_content:
            # Count content types
            content_type = doc.metadata.get('content_type', 'unknown')
            stats["content_types"][content_type] = stats["content_types"].get(content_type, 0) + 1
            
            # Count documents
            doc_path = doc.metadata.get('document_path', '')
            if doc_path:
                stats["documents"].add(doc_path)
            
            # Count extraction methods
            extraction_method = doc.metadata.get('extraction_method', 'unknown')
            stats["extraction_methods"][extraction_method] = stats["extraction_methods"].get(extraction_method, 0) + 1
        
        stats["unique_documents"] = len(stats["documents"])
        stats["documents"] = list(stats["documents"])
        
        return stats