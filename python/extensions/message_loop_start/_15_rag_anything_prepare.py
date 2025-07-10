from typing import Any
from python.helpers.extension import Extension
from agent import Agent, LoopData


class RAGAnythingPrepare(Extension):
    """
    Prepare RAG-Anything for message processing
    This extension runs at the start of each message loop iteration
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        # Check if RAG-Anything is initialized and enabled
        if not self.agent.get_data("rag_anything_initialized"):
            return  # RAG-Anything not initialized, skip
        
        try:
            # Prepare RAG-Anything context for this message loop iteration
            await self._prepare_context(loop_data)
            
        except Exception as e:
            # Log error but don't fail the message loop
            self.agent.context.log.log(
                type="warning",
                content=f"RAG-Anything preparation warning: {e}"
            )

    async def _prepare_context(self, loop_data: LoopData):
        """Prepare RAG-Anything context for message processing"""
        
        # Check if user message contains document attachments or references
        user_message = loop_data.user_message
        if user_message and hasattr(user_message, 'content'):
            message_content = str(user_message.content)
            
            # Look for document-related keywords or file paths
            document_indicators = [
                'document', 'file', 'pdf', 'image', 'table', 'equation',
                '.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg'
            ]
            
            has_document_context = any(
                indicator in message_content.lower() 
                for indicator in document_indicators
            )
            
            if has_document_context:
                # Store hint that this message might benefit from RAG-Anything
                self.agent.set_data("rag_anything_context_hint", True)
                
                # Add helpful context to loop data extras
                if not loop_data.extras_temporary:
                    loop_data.extras_temporary = {}
                
                loop_data.extras_temporary["rag_anything_hint"] = (
                    "Consider using the rag_anything tool for advanced document processing "
                    "if working with images, tables, equations, or complex document analysis."
                )
            else:
                self.agent.set_data("rag_anything_context_hint", False)