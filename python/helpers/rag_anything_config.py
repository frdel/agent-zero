import os
import json
import tempfile
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

from agent import Agent
from python.helpers.print_style import PrintStyle
from python.helpers import files


class RAGAnythingConfig:
    """
    Configuration management for RAG-Anything integration
    Handles validation, initialization, and environment setup
    """
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self._config_cache = None
    
    def get_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Get RAG-Anything configuration with validation
        
        Args:
            force_reload: Force reload from settings
            
        Returns:
            Configuration dictionary
        """
        if self._config_cache is None or force_reload:
            self._config_cache = self._load_and_validate_config()
        
        return self._config_cache
    
    def _load_and_validate_config(self) -> Dict[str, Any]:
        """Load and validate RAG-Anything configuration"""
        try:
            from python.helpers.settings import get_settings
            settings = get_settings()
            
            # Extract RAG-Anything settings
            config = {
                "enabled": settings.get("rag_anything_enabled", False),
                "working_dir": settings.get("rag_anything_working_dir", ""),
                "image_processing": settings.get("rag_anything_image_processing", True),
                "table_processing": settings.get("rag_anything_table_processing", True),
                "equation_processing": settings.get("rag_anything_equation_processing", True),
                "context_window": settings.get("rag_anything_context_window", 2000),
                "batch_size": settings.get("rag_anything_batch_size", 10),
                "mineru_config_path": settings.get("mineru_config_path", "")
            }
            
            # Validate and normalize configuration
            config = self._validate_config(config)
            
            return config
            
        except Exception as e:
            PrintStyle(font_color="red", padding=True).print(f"Error loading RAG-Anything config: {e}")
            return self._get_default_config()
    
    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize configuration values"""
        
        # Ensure working directory is set
        if not config["working_dir"]:
            config["working_dir"] = tempfile.mkdtemp(prefix="rag_anything_")
        
        # Ensure working directory exists
        working_dir = config["working_dir"]
        if not os.path.exists(working_dir):
            try:
                os.makedirs(working_dir, exist_ok=True)
            except Exception as e:
                PrintStyle(font_color="orange", padding=True).print(
                    f"Cannot create working directory {working_dir}: {e}"
                )
                # Fallback to temp directory
                config["working_dir"] = tempfile.mkdtemp(prefix="rag_anything_fallback_")
        
        # Validate numeric values
        config["context_window"] = max(500, min(10000, config["context_window"]))
        config["batch_size"] = max(1, min(100, config["batch_size"]))
        
        # Validate MinerU config path if provided
        mineru_config = config["mineru_config_path"]
        if mineru_config and not os.path.exists(mineru_config):
            PrintStyle(font_color="orange", padding=True).print(
                f"MinerU config file not found: {mineru_config}"
            )
            config["mineru_config_path"] = ""
        
        return config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration when settings are unavailable"""
        return {
            "enabled": False,
            "working_dir": tempfile.mkdtemp(prefix="rag_anything_default_"),
            "image_processing": True,
            "table_processing": True,
            "equation_processing": True,
            "context_window": 2000,
            "batch_size": 10,
            "mineru_config_path": ""
        }
    
    def is_enabled(self) -> bool:
        """Check if RAG-Anything is enabled"""
        return self.get_config().get("enabled", False)
    
    def validate_dependencies(self) -> Tuple[bool, list]:
        """
        Validate that required dependencies are available
        
        Returns:
            Tuple of (is_valid, list_of_missing_dependencies)
        """
        missing_deps = []
        
        # Check for core Python packages
        required_packages = [
            "tempfile",
            "pathlib", 
            "json",
            "base64"
        ]
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_deps.append(f"Python package: {package}")
        
        # Check for optional but recommended packages
        optional_packages = [
            ("PIL", "Pillow - for advanced image processing"),
            ("cv2", "OpenCV - for computer vision tasks"),
            ("numpy", "NumPy - for numerical operations"),
            ("pandas", "Pandas - for table processing")
        ]
        
        for package, description in optional_packages:
            try:
                __import__(package)
            except ImportError:
                # Optional packages are warnings, not failures
                PrintStyle(font_color="orange", padding=False).print(
                    f"Optional dependency missing: {description}"
                )
        
        # Check system dependencies
        system_deps = self._check_system_dependencies()
        missing_deps.extend(system_deps)
        
        return len(missing_deps) == 0, missing_deps
    
    def _check_system_dependencies(self) -> list:
        """Check for system-level dependencies"""
        missing = []
        
        # Check for LibreOffice (for document conversion)
        libreoffice_paths = [
            "/usr/bin/libreoffice",
            "/usr/local/bin/libreoffice", 
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "C:\\Program Files\\LibreOffice\\program\\soffice.exe"
        ]
        
        libreoffice_found = any(os.path.exists(path) for path in libreoffice_paths)
        if not libreoffice_found:
            missing.append("LibreOffice - for document conversion")
        
        return missing
    
    def get_model_functions(self) -> Dict[str, Any]:
        """Get model functions for RAG-Anything initialization"""
        from python.helpers.rag_anything_models import RAGAnythingModelAdapter
        
        adapter = RAGAnythingModelAdapter(self.agent)
        return adapter.get_model_functions()
    
    def create_rag_anything_config(self) -> Dict[str, Any]:
        """
        Create configuration dictionary for RAG-Anything initialization
        
        Returns:
            Configuration suitable for RAG-Anything constructor
        """
        config = self.get_config()
        
        return {
            "working_dir": config["working_dir"],
            "image_processing": config["image_processing"],
            "table_processing": config["table_processing"],
            "equation_processing": config["equation_processing"],
            "context_window": config["context_window"],
            "batch_size": config["batch_size"],
            "mineru_config": config["mineru_config_path"] if config["mineru_config_path"] else None
        }
    
    def get_processing_options(self, user_overrides: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get processing options with optional user overrides
        
        Args:
            user_overrides: User-specified options to override defaults
            
        Returns:
            Processing options dictionary
        """
        config = self.get_config()
        
        options = {
            "extract_images": config["image_processing"],
            "extract_tables": config["table_processing"],
            "extract_equations": config["equation_processing"],
            "store_in_memory": True,  # Default to storing in memory
            "context_window": config["context_window"],
            "batch_size": config["batch_size"]
        }
        
        if user_overrides:
            options.update(user_overrides)
        
        return options
    
    def validate_document_path(self, document_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a document path for processing
        
        Args:
            document_path: Path to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not document_path:
            return False, "Document path is required"
        
        if not os.path.exists(document_path):
            return False, f"Document not found: {document_path}"
        
        if not os.path.isfile(document_path):
            return False, f"Path is not a file: {document_path}"
        
        # Check file extension
        allowed_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.md',
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff',
            '.html', '.htm', '.xml', '.json'
        }
        
        file_ext = Path(document_path).suffix.lower()
        if file_ext not in allowed_extensions:
            return False, f"Unsupported file type: {file_ext}"
        
        # Check file size (reasonable limit)
        try:
            file_size = os.path.getsize(document_path)
            max_size = 100 * 1024 * 1024  # 100 MB
            if file_size > max_size:
                return False, f"File too large: {file_size / 1024 / 1024:.1f} MB (max: {max_size / 1024 / 1024} MB)"
        except OSError as e:
            return False, f"Cannot access file: {e}"
        
        return True, None
    
    def get_status_info(self) -> Dict[str, Any]:
        """
        Get comprehensive status information about RAG-Anything configuration
        
        Returns:
            Status information dictionary
        """
        config = self.get_config()
        is_valid_deps, missing_deps = self.validate_dependencies()
        
        from python.helpers.rag_anything_models import validate_model_setup
        is_valid_models, model_issues = validate_model_setup(self.agent)
        
        return {
            "enabled": config["enabled"],
            "config": config,
            "dependencies_valid": is_valid_deps,
            "missing_dependencies": missing_deps,
            "models_valid": is_valid_models,
            "model_issues": model_issues,
            "working_directory": config["working_dir"],
            "working_directory_exists": os.path.exists(config["working_dir"]),
            "processing_capabilities": {
                "images": config["image_processing"],
                "tables": config["table_processing"],
                "equations": config["equation_processing"]
            }
        }