import os
from dotenv import load_dotenv
from langchain_community.llms import Ollama
from langchain_openai import ChatOpenAI, OpenAI, OpenAIEmbeddings
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI, HarmBlockThreshold, HarmCategory
from pydantic.v1.types import SecretStr


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

def get_anthropic_sonnet_35(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-5-sonnet-20240620", temperature=temperature, api_key=api_key) # type: ignore


def get_anthropic_sonnet(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-sonnet-20240229", temperature=temperature, api_key=api_key) # type: ignore

def get_anthropic_opus(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("anthropic")
    return ChatAnthropic(model_name="claude-3-opus-20240229", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_gpt35(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name="gpt-3.5-turbo", temperature=temperature, api_key=api_key) # type: ignore

def get_openai_chat(api_key=None, model="gpt-4o-mini", temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("openai")
    return ChatOpenAI(model_name=model, temperature=temperature, api_key=api_key) # type: ignore


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

def get_groq_llama70b_json(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="llama3-70b-8192", temperature=temperature, api_key=api_key, model_kwargs={"response_format": {"type": "json_object"}}) # type: ignore


def get_groq_llama8b(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="Llama3-8b-8192", temperature=temperature, api_key=api_key) # type: ignore

def get_ollama(model_name, temperature=DEFAULT_TEMPERATURE):
    return Ollama(model=model_name,temperature=temperature)

def get_groq_gemma(api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("groq")
    return ChatGroq(model_name="gemma-7b-it", temperature=temperature, api_key=api_key) # type: ignore

def get_ollama_dolphin(temperature=DEFAULT_TEMPERATURE):
    return Ollama(model="dolphin-llama3:8b-256k-v2.9-fp16", temperature=temperature)

def get_ollama_phi(temperature=DEFAULT_TEMPERATURE):
    return Ollama(model="phi3:3.8b-mini-instruct-4k-fp16",temperature=temperature)

def get_google_chat(model_name="gemini-1.5-flash-latest", api_key=None, temperature=DEFAULT_TEMPERATURE):
    api_key = api_key or get_api_key("google")
    return ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key, 
                                  safety_settings={HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE }) # type: ignore

def get_openrouter(model_name: str="meta-llama/llama-3.1-8b-instruct:free"):
        open_router_api_key = os.getenv('API_KEY_OPENROUTER')
        open_router_api_key = SecretStr(open_router_api_key) if open_router_api_key else None
        return ChatOpenAI(api_key=open_router_api_key,
                          base_url="https://openrouter.ai/api/v1",
                         model=model_name)
        
def get_embedding_hf(model_name="sentence-transformers/all-MiniLM-L6-v2"):
    return HuggingFaceEmbeddings(model_name=model_name)

def get_embedding_openai(api_key=None):
    api_key = api_key or get_api_key("openai")
    return OpenAIEmbeddings(api_key=api_key) #type: ignore
