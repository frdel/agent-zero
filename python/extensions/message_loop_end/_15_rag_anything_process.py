from typing import Any
from python.helpers.extension import Extension
from agent import Agent, LoopData


class RAGAnythingProcess(Extension):
    """
    Process and store multimodal content at the end of message loop
    This extension runs after tools have been executed
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        # Check if RAG-Anything is initialized and enabled
        if not self.agent.get_data("rag_anything_initialized"):
            return  # RAG-Anything not initialized, skip
        
        try:
            # Check if RAG-Anything tool was used in this iteration
            rag_anything_used = self.agent.get_data("rag_anything_tool_used")
            
            if rag_anything_used:
                await self._post_process_rag_anything()
                # Reset the flag
                self.agent.set_data("rag_anything_tool_used", False)
            
        except Exception as e:
            # Log error but don't fail the message loop
            self.agent.context.log.log(
                type="warning",
                content=f"RAG-Anything post-processing warning: {e}"
            )

    async def _post_process_rag_anything(self):
        """Perform post-processing after RAG-Anything tool usage"""
        
        # Get processing results if available
        processing_results = self.agent.get_data("rag_anything_last_results")
        
        if processing_results:
            # Log successful processing
            self.agent.context.log.log(
                type="info",
                content=f"RAG-Anything processing completed: {processing_results.get('summary', 'Content processed')}"
            )
            
            # Clear the results to prevent memory buildup
            self.agent.set_data("rag_anything_last_results", None)
        
        # Cleanup any temporary context hints
        self.agent.set_data("rag_anything_context_hint", False)