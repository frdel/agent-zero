from enum import Enum
import os
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    Iterator,
    AsyncIterator,
    Tuple,
    TypedDict,
)

from litellm import completion, acompletion, embedding
from python.helpers import dotenv
from python.helpers.dotenv import load_dotenv
from python.helpers.rate_limiter import RateLimiter
from python.helpers.tokens import approximate_tokens

from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.outputs.chat_generation import ChatGenerationChunk
from langchain_core.callbacks.manager import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from langchain_core.messages import (
    BaseMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)
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
    AZURE = "OpenAI Azure"
    OPENROUTER = "OpenRouter"
    SAMBANOVA = "Sambanova"
    OTHER = "Other"


class ChatChunk(TypedDict):
    """Simplified response chunk for chat models."""

    response_delta: str
    reasoning_delta: str


rate_limiters: dict[str, RateLimiter] = {}


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
    base_url_mappings = {
        "OPENAI_BASE_URL": "OPENAI_API_BASE",
        "ANTHROPIC_BASE_URL": "ANTHROPIC_API_BASE",
        "GROQ_BASE_URL": "GROQ_API_BASE",
        "GOOGLE_BASE_URL": "GOOGLE_API_BASE",
        "MISTRAL_BASE_URL": "MISTRAL_API_BASE",
        "OLLAMA_BASE_URL": "OLLAMA_API_BASE",
        "HUGGINGFACE_BASE_URL": "HUGGINGFACE_API_BASE",
        "AZURE_BASE_URL": "AZURE_API_BASE",
        "DEEPSEEK_BASE_URL": "DEEPSEEK_API_BASE",
        "SAMBANOVA_BASE_URL": "SAMBANOVA_API_BASE",
    }
    for a0, llm in env_mappings.items():
        val = dotenv.get_dotenv_value(a0)
        if val and not os.getenv(llm):
            os.environ[llm] = val
    for a0_base, llm_base in base_url_mappings.items():
        val = dotenv.get_dotenv_value(a0_base)
        if val and not os.getenv(llm_base):
            os.environ[llm_base] = val


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
    key = f"{provider.name}\\{name}"
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


def _parse_chunk(chunk: Any) -> ChatChunk:
    delta = chunk["choices"][0].get("delta", {})
    message = chunk["choices"][0].get("model_extra", {}).get("message", {})
    response_delta = (
        delta.get("content", "")
        if isinstance(delta, dict)
        else getattr(delta, "content", "")
    ) or (
        message.get("content", "") 
        if isinstance(message, dict) 
        else getattr(message, "content", "")
    )
    reasoning_delta = (
        delta.get("reasoning_content", "")
        if isinstance(delta, dict)
        else getattr(delta, "reasoning_content", "")
    )
    return ChatChunk(reasoning_delta=reasoning_delta, response_delta=response_delta)


