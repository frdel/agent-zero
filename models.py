from enum import Enum
import os
from typing import Any, Union
from langchain_openai import (
    ChatOpenAI,
    OpenAI,
    OpenAIEmbeddings,
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    AzureOpenAI,
)
from langchain_community.llms.ollama import Ollama
from langchain_ollama import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_huggingface import (
    HuggingFaceEmbeddings,
    ChatHuggingFace,
    HuggingFaceEndpoint,
)
from langchain_google_genai import (
    GoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
    embeddings as google_embeddings,
)
from langchain_mistralai import ChatMistralAI

# from pydantic.v1.types import SecretStr
from python.helpers import dotenv, runtime
from python.helpers.dotenv import load_dotenv
from python.helpers.rate_limiter import RateLimiter
from python.helpers.print_style import PrintStyle
# environment variables
load_dotenv()


class ModelType(Enum):
    CHAT = "Chat"
    EMBEDDING = "Embedding"


class ModelProvider(Enum):
    ANTHROPIC = "Anthropic"
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


# Utility function to get API keys from environment variables
def get_api_key(service):
    return (
        dotenv.get_dotenv_value(f"API_KEY_{service.upper()}")
        or dotenv.get_dotenv_value(f"{service.upper()}_API_KEY")
        or "None"
    )


def get_model(type: ModelType, provider: ModelProvider, name: str, **kwargs):
    fnc_name = f"get_{provider.name.lower()}_{type.name.lower()}"  # function name of model getter
    model = globals()[fnc_name](name, **kwargs)  # call function by name
    return model


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


def parse_chunk(chunk: Any):
    if isinstance(chunk, str):
        content = chunk
    elif hasattr(chunk, "content"):
        content = str(chunk.content)
    else:
        content = str(chunk)
    return content


# Ollama models
def get_ollama_base_url():
    return (
        dotenv.get_dotenv_value("OLLAMA_BASE_URL")
        or f"http://{runtime.get_local_url()}:11434"
    )


def get_ollama_chat(
    model_name: str,
    base_url=None,
    num_ctx=8192,
    **kwargs,
):
    if not base_url:
        base_url = get_ollama_base_url()

    if "max_tokens" in kwargs:
        kwargs["max_output_tokens"] = kwargs.get("max_tokens", 1024)
        kwargs.pop("num_predict", None)

    return ChatOllama(
        model=model_name,
        base_url=base_url,
        num_ctx=num_ctx,
        **kwargs,
    )


def get_ollama_embedding(
    model_name: str,
    base_url=None,
    num_ctx=8192,
    **kwargs,
):
    if not base_url:
        base_url = get_ollama_base_url()
    return OllamaEmbeddings(
        model=model_name, base_url=base_url, num_ctx=num_ctx, **kwargs
    )


# HuggingFace models
def get_huggingface_chat(
    model_name: str,
    api_key=None,
    **kwargs,
):
    # different naming convention here
    if not api_key:
        api_key = get_api_key("huggingface") or os.environ["HUGGINGFACEHUB_API_TOKEN"]

    if "max_tokens" in kwargs:
        kwargs["max_new_tokens"] = kwargs.get("max_tokens", 1024)
        kwargs.pop("max_tokens", None)

    # Initialize the HuggingFaceEndpoint with the specified model and parameters
    llm = HuggingFaceEndpoint(
        repo_id=model_name,
        task="text-generation",
        do_sample=True,
        **kwargs,
    )

    # Initialize the ChatHuggingFace with the configured llm
    return ChatHuggingFace(llm=llm)


def get_huggingface_embedding(model_name: str, **kwargs):
    return HuggingFaceEmbeddings(model_name=model_name, **kwargs)


# LM Studio and other OpenAI compatible interfaces
def get_lmstudio_base_url():
    return (
        dotenv.get_dotenv_value("LM_STUDIO_BASE_URL")
        or f"http://{runtime.get_local_url()}:1234/v1"
    )


