import models
from python.helpers.api import ApiHandler
from flask import Request, Response
import aiohttp
import asyncio
import os
from python.helpers.print_style import PrintStyle
import litellm
from litellm import validate_environment

class ModelsList(ApiHandler):
    
    async def fetch_ollama_models(self):
        """Fetch models from local Ollama installation"""
        models = []
        
        # Method 1: Try API endpoint
        try:
            ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model['name'] for model in data.get('models', [])]
                        PrintStyle.info(f"Fetched {len(models)} models from Ollama API")
                        return models
        except Exception as e:
            PrintStyle.warning(f"Could not fetch Ollama models via API: {e}")
        
        # Method 2: Check local Ollama models directory
        try:
            import glob
            import json
            
            # Try multiple possible Ollama model paths
            possible_paths = [
                os.path.expanduser("~/.ollama/models"),
                os.path.expanduser("~/Library/Application Support/Ollama/models"),  # macOS
                os.getenv("OLLAMA_MODELS"),  # Custom path
            ]
            
            for models_path in possible_paths:
                if models_path and os.path.exists(models_path):
                    PrintStyle.info(f"Checking Ollama models in: {models_path}")
                    
                    # Look for manifest files that indicate installed models
                    manifest_files = glob.glob(os.path.join(models_path, "manifests", "registry.ollama.ai", "*", "*"))
                    
                    local_models = []
                    for manifest_file in manifest_files:
                        try:
                            # Extract model name from path
                            path_parts = manifest_file.split(os.sep)
                            if len(path_parts) >= 2:
                                namespace = path_parts[-2]
                                model_name = path_parts[-1]
                                full_name = f"{namespace}/{model_name}" if namespace != "library" else model_name
                                local_models.append(full_name)
                        except Exception:
                            continue
                    
                    if local_models:
                        PrintStyle.info(f"Found {len(local_models)} models in local Ollama directory")
                        return local_models
                    
        except Exception as e:
            PrintStyle.warning(f"Could not check local Ollama models: {e}")
        
        return []
    
    async def fetch_lmstudio_models(self):
        """Fetch models from local LM Studio installation"""
        try:
            lmstudio_url = os.getenv('LM_STUDIO_BASE_URL', 'http://127.0.0.1:1234/v1')
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{lmstudio_url}/models", timeout=aiohttp.ClientTimeout(total=3)) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model['id'] for model in data.get('data', [])]
                        PrintStyle.info(f"Fetched {len(models)} models from LM Studio")
                        return models
        except Exception as e:
            PrintStyle.warning(f"Could not fetch LM Studio models: {e}")
        return []
    
    async def fetch_chutes_models(self):
        """Fetch models from Chutes AI"""
        try:
            # Chutes AI API endpoint - adjust as needed based on their API
            chutes_url = "https://api.chutes.ai"  # This would need to be the actual endpoint
            async with aiohttp.ClientSession() as session:
                headers = {}
                api_key = os.getenv('API_KEY_CHUTES')
                if api_key:
                    headers['Authorization'] = f'Bearer {api_key}'
                
                async with session.get(f"{chutes_url}/models", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get('models', [])
                        PrintStyle.info(f"Fetched {len(models)} models from Chutes AI")
                        return models
        except Exception as e:
            PrintStyle.warning(f"Could not fetch Chutes AI models: {e}")
        return []
    
    def get_litellm_models_for_provider(self, provider_name):
        """Get models using LiteLLM's built-in model lists"""
        try:
            # Map our provider names to LiteLLM model lists
            provider_models = {
                'OPENAI': litellm.open_ai_chat_completion_models + litellm.open_ai_embedding_models,
                'ANTHROPIC': litellm.anthropic_models,
                'GOOGLE': litellm.gemini_models,
                'GROQ': litellm.groq_models,
                'MISTRALAI': litellm.mistral_chat_models,
                'DEEPSEEK': litellm.deepseek_models,
                'SAMBANOVA': litellm.sambanova_models,
                'OPENROUTER': litellm.openrouter_models,
                'HUGGINGFACE': litellm.huggingface_models,
            }
            
            models = provider_models.get(provider_name, [])
            if models:
                PrintStyle.info(f"LiteLLM found {len(models)} models for {provider_name}")
                return models
            else:
                PrintStyle.warning(f"No LiteLLM models found for {provider_name}")
                return []
                
        except Exception as e:
            PrintStyle.warning(f"Error getting LiteLLM models for {provider_name}: {e}")
            return []
    

    async def process(self, input: dict, request: Request) -> dict | Response:
        """Get available model names for a specific provider"""
        
        provider_name = input.get("provider", "").upper()
        
        # Model lists for each provider
        model_lists = {
            "OPENAI": [
                # Chat models
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
                # Embedding models
                "text-embedding-3-large",
                "text-embedding-3-small",
                "text-embedding-ada-002",
            ],
            "ANTHROPIC": [
                # Chat models
                "claude-3-5-sonnet-20241022",
                "claude-3-5-sonnet-20240620",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "GOOGLE": [
                # Chat models
                "gemini-1.5-pro",
                "gemini-1.5-pro-002",
                "gemini-1.5-pro-exp-0827",
                "gemini-1.5-flash",
                "gemini-1.5-flash-002",
                "gemini-1.5-flash-8b",
                "gemini-1.0-pro",
                # Embedding models
                "text-embedding-004",
                "text-multilingual-embedding-002",
            ],
            "GROQ": [
                # Chat models
                "llama-3.3-70b-versatile",
                "llama-3.1-70b-versatile",
                "llama-3.1-8b-instant",
                "llama-3.2-90b-text-preview",
                "llama-3.2-11b-text-preview",
                "llama-3.2-3b-preview",
                "llama-3.2-1b-preview",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "gemma-7b-it",
            ],
            "MISTRALAI": [
                # Chat models
                "mistral-large-latest",
                "mistral-large-2407",
                "mistral-medium-latest",
                "mistral-small-latest",
                "mistral-tiny",
                "codestral-latest",
                "codestral-mamba-latest",
                # Embedding models
                "mistral-embed",
            ],
            "OLLAMA": [
                # Common local models - users can add their own
                "llama3.2:latest",
                "llama3.2:3b",
                "llama3.2:1b",
                "llama3.1:latest",
                "llama3.1:8b",
                "llama3.1:70b",
                "qwen2.5:latest",
                "qwen2.5:7b",
                "qwen2.5:14b",
                "qwen2.5:32b",
                "codellama:latest",
                "codellama:7b",
                "codellama:13b",
                "gemma2:latest",
                "gemma2:9b",
                "gemma2:27b",
                "phi3.5:latest",
                "mistral:latest",
                "mistral:7b",
                "deepseek-coder:latest",
                "nomic-embed-text:latest",
            ],
            "HUGGINGFACE": [
                # Sentence transformers models (local)
                "sentence-transformers/all-MiniLM-L6-v2",
                "sentence-transformers/all-mpnet-base-v2",
                "sentence-transformers/paraphrase-MiniLM-L6-v2",
                "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
                "sentence-transformers/all-distilroberta-v1",
                "sentence-transformers/all-MiniLM-L12-v2",
                "sentence-transformers/msmarco-distilbert-base-v4",
                # Without prefix (also work locally)
                "all-MiniLM-L6-v2",
                "all-mpnet-base-v2",
                "paraphrase-MiniLM-L6-v2",
                # Popular HuggingFace models (require API key)
                "microsoft/DialoGPT-large",
                "google/flan-t5-large",
                "facebook/blenderbot-400M-distill",
                "microsoft/DialoGPT-medium",
                "microsoft/DialoGPT-small",
            ],
            "DEEPSEEK": [
                # Chat models
                "deepseek-chat",
                "deepseek-coder",
                "deepseek-reasoner",
            ],
            "OPENROUTER": [
                # Popular models on OpenRouter
                "anthropic/claude-3.5-sonnet",
                "anthropic/claude-3-opus",
                "anthropic/claude-3-sonnet",
                "anthropic/claude-3-haiku",
                "openai/gpt-4o",
                "openai/gpt-4-turbo",
                "openai/gpt-4",
                "openai/gpt-3.5-turbo",
                "google/gemini-pro-1.5",
                "google/gemini-flash-1.5",
                "meta-llama/llama-3.1-405b-instruct",
                "meta-llama/llama-3.1-70b-instruct",
                "meta-llama/llama-3.1-8b-instruct",
                "mistralai/mistral-large",
                "mistralai/mistral-medium",
                "qwen/qwen-2.5-72b-instruct",
            ],
            "SAMBANOVA": [
                # SambaNova models
                "Meta-Llama-3.1-405B-Instruct",
                "Meta-Llama-3.1-70B-Instruct",
                "Meta-Llama-3.1-8B-Instruct",
                "Qwen2.5-72B-Instruct",
                "Qwen2.5-32B-Instruct",
            ],
            "LMSTUDIO": [
                # Local LM Studio models - these are examples, actual models depend on what user has loaded
                "local-model",
                "llama-3.2-3b-instruct",
                "llama-3.1-8b-instruct",
                "qwen2.5-7b-instruct",
                "gemma-2-9b-it",
                "phi-3.5-mini-instruct",
                "mistral-7b-instruct",
                "codellama-7b-instruct",
            ],
            "CHUTES": [
                # Chutes AI models - these are examples, will be fetched dynamically if available
                "chutes-7b-chat",
                "chutes-13b-chat", 
                "chutes-70b-chat",
                "chutes-coder-7b",
                "chutes-coder-13b",
            ],
        }
        
        # Get models for the requested provider
        models = []
        dynamic = False
        source = "static"
        
        # For LiteLLM-supported providers, use LiteLLM's built-in functionality
        litellm_providers = ['OPENAI', 'ANTHROPIC', 'GOOGLE', 'GROQ', 'MISTRALAI', 'DEEPSEEK', 'SAMBANOVA', 'OPENROUTER', 'HUGGINGFACE']
        
        if provider_name in litellm_providers:
            # Try LiteLLM first for these providers
            litellm_models = self.get_litellm_models_for_provider(provider_name)
            if litellm_models:
                models = litellm_models
                dynamic = True
                source = "litellm"
            else:
                # Fall back to static list if LiteLLM fails (no API key, etc.)
                models = model_lists.get(provider_name, [])
                source = "static_fallback"
        
        # For local/custom providers, use our custom fetching methods
        elif provider_name == "OLLAMA":
            dynamic_models = await self.fetch_ollama_models()
            if dynamic_models:
                models = dynamic_models
                dynamic = True
                source = "ollama_api"
            else:
                models = model_lists.get(provider_name, [])
                source = "static_fallback"
        
        elif provider_name == "LMSTUDIO":
            dynamic_models = await self.fetch_lmstudio_models()
            if dynamic_models:
                models = dynamic_models
                dynamic = True
                source = "lmstudio_api"
            else:
                models = model_lists.get(provider_name, [])
                source = "static_fallback"
        
        elif provider_name == "CHUTES":
            dynamic_models = await self.fetch_chutes_models()
            if dynamic_models:
                models = dynamic_models
                dynamic = True
                source = "chutes_api"
            else:
                models = model_lists.get(provider_name, [])
                source = "static_fallback"
        
        else:
            # Unknown provider, try static list
            models = model_lists.get(provider_name, [])
            source = "static"
        
        PrintStyle.info(f"Returning {len(models)} models for {provider_name} from {source}")
        
        return {
            "models": models,
            "provider": provider_name,
            "count": len(models),
            "dynamic": dynamic,
            "source": source
        }