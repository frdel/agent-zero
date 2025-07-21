import asyncio
import nest_asyncio

nest_asyncio.apply()

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Coroutine, Dict
from enum import Enum
import uuid
import models

from python.helpers import extract_tools, files, errors, history, tokens
from python.helpers import dirty_json
from python.helpers.print_style import PrintStyle
from langchain_core.prompts import (
    ChatPromptTemplate,
)
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

import python.helpers.log as Log
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask
from typing import Callable
from python.helpers.localization import Localization


class AgentContextType(Enum):
    USER = "user"
    TASK = "task"
    MCP = "mcp"


class AgentContext:

    _contexts: dict[str, "AgentContext"] = {}
    _counter: int = 0

    def __init__(
        self,
        config: "AgentConfig",
        id: str | None = None,
        name: str | None = None,
        agent0: "Agent|None" = None,
        log: Log.Log | None = None,
        paused: bool = False,
        streaming_agent: "Agent|None" = None,
        created_at: datetime | None = None,
        type: AgentContextType = AgentContextType.USER,
        last_message: datetime | None = None,
    ):
        # build context
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.config = config
        self.log = log or Log.Log()
        self.agent0 = agent0 or Agent(0, self.config, self)
        self.paused = paused
        self.streaming_agent = streaming_agent
        self.task: DeferredTask | None = None
        self.created_at = created_at or datetime.now(timezone.utc)
        self.type = type
        AgentContext._counter += 1
        self.no = AgentContext._counter
        # set to start of unix epoch
        self.last_message = last_message or datetime.now(timezone.utc)

        existing = self._contexts.get(self.id, None)
        if existing:
            AgentContext.remove(self.id)
        self._contexts[self.id] = self

    @staticmethod
    def get(id: str):
        return AgentContext._contexts.get(id, None)

    @staticmethod
    def first():
        if not AgentContext._contexts:
            return None
        return list(AgentContext._contexts.values())[0]

    @staticmethod
    def all():
        return list(AgentContext._contexts.values())

    @staticmethod
    def remove(id: str):
        context = AgentContext._contexts.pop(id, None)
        if context and context.task:
            context.task.kill()
        return context

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "created_at": (
                Localization.get().serialize_datetime(self.created_at)
                if self.created_at
                else Localization.get().serialize_datetime(datetime.fromtimestamp(0))
            ),
            "no": self.no,
            "log_guid": self.log.guid,
            "log_version": len(self.log.updates),
            "log_length": len(self.log.logs),
            "paused": self.paused,
            "last_message": (
                Localization.get().serialize_datetime(self.last_message)
                if self.last_message
                else Localization.get().serialize_datetime(datetime.fromtimestamp(0))
            ),
            "type": self.type.value,
        }

    @staticmethod
    def log_to_all(
        type: Log.Type,
        heading: str | None = None,
        content: str | None = None,
        kvps: dict | None = None,
        temp: bool | None = None,
        update_progress: Log.ProgressUpdate | None = None,
        id: str | None = None,  # Add id parameter
        **kwargs,
    ) -> list[Log.LogItem]:
        items: list[Log.LogItem] = []
        for context in AgentContext.all():
            items.append(
                context.log.log(
                    type, heading, content, kvps, temp, update_progress, id, **kwargs
                )
            )
        return items

    def kill_process(self):
        if self.task:
            self.task.kill()

    def reset(self):
        self.kill_process()
        self.log.reset()
        self.agent0 = Agent(0, self.config, self)
        self.streaming_agent = None
        self.paused = False

    def nudge(self):
        self.kill_process()
        self.paused = False
        self.task = self.run_task(self.get_agent().monologue)
        return self.task

    def get_agent(self):
        return self.streaming_agent or self.agent0

    def communicate(self, msg: "UserMessage", broadcast_level: int = 1):
        self.paused = False  # unpause if paused

        current_agent = self.get_agent()

        if self.task and self.task.is_alive():
            # set intervention messages to agent(s):
            intervention_agent = current_agent
            while intervention_agent and broadcast_level != 0:
                intervention_agent.intervention = msg
                broadcast_level -= 1
                intervention_agent = intervention_agent.data.get(
                    Agent.DATA_NAME_SUPERIOR, None
                )
        else:
            self.task = self.run_task(self._process_chain, current_agent, msg)

        return self.task

    def run_task(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
    ):
        if not self.task:
            self.task = DeferredTask(
                thread_name=self.__class__.__name__,
            )
        self.task.start_task(func, *args, **kwargs)
        return self.task

    # this wrapper ensures that superior agents are called back if the chat was loaded from file and original callstack is gone
    async def _process_chain(self, agent: "Agent", msg: "UserMessage|str", user=True):
        try:
            msg_template = (
                agent.hist_add_user_message(msg)  # type: ignore
                if user
                else agent.hist_add_tool_result(
                    tool_name="call_subordinate", tool_result=msg  # type: ignore
                )
            )
            response = await agent.monologue()  # type: ignore
            superior = agent.data.get(Agent.DATA_NAME_SUPERIOR, None)
            if superior:
                response = await self._process_chain(superior, response, False)  # type: ignore
            return response
        except Exception as e:
            agent.handle_critical_exception(e)



