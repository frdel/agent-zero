from datetime import datetime
from typing import Any, List, Optional, Dict
from langchain_core.documents import Document
import uuid
import logging

from python.helpers.print_style import PrintStyle
from python.helpers.log import Log, LogItem
from python.helpers.memory import Memory
from agent import Agent
import models
import asyncio


class Mem0Memory:
    """
    mem0 memory backend implementation that follows the same interface as the existing Memory class
    while providing enhanced memory capabilities including user-specific memory, automatic organization,
    and advanced retrieval features.
    """

    # Static cache for mem0 instances (similar to existing Memory.index)
    index: dict[str, "Mem0Memory"] = {}
    _clients: dict[str, any] = {}  # Store mem0 clients to prevent conflicts

    @staticmethod
    async def get(agent: Agent):
        """Factory method to get or create a mem0 memory instance"""
        memory_subdir = agent.config.memory_subdir or "default"
        
        if Mem0Memory.index.get(memory_subdir) is None:
            log_item = agent.context.log.log(
                type="util",
                heading=f"Initializing mem0 memory backend in '/{memory_subdir}'",
            )
            
            mem0_instance = Mem0Memory(agent, memory_subdir)
            await mem0_instance.initialize(log_item)
            Mem0Memory.index[memory_subdir] = mem0_instance
            
            # Preload knowledge if configured and enabled in settings
            from python.helpers.settings import get_settings
            settings = get_settings()
            
            # Check if knowledge was already preloaded by checking for existing memories
            should_preload = (agent.config.knowledge_subdirs and 
                            settings.get("mem0_preload_knowledge", True))
            
            if should_preload:
                # Quick check if knowledge already exists
                try:
                    existing_memories = await mem0_instance.search_similarity_threshold(
                        "agent", limit=1, threshold=0.1
                    )
                    if existing_memories:
                        PrintStyle.standard("Knowledge already preloaded, skipping...")
                        if log_item:
                            log_item.update(heading="Knowledge already preloaded, skipping...")
                        should_preload = False
                except:
                    # If search fails, assume we need to preload
                    pass
            
            if should_preload:
                try:
                    await mem0_instance.preload_knowledge(
                        log_item, agent.config.knowledge_subdirs, memory_subdir
                    )
                except Exception as e:
                    PrintStyle.error(f"Knowledge preloading failed: {str(e)}")
                    if log_item:
                        log_item.update(heading="Knowledge preloading failed, continuing...")
                
            return mem0_instance
        else:
            return Mem0Memory.index[memory_subdir]

    @staticmethod
    async def reload(agent: Agent):
        """Reload the mem0 memory instance"""
        memory_subdir = agent.config.memory_subdir or "default"
        if Mem0Memory.index.get(memory_subdir):
            del Mem0Memory.index[memory_subdir]
        # Also clear client cache
        Mem0Memory._clients.clear()
        return await Mem0Memory.get(agent)
    
    @staticmethod
    def clear_cache():
        """Clear all cached instances - useful for debugging"""
        Mem0Memory.index.clear()
        Mem0Memory._clients.clear()

    def __init__(self, agent: Agent, memory_subdir: str):
        self.agent = agent
        self.memory_subdir = memory_subdir
        self.mem0_client = None
        self.user_id = self._get_user_id()
        
    async def initialize(self, log_item: LogItem | None = None):
        """Initialize mem0 client and configuration"""
        try:
            from mem0 import Memory as Mem0Client
            import os
            
            # Ensure memory directories exist
            self._ensure_memory_directories()
            
            # Auto-setup Docker services if needed
            await self._ensure_services_running(log_item)
            
            # Ensure API keys are available as environment variables for mem0/litellm
            self._set_environment_api_keys(log_item)
            
            # Get settings and context ID for configuration
            from python.helpers.settings import get_settings
            settings = get_settings()
            
            context_id = getattr(self.agent.context, 'id', 'default')
            safe_context_id = context_id.replace('-', '_')
            
            # Get mem0 configuration from agent settings
            mem0_config = self._get_mem0_config()
            
            # Check if we already have a client for this configuration
            client_key = f"{self.memory_subdir}_{safe_context_id}"
            
            if client_key in Mem0Memory._clients:
                self.mem0_client = Mem0Memory._clients[client_key]
                if log_item:
                    log_item.stream(progress="\nReusing existing mem0 client")
            else:
                # Initialize new mem0 client based on deployment mode
                deployment_mode = settings.get("mem0_deployment", "local")
                
                if deployment_mode == "hosted":
                    # Use MemoryClient for hosted platform
                    from mem0 import MemoryClient
                    self.mem0_client = MemoryClient(**mem0_config)
                else:
                    # Use Memory for local/self-hosted
                    self.mem0_client = Mem0Client(config=mem0_config)
                    
                Mem0Memory._clients[client_key] = self.mem0_client
            
            if log_item:
                log_item.stream(progress="\nmem0ai memory backend initialized")
                
            PrintStyle.standard("mem0ai memory backend initialized")
            
        except ImportError:
            error_msg = "mem0ai package not installed. Install with: pip install mem0ai"
            if log_item:
                log_item.update(heading=f"Error: {error_msg}")
            PrintStyle.error(error_msg)
            raise ImportError(error_msg)
        except Exception as e:
            error_msg = f"Failed to initialize mem0: {str(e)}"
            if log_item:
                log_item.update(heading=f"Error: {error_msg}")
            PrintStyle.error(error_msg)
            # Provide more specific error messages for common issues
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                PrintStyle.error("Check your API keys in settings or environment variables")
            elif "model" in str(e).lower() and "not found" in str(e).lower():
                PrintStyle.error("Check your embedding model configuration in settings")
            elif "provider" in str(e).lower():
                PrintStyle.error("Check your embedding provider configuration in settings")
            raise

    def _get_user_id(self) -> str:
        """Generate a consistent user ID for mem0 based on agent configuration"""
        from python.helpers.settings import get_settings
        settings = get_settings()
        
        strategy = settings.get("mem0_user_id_strategy", "memory_subdir")
        
        try:
            if strategy == "memory_subdir":
                user_id = f"agent_{str(self.memory_subdir)}"
            elif strategy == "session_id":
                context_id = getattr(self.agent.context, 'id', 'default')
                user_id = f"session_{str(context_id)}"
            elif strategy == "agent_id":
                agent_name = getattr(self.agent, 'agent_name', 'default')
                user_id = f"agent_{str(agent_name)}"
            else:
                user_id = f"agent_{str(self.memory_subdir)}"  # fallback
                
            # Clean user_id to ensure it's a valid string
            user_id = str(user_id).strip()
            # Replace any problematic characters with underscores (temporarily simplified)
            # import re
            # user_id = re.sub(r'[^\w\-_]', '_', user_id)
            # Simple character replacement to avoid regex issues
            user_id = ''.join(c if c.isalnum() or c in '-_' else '_' for c in user_id)
            
            PrintStyle.info(f"Generated user_id: {user_id}")
            return user_id
            
        except Exception as e:
            PrintStyle.error(f"Error generating user_id: {e}")
            fallback_id = f"agent_{str(self.memory_subdir) if hasattr(self, 'memory_subdir') else 'default'}"
            # Simple character replacement to avoid regex issues
            return ''.join(c if c.isalnum() or c in '-_' else '_' for c in fallback_id)

    def _get_mem0_config(self):
        """Build mem0 configuration from agent settings"""
        from python.helpers.settings import get_settings
        
        settings = get_settings()
        
        # Check if using hosted platform
        deployment_mode = settings.get("mem0_deployment", "local")
        
        # Deployment mode is being used
        
        if deployment_mode == "hosted":
            return self._get_hosted_config(settings)
        elif deployment_mode == "self_hosted":
            return self._get_self_hosted_config(settings)
        else:
            return self._get_local_config(settings)
    
    def _get_hosted_config(self, settings):
        """Get configuration for mem0 hosted platform"""
        # For hosted platform, we use MemoryClient instead of Memory
        # This avoids all local storage conflicts
        
        # Try to get API key from multiple sources
        api_key = settings.get("mem0_api_key")
        
        # If not in settings, try environment variable
        if not api_key:
            import os
            api_key = os.environ.get("MEM0_API_KEY")
        
        # If still not found, try Agent Zero's get_api_key function
        if not api_key:
            from models import get_api_key
            api_key = get_api_key("mem0")
        
        if not api_key or api_key == "None":
            raise ValueError("mem0_api_key is required for hosted deployment. Please set it in Settings > Agent > mem0 Integration > mem0 API Key")
            
        config = {
            "api_key": api_key,
        }
        
        # Add optional organization and project IDs if provided
        org_id = settings.get("mem0_org_id")
        if org_id:
            config["org_id"] = org_id
            
        project_id = settings.get("mem0_project_id")  
        if project_id:
            config["project_id"] = project_id
        
        return config
    
    def _get_self_hosted_config(self, settings):
        """Get configuration for self-hosted mem0 with remote backends"""
        from mem0.configs.base import MemoryConfig, EmbedderConfig, LlmConfig, VectorStoreConfig
        
        # Use remote vector stores to avoid conflicts
        vector_store_config = settings.get("mem0_vector_store_config", {})
        
        # Default to remote Qdrant server
        if not vector_store_config:
            vector_store_config = {
                "provider": "qdrant",
                "config": {
                    "url": settings.get("mem0_qdrant_url", "http://localhost:6333"),
                    "collection_name": f"agent_zero_{self.memory_subdir}",
                    "api_key": settings.get("mem0_qdrant_api_key")
                }
            }
        
        return self._build_memory_config(settings, vector_store_config)
    
    def _get_local_config(self, settings):
        """Get configuration for local mem0 with fallback to embedded alternatives"""
        # Check if Qdrant service is available
        try:
            from python.helpers.docker_service_manager import docker_service_manager
            service_status = docker_service_manager.get_service_status("mem0_store")
            qdrant_available = service_status.get('running', False)
        except:
            qdrant_available = False
        
        if qdrant_available:
            # Use external Qdrant service
            qdrant_url = settings.get("mem0_qdrant_url", "http://localhost:6333")
            collection_name = settings.get("mem0_qdrant_collection", f"mem0_{self.memory_subdir}")
            
            vector_store_config = {
                "provider": "qdrant",
                "config": {
                    "url": qdrant_url,
                    "collection_name": collection_name,
                    "api_key": settings.get("mem0_qdrant_api_key"),  # Optional
                }
            }
        else:
            # Fallback to embedded alternatives
            PrintStyle.info("Qdrant not available - using embedded memory backend")
            # Use in-memory configuration as fallback - mem0 will handle the absence gracefully
            vector_store_config = {
                "provider": "qdrant", 
                "config": {
                    "collection_name": f"embedded_{self.memory_subdir}_{getattr(self.agent.context, 'id', 'default').replace('-', '_')}",
                    "on_disk": False,  # In-memory fallback
                }
            }
            # Set flag to use embedded alternatives in operations
            self._use_embedded_fallback = True
        
        return self._build_memory_config(settings, vector_store_config)
    
    def _build_memory_config(self, settings, vector_store_config):
        """Build MemoryConfig object from settings and vector store config"""
        from mem0.configs.base import MemoryConfig, EmbedderConfig, LlmConfig, VectorStoreConfig
        
        # Get embedding model configuration with validation
        try:
            embed_model_name = str(self.agent.config.embeddings_model.name).strip()
            if not embed_model_name:
                raise ValueError("Empty embedding model name")
        except Exception as e:
            PrintStyle.error(f"Error getting embedding model name: {e}")
            embed_model_name = "text-embedding-3-small"  # fallback
        
        # Safely get provider name with type checking
        provider_obj = self.agent.config.embeddings_model.provider
        embed_model_provider = 'openai'  # default fallback
        
        try:
            if hasattr(provider_obj, 'name'):
                embed_model_provider = str(provider_obj.name).lower()
            elif hasattr(provider_obj, 'value'):
                # Handle enum types like ModelProvider.OPENAI
                embed_model_provider = str(provider_obj.value).lower()
            elif isinstance(provider_obj, str):
                embed_model_provider = str(provider_obj).lower()
            elif isinstance(provider_obj, dict):
                embed_model_provider = str(provider_obj.get('name', 'openai')).lower()
            else:
                # Handle any other types by converting to string
                embed_model_provider = str(provider_obj).lower()
        except Exception as e:
            PrintStyle.error(f"Error getting embedding provider: {e}, using default 'openai'")
            embed_model_provider = 'openai'
            
        # Debug information
        PrintStyle.info(f"Embedding model: {embed_model_name} (provider: {embed_model_provider})")
        
        # Validate that model name is not empty
        if not embed_model_name:
            raise ValueError("Embedding model name cannot be empty")
            
        # Remove any trailing spaces that might cause issues
        embed_model_name = embed_model_name.rstrip()
        
        # Map Agent Zero embedding providers to mem0 providers
        provider_mapping = {
            "openai": "openai",
            "huggingface": "huggingface", 
            "azure": "azure_openai",
            "anthropic": "openai",  # fallback to openai-compatible
            "google": "openai",     # fallback to openai-compatible
            "gemini": "openai",     # fallback to openai-compatible
            "other": "openai"       # fallback to openai-compatible
        }
        
        mem0_provider = provider_mapping.get(embed_model_provider, "openai")
        
        # Create embedder configuration based on provider
        if mem0_provider == "openai":
            # For OpenAI, let it use the environment variable set by _set_environment_api_keys
            embedder_config = EmbedderConfig(
                provider="openai",
                config={"model": embed_model_name}
            )
        elif mem0_provider == "huggingface":
            # Handle HuggingFace models - use a known working model if the current one is problematic
            hf_model = embed_model_name
            if hf_model.startswith("sentence-transformers/"):
                hf_model = hf_model.replace("sentence-transformers/", "")
            
            embedder_config = EmbedderConfig(
                provider="huggingface",
                config={
                    "model": hf_model
                }
            )
        else:
            # Default to OpenAI-compatible
            embedder_config = EmbedderConfig(
                provider="openai",
                config={
                    "model": embed_model_name
                }
            )
        
        # Create LLM configuration - use litellm to maintain compatibility
        llm_provider = settings.get("mem0_provider", "litellm")
        
        # Get utility model configuration
        util_model_name = self.agent.config.utility_model.name
        util_provider_obj = getattr(self.agent.config.utility_model, 'provider', None)
        
        # Handle provider-specific model naming for litellm
        if util_provider_obj and hasattr(util_provider_obj, 'name'):
            provider_name = str(util_provider_obj.name).lower()
            if provider_name == "openrouter":
                # For OpenRouter, use the model name as-is (litellm handles the routing)
                llm_config_dict = {
                    "model": util_model_name,
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }
            else:
                llm_config_dict = {
                    "model": util_model_name,
                    "temperature": 0.1,
                    "max_tokens": 1000,
                }
        else:
            llm_config_dict = {
                "model": util_model_name,
                "temperature": 0.1,
                "max_tokens": 1000,
            }
        
        # For litellm, let it handle API key management through environment variables
        # API keys are set in _set_environment_api_keys() method
        
        llm_config = LlmConfig(
            provider=llm_provider,
            config=llm_config_dict
        )
        
        # Determine embedding dimensions based on model
        embedding_dims = 384  # default for sentence-transformers
        if mem0_provider == "openai":
            if "3-large" in embed_model_name:
                embedding_dims = 3072
            elif "3-small" in embed_model_name:
                embedding_dims = 1536
            elif "ada-002" in embed_model_name:
                embedding_dims = 1536
            else:
                embedding_dims = 1536  # default for OpenAI models
        
        # Create vector store configuration based on provided config
        context_id = getattr(self.agent.context, 'id', 'default')
        safe_context_id = context_id.replace('-', '_')  # Make filesystem-safe
        
        # Use the provided vector store config directly for self-hosted/remote setups
        if vector_store_config:
            # For remote backends, use the provided configuration as-is
            vector_store_config_obj = VectorStoreConfig(
                provider=vector_store_config.get("provider", "qdrant"),
                config=vector_store_config.get("config", {})
            )
        else:
            # Fallback to in-memory for local setups
            vector_store_base_config = {
                "collection_name": f"mem0_{self.memory_subdir}_{safe_context_id}",
                "on_disk": False,  # Use in-memory to avoid file conflicts
            }
            
            vector_store_config_obj = VectorStoreConfig(
                provider="qdrant",
                config=vector_store_base_config
            )
        
        # Create the main memory configuration with absolute paths
        from python.helpers import files
        history_db_path = files.get_abs_path("memory", self.memory_subdir, f"mem0_history_{safe_context_id}.db")
        
        config_dict = {
            "embedder": embedder_config,
            "llm": llm_config,
            "vector_store": vector_store_config_obj,
            "version": "v1.1",
            "history_db_path": history_db_path
        }
        
        # Add Graph Memory configuration if enabled
        graph_memory_config = self._get_graph_memory_config(settings)
        if graph_memory_config:
            config_dict["graph_store"] = graph_memory_config
        
        # Disable telemetry to prevent additional vector store conflicts
        config_dict["enable_telemetry"] = False
        
        # Also try to set custom telemetry config to avoid conflicts
        config_dict["custom_prompt"] = None
        config_dict["store_messages"] = True
            
        config = MemoryConfig(**config_dict)
        
        return config

    def _get_graph_memory_config(self, settings):
        """Get Graph Memory (Neo4j) configuration if enabled"""
        # Check if graph memory is enabled
        if not settings.get("mem0_enable_graph_memory", False):
            return None
        
        import os
        
        # Get Neo4j configuration from settings or environment  
        # Use port 7688 as configured in docker-compose.yml
        neo4j_config = {
            "url": settings.get("mem0_neo4j_url") or os.getenv("NEO4J_URL", "bolt://localhost:7688"),
            "username": settings.get("mem0_neo4j_username") or os.getenv("NEO4J_USERNAME", "neo4j"),
            "password": settings.get("mem0_neo4j_password") or os.getenv("NEO4J_PASSWORD", "mem0graph")
        }
        
        # Build graph store configuration
        graph_store_config = {
            "provider": "neo4j",
            "config": neo4j_config
        }
        
        # Add custom prompt if configured
        custom_prompt = settings.get("mem0_graph_custom_prompt")
        if custom_prompt:
            graph_store_config["custom_prompt"] = custom_prompt
            
        # Add LLM config for graph operations if specified
        graph_llm_config = settings.get("mem0_graph_llm_config")
        if graph_llm_config:
            graph_store_config["llm"] = graph_llm_config
        
        return graph_store_config

    async def _ensure_services_running(self, log_item: LogItem | None = None):
        """Ensure required Docker services are running"""
        from python.helpers.settings import get_settings
        settings = get_settings()
        
        # Check if auto-service management is disabled
        if not settings.get("mem0_auto_start_services", True):
            return
        
        # Only auto-start services if using self-hosted or local deployment
        deployment_mode = settings.get("mem0_deployment", "local")
        if deployment_mode == "hosted":
            return  # Hosted mode doesn't need local services
        
        try:
            from python.helpers.docker_service_manager import docker_service_manager
            
            # Determine which services are needed
            required_services = ["mem0_store", "neo4j"]  # Always start both for robust mem0 setup
            
            # Note: Neo4j is always started to ensure Graph Memory is available
            # It can be disabled later via mem0_enable_graph_memory setting
            
            if log_item:
                log_item.stream(progress=f"\nChecking required services: {', '.join(required_services)}")
            
            # Check and start services as needed
            results = docker_service_manager.ensure_services_running(required_services)
            
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            if success_count == total_count:
                if log_item:
                    log_item.stream(progress=f"\n✅ All {total_count} services ready")
                PrintStyle.standard(f"✅ All {total_count} mem0 services are ready")
            else:
                if log_item:
                    log_item.stream(progress=f"\n⚠️ {success_count}/{total_count} services ready - using fallbacks")
                PrintStyle.warning(f"⚠️ Only {success_count}/{total_count} services ready - using fallback options")
                
                # Update configuration to use fallbacks for failed services
                if not results.get("mem0_store", False):
                    PrintStyle.info("Using in-memory vector store instead of Qdrant")
                if not results.get("neo4j", False) and settings.get("mem0_enable_graph_memory", False):
                    PrintStyle.info("Graph memory disabled - Neo4j service unavailable")
                    # Temporarily disable graph memory for this session
                    settings["mem0_enable_graph_memory"] = False
                    
        except ImportError:
            # Docker service manager not available - continue without auto-service management
            if log_item:
                log_item.stream(progress="\nSkipping auto-service management")
            PrintStyle.info("Docker service auto-management not available")
        except Exception as e:
            # Don't fail initialization if service management fails
            error_msg = f"Service auto-start failed: {str(e)}"
            if log_item:
                log_item.stream(progress=f"\n⚠️ {error_msg}")
            PrintStyle.warning(error_msg)
            PrintStyle.info("Continuing with available services...")

    async def _retry_api_call(self, api_call, operation_name: str, max_retries: int = 3, delay: float = 1.0):
        """Retry API calls with exponential backoff"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                # Call the API function
                if asyncio.iscoroutinefunction(api_call):
                    result = await api_call()
                else:
                    result = api_call()
                return result
                
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Check if this is a retryable error
                if any(retryable in error_msg for retryable in [
                    "timeout", "rate limit", "429", "503", "502", "500", "connection"
                ]):
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        PrintStyle.info(f"mem0 {operation_name} failed (attempt {attempt + 1}), retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                
                # Non-retryable error or max retries reached
                break
        
        # All retries failed
        PrintStyle.error(f"mem0 {operation_name} failed after {max_retries} attempts: {last_exception}")
        return None

    @staticmethod
    def cleanup_client(memory_subdir: str, context_id: str):
        """Clean up mem0 client for a specific context"""
        safe_context_id = context_id.replace('-', '_')
        client_key = f"{memory_subdir}_{safe_context_id}"
        
        if client_key in Mem0Memory._clients:
            del Mem0Memory._clients[client_key]

    def _ensure_memory_directories(self):
        """Ensure all required memory directories exist"""
        import os
        from python.helpers import files
        
        # Create main memory directory
        memory_dir = files.get_abs_path("memory", self.memory_subdir)
        os.makedirs(memory_dir, exist_ok=True)
        
        # Get context ID for unique paths
        context_id = getattr(self.agent.context, 'id', 'default')
        safe_context_id = context_id.replace('-', '_')
        
        # Ensure the history database file can be created by creating its directory
        history_db_path = files.get_abs_path("memory", self.memory_subdir, f"mem0_history_{safe_context_id}.db")
        history_db_dir = os.path.dirname(history_db_path)
        os.makedirs(history_db_dir, exist_ok=True)

    def _set_environment_api_keys(self, log_item: LogItem | None = None):
        """Set API keys as environment variables for mem0/litellm compatibility"""
        import os
        from models import get_api_key
        
        # Map provider names to environment variable names
        env_key_mapping = {
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",  # OpenRouter has its own API key
            "anthropic": "ANTHROPIC_API_KEY", 
            "google": "GOOGLE_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "azure": "AZURE_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "mistral": "MISTRAL_API_KEY"
        }
        
        # Get embedding model provider with robust type checking
        embed_provider_obj = self.agent.config.embeddings_model.provider
        embed_provider = 'openai'  # default fallback
        
        try:
            if hasattr(embed_provider_obj, 'name'):
                embed_provider = str(embed_provider_obj.name).lower()
            elif hasattr(embed_provider_obj, 'value'):
                embed_provider = str(embed_provider_obj.value).lower()
            elif isinstance(embed_provider_obj, str):
                embed_provider = embed_provider_obj.lower()
            elif isinstance(embed_provider_obj, dict):
                embed_provider = str(embed_provider_obj.get('name', 'openai')).lower()
            else:
                embed_provider = str(embed_provider_obj).lower()
        except Exception:
            embed_provider = 'openai'
            
        # Get utility model provider with robust type checking
        util_provider = 'openai'  # default fallback
        
        try:
            util_provider_obj = self.agent.config.utility_model.provider
        except AttributeError:
            # utility_model might not exist, use default
            util_provider_obj = None
        
        if util_provider_obj is not None:
            try:
                if hasattr(util_provider_obj, 'name'):
                    util_provider = str(util_provider_obj.name).lower()
                elif hasattr(util_provider_obj, 'value'):
                    util_provider = str(util_provider_obj.value).lower()
                elif isinstance(util_provider_obj, str):
                    util_provider = util_provider_obj.lower()
                elif isinstance(util_provider_obj, dict):
                    util_provider = str(util_provider_obj.get('name', 'openai')).lower()
                else:
                    util_provider = str(util_provider_obj).lower()
            except Exception:
                util_provider = 'openai'
            
        # Set environment variables for both providers
        providers_to_set = set([embed_provider, util_provider])
        
        for provider in providers_to_set:
            if provider in env_key_mapping:
                env_var = env_key_mapping[provider]
                if env_var not in os.environ or not os.environ[env_var]:
                    # Get API key using Agent Zero's method
                    api_key = get_api_key(provider)
                    if api_key and api_key != "None":
                        os.environ[env_var] = api_key
                        if log_item:
                            log_item.stream(progress=f"\nSet {env_var} environment variable")
        
        # Also ensure OPENROUTER_API_KEY is available for LiteLLM
        if "OPENROUTER_API_KEY" not in os.environ or not os.environ["OPENROUTER_API_KEY"]:
            openrouter_key = get_api_key("openrouter")
            if openrouter_key and openrouter_key != "None":
                os.environ["OPENROUTER_API_KEY"] = openrouter_key
                if log_item:
                    log_item.stream(progress=f"\nSet OPENROUTER_API_KEY environment variable")

    async def search_similarity_threshold(
        self, query: str, limit: int, threshold: float, filter: str = ""
    ) -> List[Document]:
        """Search for memories with similarity threshold"""
        if not self.mem0_client:
            raise RuntimeError("mem0 client not initialized")
            
        try:
            # Validate and clean query parameter
            if not isinstance(query, str):
                query = str(query) if query is not None else ""
            
            if not query.strip():
                return []  # Empty query returns no results
            
            # Debug information
            PrintStyle.info(f"mem0 search starting with query: '{query[:100]}...' (type: {type(query)})")
            PrintStyle.info(f"User ID: {self.user_id} (type: {type(self.user_id)})")
            PrintStyle.info(f"Client type: {type(self.mem0_client)}")
            
            # Apply rate limiting
            await self.agent.rate_limiter(
                model_config=self.agent.config.embeddings_model, input=query
            )
            
            # Search memories with mem0ai using retry logic
            try:
                search_results = await self._retry_api_call(
                    lambda: self.mem0_client.search(
                        query=str(query).strip(),
                        user_id=str(self.user_id),
                        limit=int(limit)
                    ),
                    operation_name="search"
                )
            except Exception as e:
                error_details = str(e)
                PrintStyle.error(f"Detailed mem0 search error: {error_details}")
                PrintStyle.error(f"Query type: {type(query)}, value: {repr(query)}")
                PrintStyle.error(f"User ID type: {type(self.user_id)}, value: {repr(self.user_id)}")
                PrintStyle.error(f"Limit type: {type(limit)}, value: {repr(limit)}")
                raise
            
            if not search_results:
                return []
            
            # Convert mem0ai search results to Documents and filter by threshold
            documents = []
            memories = search_results.get("results", []) if isinstance(search_results, dict) else search_results
            
            for memory in memories:
                # Check if memory has sufficient score (mem0ai returns relevance scores)
                score = memory.get("score", 0)
                if score >= threshold:
                    # Apply additional filtering if specified
                    if filter and not self._apply_filter(memory, filter):
                        continue
                        
                    doc = Document(
                        page_content=memory.get("memory", ""),
                        metadata={
                            "id": memory.get("id", str(uuid.uuid4())),
                            "score": score,
                            "timestamp": memory.get("created_at", self.get_timestamp()),
                            "area": memory.get("metadata", {}).get("area", Memory.Area.MAIN.value),
                            **memory.get("metadata", {})
                        }
                    )
                    documents.append(doc)
                    
            return documents
            
        except Exception as e:
            error_msg = str(e)
            PrintStyle.error(f"Error searching mem0 memories: {error_msg}")
            
            # Check if it's the specific "expected string or buffer" error
            if "expected string or buffer" in error_msg.lower():
                PrintStyle.error("This is the 'expected string or buffer' error!")
                PrintStyle.error(f"Query was: {repr(query)} (type: {type(query)})")
                PrintStyle.error(f"User ID was: {repr(self.user_id)} (type: {type(self.user_id)})")
                PrintStyle.error(f"Limit was: {repr(limit)} (type: {type(limit)})")
                
                # Try to get more details about the stack trace
                import traceback
                PrintStyle.error("Full traceback:")
                traceback.print_exc()
            
            return []

    async def asearch(self, query, search_type="similarity_score_threshold", k=10, score_threshold=0.5, filter=None, **kwargs):
        """
        Compatibility method for FAISS-style asearch interface
        This ensures the Mem0Memory class works with existing Memory interface calls
        """
        if search_type == "similarity_score_threshold":
            # Convert FAISS-style parameters to mem0 search
            docs = await self.search_similarity_threshold(
                query=query,
                limit=k,
                threshold=score_threshold,
                filter=""  # mem0 uses string-based filtering
            )
            # Return just the documents (not tuples) since that's what the existing code expects
            return docs
        else:
            # For other search types, use basic similarity search
            docs = await self.search_similarity_threshold(
                query=query,
                limit=k,
                threshold=0.0,  # No threshold for basic similarity
                filter=""
            )
            return docs

    async def delete_documents_by_query(
        self, query: str, threshold: float, filter: str = ""
    ) -> List[Document]:
        """Delete memories by query with similarity threshold"""
        if not self.mem0_client:
            raise RuntimeError("mem0 client not initialized")
            
        try:
            # Find memories to delete
            docs_to_delete = await self.search_similarity_threshold(
                query=query, limit=100, threshold=threshold, filter=filter
            )
            
            # Delete the memories using mem0ai's delete method
            deleted_docs = []
            for doc in docs_to_delete:
                memory_id = doc.metadata.get("id")
                if memory_id:
                    try:
                        # Use mem0ai's delete method with retry logic
                        result = await self._retry_api_call(
                            lambda: self.mem0_client.delete(memory_id),
                            operation_name="delete_memory"
                        )
                        if result is not None:
                            deleted_docs.append(doc)
                    except Exception as e:
                        PrintStyle.error(f"Error deleting memory {memory_id}: {str(e)}")
                        continue
                    
            return deleted_docs
            
        except Exception as e:
            PrintStyle.error(f"Error deleting mem0 memories: {str(e)}")
            return []

    async def delete_documents_by_ids(self, ids: List[str]) -> List[Document]:
        """Delete memories by their IDs"""
        if not self.mem0_client:
            raise RuntimeError("mem0 client not initialized")
            
        deleted_docs = []
        
        try:
            for memory_id in ids:
                # Get the memory before deletion for return value
                try:
                    # Get memory details before deletion
                    memory = await self._retry_api_call(
                        lambda: self.mem0_client.get(memory_id),
                        operation_name="get_memory"
                    )
                    if memory:
                        doc = Document(
                            page_content=memory.get("memory", ""),
                            metadata={
                                "id": memory_id,
                                "timestamp": memory.get("created_at", self.get_timestamp()),
                                "area": memory.get("metadata", {}).get("area", Memory.Area.MAIN.value),
                                **memory.get("metadata", {})
                            }
                        )
                        deleted_docs.append(doc)
                        
                    # Delete the memory using mem0ai's delete method with retry
                    result = await self._retry_api_call(
                        lambda: self.mem0_client.delete(memory_id),
                        operation_name="delete_memory"
                    )
                    
                except Exception as e:
                    PrintStyle.error(f"Error deleting memory {memory_id}: {str(e)}")
                    continue
                    
            return deleted_docs
            
        except Exception as e:
            PrintStyle.error(f"Error deleting mem0 memories by IDs: {str(e)}")
            return []

    async def insert_text(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Insert text into mem0 memory"""
        if not self.mem0_client:
            raise RuntimeError("mem0 client not initialized")
            
        try:
            # Validate and clean text parameter
            if not isinstance(text, str):
                text = str(text) if text is not None else ""
            
            if not text.strip():
                raise ValueError("Cannot insert empty text into memory")
            
            # Prepare metadata
            if metadata is None:
                metadata = {}
                
            # Add default area if not specified
            if "area" not in metadata:
                metadata["area"] = Memory.Area.MAIN.value
                
            # Add timestamp
            metadata["timestamp"] = self.get_timestamp()
            
            # Apply rate limiting
            await self.agent.rate_limiter(
                model_config=self.agent.config.embeddings_model, input=text
            )
            
            # Add memory to mem0ai using the correct API with retry logic
            result = await self._retry_api_call(
                lambda: self.mem0_client.add(
                    messages=[{"role": "user", "content": text.strip()}],
                    user_id=self.user_id,
                    metadata=metadata
                ),
                operation_name="add_memory"
            )
            
            # Extract memory ID from result
            memory_id = str(uuid.uuid4())  # fallback
            if isinstance(result, dict):
                # Check for different possible result structures
                if "results" in result and len(result["results"]) > 0:
                    memory_id = result["results"][0].get("id", memory_id)
                elif "id" in result:
                    memory_id = result["id"]
            elif isinstance(result, list) and len(result) > 0:
                memory_id = result[0].get("id", memory_id)
                
            return memory_id
            
        except Exception as e:
            PrintStyle.error(f"Error inserting text into mem0: {str(e)}")
            return str(uuid.uuid4())

    async def insert_documents(self, docs: List[Document]) -> List[str]:
        """Insert multiple documents into mem0 memory"""
        ids = []
        
        for doc in docs:
            doc_id = await self.insert_text(doc.page_content, doc.metadata)
            ids.append(doc_id)
            
        return ids

    async def aadd_documents(self, documents: List[Document], ids: List[str] = None, **kwargs):
        """
        Compatibility method for FAISS-style aadd_documents interface
        This ensures the Mem0Memory class works with existing Memory wrapper calls
        """
        if not documents:
            return []
            
        # Use the existing insert_documents method
        return await self.insert_documents(documents)

    async def adelete(self, ids: List[str], **kwargs):
        """
        Compatibility method for FAISS-style adelete interface
        """
        return await self.delete_documents_by_ids(ids)

    async def aget_by_ids(self, ids: List[str], **kwargs) -> List[Document]:
        """
        Compatibility method for FAISS-style aget_by_ids interface
        """
        if not self.mem0_client:
            raise RuntimeError("mem0 client not initialized")
            
        # Validate and clean IDs
        if not ids:
            return []
            
        clean_ids = []
        for id_val in ids:
            if id_val and isinstance(id_val, str):
                clean_ids.append(str(id_val).strip())
        
        if not clean_ids:
            return []
            
        documents = []
        for memory_id in clean_ids:
            try:
                # Validate memory_id is a proper string
                if not memory_id or not isinstance(memory_id, str):
                    continue
                    
                # Get memory details from mem0
                memory = await self._retry_api_call(
                    lambda: self.mem0_client.get(str(memory_id).strip(), user_id=str(self.user_id)),
                    operation_name="get_memory"
                )
                if memory:
                    # Ensure memory content is a string
                    memory_content = memory.get("memory", "")
                    if not isinstance(memory_content, str):
                        memory_content = str(memory_content) if memory_content is not None else ""
                    
                    doc = Document(
                        page_content=memory_content,
                        metadata={
                            "id": memory_id,
                            "timestamp": memory.get("created_at", self.get_timestamp()),
                            "area": memory.get("metadata", {}).get("area", Memory.Area.MAIN.value),
                            **memory.get("metadata", {})
                        }
                    )
                    documents.append(doc)
            except Exception as e:
                PrintStyle.error(f"Error getting memory {memory_id}: {str(e)}")
                continue
                
        return documents

    def save_local(self, folder_path: str = None, **kwargs):
        """
        Compatibility method for FAISS-style save_local interface
        For mem0, this is a no-op since mem0 handles persistence automatically
        """
        # mem0 handles persistence automatically, so this is a no-op
        pass

    async def preload_knowledge(
        self, log_item: LogItem | None, kn_dirs: List[str], memory_subdir: str
    ):
        """Preload knowledge files into mem0 memory"""
        if log_item:
            log_item.update(heading="Preloading knowledge into mem0...")
            
        # Import existing knowledge loading logic
        from python.helpers import knowledge_import
        from python.helpers import files
        from python.helpers.settings import get_settings
        
        settings = get_settings()
        max_docs = settings.get("mem0_max_knowledge_docs", 100)  # Limit to prevent slowness
        
        # Load knowledge using existing system but insert into mem0
        index = {}
        total_docs = 0
        
        for kn_dir in kn_dirs:
            for area in Memory.Area:
                index = knowledge_import.load_knowledge(
                    log_item,
                    files.get_abs_path("knowledge", kn_dir, area.value),
                    index,
                    {"area": area.value},
                )
                
        # Load instrument descriptions
        index = knowledge_import.load_knowledge(
            log_item,
            files.get_abs_path("instruments"),
            index,
            {"area": Memory.Area.INSTRUMENTS.value},
            filename_pattern="**/*.md",
        )
        
        # Insert knowledge documents into mem0 with enhanced error handling and batching
        all_docs = []
        for file_path, knowledge_data in index.items():
            if knowledge_data.get("documents"):
                all_docs.extend(knowledge_data["documents"])
        
        if len(all_docs) > max_docs:
            PrintStyle.info(f"Limiting knowledge preload to {max_docs} documents (found {len(all_docs)})")
            all_docs = all_docs[:max_docs]
            
        if all_docs:
            try:
                if log_item:
                    log_item.update(heading=f"Inserting {len(all_docs)} knowledge documents into mem0...")
                
                # Use smaller batches and retry logic for hosted platform
                from python.helpers.settings import get_settings
                settings = get_settings()
                deployment_mode = settings.get("mem0_deployment", "local")
                
                # Adjust batch size based on deployment mode
                if deployment_mode == "hosted":
                    batch_size = 5  # Smaller batches for hosted platform to avoid rate limits
                    delay_between_batches = 1.0  # Add delay to respect rate limits
                else:
                    batch_size = 10
                    delay_between_batches = 0.1
                
                successful_inserts = 0
                failed_inserts = 0
                
                for i in range(0, len(all_docs), batch_size):
                    batch = all_docs[i:i + batch_size]
                    
                    try:
                        # Insert batch with retry logic
                        for doc in batch:
                            try:
                                await self.insert_text(doc.page_content, doc.metadata)
                                successful_inserts += 1
                            except Exception as e:
                                failed_inserts += 1
                                if "rate limit" in str(e).lower() or "429" in str(e):
                                    # Rate limited - wait longer
                                    await asyncio.sleep(5.0)
                                
                        # Progress update
                        if log_item:
                            progress = f"Processed {min(i + batch_size, len(all_docs))}/{len(all_docs)} documents (success: {successful_inserts}, failed: {failed_inserts})"
                            log_item.stream(progress=f"\n{progress}")
                        
                        # Delay between batches
                        if i + batch_size < len(all_docs):
                            await asyncio.sleep(delay_between_batches)
                            
                    except Exception as e:
                        failed_inserts += len(batch)
                        PrintStyle.error(f"Batch {i//batch_size + 1} failed: {str(e)}")
                        
                if log_item:
                    result_msg = f"Knowledge preloading completed: {successful_inserts} successful, {failed_inserts} failed"
                    log_item.update(heading=result_msg)
                    
                if failed_inserts > 0:
                    PrintStyle.error(f"Knowledge preloading: {failed_inserts} documents failed to insert")
                    
            except Exception as e:
                PrintStyle.error(f"Error during knowledge preloading: {str(e)}")
                if log_item:
                    log_item.update(heading=f"Knowledge preloading failed: {str(e)}")
        else:
            if log_item:
                log_item.update(heading="No knowledge documents found to preload")

    def _apply_filter(self, memory: Dict[str, Any], filter_condition: str) -> bool:
        """Apply filter condition to memory metadata using safe parsing"""
        if not filter_condition.strip():
            return True
            
        try:
            metadata = memory.get("metadata", {})
            return self._parse_filter_safely(filter_condition, metadata)
        except Exception:
            return False
    
    def _parse_filter_safely(self, filter_condition: str, metadata: Dict[str, Any]) -> bool:
        """Safely parse filter conditions without using eval()"""
        # Handle common Agent Zero filter patterns
        filter_condition = filter_condition.strip()
        
        # Handle single equality checks like "area=='main'"
        if "==" in filter_condition:
            return self._parse_equality_filter(filter_condition, metadata)
        
        # Handle OR conditions like "area == 'main' or area == 'fragments'"
        if " or " in filter_condition:
            return self._parse_or_filter(filter_condition, metadata)
        
        # Handle AND conditions
        if " and " in filter_condition:
            return self._parse_and_filter(filter_condition, metadata)
        
        # Default fallback for unknown patterns
        return True
    
    def _parse_equality_filter(self, condition: str, metadata: Dict[str, Any]) -> bool:
        """Parse single equality conditions like area=='main'"""
        try:
            # Split on == and clean up
            parts = condition.split("==")
            if len(parts) != 2:
                return True
                
            key = parts[0].strip()
            value = parts[1].strip().strip("'\"")  # Remove quotes
            
            # Get the actual value from metadata
            actual_value = metadata.get(key, "")
            
            return str(actual_value) == value
        except Exception:
            return True
    
    def _parse_or_filter(self, condition: str, metadata: Dict[str, Any]) -> bool:
        """Parse OR conditions like 'area == main or area == fragments'"""
        try:
            # Split on 'or' and check each condition
            or_parts = condition.split(" or ")
            for part in or_parts:
                if self._parse_equality_filter(part.strip(), metadata):
                    return True
            return False
        except Exception:
            return True
    
    def _parse_and_filter(self, condition: str, metadata: Dict[str, Any]) -> bool:
        """Parse AND conditions"""
        try:
            # Split on 'and' and check all conditions
            and_parts = condition.split(" and ")
            for part in and_parts:
                if not self._parse_equality_filter(part.strip(), metadata):
                    return False
            return True
        except Exception:
            return True

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp in standard format"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def format_docs_plain(docs: List[Document]) -> List[str]:
        """Format documents for plain text output (compatibility with existing code)"""
        result = []
        for doc in docs:
            text = ""
            for k, v in doc.metadata.items():
                text += f"{k}: {v}\n"
            text += f"Content: {doc.page_content}"
            result.append(text)
        return result


# Compatibility functions for existing code
def get_memory_subdir_abs(agent: Agent) -> str:
    """Get absolute path to memory subdirectory"""
    from python.helpers import files
    return files.get_abs_path("memory", agent.config.memory_subdir or "default")


def get_custom_knowledge_subdir_abs(agent: Agent) -> str:
    """Get absolute path to custom knowledge subdirectory"""
    from python.helpers import files
    for dir in agent.config.knowledge_subdirs:
        if dir != "default":
            return files.get_abs_path("knowledge", dir)
    raise Exception("No custom knowledge subdir set")


def reload():
    """Reload all mem0 memory instances"""
    Mem0Memory.index = {}