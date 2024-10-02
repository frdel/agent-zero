from config import AgentConfig
from models import get_model_by_name, get_available_models

# Initialize Agent Configuration
config = AgentConfig()

# Set default values for the model names
config.chat_model_name = "groq_llama"
config.utility_model_name = "groq_llama"
config.embedding_model_name = "default_embedding_model"

# Get available models
available_models = get_available_models()

# Create the actual model instances
config.chat_model = get_model_by_name(config.chat_model_name)
config.utility_model = get_model_by_name(config.utility_model_name)

# Set embeddings_model to None
# TODO: Implement appropriate embedding model initialization
config.embeddings_model = None

# Export the config and available models
__all__ = [
    "config",
    "available_models",
]