@dataclass
class AgentConfig:
    chat_model: models.ModelConfig
    utility_model: models.ModelConfig
    embeddings_model: models.ModelConfig
    browser_model: models.ModelConfig
    mcp_servers: str
    prompts_subdir: str = ""
    memory_subdir: str = ""
    knowledge_subdirs: list[str] = field(default_factory=lambda: ["default", "custom"])
    code_exec_docker_enabled: bool = False
    code_exec_docker_name: str = "A0-dev"
    code_exec_docker_image: str = "agent0ai/agent-zero-run:development"
    code_exec_docker_ports: dict[str, int] = field(
        default_factory=lambda: {"22/tcp": 55022, "80/tcp": 55080}
    )
    code_exec_docker_volumes: dict[str, dict[str, str]] = field(
        default_factory=lambda: {
            files.get_base_dir(): {"bind": "/a0", "mode": "rw"},
            files.get_abs_path("work_dir"): {"bind": "/root", "mode": "rw"},
        }
    )
    code_exec_ssh_enabled: bool = True
    code_exec_ssh_addr: str = "localhost"
    code_exec_ssh_port: int = 55022
    code_exec_ssh_user: str = "root"
    code_exec_ssh_pass: str = ""
    additional: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserMessage:
    message: str
    attachments: list[str] = field(default_factory=list[str])
    system_message: list[str] = field(default_factory=list[str])


class LoopData:
    def __init__(self, **kwargs):
        self.iteration = -1
        self.system = []
        self.user_message: history.Message | None = None
        self.history_output: list[history.OutputMessage] = []
        self.extras_temporary: OrderedDict[str, history.MessageContent] = OrderedDict()
        self.extras_persistent: OrderedDict[str, history.MessageContent] = OrderedDict()
        self.last_response = ""
        self.params_temporary: dict = {}
        self.params_persistent: dict = {}

        # override values with kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


# intervention exception class - skips rest of message loop iteration
class InterventionException(Exception):
    pass


# killer exception class - not forwarded to LLM, cannot be fixed on its own, ends message loop
class RepairableException(Exception):
    pass


class HandledException(Exception):
    pass


