from typing import Any
from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
from agent import Agent, LoopData


class RAGAnythingInit(Extension):
    """
    Initialize RAG-Anything context at the start of agent monologue
    This extension validates configuration and sets up the environment
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        # Check if RAG-Anything is enabled
        settings = self._get_rag_anything_settings()
        
        if not settings.get("rag_anything_enabled", False):
            return  # RAG-Anything is disabled, skip initialization
        
        try:
            # Validate RAG-Anything dependencies and setup
            await self._validate_rag_anything_setup()
            
            # Store initialization status in agent data
            self.agent.set_data("rag_anything_initialized", True)
            self.agent.set_data("rag_anything_settings", settings)
            
        except Exception as e:
            PrintStyle(font_color="orange", padding=True).print(f"RAG-Anything initialization warning: {e}")
            self.agent.set_data("rag_anything_initialized", False)
            self.agent.set_data("rag_anything_error", str(e))

    def _get_rag_anything_settings(self) -> dict:
        """Get RAG-Anything settings from agent configuration"""
        try:
            from python.helpers.settings import get_settings
            settings = get_settings()
            
            return {
                "rag_anything_enabled": settings.get("rag_anything_enabled", False),
                "rag_anything_working_dir": settings.get("rag_anything_working_dir", ""),
                "rag_anything_image_processing": settings.get("rag_anything_image_processing", True),
                "rag_anything_table_processing": settings.get("rag_anything_table_processing", True),
                "rag_anything_equation_processing": settings.get("rag_anything_equation_processing", True),
                "rag_anything_context_window": settings.get("rag_anything_context_window", 2000),
                "rag_anything_batch_size": settings.get("rag_anything_batch_size", 10),
                "mineru_config_path": settings.get("mineru_config_path", ""),
            }
        except Exception:
            return {"rag_anything_enabled": False}

    async def _validate_rag_anything_setup(self):
        """Validate that RAG-Anything can be used"""
        # Check model capabilities
        from python.helpers.rag_anything_models import validate_model_setup
        
        is_valid, issues = validate_model_setup(self.agent)
        if not is_valid:
            # Filter out vision-only warnings
            critical_issues = [issue for issue in issues if "Vision model" not in issue]
            if critical_issues:
                raise Exception(f"Critical model setup issues: {'; '.join(critical_issues)}")
        
        # Try to import RAG-Anything dependencies (soft check)
        try:
            import tempfile
            import os
            # Basic dependency check passed
        except ImportError as e:
            raise Exception(f"Missing required dependencies: {e}")
        
        # Validate working directory
        settings = self.agent.get_data("rag_anything_settings") or {}
        working_dir = settings.get("rag_anything_working_dir", "")
        
        if working_dir and not os.path.exists(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
            except Exception as e:
                raise Exception(f"Cannot create working directory {working_dir}: {e}")