class LiteLLMChatWrapper(SimpleChatModel):
    model_name: str
    provider: str
    kwargs: dict = {}

    def __init__(self, model: str, provider: str, **kwargs: Any):
        model_value = f"{provider}/{model}"
        super().__init__(model_name=model_value, provider=provider, kwargs=kwargs)  # type: ignore

    @property
    def _llm_type(self) -> str:
        return "litellm-chat"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        result = []
        # Map LangChain message types to LiteLLM roles
        role_mapping = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "tool": "tool",
        }
        for m in messages:
            role = role_mapping.get(m.type, m.type)
            message_dict = {"role": role, "content": m.content}

            # Handle tool calls for AI messages
            tool_calls = getattr(m, "tool_calls", None)
            if tool_calls:
                # Convert LangChain tool calls to LiteLLM format
                new_tool_calls = []
                for tool_call in tool_calls:
                    # Ensure arguments is a JSON string
                    args = tool_call["args"]
                    if isinstance(args, dict):
                        import json

                        args_str = json.dumps(args)
                    else:
                        args_str = str(args)

                    new_tool_calls.append(
                        {
                            "id": tool_call.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tool_call["name"],
                                "arguments": args_str,
                            },
                        }
                    )
                message_dict["tool_calls"] = new_tool_calls

            # Handle tool call ID for ToolMessage
            tool_call_id = getattr(m, "tool_call_id", None)
            if tool_call_id:
                message_dict["tool_call_id"] = tool_call_id

            result.append(message_dict)
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
            model=self.model_name, messages=msgs, stop=stop, **{**self.kwargs, **kwargs}
        )
        parsed = _parse_chunk(resp)
        return parsed["response_delta"]

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        msgs = self._convert_messages(messages)
        for chunk in completion(
            model=self.model_name,
            messages=msgs,
            stream=True,
            stop=stop,
            **{**self.kwargs, **kwargs},
        ):
            parsed = _parse_chunk(chunk)
            # Only yield chunks with non-None content
            if parsed["response_delta"]:
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=parsed["response_delta"])
                )

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        msgs = self._convert_messages(messages)
        response = await acompletion(
            model=self.model_name,
            messages=msgs,
            stream=True,
            stop=stop,
            **{**self.kwargs, **kwargs},
        )
        async for chunk in response:  # type: ignore
            parsed = _parse_chunk(chunk)
            # Only yield chunks with non-None content
            if parsed["response_delta"]:
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content=parsed["response_delta"])
                )

    async def unified_call(
        self,
        system_message="",
        user_message="",
        messages: List[BaseMessage] = [],
        response_callback: Callable[[str, str], Awaitable[None]] | None = None,
        reasoning_callback: Callable[[str, str], Awaitable[None]] | None = None,
        tokens_callback: Callable[[str, int], Awaitable[None]] | None = None,
        **kwargs: Any,
    ) -> Tuple[str, str]:
        # construct messages
        if system_message:
            messages.insert(0, SystemMessage(content=system_message))
        if user_message:
            messages.append(HumanMessage(content=user_message))

        # convert to litellm format
        msgs_conv = self._convert_messages(messages)

        # call model
        _completion = await acompletion(
            model=self.model_name,
            messages=msgs_conv,
            stream=True,
            **{**self.kwargs, **kwargs},
        )

        # results
        reasoning = ""
        response = ""

        # iterate over chunks
        async for chunk in _completion:  # type: ignore
            parsed = _parse_chunk(chunk)
            # collect reasoning delta and call callbacks
            if parsed["reasoning_delta"]:
                reasoning += parsed["reasoning_delta"]
                if reasoning_callback:
                    await reasoning_callback(parsed["reasoning_delta"], reasoning)
                if tokens_callback:
                    await tokens_callback(
                        parsed["reasoning_delta"],
                        approximate_tokens(parsed["reasoning_delta"]),
                    )
            # collect response delta and call callbacks
            if parsed["response_delta"]:
                response += parsed["response_delta"]
                if response_callback:
                    await response_callback(parsed["response_delta"], response)
                if tokens_callback:
                    await tokens_callback(
                        parsed["response_delta"],
                        approximate_tokens(parsed["response_delta"]),
                    )

        # return complete results
        return response, reasoning


class BrowserCompatibleChatWrapper(LiteLLMChatWrapper):
    """
    A wrapper for browser agent that can filter/sanitize messages
    before sending them to the LLM.
    """

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        # In the future, message filtering logic can be added here.
        result = super()._call(messages, stop, run_manager, **kwargs)
        return result

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        # In the future, message filtering logic can be added here.
        async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
            yield chunk


class LiteLLMEmbeddingWrapper(Embeddings):
    model_name: str
    kwargs: dict = {}

    def __init__(self, model: str, provider: str, **kwargs: Any):
        self.model_name = f"{provider}/{model}" if provider != "openai" else model
        self.kwargs = kwargs

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        resp = embedding(model=self.model_name, input=texts, **self.kwargs)
        return [
            item.get("embedding") if isinstance(item, dict) else item.embedding
            for item in resp.data
        ]

    def embed_query(self, text: str) -> List[float]:
        resp = embedding(model=self.model_name, input=[text], **self.kwargs)
        item = resp.data[0]
        return item.get("embedding") if isinstance(item, dict) else item.embedding


class LocalSentenceTransformerWrapper(Embeddings):
    """Local wrapper for sentence-transformers models to avoid HuggingFace API calls"""

    def __init__(self, model_name: str, **kwargs: Any):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers library is required for local embeddings. Install with: pip install sentence-transformers"
            )

        # Remove the "sentence-transformers/" prefix if present
        if model_name.startswith("sentence-transformers/"):
            model_name = model_name[len("sentence-transformers/") :]

        self.model = SentenceTransformer(model_name, **kwargs)
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings

    def embed_query(self, text: str) -> List[float]:
        embedding = self.model.encode([text], convert_to_tensor=False)
        result = (
            embedding[0].tolist() if hasattr(embedding[0], "tolist") else embedding[0]
        )
        return result


