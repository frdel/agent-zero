from enum import Enum
import os
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
from pydantic.v1.types import SecretStr
from python.helpers.dotenv import load_dotenv

# environment variables
load_dotenv()

# Configuration
DEFAULT_TEMPERATURE = 0.0


class ModelType(Enum):
    CHAT = "Chat"
    EMBEDDING = "Embedding"


class ModelProvider(Enum):
    ANTHROPIC = "Anthropic"
    HUGGINGFACE = "HuggingFace"
    GOOGLE = "Google"
    GROQ = "Groq"
    LMSTUDIO = "LM Studio"
    MISTRALAI = "Mistral AI"
    OLLAMA = "Ollama"
    OPENAI = "OpenAI"
    OPENAI_AZURE = "OpenAI Azure"
    OPENROUTER = "OpenRouter"
    SAMBANOVA = "Sambanova"
    OTHER = "Other"


# Utility function to get API keys from environment variables
def get_api_key(service):
    return os.getenv(f"API_KEY_{service.upper()}") or os.getenv(f"{service.upper()}_API_KEY") or "None"


def get_model(type: ModelType, provider: ModelProvider, name: str, **kwargs):
    fnc_name = f"get_{provider.name.lower()}_{type.name.lower()}"  # function name of model getter
    model = globals()[fnc_name](name, **kwargs)  # call function by name
    return model


# Ollama models
def get_ollama_chat(
    model_name: str,
    temperature=DEFAULT_TEMPERATURE,
    base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
    num_ctx=8192,
    **kwargs,
):
    return ChatOllama(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        num_ctx=num_ctx,
        **kwargs,
    )


def get_ollama_embedding(
    model_name: str,
    temperature=DEFAULT_TEMPERATURE,
    base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434",
    **kwargs,
):
    return OllamaEmbeddings(
        model=model_name, temperature=temperature, base_url=base_url, **kwargs
    )


# HuggingFace models
def get_huggingface_chat(
    model_name: str,
    api_key=get_api_key("huggingface"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    # different naming convention here
    if not api_key:
        api_key = os.environ["HUGGINGFACEHUB_API_TOKEN"]

    # Initialize the HuggingFaceEndpoint with the specified model and parameters
    llm = HuggingFaceEndpoint(
        repo_id=model_name,
        task="text-generation",
        do_sample=True,
        temperature=temperature,
        **kwargs,
    )

    # Initialize the ChatHuggingFace with the configured llm
    return ChatHuggingFace(llm=llm)


def get_huggingface_embedding(model_name: str, **kwargs):
    return HuggingFaceEmbeddings(model_name=model_name, **kwargs)


# LM Studio and other OpenAI compatible interfaces
def get_lmstudio_chat(
    model_name: str,
    temperature=DEFAULT_TEMPERATURE,
    base_url=os.getenv("LM_STUDIO_BASE_URL") or "http://127.0.0.1:1234/v1",
    **kwargs,
):
    return ChatOpenAI(model_name=model_name, base_url=base_url, temperature=temperature, api_key="none", **kwargs)  # type: ignore


def get_lmstudio_embedding(
    model_name: str,
    base_url=os.getenv("LM_STUDIO_BASE_URL") or "http://127.0.0.1:1234/v1",
    **kwargs,
):
    return OpenAIEmbeddings(model=model_name, api_key="none", base_url=base_url, check_embedding_ctx_length=False, **kwargs)  # type: ignore


# Anthropic models
def get_anthropic_chat(
    model_name: str,
    api_key=get_api_key("anthropic"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return ChatAnthropic(model_name=model_name, temperature=temperature, api_key=api_key, **kwargs)  # type: ignore


# right now anthropic does not have embedding models, but that might change
def get_anthropic_embedding(
    model_name: str,
    api_key=get_api_key("anthropic"),
    **kwargs,
):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


# OpenAI models
def get_openai_chat(
    model_name: str,
    api_key=get_api_key("openai"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key, **kwargs)  # type: ignore


def get_openai_instruct(
    model_name: str,
    api_key=get_api_key("openai"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return OpenAI(model=model_name, temperature=temperature, api_key=api_key, **kwargs)  # type: ignore


def get_openai_embedding(model_name: str, api_key=get_api_key("openai"), **kwargs):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


def get_azure_openai_chat(
    deployment_name: str,
    api_key=get_api_key("openai_azure"),
    temperature=DEFAULT_TEMPERATURE,
    azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT"),
    **kwargs,
):
    return AzureChatOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint, **kwargs)  # type: ignore


def get_azure_openai_instruct(
    deployment_name: str,
    api_key=get_api_key("openai_azure"),
    temperature=DEFAULT_TEMPERATURE,
    azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT"),
    **kwargs,
):
    return AzureOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint, **kwargs)  # type: ignore


def get_azure_openai_embedding(
    deployment_name: str,
    api_key=get_api_key("openai_azure"),
    azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT"),
    **kwargs,
):
    return AzureOpenAIEmbeddings(deployment_name=deployment_name, api_key=api_key, azure_endpoint=azure_endpoint, **kwargs)  # type: ignore


# Google models
def get_google_chat(
    model_name: str,
    api_key=get_api_key("google"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return GoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key, safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}, **kwargs)  # type: ignore


def get_google_embedding(
    model_name: str,
    api_key=get_api_key("google"),
    **kwargs,
):
    return google_embeddings.GoogleGenerativeAIEmbeddings(model=model_name, api_key=api_key, **kwargs)  # type: ignore


# Mistral models
def get_mistral_chat(
    model_name: str,
    api_key=get_api_key("mistral"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return ChatMistralAI(model=model_name, temperature=temperature, api_key=api_key, **kwargs)  # type: ignore


# Groq models
def get_groq_chat(
    model_name: str,
    api_key=get_api_key("groq"),
    temperature=DEFAULT_TEMPERATURE,
    **kwargs,
):
    return ChatGroq(model_name=model_name, temperature=temperature, api_key=api_key, **kwargs)  # type: ignore


# OpenRouter models
def get_openrouter_chat(
    model_name: str,
    api_key=get_api_key("openrouter"),
    temperature=DEFAULT_TEMPERATURE,
    base_url=os.getenv("OPEN_ROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
    **kwargs,
):
    return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, base_url=base_url, **kwargs)  # type: ignore


def get_openrouter_embedding(
    model_name: str,
    api_key=get_api_key("openrouter"),
    base_url=os.getenv("OPEN_ROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
    **kwargs,
):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore


# Sambanova models
def get_sambanova_chat(
    model_name: str,
    api_key=get_api_key("sambanova"),
    temperature=DEFAULT_TEMPERATURE,
    base_url=os.getenv("SAMBANOVA_BASE_URL") or "https://fast-api.snova.ai/v1",
    max_tokens=1024,
    **kwargs,
):
    return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, base_url=base_url, max_tokens=max_tokens, **kwargs)  # type: ignore


# right now sambanova does not have embedding models, but that might change
def get_sambanova_embedding(
    model_name: str,
    api_key=get_api_key("sambanova"),
    base_url=os.getenv("SAMBANOVA_BASE_URL") or "https://fast-api.snova.ai/v1",
    **kwargs,
):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore


# Other OpenAI compatible models
def get_other_chat(
    model_name: str,
    api_key=None,
    temperature=DEFAULT_TEMPERATURE,
    base_url=None,
    **kwargs,
):
    return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, base_url=base_url, **kwargs)  # type: ignore


def get_other_embedding(model_name: str, api_key=None, base_url=None, **kwargs):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url, **kwargs)  # type: ignore
