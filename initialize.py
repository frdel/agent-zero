from agent import AgentConfig
import models
from python.helpers import runtime, settings, defer
from python.helpers.print_style import PrintStyle


def initialize_agent():
    current_settings = settings.get_settings()

    def _normalize_model_kwargs(kwargs: dict) -> dict:
        # convert string values that represent valid Python numbers to numeric types
        result = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                # try to convert string to number if it's a valid Python number
                try:
                    # try int first, then float
                    result[key] = int(value)
                except ValueError:
                    try:
                        result[key] = float(value)
                    except ValueError:
                        result[key] = value
            else:
                result[key] = value
        return result

    # chat model from user settings
    chat_llm = models.ModelConfig(
        type=models.ModelType.CHAT,
        provider=current_settings["chat_model_provider"],
        name=current_settings["chat_model_name"],
        api_base=current_settings["chat_model_api_base"],
        ctx_length=current_settings["chat_model_ctx_length"],
        vision=current_settings["chat_model_vision"],
        limit_requests=current_settings["chat_model_rl_requests"],
        limit_input=current_settings["chat_model_rl_input"],
        limit_output=current_settings["chat_model_rl_output"],
        kwargs=_normalize_model_kwargs(current_settings["chat_model_kwargs"]),
    )

    # utility model from user settings
    utility_llm = models.ModelConfig(
        type=models.ModelType.CHAT,
        provider=current_settings["util_model_provider"],
        name=current_settings["util_model_name"],
        api_base=current_settings["util_model_api_base"],
        ctx_length=current_settings["util_model_ctx_length"],
        limit_requests=current_settings["util_model_rl_requests"],
        limit_input=current_settings["util_model_rl_input"],
        limit_output=current_settings["util_model_rl_output"],
        kwargs=_normalize_model_kwargs(current_settings["util_model_kwargs"]),
    )
    # embedding model from user settings
    embedding_llm = models.ModelConfig(
        type=models.ModelType.EMBEDDING,
        provider=current_settings["embed_model_provider"],
        name=current_settings["embed_model_name"],
        api_base=current_settings["embed_model_api_base"],
        limit_requests=current_settings["embed_model_rl_requests"],
        kwargs=_normalize_model_kwargs(current_settings["embed_model_kwargs"]),
    )
    # browser model from user settings
    browser_llm = models.ModelConfig(
        type=models.ModelType.CHAT,
        provider=current_settings["browser_model_provider"],
        name=current_settings["browser_model_name"],
        api_base=current_settings["browser_model_api_base"],
        vision=current_settings["browser_model_vision"],
        kwargs=_normalize_model_kwargs(current_settings["browser_model_kwargs"]),
    )
    # agent configuration
    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        browser_model=browser_llm,
        profile=current_settings["agent_profile"],
        memory_subdir=current_settings["agent_memory_subdir"],
        knowledge_subdirs=[current_settings["agent_knowledge_subdir"], "default"],
        mcp_servers=current_settings["mcp_servers"],
        code_exec_docker_enabled=False,
        # code_exec_docker_name = "A0-dev",
        # code_exec_docker_image = "agent0ai/agent-zero:development",
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
    _set_runtime_config(config, current_settings)

    # update config with runtime args
    _args_override(config)

    # initialize MCP in deferred task to prevent blocking the main thread
    # async def initialize_mcp_async(mcp_servers_config: str):
    #     return initialize_mcp(mcp_servers_config)
    # defer.DeferredTask(thread_name="mcp-initializer").start_task(initialize_mcp_async, config.mcp_servers)
    # initialize_mcp(config.mcp_servers)

    # import python.helpers.mcp_handler as mcp_helper
    # import agent as agent_helper
    # import python.helpers.print_style as print_style_helper
    # if not mcp_helper.MCPConfig.get_instance().is_initialized():
    #     try:
    #         mcp_helper.MCPConfig.update(config.mcp_servers)
    #     except Exception as e:
    #         first_context = agent_helper.AgentContext.first()
    #         if first_context:
    #             (
    #                 first_context.log
    #                 .log(type="warning", content=f"Failed to update MCP settings: {e}", temp=False)
    #             )
    #         (
    #             print_style_helper.PrintStyle(background_color="black", font_color="red", padding=True)
    #             .print(f"Failed to update MCP settings: {e}")
    #         )

    # return config object
    return config

def initialize_chats():
    from python.helpers import persist_chat
    async def initialize_chats_async():
        persist_chat.load_tmp_chats()
    return defer.DeferredTask().start_task(initialize_chats_async)

def initialize_mcp():
    set = settings.get_settings()
    async def initialize_mcp_async():
        from python.helpers.mcp_handler import initialize_mcp as _initialize_mcp
        return _initialize_mcp(set["mcp_servers"])
    return defer.DeferredTask().start_task(initialize_mcp_async)

def initialize_job_loop():
    from python.helpers.job_loop import run_loop
    return defer.DeferredTask("JobLoop").start_task(run_loop)

def initialize_preload():
    import preload
    return defer.DeferredTask().start_task(preload.preload)


def _args_override(config):
    # update config with runtime args
    for key, value in runtime.args.items():
        if hasattr(config, key):
            # conversion based on type of config[key]
            if isinstance(getattr(config, key), bool):
                value = value.lower().strip() == "true"
            elif isinstance(getattr(config, key), int):
                value = int(value)
            elif isinstance(getattr(config, key), float):
                value = float(value)
            elif isinstance(getattr(config, key), str):
                value = str(value)
            else:
                raise Exception(
                    f"Unsupported argument type of '{key}': {type(getattr(config, key))}"
                )

            setattr(config, key, value)


def _set_runtime_config(config: AgentConfig, set: settings.Settings):
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
