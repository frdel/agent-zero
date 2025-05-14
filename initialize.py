import asyncio
import models
from agent import AgentConfig, ModelConfig
from python.helpers import dotenv, files, rfc_exchange, runtime, settings, docker, log
import subprocess
import shutil
from python.helpers.print_style import PrintStyle


def initialize():

    PrintStyle(background_color="blue", font_color="white", padding=True).print(
        "Attempting to ensure MCP server 'mcp-server-sequential-thinking' is available..."
    )
    # Check if npm is available first, as it's needed for the install.
    if shutil.which("npm"):
        if not shutil.which("mcp-server-sequential-thinking"):
            PrintStyle(font_color="yellow", padding=True).print(
                "'mcp-server-sequential-thinking' not found in PATH. Attempting global npm install..."
            )
            try:
                # Attempt to install @modelcontextprotocol/server-sequential-thinking globally
                npm_command = ["npm", "i", "-g", "@modelcontextprotocol/server-sequential-thinking", "--no-fund", "--no-audit"]
                process = subprocess.run(npm_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    PrintStyle(font_color="green", padding=True).print(
                        "Successfully installed @modelcontextprotocol/server-sequential-thinking globally via npm."
                    )
                    # Re-check if it's available in PATH now. This depends on npm's global bin location being in PATH.
                    if shutil.which("mcp-server-sequential-thinking"):
                        PrintStyle(font_color="green", padding=True).print(
                            "'mcp-server-sequential-thinking' is now available in PATH after install."
                        )
                    else:
                        PrintStyle(font_color="orange", padding=True).print(
                            "WARNING: npm install reported success, but 'mcp-server-sequential-thinking' still not found in PATH by shutil.which(). " +
                            "The 'npx' command in settings.json might still be necessary and hopefully works."
                        )
                else:
                    PrintStyle(font_color="red", padding=True).print(
                        f"Failed to install @modelcontextprotocol/server-sequential-thinking globally via npm. Return code: {process.returncode}"
                    )
                    PrintStyle(font_color="red", padding=False).print(f"npm stdout: {process.stdout.strip()}")
                    PrintStyle(font_color="red", padding=False).print(f"npm stderr: {process.stderr.strip()}")
            except FileNotFoundError:
                 PrintStyle(font_color="red", padding=True).print(
                    "ERROR: 'npm' command not found. Cannot attempt to install @modelcontextprotocol/server-sequential-thinking."
                )
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(
                    f"Exception during npm install of @modelcontextprotocol/server-sequential-thinking: {e}"
                )
        else:
            PrintStyle(font_color="green", padding=True).print(
                "'mcp-server-sequential-thinking' already found in PATH."
            )
    else:
        PrintStyle(font_color="red", padding=True).print(
            "ERROR: 'npm' command not found. Cannot check for or install 'mcp-server-sequential-thinking'."
        )

    current_settings = settings.get_settings()

    # chat model from user settings
    chat_llm = ModelConfig(
        provider=models.ModelProvider[current_settings["chat_model_provider"]],
        name=current_settings["chat_model_name"],
        ctx_length=current_settings["chat_model_ctx_length"],
        vision=current_settings["chat_model_vision"],
        limit_requests=current_settings["chat_model_rl_requests"],
        limit_input=current_settings["chat_model_rl_input"],
        limit_output=current_settings["chat_model_rl_output"],
        kwargs=current_settings["chat_model_kwargs"],
    )

    # utility model from user settings
    utility_llm = ModelConfig(
        provider=models.ModelProvider[current_settings["util_model_provider"]],
        name=current_settings["util_model_name"],
        ctx_length=current_settings["util_model_ctx_length"],
        limit_requests=current_settings["util_model_rl_requests"],
        limit_input=current_settings["util_model_rl_input"],
        limit_output=current_settings["util_model_rl_output"],
        kwargs=current_settings["util_model_kwargs"],
    )
    # embedding model from user settings
    embedding_llm = ModelConfig(
        provider=models.ModelProvider[current_settings["embed_model_provider"]],
        name=current_settings["embed_model_name"],
        limit_requests=current_settings["embed_model_rl_requests"],
        kwargs=current_settings["embed_model_kwargs"],
    )
    # browser model from user settings
    browser_llm = ModelConfig(
        provider=models.ModelProvider[current_settings["browser_model_provider"]],
        name=current_settings["browser_model_name"],
        vision=current_settings["browser_model_vision"],
        kwargs=current_settings["browser_model_kwargs"],
    )
    # agent configuration
    config = AgentConfig(
        chat_model=chat_llm,
        utility_model=utility_llm,
        embeddings_model=embedding_llm,
        browser_model=browser_llm,
        prompts_subdir=current_settings["agent_prompts_subdir"],
        memory_subdir=current_settings["agent_memory_subdir"],
        knowledge_subdirs=["default", current_settings["agent_knowledge_subdir"]],
        mcp_servers=current_settings["mcp_servers"],
        code_exec_docker_enabled=False,
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

    import python.helpers.mcp_handler as mcp_helper
    import agent as agent_helper
    import python.helpers.print_style as print_style_helper
    if not mcp_helper.MCPConfig.get_instance().is_initialized():
        try:
            mcp_helper.MCPConfig.update(config.mcp_servers)
        except Exception as e:
            first_context = agent_helper.AgentContext.first()
            if first_context:
                (
                    first_context.log
                    .log(type="warning", content=f"Failed to update MCP settings: {e}", temp=False)
                )
            (
                print_style_helper.PrintStyle(background_color="black", font_color="red", padding=True)
                .print(f"Failed to update MCP settings: {e}")
            )

    # return config object
    return config


def args_override(config):
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
