from typing import Any
from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
from agent import Agent, LoopData


class RAGAnythingCleanup(Extension):
    """
    Clean up RAG-Anything resources at the end of agent monologue
    This extension handles resource cleanup and temporary file removal
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        # Check if RAG-Anything was initialized
        if not self.agent.get_data("rag_anything_initialized"):
            return  # RAG-Anything not initialized, skip cleanup
        
        try:
            await self._cleanup_rag_anything_resources()
            
        except Exception as e:
            # Log cleanup errors but don't fail
            PrintStyle(font_color="orange", padding=True).print(f"RAG-Anything cleanup warning: {e}")
            self.agent.context.log.log(
                type="warning",
                content=f"RAG-Anything cleanup warning: {e}"
            )

    async def _cleanup_rag_anything_resources(self):
        """Clean up RAG-Anything resources"""
        
        # Clear temporary data from agent
        temp_data_keys = [
            "rag_anything_context_hint",
            "rag_anything_tool_used", 
            "rag_anything_last_results"
        ]
        
        for key in temp_data_keys:
            if self.agent.get_data(key) is not None:
                self.agent.set_data(key, None)
        
        # Optional: Clean up temporary files if needed
        # This would be implemented based on the actual RAG-Anything library's cleanup requirements
        await self._cleanup_temporary_files()

    async def _cleanup_temporary_files(self):
        """Clean up any temporary files created during processing"""
        import os
        import tempfile
        import shutil
        
        # Get working directory from settings
        settings = self.agent.get_data("rag_anything_settings") or {}
        working_dir = settings.get("rag_anything_working_dir", "")
        
        # Only clean up if using a temporary directory (not user-specified)
        if not working_dir or working_dir.startswith(tempfile.gettempdir()):
            try:
                # Clean up old temporary files (keep recent ones)
                # This is a conservative approach - only clean files older than 1 hour
                import time
                current_time = time.time()
                one_hour_ago = current_time - 3600
                
                if working_dir and os.path.exists(working_dir):
                    for filename in os.listdir(working_dir):
                        file_path = os.path.join(working_dir, filename)
                        if os.path.isfile(file_path):
                            file_mtime = os.path.getmtime(file_path)
                            if file_mtime < one_hour_ago:
                                try:
                                    os.remove(file_path)
                                except OSError:
                                    pass  # File might be in use, skip
                                    
            except Exception:
                # Ignore cleanup errors - they're not critical
                pass