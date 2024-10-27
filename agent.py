import asyncio
from dataclasses import dataclass, field
import time, importlib, inspect, os, json
from typing import Any, Optional, Dict, TypedDict, Callable
import uuid

from langchain.schema import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.llms import BaseLLM
from langchain_core.embeddings import Embeddings

from python.helpers import extract_tools, rate_limiter, files, errors
from python.helpers.print_style import PrintStyle
import python.helpers.log as Log
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask

# Base Exception Classes
class InterventionException(Exception):
    """Raised when intervention is needed - skips rest of message loop iteration"""
    pass

class RepairableException(Exception):
    """Not forwarded to LLM, cannot be fixed on its own, ends message loop"""
    pass

class HandledException(Exception):
    """Indicates an exception has already been handled"""
    pass

# Configuration Classes
@dataclass
class AgentAPIConfig:
    """Configuration class for agent-specific API settings"""
    chat_model: Optional[BaseChatModel | BaseLLM] = None
    utility_model: Optional[BaseChatModel | BaseLLM] = None
    
    def merge_with_default(self, default_config: 'AgentConfig') -> 'AgentAPIConfig':
        """Merges this config with default config, preferring this config's non-None values"""
        return AgentAPIConfig(
            chat_model=self.chat_model or default_config.chat_model,
            utility_model=self.utility_model or default_config.utility_model
        )

@dataclass
class AgentConfig:
    chat_model: BaseChatModel | BaseLLM
    utility_model: BaseChatModel | BaseLLM
    embeddings_model: Embeddings
    prompts_subdir: str = ""
    memory_subdir: str = ""
    knowledge_subdirs: list[str] = field(default_factory=lambda: ["default", "custom"])
    auto_memory_count: int = 3
    auto_memory_skip: int = 2
    rate_limit_seconds: int = 60
    rate_limit_requests: int = 15
    rate_limit_input_tokens: int = 0
    rate_limit_output_tokens: int = 0
    msgs_keep_max: int = 25
    msgs_keep_start: int = 5
    msgs_keep_end: int = 10
    response_timeout_seconds: int = 60
    max_tool_response_length: int = 3000
    code_exec_docker_enabled: bool = True
    code_exec_docker_name: str = "agent-zero-exe"
    code_exec_docker_image: str = "frdel/agent-zero-exe:latest"
    code_exec_docker_ports: dict[str, int] = field(
        default_factory=lambda: {"22/tcp": 50022}
    )
    code_exec_docker_volumes: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"},
            files.get_abs_path("instruments"): {"bind": "/instruments", "mode": "rw"},
        }
    )
    code_exec_ssh_enabled: bool = True
    code_exec_ssh_addr: str = "localhost"
    code_exec_ssh_port: int = 50022
    code_exec_ssh_user: str = "root"
    code_exec_ssh_pass: str = "toor"
    additional: Dict[str, Any] = field(default_factory=dict)
    subordinate_configs: Dict[str, AgentAPIConfig] = field(default_factory=dict)

    def get_subordinate_config(self, role: str) -> AgentAPIConfig:
        """Get API configuration for a specific subordinate role"""
        return self.subordinate_configs.get(role, AgentAPIConfig()).merge_with_default(self)

