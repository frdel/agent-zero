from __future__ import annotations
from enum import Enum  
import os  
from typing import Any,AsyncIterator, Iterable, List, Dict, Union, cast  

import litellm  
from langchain_core.embeddings import Embeddings  
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import BaseMessage
from python.helpers import dotenv, runtime  
from python.helpers.dotenv import load_dotenv  
from python.helpers.rate_limiter import RateLimiter  

# environment variables  
load_dotenv()  

class ModelType(Enum):  
    CHAT = "Chat"  
    EMBEDDING = "Embedding"  

class ModelProvider(Enum):  
    ANTHROPIC = "Anthropic"
    CHUTES = "Chutes"
    DEEPSEEK = "DeepSeek"
    GOOGLE = "Google"
    GROQ = "Groq"
    HUGGINGFACE = "HuggingFace"
    LMSTUDIO = "LM Studio"
    MISTRALAI = "Mistral AI"
    OLLAMA = "Ollama"
    OPENAI = "OpenAI"
    OPENAI_AZURE = "OpenAI Azure"
    OPENROUTER = "OpenRouter"
    SAMBANOVA = "Sambanova"
    OTHER = "Other"


rate_limiters: dict[str, RateLimiter] = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# Utility function to get API keys from environment variables  
def get_api_key(service):  
    return (  
        dotenv.get_dotenv_value(f"API_KEY_{service.upper()}")  
        or dotenv.get_dotenv_value(f"{service.upper()}_API_KEY")
        # or dotenv.get_dotenv_value(f"{service.upper()}_API_TOKEN")
        or "None"  
    )


BASE_URL_ENV = {
    ModelProvider.OLLAMA: "OLLAMA_BASE_URL",
    ModelProvider.LMSTUDIO: "LM_STUDIO_BASE_URL",
    ModelProvider.ANTHROPIC: "ANTHROPIC_BASE_URL",
    ModelProvider.DEEPSEEK: "DEEPSEEK_BASE_URL",
    ModelProvider.OPENROUTER: "OPEN_ROUTER_BASE_URL",
    ModelProvider.SAMBANOVA: "SAMBANOVA_BASE_URL",
    ModelProvider.CHUTES: "CHUTES_BASE_URL",
}

def get_base_url(provider: ModelProvider) -> str | None:
    if provider == ModelProvider.OLLAMA:
        return dotenv.get_dotenv_value("OLLAMA_BASE_URL") or f"http://{runtime.get_local_url()}:11434"
    if provider == ModelProvider.LMSTUDIO:
        return dotenv.get_dotenv_value("LM_STUDIO_BASE_URL") or f"http://{runtime.get_local_url()}:1234/v1"
    env = BASE_URL_ENV.get(provider)
    if env:
        return dotenv.get_dotenv_value(env)
    if provider == ModelProvider.OPENAI_AZURE:
        return dotenv.get_dotenv_value("OPENAI_AZURE_ENDPOINT")
    return None

def parse_chunk(chunk: Any) -> str:
    """Parse a streaming chunk from LiteLLM."""
    if isinstance(chunk, str):
        return chunk

    # Handle LiteLLM ModelResponseStream objects
    if hasattr(chunk, "choices") and chunk.choices:
        choice = chunk.choices[0]
        if hasattr(choice, "delta") and choice.delta:
            delta = choice.delta
            if hasattr(delta, "content") and delta.content:
                return str(delta.content)

    # Some SDKs return an object with a `content` attribute rather than a dict.
    if hasattr(chunk, "content"):
        return str(chunk.content)

    # Handle dict format
    if isinstance(chunk, dict):
        delta = (
            chunk.get("choices", [{}])[0]
            .get("delta", {})
            .get("content")
        )
        if delta:
            return str(delta)
    return str(chunk)

# ---------------------------------------------------------------------------
# LiteLLM wrappers
# ---------------------------------------------------------------------------

class LiteLLMEmbeddings(Embeddings):
    """LangChain embeddings wrapper around LiteLLM."""

    def __init__(self, model: str, *, api_key: str | None = None, api_base: str | None = None, **kwargs: Any) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.kwargs = kwargs

    def _embedding_args(self) -> Dict[str, Any]:
        args = {"model": self.model, **self.kwargs}
        if self.api_key:
            args["api_key"] = self.api_key
        if self.api_base:
            args["api_base"] = self.api_base
        return args

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        resp = litellm.embedding(input=texts, **self._embedding_args())  # type: ignore
        return [d["embedding"] for d in resp["data"]]  # type: ignore[index]

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]

