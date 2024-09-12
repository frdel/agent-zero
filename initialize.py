import models
from agent import AgentConfig
from src.lib.awm import AgentWorkflowMemory
from src.lib.embedding_memory import EmbeddingMemory
import os
from dotenv import load_dotenv

def initialize():
    load_dotenv()
    
    # main chat model used by agents (smarter, more accurate)
    chat_llm = models.get_openai_chat(model_name="gpt-4-turbo-preview", temperature=0)
    # chat_llm = models.get_ollama_chat(model_name="gemma:latest", temperature=0)
    # chat_llm = models.get_lmstudio_chat(model_name="TheBloke/Mistral-7B-Instruct-v0.2-GGUF", temperature=0)
    # chat_llm = models.get_openrouter(model_name="meta-llama/llama-2-70b-chat:free")
    # chat_llm = models.get_azure_openai_chat(deployment_name="gpt-4", temperature=0)
    # chat_llm = models.get_anthropic_chat(model_name="claude-3-opus-20240229", temperature=0)
    # chat_llm = models.get_google_chat(model_name="gemini-1.0-pro", temperature=0)
    # chat_llm = models.get_groq_chat(model_name="mixtral-8x7b-32768", temperature=0)
    
    # utility model used for helper functions (cheaper, faster)
    utility_llm = chat_llm # change if you want to use a different utility model

    # embedding model used for memory
    embedding_llm = models.get_openai_embedding(model_name="text-embedding-3-small")
    # embedding_llm = models.get_ollama_embedding(model_name="nomic-embed-text")
    # embedding_llm = models.get_huggingface_embedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

    # Initialize EmbeddingMemory
    embedding_memory = EmbeddingMemory(embedding_llm)

    # Initialize AgentWorkflowMemory with EmbeddingMemory
    openai_api_key = os.getenv("OPENAI_API_KEY")
    is_online_mode = os.getenv("AWM_ONLINE_MODE", "true").lower() == "true"
    awm = AgentWorkflowMemory(api_key=openai_api_key, is_online_mode=is_online_mode, embedding_memory=embedding_memory)

    # agent configuration
    config = AgentConfig(
        chat_model = chat_llm,
        utility_model = utility_llm,
        embeddings_model = embedding_llm,
        # prompts_subdir = "",
        # memory_subdir = "",
        # knowledge_subdir = "",
        auto_memory_count = 0,
        # auto_memory_skip = 2,
        # rate_limit_seconds = 60,
        rate_limit_requests = 15,
        # rate_limit_input_tokens = 0,
        # rate_limit_output_tokens = 0,
        # msgs_keep_max = 25,
        # msgs_keep_start = 5,
        # msgs_keep_end = 10,
        max_tool_response_length = 3000,
        # response_timeout_seconds = 60,
        code_exec_docker_enabled = True,
        # code_exec_docker_name = "agent-zero-exe",
        # code_exec_docker_image = "frdel/agent-zero-exe:latest",
        # code_exec_docker_ports = { "22/tcp": 50022 }
        # code_exec_docker_volumes = { files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"} }
        code_exec_ssh_enabled = True,
        # code_exec_ssh_addr = "localhost",
        # code_exec_ssh_port = 50022,
        # code_exec_ssh_user = "root",
        # code_exec_ssh_pass = "toor",
        # additional = {},
        awm = awm  # Add the AWM instance to the config
    )

    # return config object
    return config