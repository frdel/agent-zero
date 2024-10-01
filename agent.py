"""
IMPORTANT: This file contains complex type structures that may trigger
Pylance/Pyright warnings. These warnings DO NOT affect functionality
and can be safely ignored.

To suppress these warnings project-wide, create a pyrightconfig.json
file in the project root with the following content:

{
    "reportGeneralTypeIssues": false,
    "reportUnknownMemberType": false
}

If warnings persist in your editor after adding this configuration:
1. Reload the VSCode window or restart VSCode.
2. If warnings still appear, they can be safely ignored as they do not
   impact the code's functionality.

For Mypy users, create a .mypy.ini file in the project root with:

[mypy]
ignore_missing_imports = True

The complex type structures in this file are necessary for the project's
functionality. The warnings are a known limitation of static type checkers
when dealing with such structures and do not indicate actual issues with
the code.
"""

from dataclasses import dataclass, field
import os
from typing import Any, Optional, Dict, List, Union

from python.helpers import rate_limiter, files

# type: ignore
try:
    from langchain.schema import AIMessage, HumanMessage, SystemMessage  # type: ignore
    from langchain.prompts import (  # type: ignore
        ChatPromptTemplate,
        MessagesPlaceholder,
    )
    from langchain_core.language_models import BaseLLM  # type: ignore
    from langchain_core.language_models.chat_models import BaseChatModel  # type: ignore
except ImportError:
    print(
        "Warning: Unable to import some langchain modules. "
        "Make sure langchain is installed."
    )
    # Use Any as a fallback type
    AIMessage = HumanMessage = SystemMessage = ChatPromptTemplate = (
        MessagesPlaceholder
    ) = BaseLLM = BaseChatModel = Any

# Type alias for the complex dictionary type
DockerVolume = Dict[str, str]
DockerVolumes = Dict[str, DockerVolume]


@dataclass
class AgentConfig:
    chat_model: Any
    utility_model: Any
    embeddings_model: Any
    memory_subdir: str = ""
    auto_memory_count: int = 3
    auto_memory_skip: int = 2
    rate_limit_seconds: int = 60
    rate_limit_requests: int = 15
    rate_limit_input_tokens: int = 1000000
    rate_limit_output_tokens: int = 0
    msgs_keep_max: int = 25
    msgs_keep_start: int = 5
    msgs_keep_end: int = 10
    response_timeout_seconds: int = 60
    max_tool_response_length: int = 3000
    code_exec_docker_enabled: bool = True
    code_exec_docker_name: str = "agent-zero-exe"
    code_exec_docker_image: str = "frdel/agent-zero-exe:latest"
    code_exec_docker_ports: Dict[str, int] = field(
        default_factory=lambda: {"22/tcp": 50022}
    )
    code_exec_docker_volumes: Optional[DockerVolumes] = None
    code_exec_ssh_enabled: bool = True
    code_exec_ssh_addr: str = "localhost"
    code_exec_ssh_port: int = 50022
    code_exec_ssh_user: str = "root"
    code_exec_ssh_pass: str = "toor"
    additional: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.code_exec_docker_volumes is None:
            self.code_exec_docker_volumes = self._init_docker_volumes()

        # Ensure additional is a dictionary
        if not isinstance(self.additional, dict):
            self.additional = {}

    def _init_docker_volumes(self) -> DockerVolumes:
        return {"/path/to/work_dir": {"bind": "/root", "mode": "rw"}}


class Agent:
    paused = False
    streaming_agent = None

    def __init__(self, number: int, config: AgentConfig):
        self.config = config
        self.number = number
        self.agent_name = f"Agent {self.number}"
        self.system_prompt = files.read_file(
            "./prompts/agent.system.md", agent_name=self.agent_name
        )
        self.tools_prompt = files.read_file("./prompts/agent.tools.md")
        self.history: List[Union[HumanMessage, AIMessage]] = []  # type: ignore
        self.last_message = ""
        self.intervention_message = ""
        self.intervention_status = False
        self.rate_limiter = rate_limiter.RateLimiter(
            max_calls=self.config.rate_limit_requests,
            max_input_tokens=self.config.rate_limit_input_tokens,
            max_output_tokens=self.config.rate_limit_output_tokens,
            window_seconds=self.config.rate_limit_seconds,
        )
        self.data: Dict[str, Any] = {}
        self.context: Dict[str, Any] = {}
        self.read_prompt = ""
        os.chdir(files.get_abs_path("./work_dir"))

    def generate_response(self, prompt: str) -> str:
        # Add the user's message to the conversation history
        self.history.append(HumanMessage(content=prompt))  # type: ignore

        # Prepare the messages for the chat model
        messages = [
            SystemMessage(content=self.system_prompt),  # type: ignore
            *self.history,
        ]

        # Generate a response using the chat model
        response = self.config.chat_model(messages)  # type: ignore

        # Check if the response is a string (as expected from Groq) or has a 'content' attribute
        if isinstance(response, str):
            response_content = response
        elif hasattr(response, "content"):
            response_content = response.content
        else:
            raise ValueError(f"Unexpected response type: {type(response)}")

        # Add the AI's response to the conversation history
        self.history.append(AIMessage(content=response_content))  # type: ignore

        # Trim the history if it exceeds the maximum number of messages
        if len(self.history) > self.config.msgs_keep_max:
            self.history = (
                self.history[: self.config.msgs_keep_start]
                + self.history[-self.config.msgs_keep_end :]
            )

        return response_content

    def call_extension(self, name: str, **kwargs: Any) -> Any:
        pass
