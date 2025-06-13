from enum import Enum
import os
from typing import Any, List, Optional, Iterator, AsyncIterator

from litellm import completion, acompletion, embedding
from python.helpers import dotenv
from python.helpers.dotenv import load_dotenv
from python.helpers.rate_limiter import RateLimiter

from langchain_core.language_models.chat_models import SimpleChatModel, ChatGenerationChunk
from langchain_core.callbacks.manager import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.messages import BaseMessage, AIMessageChunk
from langchain.embeddings.base import Embeddings

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

LITELLM_PROVIDER_MAP = {
    "OPENAI": "openai",
    "ANTHROPIC": "anthropic",
    "GROQ": "groq",
    "GOOGLE": "gemini",
    "MISTRALAI": "mistral",
    "OLLAMA": "ollama",
    "HUGGINGFACE": "huggingface",
    "OPENAI_AZURE": "azure",
    "DEEPSEEK": "deepseek",
    "SAMBANOVA": "sambanova",
}

def configure_litellm_environment():
    env_mappings = {
        "API_KEY_OPENAI": "OPENAI_API_KEY",
        "API_KEY_ANTHROPIC": "ANTHROPIC_API_KEY",
        "API_KEY_GROQ": "GROQ_API_KEY",
        "API_KEY_GOOGLE": "GOOGLE_API_KEY",
        "API_KEY_MISTRAL": "MISTRAL_API_KEY",
        "API_KEY_OLLAMA": "OLLAMA_API_KEY",
        "API_KEY_HUGGINGFACE": "HUGGINGFACE_API_KEY",
        "API_KEY_OPENAI_AZURE": "AZURE_API_KEY",
        "API_KEY_DEEPSEEK": "DEEPSEEK_API_KEY",
        "API_KEY_SAMBANOVA": "SAMBANOVA_API_KEY",
    }
    for a0, llm in env_mappings.items():
        val = dotenv.get_dotenv_value(a0)
        if val and not os.getenv(llm):
            os.environ[llm] = val


def get_api_key(service: str) -> str:
    return (
        dotenv.get_dotenv_value(f"API_KEY_{service.upper()}")
        or dotenv.get_dotenv_value(f"{service.upper()}_API_KEY")
        or dotenv.get_dotenv_value(f"{service.upper()}_API_TOKEN")
        or "None"
    )

def get_rate_limiter(
    provider: ModelProvider, name: str, requests: int, input: int, output: int
) -> RateLimiter:
    key = f"{provider.name}\{name}"
    rate_limiters[key] = limiter = rate_limiters.get(key, RateLimiter(seconds=60))
    limiter.limits["requests"] = requests or 0
    limiter.limits["input"] = input or 0
    limiter.limits["output"] = output or 0
    return limiter

def parse_chunk(chunk: Any):
    if isinstance(chunk, str):
        content = chunk
    elif hasattr(chunk, "content"):
        content = str(chunk.content)
    else:
        content = str(chunk)
    return content

class LiteLLMChatWrapper(SimpleChatModel):
    def __init__(self, model: str, provider: str, **kwargs: Any):
        super().__init__()
        self.model = f"{provider}/{model}" if provider != "openai" else model
        self.kwargs = kwargs

    @property
    def _llm_type(self) -> str:
        return "litellm-chat"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        result = []
        for m in messages:
            role = m.type if m.type != "human" else "user"
            result.append({"role": role, "content": m.content})
        return result

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        msgs = self._convert_messages(messages)
        resp = completion(
            model=self.model, messages=msgs, stop=stop, **{**self.kwargs, **kwargs}
        )
        delta = resp["choices"][0].get("message")
        return delta.get("content") if isinstance(delta, dict) else getattr(delta, "content", "")

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        msgs = self._convert_messages(messages)
        for chunk in completion(
            model=self.model,
            messages=msgs,
            stream=True,
            stop=stop,
            **{**self.kwargs, **kwargs},
        ):
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "") if isinstance(delta, dict) else getattr(delta, "content", "")
            yield ChatGenerationChunk(message=AIMessageChunk(content=content))

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        msgs = self._convert_messages(messages)
        async for chunk in acompletion(
            model=self.model,
            messages=msgs,
            stream=True,
            stop=stop,
            **{**self.kwargs, **kwargs},
        ):
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content", "") if isinstance(delta, dict) else getattr(delta, "content", "")
            yield ChatGenerationChunk(message=AIMessageChunk(content=content))

class LiteLLMEmbeddingWrapper(Embeddings):
    def __init__(self, model: str, provider: str, **kwargs: Any):
        self.model = f"{provider}/{model}" if provider != "openai" else model
        self.kwargs = kwargs

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        resp = embedding(model=self.model, input=texts, **self.kwargs)
        return [
            item.get("embedding") if isinstance(item, dict) else item.embedding
            for item in resp.data
        ]

    def embed_query(self, text: str) -> List[float]:
        resp = embedding(model=self.model, input=[text], **self.kwargs)
        item = resp.data[0]
        return item.get("embedding") if isinstance(item, dict) else item.embedding

def get_litellm_chat(model_name: str, provider: str, **kwargs: Any):
    configure_litellm_environment()
    api_key = kwargs.pop("api_key", None) or get_api_key(provider)
    base_url = kwargs.pop("base_url", None) or dotenv.get_dotenv_value(f"{provider.upper()}_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return LiteLLMChatWrapper(model=model_name, provider=provider, **kwargs)

def get_litellm_embedding(model_name: str, provider: str, **kwargs: Any):
    configure_litellm_environment()
    api_key = kwargs.pop("api_key", None) or get_api_key(provider)
    base_url = kwargs.pop("base_url", None) or dotenv.get_dotenv_value(f"{provider.upper()}_BASE_URL")
    if base_url:
        kwargs["api_base"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return LiteLLMEmbeddingWrapper(model=model_name, provider=provider, **kwargs)

def get_model(type: ModelType, provider: ModelProvider, name: str, **kwargs: Any):
    provider_name = LITELLM_PROVIDER_MAP.get(provider.name, provider.name.lower())
    if type == ModelType.CHAT:
        return get_litellm_chat(name, provider_name, **kwargs)
    elif type == ModelType.EMBEDDING:
        return get_litellm_embedding(name, provider_name, **kwargs)
    else:
        raise ValueError(f"Unsupported model type: {type}")
