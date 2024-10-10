import os
from langchain_openai import ChatOpenAI, OpenAI, OpenAIEmbeddings, AzureChatOpenAI, AzureOpenAIEmbeddings, AzureOpenAI
from langchain_community.llms.ollama import Ollama
from langchain_ollama import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import GoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from langchain_mistralai import ChatMistralAI
from pydantic.v1.types import SecretStr
from python.helpers.dotenv import load_dotenv

# environment variables
load_dotenv()

# Configuration
DEFAULT_TEMPERATURE = 0.0

# Utility function to get API keys from environment variables
def get_api_key(service):
    return os.getenv(f"API_KEY_{service.upper()}") or os.getenv(f"{service.upper()}_API_KEY")


# Ollama models
def get_ollama_chat(model_name:str, temperature=DEFAULT_TEMPERATURE, base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434", num_ctx=8192):
    return ChatOllama(model=model_name,temperature=temperature, base_url=base_url, num_ctx=num_ctx)

def get_ollama_embedding(model_name:str, temperature=DEFAULT_TEMPERATURE, base_url=os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434"):
    
    return OllamaEmbeddings(model=model_name,temperature=temperature, base_url=base_url)

# HuggingFace models

def get_huggingface_embedding(model_name:str):
    return HuggingFaceEmbeddings(model_name=model_name)

# LM Studio and other OpenAI compatible interfaces
def get_lmstudio_chat(model_name:str, temperature=DEFAULT_TEMPERATURE, base_url=os.getenv("LM_STUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"):
    return ChatOpenAI(model_name=model_name, base_url=base_url, temperature=temperature, api_key="none") # type: ignore

def get_lmstudio_embedding(model_name:str, base_url=os.getenv("LM_STUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"):
    return OpenAIEmbeddings(model=model_name, api_key="none", base_url=base_url, check_embedding_ctx_length=False) # type: ignore

# Anthropic models
def get_anthropic_chat(model_name:str, api_key=get_api_key("anthropic"), temperature=DEFAULT_TEMPERATURE):
    return ChatAnthropic(model_name=model_name, temperature=temperature, api_key=api_key) # type: ignore

# OpenAI models
def get_openai_chat(model_name:str, api_key=get_api_key("openai"), temperature=DEFAULT_TEMPERATURE):
    return ChatOpenAI(model_name=model_name, temperature=temperature, api_key=api_key) # type: ignore

def get_openai_instruct(model_name:str, api_key=get_api_key("openai"), temperature=DEFAULT_TEMPERATURE):
    return OpenAI(model=model_name, temperature=temperature, api_key=api_key) # type: ignore

def get_openai_embedding(model_name:str, api_key=get_api_key("openai")):
    return OpenAIEmbeddings(model=model_name, api_key=api_key) # type: ignore

def get_azure_openai_chat(deployment_name:str, api_key=get_api_key("openai_azure"), temperature=DEFAULT_TEMPERATURE, azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT")):
    return AzureChatOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint) # type: ignore

def get_azure_openai_instruct(deployment_name:str, api_key=get_api_key("openai_azure"), temperature=DEFAULT_TEMPERATURE, azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT")):
    return AzureOpenAI(deployment_name=deployment_name, temperature=temperature, api_key=api_key, azure_endpoint=azure_endpoint) # type: ignore

def get_azure_openai_embedding(deployment_name:str, api_key=get_api_key("openai_azure"), azure_endpoint=os.getenv("OPENAI_AZURE_ENDPOINT")):
    return AzureOpenAIEmbeddings(deployment_name=deployment_name, api_key=api_key, azure_endpoint=azure_endpoint) # type: ignore

# Google models
def get_google_chat(model_name:str, api_key=get_api_key("google"), temperature=DEFAULT_TEMPERATURE):
    return GoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key, safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE }) # type: ignore

# Mistral models
def get_mistral_chat(model_name:str, api_key=get_api_key("mistral"), temperature=DEFAULT_TEMPERATURE):
    return ChatMistralAI(model=model_name, temperature=temperature, api_key=api_key) # type: ignore

# Groq models
def get_groq_chat(model_name:str, api_key=get_api_key("groq"), temperature=DEFAULT_TEMPERATURE):
    return ChatGroq(model_name=model_name, temperature=temperature, api_key=api_key) # type: ignore
   
# OpenRouter models
def get_openrouter_chat(model_name: str, api_key=get_api_key("openrouter"), temperature=DEFAULT_TEMPERATURE, base_url=os.getenv("OPEN_ROUTER_BASE_URL") or "https://openrouter.ai/api/v1"):
    return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, base_url=base_url) # type: ignore
      
def get_openrouter_embedding(model_name: str, api_key=get_api_key("openrouter"), base_url=os.getenv("OPEN_ROUTER_BASE_URL") or "https://openrouter.ai/api/v1"):
    return OpenAIEmbeddings(model=model_name, api_key=api_key, base_url=base_url) # type: ignore

# Sambanova models
def get_sambanova_chat(model_name: str, api_key=get_api_key("sambanova"), temperature=DEFAULT_TEMPERATURE, base_url=os.getenv("SAMBANOVA_BASE_URL") or "https://fast-api.snova.ai/v1", max_tokens=1024):
    return ChatOpenAI(api_key=api_key, model=model_name, temperature=temperature, base_url=base_url, max_tokens=max_tokens) # type: ignore
   
