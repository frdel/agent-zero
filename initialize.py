import asyncio
import json
import models
from agent import AgentConfig, ModelConfig
from python.helpers import dotenv, files, rfc_exchange, runtime, settings, docker, log
import subprocess
import shutil
from python.helpers.print_style import PrintStyle


# Helper function to ensure an MCP package is globally installed
def _ensure_mcp_package_globally_installed(package_name: str, executable_name: str):
    PrintStyle(background_color="blue", font_color="white", padding=True).print(
        f"Attempting to ensure MCP server executable '{executable_name}' (from package '{package_name}') is available..."
    )
    if shutil.which("npm"):
        if not shutil.which(executable_name):
            PrintStyle(font_color="yellow", padding=True).print(
                f"'{executable_name}' not found in PATH. Attempting global npm install of '{package_name}'..."
            )
            try:
                npm_command = ["npm", "i", "-g", package_name, "--no-fund", "--no-audit"]
                process = subprocess.run(npm_command, capture_output=True, text=True, check=False)
                if process.returncode == 0:
                    PrintStyle(font_color="green", padding=True).print(
                        f"Successfully installed '{package_name}' globally via npm."
                    )
                    if shutil.which(executable_name):
                        PrintStyle(font_color="green", padding=True).print(
                            f"'{executable_name}' is now available in PATH after install."
                        )
                    else:
                        PrintStyle(font_color="orange", padding=True).print(
                            f"WARNING: npm install of '{package_name}' reported success, but '{executable_name}' still not found in PATH. " +
                            "The 'npx' command in settings.json might still be necessary or there might be an issue with PATH."
                        )
                else:
                    PrintStyle(font_color="red", padding=True).print(
                        f"Failed to install '{package_name}' globally via npm. Return code: {process.returncode}"
                    )
                    PrintStyle(font_color="red", padding=False).print(f"npm stdout: {process.stdout.strip()}")
                    PrintStyle(font_color="red", padding=False).print(f"npm stderr: {process.stderr.strip()}")
            except FileNotFoundError:
                 PrintStyle(font_color="red", padding=True).print(
                    f"ERROR: 'npm' command not found. Cannot attempt to install '{package_name}'."
                )
            except Exception as e:
                PrintStyle(font_color="red", padding=True).print(
                    f"Exception during npm install of '{package_name}': {e}"
                )
        else:
            PrintStyle(font_color="green", padding=True).print(
                f"'{executable_name}' (from package '{package_name}') already found in PATH."
            )
    else:
        PrintStyle(font_color="red", padding=True).print(
            f"ERROR: 'npm' command not found. Cannot check for or install '{executable_name}' from '{package_name}'."
        )
    PrintStyle().print() # For a blank line after each attempt


def initialize():
    current_settings = settings.get_settings()
    mcp_servers_json_string = current_settings.get("mcp_servers", "[]")

    try:
        mcp_server_configs = json.loads(mcp_servers_json_string)
        if not isinstance(mcp_server_configs, list):
            PrintStyle(font_color="red", padding=True).print(
                f"Error: Parsed mcp_servers from settings is not a list. Value: {mcp_server_configs}"
            )
            mcp_server_configs = []
    except json.JSONDecodeError as e:
        PrintStyle(font_color="red", padding=True).print(
            f"Error decoding mcp_servers JSON string from settings: {e}. String was: '{mcp_servers_json_string}'"
        )
        mcp_server_configs = []

    if shutil.which("npm"):
        for server_config in mcp_server_configs:
            if not isinstance(server_config, dict):
                PrintStyle(font_color="orange", padding=True).print(
                    f"Warning: Skipping MCP server config item as it's not a dictionary: {server_config}"
                )
                continue

            command = server_config.get("command")
            args = server_config.get("args", [])
            server_name = server_config.get("name", "Unknown MCP Server")

            if command == "npx" and "--package" in args:
                try:
                    package_keyword_index = args.index("--package")
                    # Expect package name at +1 and executable name at +2 from "--package"
                    if package_keyword_index + 2 < len(args):
                        package_name = args[package_keyword_index + 1]
                        executable_name = args[package_keyword_index + 2]
                        if package_name and executable_name: # Ensure they are not empty strings
                             _ensure_mcp_package_globally_installed(package_name, executable_name)
                        else:
                            PrintStyle(font_color="orange", padding=True).print(
                                f"Warning: Skipping MCP server '{server_name}' due to empty package or executable name extracted from args: {args}"
                            )
                    else:
                        PrintStyle(font_color="orange", padding=True).print(
                            f"Warning: Skipping MCP server '{server_name}' as package name or executable name could not be determined from args: {args}"
                        )
                except ValueError: # Should not happen if "--package" is in args, but good for safety
                    PrintStyle(font_color="orange", padding=True).print(
                        f"Warning: '--package' keyword found but .index() failed for args: {args} in server '{server_name}'"
                    )
                except Exception as e:
                     PrintStyle(font_color="red", padding=True).print(
                        f"Error processing npx args for server '{server_name}': {e}. Args: {args}"
                    )
    else:
        PrintStyle(font_color="red", padding=True).print(
            "ERROR: 'npm' command not found. Cannot attempt to install any MCP server packages."
        )
    PrintStyle().print() # Extra blank line after all attempts or npm not found message

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
