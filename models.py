import os
from dotenv import load_dotenv
from langchain_openai import (  # type: ignore
    ChatOpenAI,
    OpenAI,
    OpenAIEmbeddings,
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    AzureOpenAI,
)
from langchain_community.llms.ollama import Ollama  # type: ignore
from langchain_community.embeddings import OllamaEmbeddings  # type: ignore
from langchain_anthropic import ChatAnthropic  # type: ignore
from langchain_groq import ChatGroq  # type: ignore
from langchain_huggingface import HuggingFaceEmbeddings  # type: ignore
from langchain_google_genai import (  # type: ignore
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)


# Load environment variables
load_dotenv()

# Configuration
DEFAULT_TEMPERATURE = 0.0


def get_api_key(service):
    return os.getenv(f"API_KEY_{service.upper()}") or os.getenv(f"{service.upper()}_API_KEY")


def get_ollama_chat(model_name: str, temperature=DEFAULT_TEMPERATURE, base_url="http://localhost:11434"):
    return Ollama(model=model_name, temperature=temperature, base_url=base_url)


def get_ollama_embedding(model_name: str, temperature=DEFAULT_TEMPERATURE):
    return OllamaEmbeddings(model=model_name, temperature=temperature)


def get_huggingface_embedding(model_name: str):
    return HuggingFaceEmbeddings(model_name=model_name)


def get_lmstudio_chat(
    model_name: str,
    base_url="http://localhost:1234/v1",
    temperature=DEFAULT_TEMPERATURE,
):
    return ChatOpenAI(model_name=model_name, base_url=base_url, temperature=temperature, api_key="none")  # type: ignore


def get_lmstudio_embedding(model_name: str, base_url="http://localhost:1234/v1"):
    return OpenAIEmbeddings(model_name=model_name, base_url=base_url)  # type: ignore


def get_anthropic_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name=model_name, temperature=temperature, api_key=api_key)  # type: ignore


def get_openai_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key)  # type: ignore


def get_openai_instruct(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return OpenAI(model=model_name, temperature=temperature, api_key=api_key)  # type: ignore


def get_openai_embedding(model_name: str, api_key=None):
    api_key = api_key or get_api_key("openai")
    return OpenAIEmbeddings(model=model_name, api_key=api_key)  # type: ignore


def get_azure_openai_chat(
    deployment_name: str,
    api_key=None,
    temperature=DEFAULT_TEMPERATURE,
    azure_endpoint=None,
):
    api_key = api_key or get_api_key("openai_azure")
    azure_endpoint = azure_endpoint or os.getenv("OPENAI_AZURE_ENDPOINT")
    return AzureChatOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint)  # type: ignore


def get_azure_openai_instruct(
    deployment_name: str,
    api_key=None,
    temperature=DEFAULT_TEMPERATURE,
    azure_endpoint=None,
):
    api_key = api_key or get_api_key("openai_azure")
    azure_endpoint = azure_endpoint or os.getenv("OPENAI_AZURE_ENDPOINT")
    return AzureOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint)  # type: ignore


def get_azure_openai_embedding(deployment_name: str, api_key=None, azure_endpoint=None):
    api_key = api_key or get_api_key("openai_azure")
    azure_endpoint = azure_endpoint or os.getenv("OPENAI_AZURE_ENDPOINT")
    return AzureOpenAIEmbeddings(deployment_name=deployment_name, api_key=api_key, azure_endpoint=azure_endpoint)  # type: ignore


def get_google_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("google")
    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key, safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE})  # type: ignore


def get_groq_chat(model_name: str, api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name=model_name, temperature=temperature, api_key=api_key)  # type: ignore


def get_openrouter(
    model_name: str = "meta-llama/llama-3.1-8b-instruct:free",
    api_key=None,
    temperature=DEFAULT_TEMPERATURE,
):
    api_key = api_key or get_api_key("openrouter")
    return ChatOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1", model=model_name, temperature=temperature)  # type: ignore


def get_embedding_hf(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    return HuggingFaceEmbeddings(model_name=model_name)


def get_embedding_openai(api_key=None):
    api_key = api_key or get_api_key("openai")
    return OpenAIEmbeddings(api_key=api_key)  # type: ignore


def get_available_models():
    # This is a placeholder. You should return a list of available models.
    return [
        "gpt-3.5-turbo",
        "gpt-4",
        "claude-2",
        "llama-3.2-3b-preview",
        "gemini-pro",
        # Add more models as needed
    ]


def get_model_by_name(model_name: str, temperature=DEFAULT_TEMPERATURE):
    # This function should return the appropriate model based on the name
    if model_name.startswith("gpt-"):
        return get_openai_chat(model_name, temperature=temperature)
    elif model_name.startswith("claude-"):
        return get_anthropic_chat(model_name, temperature=temperature)
    elif model_name.startswith("llama-"):
        return get_groq_chat(model_name, temperature=temperature)
    elif model_name == "gemini-pro":
        return get_google_chat(model_name, temperature=temperature)
    else:
        raise ValueError(f"Unknown model: {model_name}")


def get_embedding_model_by_name(model_name: str):
    # This function should return the appropriate embedding model based on the name
    if model_name == "text-embedding-ada-002":
        return get_embedding_openai()
    elif model_name.startswith("sentence-transformers/"):
        return get_embedding_hf(model_name)
    else:
        raise ValueError(f"Unknown embedding model: {model_name}")
