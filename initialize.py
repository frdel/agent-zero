import asyncio
import models
from agent import AgentConfig
from python.helpers import dotenv, files, rfc_exchange, runtime, settings, docker, log


def initialize():

    current_settings = settings.get_settings()

    # main chat model used by agents (smarter, more accurate)
    # chat_llm = models.get_openai_chat(model_name="gpt-4o-mini", temperature=0)
    # chat_llm = models.get_ollama_chat(model_name="llama3.2:3b-instruct-fp16", temperature=0)
    # chat_llm = models.get_lmstudio_chat(model_name="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF", temperature=0)
    # chat_llm = models.get_openrouter_chat(model_name="openai/o1-mini-2024-09-12")
    # chat_llm = models.get_azure_openai_chat(deployment_name="gpt-4o-mini", temperature=0)
    # chat_llm = models.get_anthropic_chat(model_name="claude-3-5-sonnet-20240620", temperature=0)
    # chat_llm = models.get_google_chat(model_name="gemini-1.5-flash", temperature=0)
    # chat_llm = models.get_mistral_chat(model_name="mistral-small-latest", temperature=0)
    # chat_llm = models.get_groq_chat(model_name="llama-3.2-90b-text-preview", temperature=0)
    # chat_llm = models.get_sambanova_chat(model_name="Meta-Llama-3.1-70B-Instruct-8k", temperature=0)
    chat_llm = settings.get_chat_model(
        current_settings
    )  # chat model from user settings

    # utility model used for helper functions (cheaper, faster)
    # utility_llm = chat_llm
    utility_llm = settings.get_utility_model(
        current_settings
    )  # utility model from user settings

    # embedding model used for memory
    # embedding_llm = models.get_openai_embedding(model_name="text-embedding-3-small")
    # embedding_llm = models.get_ollama_embedding(model_name="nomic-embed-text")
    # embedding_llm = models.get_huggingface_embedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    # embedding_llm = models.get_lmstudio_embedding(model_name="nomic-ai/nomic-embed-text-v1.5-GGUF")
    embedding_llm = settings.get_embedding_model(
        current_settings
    )  # embedding model from user settings

    # agent configuration
    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        prompts_subdir=current_settings["agent_prompts_subdir"],
        memory_subdir=current_settings["agent_memory_subdir"],
        knowledge_subdirs=["default", current_settings["agent_knowledge_subdir"]],
        # rate_limit_seconds = 60,
        rate_limit_requests=30,
        # rate_limit_input_tokens = 0,
        # rate_limit_output_tokens = 0,
        # response_timeout_seconds = 60,
        code_exec_docker_enabled = False,
        # code_exec_docker_name = "A0-dev",
        # code_exec_docker_image = "frdel/agent-zero-run:development",
        # code_exec_docker_ports = { "22/tcp": 55022, "80/tcp": 55080 }
        # code_exec_docker_volumes = {
        # files.get_base_dir(): {"bind": "/a0", "mode": "rw"},
        # files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"},
        # },
        # code_exec_ssh_enabled = True,
        # code_exec_ssh_addr = "localhost",
        # code_exec_ssh_port = 55022,
        # code_exec_ssh_user = "root",
        # code_exec_ssh_pass = "",
        # additional = {},
    )

    # update SSH and docker settings
    set_runtime_config(config, current_settings)

    # update config with runtime args
    args_override(config)

    # return config object
    return config


def args_override(config):
    # update config with runtime args
    for key, value in runtime.args.items():
        if hasattr(config, key):
            # conversion based on type of config[key]
            if isinstance(getattr(config, key), bool):
                value = value.lower().strip() == "true"
                print("bool", value)
            elif isinstance(getattr(config, key), int):
                value = int(value)
                print("int", value)
            elif isinstance(getattr(config, key), float):
                value = float(value)
                print("float", value)
            elif isinstance(getattr(config, key), str):
                value = str(value)
                print("str", value)
            else:
                raise Exception(
                    f"Unsupported argument type of '{key}': {type(getattr(config, key))}"
                )

            setattr(config, key, value)


def set_runtime_config(config: AgentConfig, set: settings.Settings):
    ssh_conf = settings.get_runtime_config(set)
    for key, value in ssh_conf.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # if config.code_exec_docker_enabled:
    #     config.code_exec_docker_ports["22/tcp"] = ssh_conf["code_exec_ssh_port"]
    #     config.code_exec_docker_ports["80/tcp"] = ssh_conf["code_exec_http_port"]
    #     config.code_exec_docker_name = f"{config.code_exec_docker_name}-{ssh_conf['code_exec_ssh_port']}-{ssh_conf['code_exec_http_port']}"

    #     dman = docker.DockerContainerManager(
    #         logger=log.Log(),
    #         name=config.code_exec_docker_name,
    #         image=config.code_exec_docker_image,
    #         ports=config.code_exec_docker_ports,
    #         volumes=config.code_exec_docker_volumes,
    #     )
    #     dman.start_container()

    # config.code_exec_ssh_pass = asyncio.run(rfc_exchange.get_root_password())
