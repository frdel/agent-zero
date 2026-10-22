from agent import AgentConfig
from helpers import runtime, settings, defer, extension
from helpers.print_style import PrintStyle


@extension.extensible
def initialize_agent(override_settings: dict | None = None):
    current_settings = settings.get_settings()
    if override_settings:
        current_settings = settings.merge_settings(current_settings, override_settings)

    # agent configuration - models are now resolved at call time via _model_config plugin
    config = AgentConfig(
        profile=current_settings["agent_profile"],
        knowledge_subdirs=[current_settings["agent_knowledge_subdir"], "default"],
        mcp_servers=current_settings["mcp_servers"],
    )

    # update config with runtime args
    _args_override(config)

    # initialize MCP in deferred task to prevent blocking the main thread
    # async def initialize_mcp_async(mcp_servers_config: str):
    #     return initialize_mcp(mcp_servers_config)
    # defer.DeferredTask(thread_name="mcp-initializer").start_task(initialize_mcp_async, config.mcp_servers)
    # initialize_mcp(config.mcp_servers)

    # import helpers.mcp_handler as mcp_helper
    # import agent as agent_helper
    # import helpers.print_style as print_style_helper
    # if not mcp_helper.MCPConfig.get_instance().is_initialized():
    #     try:
    #         mcp_helper.MCPConfig.update(config.mcp_servers)
    #     except Exception as e:
    #         first_context = agent_helper.AgentContext.first()
    #         if first_context:
    #             (
    #                 first_context.log
    #                 .log(type="warning", content=f"Failed to update MCP settings: {e}")
    #             )
    #         (
    #             print_style_helper.PrintStyle(background_color="black", font_color="red", padding=True)
    #             .print(f"Failed to update MCP settings: {e}")
    #         )

    # return config object
    return config

@extension.extensible
def initialize_chats():
    from helpers import persist_chat
    async def initialize_chats_async():
        from helpers.durable.runtime import initialize
        initialize()
        persist_chat.load_tmp_chats()
    return defer.DeferredTask().start_task(initialize_chats_async)


def initialize_recovery():
    from helpers.durable.runtime import service
    owner = service()
    if owner:
        owner.recover()

@extension.extensible
def initialize_mcp():
    set = settings.get_settings()
    async def initialize_mcp_async():
        from helpers.mcp_handler import initialize_mcp as _initialize_mcp
        return _initialize_mcp(set["mcp_servers"])
    return defer.DeferredTask().start_task(initialize_mcp_async)

@extension.extensible
def initialize_job_loop():
    from helpers.job_loop import run_loop
    return defer.DeferredTask("JobLoop").start_task(run_loop)

@extension.extensible
def initialize_preload():
    import preload
    return defer.DeferredTask().start_task(preload.preload)

@extension.extensible
def initialize_migration():
    from helpers import migration, dotenv
    # run migration
    migration.startup_migration()
    # reload .env as it might have been moved
    dotenv.load_dotenv()
    # reload settings to ensure new paths are picked up
    settings.reload_settings()

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