class AgentContext:
    _contexts: dict[str, "AgentContext"] = {}
    _counter: int = 0

    def __init__(
        self,
        config: AgentConfig,
        id: str | None = None,
        name: str | None = None,
        agent0: "Agent|None" = None,
        log: Log.Log | None = None,
        paused: bool = False,
        streaming_agent: "Agent|None" = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.config = config
        self.log = log or Log.Log()
        self.agent0 = agent0 or Agent(0, self.config, self)
        self.paused = paused
        self.streaming_agent = streaming_agent
        self.process: DeferredTask | None = None
        AgentContext._counter += 1
        self.no = AgentContext._counter
        AgentContext._contexts[self.id] = self

    @staticmethod
    def get(id: str) -> Optional["AgentContext"]:
        return AgentContext._contexts.get(id, None)

    @staticmethod
    def first() -> Optional["AgentContext"]:
        if not AgentContext._contexts:
            return None
        return list(AgentContext._contexts.values())[0]

    @staticmethod
    def remove(id: str) -> Optional["AgentContext"]:
        context = AgentContext._contexts.pop(id, None)
        if context and context.process:
            context.process.kill()
        return context

    def reset(self) -> None:
        if self.process:
            self.process.kill()
        self.log.reset()
        self.agent0 = Agent(0, self.config, self)
        self.streaming_agent = None
        self.paused = False

    def communicate(self, msg: str, broadcast_level: int = 1) -> DeferredTask:
        self.paused = False  # unpause if paused

        current_agent = self.streaming_agent if self.streaming_agent else self.agent0

        if self.process and self.process.is_alive():
            # Set intervention messages to agent(s)
            intervention_agent = current_agent
            while intervention_agent and broadcast_level != 0:
                intervention_agent.intervention_message = msg
                broadcast_level -= 1
                intervention_agent = intervention_agent.get_data("superior")
        else:
            self.process = DeferredTask(self._process_chain, current_agent, msg)

        return self.process

    async def _process_chain(self, agent: 'Agent', msg: str, user: bool = True) -> str:
        try:
            msg_template = (
                agent.read_prompt("fw.user_message.md", message=msg)
                if user
                else agent.read_prompt(
                    "fw.tool_response.md",
                    tool_name="call_subordinate",
                    tool_response=msg,
                )
            )
            response = await agent.monologue(msg_template)
            superior = agent.get_data("superior")
            if superior:
                response = await self._process_chain(superior, response, False)
            return response
        except Exception as e:
            agent.handle_critical_exception(e)
            raise

class LoopData:
    def __init__(self):
        self.iteration: int = -1
        self.system: list[str] = []
        self.message: str = ""
        self.history_from: int = 0
        self.history: list = []

class Message:
    def __init__(self):
        self.segments: list[str] = []
        self.human: bool = False
        self.timestamp: float = time.time()

class Monologue:
    def __init__(self):
        self.done: bool = False
        self.summary: str = ""
        self.messages: list[Message] = []
        self.start_time: float = time.time()

    def finish(self):
        self.done = True
        self.end_time: float = time.time()

class History:
    def __init__(self):
        self.monologues: list[Monologue] = []
        self.start_monologue()

    def current_monologue(self) -> Monologue:
        return self.monologues[-1]

    def start_monologue(self) -> Monologue:
        if self.monologues:
            self.current_monologue().finish()
        self.monologues.append(Monologue())
        return self.current_monologue()

class Agent:
    def __init__(
        self, 
        number: int, 
        config: AgentConfig, 
        context: Optional['AgentContext'] = None,
        role: str = "",
    ):
        # Core initialization
        self.config = AgentConfig(**vars(config))
        self.role = role
        self.number = number
        self.agent_name = f"Agent {self.number}"
        self.context = context or AgentContext(config)
        
        # State management
        self.history: list[Any] = []
        self.last_message: str = ""
        self.intervention_message: str = ""
        self.data: Dict[str, Any] = {}
        
        # Rate limiting
        self.rate_limiter = rate_limiter.RateLimiter(
            self.context.log,
            max_calls=self.config.rate_limit_requests,
            max_input_tokens=self.config.rate_limit_input_tokens,
            max_output_tokens=self.config.rate_limit_output_tokens,
            window_seconds=self.config.rate_limit_seconds,
        )

        # Apply role-specific configuration
        if role and role in self.config.subordinate_configs:
            role_config = self.config.get_subordinate_config(role)
            if role_config.chat_model:
                self.config.chat_model = role_config.chat_model
            if role_config.utility_model:
                self.config.utility_model = role_config.utility_model

    async def monologue(self, msg: str) -> str:
        while True:
            try:
                loop_data = LoopData()
                loop_data.message = msg
                loop_data.history_from = len(self.history)

                # Start monologue extensions
                await self.call_extensions("monologue_start", loop_data=loop_data)

                printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)
                await self.append_message(msg, human=True)

                while True:
                    self.context.streaming_agent = self
                    agent_response = ""
                    loop_data.iteration += 1

                    try:
                        # Prepare system prompt and history
                        loop_data.system = []
                        loop_data.history = self.history
                        await self.call_extensions("message_loop_prompts", loop_data=loop_data)

                        # Build and execute chain
                        response = await self._execute_chain(loop_data, printer)
                        
                        # Process response
                        if response:
                            return response

                    except InterventionException:
                        continue  # Continue with conversation loop
                    except RepairableException as e:
                        await self._handle_repairable_error(e)
                    except Exception as e:
                        self.handle_critical_exception(e)

                    finally:
                        await self.call_extensions("message_loop_end", loop_data=loop_data)

            except InterventionException:
                continue  # Start over
            except Exception as e:
                self.handle_critical_exception(e)
            finally:
                self.context.streaming_agent = None
                await self.call_extensions("monologue_end", loop_data=loop_data)

    async def _execute_chain(self, loop_data: LoopData, printer: PrintStyle) -> Optional[str]:
        # Build chain
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="\n\n".join(loop_data.system)),
            MessagesPlaceholder(variable_name="messages"),
        ])
        chain = prompt | self.config.chat_model

        # Rate limiting
        formatted_inputs = prompt.format(messages=self.history)
        tokens = int(len(formatted_inputs) / 4)
        self.rate_limiter.limit_call_and_input(tokens)

        # Execute chain
        PrintStyle(bold=True, font_color="green", padding=True, background_color="white").print(
            f"{self.agent_name}: Generating"
        )
        log = self.context.log.log(type="agent", heading=f"{self.agent_name}: Generating")

        agent_response = ""
        async for chunk in chain.astream({"messages": loop_data.history}):
            await self.handle_intervention(agent_response)
            
            content = self._extract_chunk_content(chunk)
            if content:
                printer.stream(content)
                agent_response += content
                self.log_from_stream(agent_response, log)

        self.rate_limiter.set_output_tokens(int(len(agent_response) / 4))
        await self.handle_intervention(agent_response)

        # Handle response
        if self.last_message == agent_response:
            await self._handle_repeated_message(agent_response)
            return None

        await self.append_message(agent_response)
        return await self.process_tools(agent_response)

    def handle_critical_exception(self, exception: Exception) -> None:
        if isinstance(exception, HandledException):
            raise exception
        elif isinstance(exception, asyncio.CancelledError):
            PrintStyle(font_color="white", background_color="red", padding=True).print(
                f"Context {self.context.id} terminated during message loop"
            )
            raise HandledException(exception)
        else:
            error_message = errors.format_error(exception)
            PrintStyle(font_color="red", padding=True).print(error_message)
            self.context.log.log(type="error", content=error_message)
            raise HandledException(exception)

    async def handle_intervention(self, progress: str = "") -> None:
        while self.context.paused:
            await asyncio.sleep(0.1)
        if self.intervention_message:
            msg = self.intervention_message
            self.intervention_message = ""
            if progress.strip():
                await self.append_message(progress)
            user_msg = self.read_prompt("fw.intervention.md", user_message=msg)
            await self.append_message(user_msg, human=True)
            raise InterventionException(msg)

    async def create_subordinate(self, role: str = "") -> 'Agent':
        subordinate = Agent(
            number=self.number + 1,
            config=self.config,
            context=self.context,
            role=role
        )
        subordinate.set_data("superior", self)
        self.set_data("subordinate", subordinate)
        return subordinate

    # Helper methods
    def get_data(self, field: str) -> Any:
        return self.data.get(field, None)

    def set_data(self, field: str, value: Any) -> None:
        self.data[field] = value

    def read_prompt(self, file: str, **kwargs) -> str:
        prompt_dir = files.get_abs_path("prompts/default")
        backup_dir = []
        if self.config.prompts_subdir:
            prompt_dir = files.get_abs_path("prompts", self.config.prompts_subdir)
            backup_dir.append(files.get_abs_path("prompts/default"))
        return files.read_file(
            files.get_abs_path(prompt_dir, file), 
            backup_dirs=backup_dir, 
            **kwargs
        )

    def log_from_stream(self, stream: str, log_item: Log.LogItem) -> None:
        try:
            if len(stream) >= 25:
                response = DirtyJson.parse_string(stream)
                if isinstance(response, dict):
                    log_item.update(content=stream, kvps=response)
        except Exception:
            pass

     # Continuing the Agent class...

    async def append_message(self, msg: str, human: bool = False) -> None:
        message_type = "human" if human else "ai"
        if self.history and self.history[-1].type == message_type:
            self.history[-1].content += "\n\n" + msg
        else:
            new_message = HumanMessage(content=msg) if human else AIMessage(content=msg)
            self.history.append(new_message)
            await self.cleanup_history(
                self.config.msgs_keep_max,
                self.config.msgs_keep_start,
                self.config.msgs_keep_end,
            )
        if message_type == "ai":
            self.last_message = msg

    async def cleanup_history(self, max_msgs: int, keep_start: int, keep_end: int) -> list:
        if len(self.history) <= max_msgs:
            return self.history

        first_x = self.history[:keep_start]
        last_y = self.history[-keep_end:]
        middle_part = self.history[keep_start:-keep_end]

        # Ensure first message in middle is "human"
        if middle_part and middle_part[0].type != "human":
            if first_x:
                middle_part.insert(0, first_x.pop())

        # Ensure odd number of messages in middle
        if len(middle_part) % 2 == 0:
            middle_part = middle_part[:-1]

        new_middle_part = await self.replace_middle_messages(middle_part)
        self.history = first_x + new_middle_part + last_y
        return self.history

    async def replace_middle_messages(self, middle_messages: list) -> list:
        cleanup_prompt = self.read_prompt("fw.msg_cleanup.md")
        log_item = self.context.log.log(type="util", heading="Mid messages cleanup summary")

        PrintStyle(
            bold=True,
            font_color="orange",
            padding=True,
            background_color="white"
        ).print(f"{self.agent_name}: Mid messages cleanup summary")
        
        printer = PrintStyle(italic=True, font_color="orange", padding=False)

        def log_callback(content: str) -> None:
            printer.print(content)
            log_item.stream(content=content)

        summary = await self.call_utility_llm(
            system=cleanup_prompt,
            msg=self.concat_messages(middle_messages),
            callback=log_callback,
        )
        return [HumanMessage(content=summary)]

    async def call_utility_llm(
        self,
        system: str,
        msg: str,
        callback: Optional[Callable[[str], None]] = None
    ) -> str:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system),
            HumanMessage(content=msg)
        ])

        chain = prompt | self.config.utility_model
        response = ""

        formatted_inputs = prompt.format()
        tokens = int(len(formatted_inputs) / 4)
        self.rate_limiter.limit_call_and_input(tokens)

        async for chunk in chain.astream({}):
            await self.handle_intervention()
            content = self._extract_chunk_content(chunk)
            
            if callback and content:
                callback(content)
            
            response += content

        self.rate_limiter.set_output_tokens(int(len(response) / 4))
        return response

    async def process_tools(self, msg: str) -> Optional[str]:
        tool_request = extract_tools.json_parse_dirty(msg)

        if tool_request is not None:
            tool_name = tool_request.get("tool_name", "")
            tool_args = tool_request.get("tool_args", {})
            tool = self.get_tool(tool_name, tool_args, msg)

            await self.handle_intervention()
            await tool.before_execution(**tool_args)
            
            await self.handle_intervention()
            response = await tool.execute(**tool_args)
            
            await self.handle_intervention()
            await tool.after_execution(response)
            
            await self.handle_intervention()
            if response.break_loop:
                return response.message
        else:
            error_msg = self.read_prompt("fw.msg_misformat.md")
            await self.append_message(error_msg, human=True)
            PrintStyle(font_color="red", padding=True).print(error_msg)
            self.context.log.log(type="error", content=f"{self.agent_name}: Message misformat")
        
        return None

    def get_tool(self, name: str, args: dict, message: str, **kwargs):
        from python.tools.unknown import Unknown
        from python.helpers.tool import Tool

        classes = extract_tools.load_classes_from_folder(
            "python/tools", name + ".py", Tool
        )
        tool_class = classes[0] if classes else Unknown
        return tool_class(agent=self, name=name, args=args, message=message, **kwargs)

    async def call_extensions(self, folder: str, **kwargs) -> Any:
        from python.helpers.extension import Extension

        classes = extract_tools.load_classes_from_folder(
            "python/extensions/" + folder, "*", Extension
        )
        for cls in classes:
            await cls(agent=self).execute(**kwargs)

    def concat_messages(self, messages: list) -> str:
        return "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

    def _extract_chunk_content(self, chunk: Any) -> str:
        if isinstance(chunk, str):
            return chunk
        elif hasattr(chunk, "content"):
            return str(chunk.content)
        return str(chunk)

    async def _handle_repairable_error(self, error: RepairableException) -> None:
        error_message = errors.format_error(error)
        msg_response = self.read_prompt("fw.error.md", error=error_message)
        await self.append_message(msg_response, human=True)
        PrintStyle(font_color="red", padding=True).print(msg_response)
        self.context.log.log(type="error", content=msg_response)

    async def _handle_repeated_message(self, agent_response: str) -> None:
        await self.append_message(agent_response)
        warning_msg = self.read_prompt("fw.msg_repeat.md")
        await self.append_message(warning_msg, human=True)
        PrintStyle(font_color="orange", padding=True).print(warning_msg)
        self.context.log.log(type="warning", content=warning_msg)
