from config import DEFAULT_MODEL, FALLBACK_MODEL, MODEL_SPECS


def get_groq_chat():
    # Implementation for Groq Chat model
    pass


def get_gpt4o():
    # Implementation for GPT-4O model
    pass


def get_gpt4o_mini():
    # Implementation for GPT-4O Mini model
    pass


def get_claude_chat():
    # Implementation for Claude Chat model
    pass


def get_available_models():
    return list(MODEL_SPECS.keys())


def get_api_key() -> str:
    # Implementation to retrieve the API key
    return "your_api_key"
