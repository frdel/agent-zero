from config import AgentConfig
from models import (
    get_groq_chat,
)

# Commented out imports that are not currently used to avoid linting errors
# from models import (
#     get_gpt4o,
#     get_gpt4o_mini,
#     get_claude_chat,
#     get_available_models,
# )

# Initialize Agent Configuration
config = AgentConfig()

# Example usage of the imported functions (if needed)
# groq_chat = get_groq_chat()
# gpt4o = get_gpt4o()
# gpt4o_mini = get_gpt4o_mini()
# claude_chat = get_claude_chat()
# available_models = get_available_models()

# If these functions are not used in initialize.py, consider removing the imports to eliminate warnings

class AgentConfig:
    # Existing code...

    def __init__(self):
        # Other initializations...
        self.chat_model_name = 'default_chat_model'
        self.utility_model_name = 'default_utility_model'
        self.embedding_model_name = 'default_embedding_model'