class Agent:

    DATA_NAME_SUPERIOR = "_superior"
    DATA_NAME_SUBORDINATE = "_subordinate"
    DATA_NAME_CTX_WINDOW = "ctx_window"

    def __init__(
        self, number: int, config: AgentConfig, context: AgentContext | None = None
    ):

        # agent config
        self.config = config

        # agent context
        self.context = context or AgentContext(config=config, agent0=self)

        # non-config vars
        self.number = number
        self.agent_name = f"A{self.number}"

        self.history = history.History(self)
        self.last_user_message: history.Message | None = None
        self.intervention: UserMessage | None = None
        self.data = {}  # free data object all the tools can use

    async def monologue(self):
        while True:
            try:
                # loop data dictionary to pass to extensions
                self.loop_data = LoopData(user_message=self.last_user_message)
                # call monologue_start extensions
                await self.call_extensions("monologue_start", loop_data=self.loop_data)

                printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)

                # let the agent run message loop until he stops it with a response tool
                while True:

                    self.context.streaming_agent = self  # mark self as current streamer
                    self.loop_data.iteration += 1
                    self.loop_data.params_temporary = {}  # clear temporary params

                    # call message_loop_start extensions
                    await self.call_extensions(
                        "message_loop_start", loop_data=self.loop_data
                    )

                    try:
                        # prepare LLM chain (model, system, history)
                        prompt = await self.prepare_prompt(loop_data=self.loop_data)

                        # call before_main_llm_call extensions
                        await self.call_extensions("before_main_llm_call", loop_data=self.loop_data)

                        async def reasoning_callback(chunk: str, full: str):
                            if chunk == full:
                                printer.print("Reasoning: ")  # start of reasoning
                            printer.stream(chunk)
                            await self.handle_reasoning_stream(full)

                        async def stream_callback(chunk: str, full: str):
                            # output the agent response stream
                            if chunk == full:
                                printer.print("Response: ")  # start of response
                            printer.stream(chunk)
                            await self.handle_response_stream(full)

                        # call main LLM
                        agent_response, _reasoning = await self.call_chat_model(
                            messages=prompt,
                            response_callback=stream_callback,
                            reasoning_callback=reasoning_callback,
                        )

                        await self.handle_intervention(agent_response)

                        if (
                            self.loop_data.last_response == agent_response
                        ):  # if assistant_response is the same as last message in history, let him know
                            # Append the assistant's response to the history
                            self.hist_add_ai_response(agent_response)
                            # Append warning message to the history
                            warning_msg = self.read_prompt("fw.msg_repeat.md")
                            self.hist_add_warning(message=warning_msg)
                            PrintStyle(font_color="orange", padding=True).print(
                                warning_msg
                            )
                            self.context.log.log(type="warning", content=warning_msg)

                        else:  # otherwise proceed with tool
                            # Append the assistant's response to the history
                            self.hist_add_ai_response(agent_response)
                            # process tools requested in agent message
                            tools_result = await self.process_tools(agent_response)
                            if tools_result:  # final response of message loop available
                                return tools_result  # break the execution if the task is done

                    # exceptions inside message loop:
                    except InterventionException as e:
                        pass  # intervention message has been handled in handle_intervention(), proceed with conversation loop
                    except RepairableException as e:
                        # Forward repairable errors to the LLM, maybe it can fix them
                        error_message = errors.format_error(e)
                        self.hist_add_warning(error_message)
                        PrintStyle(font_color="red", padding=True).print(error_message)
                        self.context.log.log(type="error", content=error_message)
                    except Exception as e:
                        # Other exception kill the loop
                        self.handle_critical_exception(e)

                    finally:
                        # call message_loop_end extensions
                        await self.call_extensions(
                            "message_loop_end", loop_data=self.loop_data
                        )

            # exceptions outside message loop:
            except InterventionException as e:
                pass  # just start over
            except Exception as e:
                self.handle_critical_exception(e)
            finally:
                self.context.streaming_agent = None  # unset current streamer
                # call monologue_end extensions
                await self.call_extensions("monologue_end", loop_data=self.loop_data)  # type: ignore

    async def prepare_prompt(self, loop_data: LoopData) -> list[BaseMessage]:
        self.context.log.set_progress("Building prompt")

        # call extensions before setting prompts
        await self.call_extensions("message_loop_prompts_before", loop_data=loop_data)

        # set system prompt and message history
        loop_data.system = await self.get_system_prompt(self.loop_data)
        loop_data.history_output = self.history.output()

        # and allow extensions to edit them
        await self.call_extensions("message_loop_prompts_after", loop_data=loop_data)

        # concatenate system prompt
        system_text = "\n\n".join(loop_data.system)

        # join extras
        extras = history.Message(
            False,
            content=self.read_prompt(
                "agent.context.extras.md",
                extras=dirty_json.stringify(
                    {**loop_data.extras_persistent, **loop_data.extras_temporary}
                ),
            ),
        ).output()
        loop_data.extras_temporary.clear()

        # convert history + extras to LLM format
        history_langchain: list[BaseMessage] = history.output_langchain(
            loop_data.history_output + extras
        )

        # build full prompt from system prompt, message history and extrS
        full_prompt: list[BaseMessage] = [
            SystemMessage(content=system_text),
            *history_langchain,
        ]
        full_text = ChatPromptTemplate.from_messages(full_prompt).format()

        # store as last context window content
        self.set_data(
            Agent.DATA_NAME_CTX_WINDOW,
            {
                "text": full_text,
                "tokens": tokens.approximate_tokens(full_text),
            },
        )

        return full_prompt

    def handle_critical_exception(self, exception: Exception):
        if isinstance(exception, HandledException):
            raise exception  # Re-raise the exception to kill the loop
        elif isinstance(exception, asyncio.CancelledError):
            # Handling for asyncio.CancelledError
            PrintStyle(font_color="white", background_color="red", padding=True).print(
                f"Context {self.context.id} terminated during message loop"
            )
            raise HandledException(
                exception
            )  # Re-raise the exception to cancel the loop
        else:
            # Handling for general exceptions
            error_text = errors.error_text(exception)
            error_message = errors.format_error(exception)
            PrintStyle(font_color="red", padding=True).print(error_message)
            self.context.log.log(
                type="error",
                heading="Error",
                content=error_message,
                kvps={"text": error_text},
            )
            raise HandledException(exception)  # Re-raise the exception to kill the loop

    async def get_system_prompt(self, loop_data: LoopData) -> list[str]:
        system_prompt = []
        await self.call_extensions(
            "system_prompt", system_prompt=system_prompt, loop_data=loop_data
        )
        return system_prompt

    def parse_prompt(self, file: str, **kwargs):
        prompt_dir = files.get_abs_path("prompts/default")
        backup_dir = []
        if (
            self.config.prompts_subdir
        ):  # if agent has custom folder, use it and use default as backup
            prompt_dir = files.get_abs_path("prompts", self.config.prompts_subdir)
            backup_dir.append(files.get_abs_path("prompts/default"))
        prompt = files.parse_file(
            files.get_abs_path(prompt_dir, file), _backup_dirs=backup_dir, **kwargs
        )
        return prompt

    def read_prompt(self, file: str, **kwargs) -> str:
        prompt_dir = files.get_abs_path("prompts/default")
        backup_dir = []
        if (
            self.config.prompts_subdir
        ):  # if agent has custom folder, use it and use default as backup
            prompt_dir = files.get_abs_path("prompts", self.config.prompts_subdir)
            backup_dir.append(files.get_abs_path("prompts/default"))
        prompt = files.read_file(
            files.get_abs_path(prompt_dir, file), _backup_dirs=backup_dir, **kwargs
        )
        prompt = files.remove_code_fences(prompt)
        return prompt

    def get_data(self, field: str):
        return self.data.get(field, None)

    def set_data(self, field: str, value):
        self.data[field] = value

    def hist_add_message(
        self, ai: bool, content: history.MessageContent, tokens: int = 0
    ):
        self.last_message = datetime.now(timezone.utc)
        return self.history.add_message(ai=ai, content=content, tokens=tokens)

    def hist_add_user_message(self, message: UserMessage, intervention: bool = False):
        self.history.new_topic()  # user message starts a new topic in history

        # load message template based on intervention
        if intervention:
            content = self.parse_prompt(
                "fw.intervention.md",
                message=message.message,
                attachments=message.attachments,
                system_message=message.system_message,
            )
        else:
            content = self.parse_prompt(
                "fw.user_message.md",
                message=message.message,
                attachments=message.attachments,
                system_message=message.system_message,
            )

        # remove empty parts from template
        if isinstance(content, dict):
            content = {k: v for k, v in content.items() if v}

        # add to history
        msg = self.hist_add_message(False, content=content)  # type: ignore
        self.last_user_message = msg
        return msg

    def hist_add_ai_response(self, message: str):
        self.loop_data.last_response = message
        content = self.parse_prompt("fw.ai_response.md", message=message)
        return self.hist_add_message(True, content=content)

    def hist_add_warning(self, message: history.MessageContent):
        content = self.parse_prompt("fw.warning.md", message=message)
        return self.hist_add_message(False, content=content)

    def hist_add_tool_result(self, tool_name: str, tool_result: str):
        content = self.parse_prompt(
            "fw.tool_result.md", tool_name=tool_name, tool_result=tool_result
        )
        return self.hist_add_message(False, content=content)

    def concat_messages(
        self, messages
    ):  # TODO add param for message range, topic, history
        return self.history.output_text(human_label="user", ai_label="assistant")

    def get_chat_model(self):
        return models.get_chat_model(
            self.config.chat_model.provider,
            self.config.chat_model.name,
            **self.config.chat_model.build_kwargs(),
        )

    def get_utility_model(self):
        return models.get_chat_model(
            self.config.utility_model.provider,
            self.config.utility_model.name,
            **self.config.utility_model.build_kwargs(),
        )

    def get_browser_model(self):
        return models.get_browser_model(
            self.config.browser_model.provider,
            self.config.browser_model.name,
            **self.config.browser_model.build_kwargs(),
        )

    def get_embedding_model(self):
        return models.get_embedding_model(
            self.config.embeddings_model.provider,
            self.config.embeddings_model.name,
            **self.config.embeddings_model.build_kwargs(),
        )

    async def call_utility_model(
        self,
        system: str,
        message: str,
        callback: Callable[[str], Awaitable[None]] | None = None,
        background: bool = False,
    ):
        model = self.get_utility_model()

        # rate limiter
        limiter = await self.rate_limiter(
            self.config.utility_model, f"SYSTEM: {system}\nUSER: {message}", background
        )

        # add output tokens to rate limiter in tokens callback
        async def tokens_callback(delta: str, tokens: int):
            await self.handle_intervention()
            limiter.add(output=tokens)

        # propagate stream to callback if set
        async def stream_callback(chunk: str, total: str):
            if callback:
                await callback(chunk)

        response, _reasoning = await model.unified_call(
            system_message=system,
            user_message=message,
            response_callback=stream_callback,
            tokens_callback=tokens_callback,
        )

        return response

    async def call_chat_model(
        self,
        messages: list[BaseMessage],
        response_callback: Callable[[str, str], Awaitable[None]] | None = None,
        reasoning_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        response = ""

        # model class
        model = self.get_chat_model()

        # rate limiter
        limiter = await self.rate_limiter(
            self.config.chat_model, ChatPromptTemplate.from_messages(messages).format()
        )

        # add output tokens to rate limiter in tokens callback
        async def tokens_callback(delta: str, tokens: int):
            await self.handle_intervention()
            limiter.add(output=tokens)

        # call model
        response, reasoning = await model.unified_call(
            messages=messages,
            reasoning_callback=reasoning_callback,
            response_callback=response_callback,
            tokens_callback=tokens_callback,
        )

        return response, reasoning

    async def rate_limiter(
        self, model_config: models.ModelConfig, input: str, background: bool = False
    ):
        # rate limiter log
        wait_log = None

        async def wait_callback(msg: str, key: str, total: int, limit: int):
            nonlocal wait_log
            if not wait_log:
                wait_log = self.context.log.log(
                    type="util",
                    update_progress="none",
                    heading=msg,
                    model=f"{model_config.provider.value}\\{model_config.name}",
                )
            wait_log.update(heading=msg, key=key, value=total, limit=limit)
            if not background:
                self.context.log.set_progress(msg, -1)

        # rate limiter
        limiter = models.get_rate_limiter(
            model_config.provider,
            model_config.name,
            model_config.limit_requests,
            model_config.limit_input,
            model_config.limit_output,
        )
        limiter.add(input=tokens.approximate_tokens(input))
        limiter.add(requests=1)
        await limiter.wait(callback=wait_callback)
        return limiter

    async def handle_intervention(self, progress: str = ""):
        while self.context.paused:
            await asyncio.sleep(0.1)  # wait if paused
        if (
            self.intervention
        ):  # if there is an intervention message, but not yet processed
            msg = self.intervention
            self.intervention = None  # reset the intervention message
            if progress.strip():
                self.hist_add_ai_response(progress)
            # append the intervention message
            self.hist_add_user_message(msg, intervention=True)
            raise InterventionException(msg)

    async def wait_if_paused(self):
        while self.context.paused:
            await asyncio.sleep(0.1)

    async def process_tools(self, msg: str):
        # search for tool usage requests in agent message
        tool_request = extract_tools.json_parse_dirty(msg)

        if tool_request is not None:
            raw_tool_name = tool_request.get("tool_name", "")  # Get the raw tool name
            tool_args = tool_request.get("tool_args", {})

            tool_name = raw_tool_name  # Initialize tool_name with raw_tool_name
            tool_method = None  # Initialize tool_method

            # Split raw_tool_name into tool_name and tool_method if applicable
            if ":" in raw_tool_name:
                tool_name, tool_method = raw_tool_name.split(":", 1)

            tool = None  # Initialize tool to None

            # Try getting tool from MCP first
            try:
                import python.helpers.mcp_handler as mcp_helper

                mcp_tool_candidate = mcp_helper.MCPConfig.get_instance().get_tool(
                    self, tool_name
                )
                if mcp_tool_candidate:
                    tool = mcp_tool_candidate
            except ImportError:
                PrintStyle(
                    background_color="black", font_color="yellow", padding=True
                ).print("MCP helper module not found. Skipping MCP tool lookup.")
            except Exception as e:
                PrintStyle(
                    background_color="black", font_color="red", padding=True
                ).print(f"Failed to get MCP tool '{tool_name}': {e}")

            # Fallback to local get_tool if MCP tool was not found or MCP lookup failed
            if not tool:
                tool = self.get_tool(
                    name=tool_name, method=tool_method, args=tool_args, message=msg, loop_data=self.loop_data
                )

            if tool:
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
                error_detail = (
                    f"Tool '{raw_tool_name}' not found or could not be initialized."
                )
                self.hist_add_warning(error_detail)
                PrintStyle(font_color="red", padding=True).print(error_detail)
                self.context.log.log(
                    type="error", content=f"{self.agent_name}: {error_detail}"
                )
        else:
            warning_msg_misformat = self.read_prompt("fw.msg_misformat.md")
            self.hist_add_warning(warning_msg_misformat)
            PrintStyle(font_color="red", padding=True).print(warning_msg_misformat)
            self.context.log.log(
                type="error",
                content=f"{self.agent_name}: Message misformat, no valid tool request found.",
            )

    async def handle_reasoning_stream(self, stream: str):
        await self.call_extensions(
            "reasoning_stream",
            loop_data=self.loop_data,
            text=stream,
        )

    async def handle_response_stream(self, stream: str):
        try:
            if len(stream) < 25:
                return  # no reason to try
            response = DirtyJson.parse_string(stream)
            if isinstance(response, dict):
                await self.call_extensions(
                    "response_stream",
                    loop_data=self.loop_data,
                    text=stream,
                    parsed=response,
                )

        except Exception as e:
            pass

    def get_tool(
        self, name: str, method: str | None, args: dict, message: str, loop_data: LoopData | None, **kwargs
    ):
        from python.tools.unknown import Unknown
        from python.helpers.tool import Tool

        classes = extract_tools.load_classes_from_folder(
            "python/tools", name + ".py", Tool
        )
        tool_class = classes[0] if classes else Unknown
        return tool_class(
            agent=self, name=name, method=method, args=args, message=message, loop_data=loop_data, **kwargs
        )

    async def call_extensions(self, folder: str, **kwargs) -> Any:
        from python.helpers.extension import Extension

        cache = {}  # some extensions can be called very often, like response_stream

        if folder in cache:
            classes = cache[folder]
        else:
            classes = extract_tools.load_classes_from_folder(
                "python/extensions/" + folder, "*", Extension
            )
            cache[folder] = classes

        for cls in classes:
            await cls(agent=self).execute(**kwargs)