# ---------------------------------------------------------------------------


def _to_litellm_messages(messages: Iterable[BaseMessage]) -> List[Dict[str, str]]:
    llm_messages = []
    for m in messages:
        # Convert LangChain message types to LiteLLM/OpenAI format
        if m.type == "ai":
            role = "assistant"
        elif m.type == "human":
            role = "user"  # LiteLLM expects "user" not "human"
        elif m.type == "system":
            role = "system"
        else:
            role = "user"  # Default fallback

        llm_messages.append({"role": role, "content": m.content})
    return llm_messages


def _convert_numeric_params(kwargs: dict) -> dict:
    """Convert string numeric parameters to proper types for LiteLLM"""
    converted = kwargs.copy()

    # Parameters that should be converted to float
    float_params = ['temperature', 'top_p', 'frequency_penalty', 'presence_penalty']
    # Parameters that should be converted to int
    int_params = ['max_tokens', 'n', 'seed', 'timeout']

    for param in float_params:
        if param in converted and isinstance(converted[param], str):
            try:
                converted[param] = float(converted[param])
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails

    for param in int_params:
        if param in converted and isinstance(converted[param], str):
            try:
                converted[param] = int(converted[param])
            except (ValueError, TypeError):
                pass  # Keep original value if conversion fails

    return converted


def get_chat_model(provider: ModelProvider, name: str, **kwargs: Any) -> RunnableLambda:
    # Convert string numeric parameters to proper types
    kwargs = _convert_numeric_params(kwargs)

    api_key = kwargs.pop("api_key", None) or get_api_key(provider.name)
    api_base = kwargs.pop("api_base", None) or get_base_url(provider)

    if provider == ModelProvider.OPENAI_AZURE:
        kwargs.setdefault("custom_llm_provider", "azure")
        version = dotenv.get_dotenv_value("OPENAI_API_VERSION")
        if version:
            kwargs.setdefault("api_version", version)

    async def _chat(messages: List[BaseMessage]) -> AsyncIterator[str]:
        llm_messages = _to_litellm_messages(messages)
        # Await the coroutine returned by `litellm.acompletion` to obtain the
        # stream wrapper that implements `__aiter__`, then iterate over it.
        stream_wrapper = await litellm.acompletion(
            model=name,
            messages=llm_messages,
            stream=True,
            api_key=api_key,
            api_base=api_base,
            **kwargs,
        )
        async for chunk in cast(AsyncIterator[Any], stream_wrapper):
            text = parse_chunk(chunk)
            if text:
                yield text

    return RunnableLambda(lambda msgs: _chat(msgs), afunc=_chat, name=f"litellm_chat_{name}")


def get_embedding_model(provider: ModelProvider, name: str, **kwargs: Any) -> LiteLLMEmbeddings:
    api_key = kwargs.pop("api_key", None) or get_api_key(provider.name)
    api_base = kwargs.pop("api_base", None) or get_base_url(provider)
    if provider == ModelProvider.OPENAI_AZURE:
        kwargs.setdefault("custom_llm_provider", "azure")
        version = dotenv.get_dotenv_value("OPENAI_API_VERSION")
        if version:
            kwargs.setdefault("api_version", version)
    return LiteLLMEmbeddings(model=name, api_key=api_key, api_base=api_base, **kwargs)

# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def get_model(type: ModelType, provider: ModelProvider, name: str, **kwargs: Any) -> Union[RunnableLambda, LiteLLMEmbeddings]:
    if type == ModelType.CHAT:
        return get_chat_model(provider, name, **kwargs)
    elif type == ModelType.EMBEDDING:
        return get_embedding_model(provider, name, **kwargs)
    else:
        raise ValueError(f"Unsupported model type: {type}")
    
def get_rate_limiter(
    provider: ModelProvider, name: str, requests: int, input: int, output: int
) -> RateLimiter:
    # get or create
    key = f"{provider.name}\\{name}"
    rate_limiters[key] = limiter = rate_limiters.get(key, RateLimiter(seconds=60))
    # always update
    limiter.limits["requests"] = requests or 0
    limiter.limits["input"] = input or 0
    limiter.limits["output"] = output or 0
    return limiter



