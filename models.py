import os
from dotenv import load_dotenv
from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI, OpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings


# Load environment variables
load_dotenv()

# Configuration
DEFAULT_TEMPERATURE = 0.0

# Utility function to get API keys from environment variables
def get_api_key(service):
    return os.getenv(f"API_KEY_{service.upper()}")

# Factory functions for each model type
def get_anthropic_haiku(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-haiku-20240307", temperature=temperature, api_key=api_key) # type: ignore

def get_anthropic_sonnet(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-sonnet-20240229", temperature=temperature, api_key=api_key) # type: ignore

def get_anthropic_opus(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-opus-20240229", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_gpt35(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name="gpt-3.5-turbo", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_gpt35_instruct(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return OpenAI(model_name="gpt-3.5-turbo-instruct", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_gpt4(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name="gpt-4-0125-preview", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_gpt4o(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name="gpt-4o", temperature=temperature, api_key=api_key) # type: ignore

def get_groq_mixtral7b(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="mixtral-8x7b-32768", temperature=temperature, api_key=api_key) # type: ignore

def get_groq_llama70b(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="llama3-70b-8192", temperature=temperature, api_key=api_key) # type: ignore

def get_groq_llama8b(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="Llama3-8b-8192", temperature=temperature, api_key=api_key) # type: ignore

def get_groq_gemma(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="gemma-7b-it", temperature=temperature, api_key=api_key) # type: ignore

def get_ollama_dolphin(api_key=None, temperature=DEFAULT_TEMPERATURE):
    return Ollama(model="dolphin-llama3:8b-256k-v2.9-fp16")

def get_ollama_phi(api_key=None, temperature=DEFAULT_TEMPERATURE):
    return Ollama(model="phi3:3.8b-mini-instruct-4k-fp16")

def get_embedding_hf(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    return HuggingFaceEmbeddings(model_name=model_name)

def get_embedding_openai(api_key=None):
    api_key = api_key or get_api_key("openai")
    return OpenAIEmbeddings(api_key=api_key) #type: ignore