def _get_litellm_chat(
    cls: type = LiteLLMChatWrapper,
    model_name: str = "",
    provider_name: str = "",
    **kwargs: Any,
):
    provider_name = provider_name.lower()

    configure_litellm_environment()
    # Use original provider name for API key lookup, fallback to mapped provider name
    api_key = kwargs.pop("api_key", None) or get_api_key(provider_name)

    # litellm will pick up base_url from env. We just need to control the api_key.
    base_url = dotenv.get_dotenv_value(f"{provider_name.upper()}_BASE_URL")

    # If a base_url is set, ensure api_key is not passed to litellm
    if base_url:
        if "api_key" in kwargs:
            del kwargs["api_key"]
    # Only pass API key if no base_url is set and key is not a placeholder
    elif api_key and api_key not in ("None", "NA"):
        kwargs["api_key"] = api_key

    # for openrouter add app reference
    if provider_name == "openrouter":
        kwargs["extra_headers"] = {
            "HTTP-Referer": "https://agent-zero.ai",
            "X-Title": "Agent Zero",
        }

    return cls(model=model_name, provider=provider_name, **kwargs)


def get_litellm_embedding(model_name: str, provider: str, **kwargs: Any):
    # Check if this is a local sentence-transformers model
    if provider == "huggingface" and model_name.startswith("sentence-transformers/"):
        # Use local sentence-transformers instead of LiteLLM for local models
        return LocalSentenceTransformerWrapper(model_name=model_name, **kwargs)

    configure_litellm_environment()
    # Use original provider name for API key lookup, fallback to mapped provider name
    api_key = kwargs.pop("api_key", None) or get_api_key(provider)

    # litellm will pick up base_url from env. We just need to control the api_key.
    base_url = dotenv.get_dotenv_value(f"{provider.upper()}_BASE_URL")

    # If a base_url is set, ensure api_key is not passed to litellm
    if base_url:
        if "api_key" in kwargs:
            del kwargs["api_key"]
    # Only pass API key if no base_url is set and key is not a placeholder
    elif api_key and api_key not in ("None", "NA"):
        kwargs["api_key"] = api_key

    return LiteLLMEmbeddingWrapper(model=model_name, provider=provider, **kwargs)


def get_model(type: ModelType, provider: ModelProvider, name: str, **kwargs: Any):
    provider_name = provider.name.lower()
    kwargs = _normalize_chat_kwargs(kwargs)
    if type == ModelType.CHAT:
        return _get_litellm_chat(LiteLLMChatWrapper, name, provider_name, **kwargs)
    elif type == ModelType.EMBEDDING:
        return get_litellm_embedding(name, provider_name, **kwargs)
    else:
        raise ValueError(f"Unsupported model type: {type}")


def get_chat_model(
    provider: ModelProvider, name: str, **kwargs: Any
) -> LiteLLMChatWrapper:
    provider_name = provider.name.lower()
    kwargs = _normalize_chat_kwargs(kwargs)
    model = _get_litellm_chat(LiteLLMChatWrapper, name, provider_name, **kwargs)
    return model


def get_browser_model(
    provider: ModelProvider, name: str, **kwargs: Any
) -> BrowserCompatibleChatWrapper:
    provider_name = provider.name.lower()
    kwargs = _normalize_chat_kwargs(kwargs)
    model = _get_litellm_chat(
        BrowserCompatibleChatWrapper, name, provider_name, **kwargs
    )
    return model


def get_embedding_model(
    provider: ModelProvider, name: str, **kwargs: Any
) -> LiteLLMEmbeddingWrapper | LocalSentenceTransformerWrapper:
    provider_name = provider.name.lower()
    kwargs = _normalize_embedding_kwargs(kwargs)
    model = get_litellm_embedding(name, provider_name, **kwargs)
    return model


def _normalize_chat_kwargs(kwargs: Any) -> Any:
    return kwargs


def _normalize_embedding_kwargs(kwargs: Any) -> Any:
    return kwargs
