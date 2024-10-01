from config import DEFAULT_MODEL, FALLBACK_MODEL, MODEL_SPECS
from langchain.chat_models import ChatOpenAI, ChatAnthropic
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain.llms import OpenAI
from constants import DEFAULT_TEMPERATURE  # Or define it if not available


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


def get_model_by_name(model_name: str):
    model_getters = {
        "groq_llama": get_groq_chat,
        "gpt4o": get_openai_chat,
        "gpt4o_mini": get_openai_chat,
        "claude_3_5_sonnet": get_anthropic_chat,
        # Add other models as needed
    }
    if model_name not in model_getters:
        raise ValueError(f"Model '{model_name}' is not available.")
    # You may need to adjust the parameters passed based on the actual model
    return model_getters[model_name](model_name)


def get_embedding_model_by_name(model_name: str):
    embedding_getters = {
        "openai_embedding": get_openai_embedding,
        "huggingface_embedding": get_huggingface_embedding,
        # Add other embedding models as needed
    }
    if model_name not in embedding_getters:
        raise ValueError(f"Embedding model '{model_name}' is not available.")
    return embedding_getters[model_name]()


def get_openai_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)


def get_anthropic_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(
        model_name=model_name, temperature=temperature, api_key=api_key
    )


def get_openai_embedding(model_name: str, api_key=None):
    api_key = api_key or get_api_key("openai")
    return OpenAIEmbeddings(model=model_name, api_key=api_key)


def get_huggingface_embedding(model_name: str):
    return HuggingFaceEmbeddings(model_name=model_name)
