import models
from python.helpers.api import ApiHandler
from flask import Request, Response
from python.helpers.print_style import PrintStyle
import litellm
from litellm import validate_environment

class ModelsAll(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Get all available models across all providers with valid API keys"""
        
        try:
            PrintStyle.info("Fetching all models using LiteLLM model lists...")
            
            # Get models from LiteLLM's built-in lists
            grouped_models = {
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
            
            # Flatten all models
            all_models = []
            for provider, models in grouped_models.items():
                all_models.extend(models)
            
            PrintStyle.info(f"LiteLLM found {len(all_models)} total models across {len(grouped_models)} providers")
            
            return {
                "all_models": all_models,
                "grouped_models": grouped_models,
                "total_count": len(all_models),
                "provider_count": len(grouped_models),
                "source": "litellm_lists"
            }
                
        except Exception as e:
            PrintStyle.error(f"Error getting all LiteLLM models: {e}")
            return {
                "all_models": [],
                "grouped_models": {},
                "total_count": 0,
                "provider_count": 0,
                "source": "error",
                "error": str(e)
            }