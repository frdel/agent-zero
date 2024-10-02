from typing import Optional, Any, Callable, Type, cast
from pydantic import SecretStr

from config import MODEL_SPECS
from langchain.chat_models import ChatOpenAI, ChatAnthropic
from langchain.embeddings import OpenAIEmbeddings, HuggingFaceEmbeddings
from langchain_groq import ChatGroq

# Define DEFAULT_TEMPERATURE if not available from constants
DEFAULT_TEMPERATURE = 0.7


def get_groq_chat(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> ChatGroq:
    api_key = api_key or get_api_key("groq")
    if api_key is None:
        raise ValueError("API key for Groq is not available")
    return ChatGroq(model=model_name, temperature=temperature, api_key=SecretStr(api_key) if api_key else None, stop_sequences=None)


def get_gpt4o(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    return get_openai_chat(model_name, api_key, temperature)


def get_gpt4o_mini(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    return get_openai_chat(model_name, api_key, temperature)


def get_claude_chat(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    return get_anthropic_chat(model_name, api_key, temperature)


def get_available_models() -> list[str]:
    return list(MODEL_SPECS.keys())


def get_api_key(provider: str) -> Optional[str]:
    # Implementation to retrieve the API key
    # This should be implemented to securely retrieve API keys
    return "your_api_key"


def get_model_by_name(model_name: str) -> Any:
    model_getters: dict[str, Callable] = {
        "groq_llama": get_groq_chat,
        "gpt4o": get_gpt4o,
        "gpt4o_mini": get_gpt4o_mini,
        "claude_3_5_sonnet": get_claude_chat,
        # Add other models as needed
    }
    if model_name not in model_getters:
        raise ValueError(f"Model '{model_name}' is not available.")
    # Type assertion to satisfy type checker
    getter = cast(Type[Any], model_getters[model_name])
    return getter(model_name)


def get_embedding_model_by_name(model_name: str) -> Any:
    embedding_getters: dict[str, Callable] = {
        "openai_embedding": get_openai_embedding,
        "huggingface_embedding": get_huggingface_embedding,
        # Add other embedding models as needed
    }
    if model_name not in embedding_getters:
        raise ValueError(f"Embedding model '{model_name}' is not available.")
    # Type assertion to satisfy type checker
    getter = cast(Type[Any], embedding_getters[model_name])
    return getter(model_name)


def get_openai_chat(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    api_key = api_key or get_api_key("openai")
    if api_key is None:
        raise ValueError("API key for OpenAI is not available")
    return cast(Any, ChatOpenAI(model_name=model_name, temperature=temperature, openai_api_key=api_key))  # type: ignore


def get_anthropic_chat(model_name: str, api_key: Optional[str] = None, temperature: float = DEFAULT_TEMPERATURE) -> Any:
    api_key = api_key or get_api_key("anthropic")
    if api_key is None:
        raise ValueError("API key for Anthropic is not available")
    return cast(Any, ChatAnthropic(model=model_name, temperature=temperature, anthropic_api_key=api_key))  # type: ignore


def get_openai_embedding(model_name: str, api_key: Optional[str] = None) -> OpenAIEmbeddings:
    api_key = api_key or get_api_key("openai")
    if api_key is None:
        raise ValueError("API key for OpenAI is not available")
    return OpenAIEmbeddings(model=model_name, api_key=api_key)


def get_huggingface_embedding(model_name: str) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name=model_name)