def get_lmstudio_chat(
    model_name: str,
    base_url=None,
    **kwargs,
):
    if not base_url:
        base_url = get_lmstudio_base_url()
    return ChatOpenAI(model_name=model_name, base_url=base_url, api_key="none", **kwargs)  # type: ignore


def get_lmstudio_embedding(
    model_name: str,
    base_url=None,
    **kwargs,
):
    if not base_url:
        base_url = get_lmstudio_base_url()
    return OpenAIEmbeddings(model=model_name, api_key="none", base_url=base_url, check_embedding_ctx_length=False, **kwargs)  # type: ignore


# Anthropic models
def get_anthropic_chat(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("anthropic")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
        )
    if int(kwargs.get("chat_model_reasoning_tokens", 0)) > 0:
        kwargs["temperature"] = 1  # Anthropic requires temperature to be 1 for reasoning
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": int(kwargs["chat_model_reasoning_tokens"])}
        PrintStyle(font_color="blue", padding=True).print(
            f"get_anthropic_chat: reasoning_tokens: {int(kwargs['chat_model_reasoning_tokens'])}"
        )
    if "chat_model_reasoning_tokens" in kwargs: kwargs.pop("chat_model_reasoning_tokens")
    if "chat_model_reasoning_effort" in kwargs: kwargs.pop("chat_model_reasoning_effort")
    return ChatAnthropic(model_name=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore


# right now anthropic does not have embedding models, but that might change
def get_anthropic_embedding(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("anthropic")
    return OpenAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


# OpenAI models
def get_openai_chat(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("openai")
    if kwargs.get("chat_model_reasoning_effort", "none").lower() in ["low", "medium", "high"] and model_name.startswith("o"):
        kwargs["reasoning_effort"] = kwargs["chat_model_reasoning_effort"].lower()
        PrintStyle(font_color="blue", padding=True).print(
            f"get_openai_chat: reasoning_effort: {str(kwargs['reasoning_effort'])}"
        )
    if "chat_model_reasoning_effort" in kwargs: kwargs.pop("chat_model_reasoning_effort")
    if "chat_model_reasoning_tokens" in kwargs: kwargs.pop("chat_model_reasoning_tokens")
    return ChatOpenAI(model_name=model_name, api_key=api_key, **kwargs)  # type: ignore


def get_openai_embedding(model_name: str, api_key=None, **kwargs):
    if not api_key:
        api_key = get_api_key("openai")
    return OpenAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


def get_openai_azure_chat(
    deployment_name: str,
    api_key=None,
    azure_endpoint=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("openai_azure")
    if not azure_endpoint:
        azure_endpoint = dotenv.get_dotenv_value("OPENAI_AZURE_ENDPOINT")
    return AzureChatOpenAI(deployment_name=deployment_name, api_key=api_key, azure_endpoint=azure_endpoint, **kwargs)  # type: ignore


def get_openai_azure_embedding(
    deployment_name: str,
    api_key=None,
    azure_endpoint=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("openai_azure")
    if not azure_endpoint:
        azure_endpoint = dotenv.get_dotenv_value("OPENAI_AZURE_ENDPOINT")
    return AzureOpenAIEmbeddings(deployment_name=deployment_name, api_key=api_key, azure_endpoint=azure_endpoint, **kwargs)  # type: ignore


# Google models
def get_google_chat(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("google")
    if "max_tokens" in kwargs:
        kwargs["max_output_tokens"] = kwargs.get("max_tokens", 1024)
        kwargs.pop("max_tokens", None)
    return GoogleGenerativeAI(model=model_name, google_api_key=api_key, safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}, **kwargs)  # type: ignore


def get_google_embedding(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("google")
    return google_embeddings.GoogleGenerativeAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


# Mistral models
def get_mistralai_chat(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("mistral")
    return ChatMistralAI(model=model_name, api_key=api_key, **kwargs)  # type: ignore


# Groq models
def get_groq_chat(
    model_name: str,
    api_key=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("groq")
    return ChatGroq(model_name=model_name, api_key=api_key, **kwargs)  # type: ignore


# DeepSeek models
def get_deepseek_chat(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("deepseek")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        )

    return ChatOpenAI(api_key=api_key, model=model_name, base_url=base_url, **kwargs)  # type: ignore

# OpenRouter models
def get_openrouter_chat(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("openrouter")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("OPEN_ROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
    if (
        kwargs.get("chat_model_reasoning_effort", "none").lower() in ["low", "medium", "high"]
        and kwargs.get("chat_model_reasoning_tokens", 0) > 0
    ):
        reasoning: dict[str, Any] = {}
        if model_name.startswith("openai/o"):
            reasoning: dict[str, Any] = {
                "effort": kwargs["chat_model_reasoning_effort"].lower(),
                "exclude": True,
            }
            PrintStyle(font_color="grey", padding=True).print(
                f"get_openrouter_chat/openai: reasoning_effort: {str(kwargs['chat_model_reasoning_effort'])}"
            )
            if "model_kwargs" in kwargs:
                kwargs["model_kwargs"]["reasoning_effort"] = reasoning["effort"]
            else:
                kwargs["model_kwargs"] = {"reasoning_effort": reasoning["effort"]}
        elif model_name.startswith("anthropic/claude-") and "3.5" not in model_name:  # claude > 3.5 has reasoning built i
            reasoning: dict[str, Any] = {
                "max_tokens": int(kwargs["chat_model_reasoning_tokens"]),
                "exclude": True,
            }
            PrintStyle(font_color="grey", padding=True).print(
                f"get_openrouter_chat/anthropic: reasoning_tokens: {int(kwargs['chat_model_reasoning_tokens'])}"
            )
            if "extra_body" in kwargs:
                kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": reasoning["max_tokens"] }}
            else:
                kwargs = {"extra_body": {"thinking": {"type": "enabled", "budget_tokens": reasoning["max_tokens"]}}}
        if bool(reasoning):
            if "extra_body" in kwargs:
                kwargs["extra_body"]["reasoning"] = reasoning
                kwargs["extra_body"]["include_reasoning"] = False
            else:
                kwargs["extra_body"] = dict[Any, Any]({"reasoning": reasoning, "include_reasoning": False})

    if "chat_model_reasoning_effort" in kwargs: kwargs.pop("chat_model_reasoning_effort")
    if "chat_model_reasoning_tokens" in kwargs: kwargs.pop("chat_model_reasoning_tokens")
    return ChatOpenAI(api_key=api_key, model=model_name, base_url=base_url, **kwargs)  # type: ignore


def get_openrouter_embedding(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("openrouter")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("OPEN_ROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore


# Sambanova models
def get_sambanova_chat(
    model_name: str,
    api_key=None,
    base_url=None,
    max_tokens=1024,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("sambanova")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("SAMBANOVA_BASE_URL")
            or "https://fast-api.snova.ai/v1"
        )
    return ChatOpenAI(api_key=api_key, model=model_name, base_url=base_url, max_tokens=max_tokens, **kwargs)  # type: ignore


# right now sambanova does not have embedding models, but that might change
def get_sambanova_embedding(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    if not api_key:
        api_key = get_api_key("sambanova")
    if not base_url:
        base_url = (
            dotenv.get_dotenv_value("SAMBANOVA_BASE_URL")
            or "https://fast-api.snova.ai/v1"
        )
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore


# Other OpenAI compatible models
def get_other_chat(
    model_name: str,
    api_key=None,
    base_url=None,
    **kwargs,
):
    return ChatOpenAI(api_key=api_key, model=model_name, base_url=base_url, **kwargs)  # type: ignore


def get_other_embedding(model_name: str, api_key=None, base_url=None, **kwargs):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore
