import asyncio
from dataclasses import dataclass, field
import time, importlib, inspect, os, json
from typing import Any, Optional, Dict, TypedDict
import uuid
from python.helpers import extract_tools, rate_limiter, files, errors
from python.helpers.print_style import PrintStyle
from langchain.schema import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.language_models.llms import BaseLLM
from langchain_core.embeddings import Embeddings
import python.helpers.log as Log
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask
from typing import Callable


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
    ):
        # build context
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
    def remove(id: str):
        context = AgentContext._contexts.pop(id, None)
        if context and context.process:
            context.process.kill()
        return context

    def reset(self):
        if self.process:
            self.process.kill()
        self.log.reset()
        self.agent0 = Agent(0, self.config, self)
        self.streaming_agent = None
        self.paused = False

    def communicate(self, msg: str, broadcast_level: int = 1):
        self.paused = False  # unpause if paused

        if self.streaming_agent:
            current_agent = self.streaming_agent
        else:
            current_agent = self.agent0

        if self.process and self.process.is_alive():
            # set intervention messages to agent(s):
            intervention_agent = current_agent
            while intervention_agent and broadcast_level != 0:
                intervention_agent.intervention_message = msg
                broadcast_level -= 1
                intervention_agent = intervention_agent.data.get("superior", None)
        else:

            # self.process = DeferredTask(current_agent.monologue, msg)
            self.process = DeferredTask(self._process_chain, current_agent, msg)

        return self.process

    # this wrapper ensures that superior agents are called back if the chat was loaded from file and original callstack is gone
    async def _process_chain(self, agent: 'Agent', msg: str, user=True):
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
            superior = agent.data.get("superior", None)
            if superior:
                response = await self._process_chain(superior, response, False)
            return response
        except Exception as e:
            agent.handle_critical_exception(e)

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


class Message:
    def __init__(self):
        self.segments: list[str]
        self.human: bool


class Monologue:
    def __init__(self):
        self.done = False
        self.summary: str = ""
        self.messages: list[Message] = []

    def finish(self):
        pass


class History:
    def __init__(self):
        self.monologues: list[Monologue] = []
        self.start_monologue()

    def current_monologue(self):
        return self.monologues[-1]

    def start_monologue(self):
        if self.monologues:
            self.current_monologue().finish()
        self.monologues.append(Monologue())
        return self.current_monologue()


class LoopData:
    def __init__(self):
        self.iteration = -1
        self.system = []
        self.message = ""
        self.history_from = 0
        self.history = []


# intervention exception class - skips rest of message loop iteration
class InterventionException(Exception):
    pass


# killer exception class - not forwarded to LLM, cannot be fixed on its own, ends message loop
class RepairableException(Exception):
    pass


class HandledException(Exception):
    pass


class Agent:

    def __init__(
        self, number: int, config: AgentConfig, context: AgentContext | None = None
    ):

        # agent config
        self.config = config

        # agent context
        self.context = context or AgentContext(config)

        # non-config vars
        self.number = number
        self.agent_name = f"Agent {self.number}"

        self.history = []
        self.last_message = ""
        self.intervention_message = ""
        self.rate_limiter = rate_limiter.RateLimiter(
            self.context.log,
            max_calls=self.config.rate_limit_requests,
            max_input_tokens=self.config.rate_limit_input_tokens,
            max_output_tokens=self.config.rate_limit_output_tokens,
            window_seconds=self.config.rate_limit_seconds,
        )
        self.data = {}  # free data object all the tools can use

    async def monologue(self, msg: str):
        while True:
            try:
                # loop data dictionary to pass to extensions
                loop_data = LoopData()
                loop_data.message = msg
                loop_data.history_from = len(self.history)

                # call monologue_start extensions
                await self.call_extensions("monologue_start", loop_data=loop_data)

                printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)
                user_message = loop_data.message
                await self.append_message(user_message, human=True)

                # let the agent run message loop until he stops it with a response tool
                while True:

                    self.context.streaming_agent = self  # mark self as current streamer
                    agent_response = ""
                    loop_data.iteration += 1

                    try:

                        # set system prompt and message history
                        loop_data.system = []
                        loop_data.history = self.history

                        # and allow extensions to edit them
                        await self.call_extensions(
                            "message_loop_prompts", loop_data=loop_data
                        )

                        # build chain from system prompt, message history and model
                        prompt = ChatPromptTemplate.from_messages(
                            [
                                SystemMessage(content="\n\n".join(loop_data.system)),
                                MessagesPlaceholder(variable_name="messages"),
                            ]
                        )
                        chain = prompt | self.config.chat_model

                        # rate limiter TODO - move to extension, make per-model
                        formatted_inputs = prompt.format(messages=self.history)
                        tokens = int(len(formatted_inputs) / 4)
                        self.rate_limiter.limit_call_and_input(tokens)

                        # output that the agent is starting
                        PrintStyle(
                            bold=True,
                            font_color="green",
                            padding=True,
                            background_color="white",
                        ).print(f"{self.agent_name}: Generating")
                        log = self.context.log.log(
                            type="agent", heading=f"{self.agent_name}: Generating"
                        )

                        async for chunk in chain.astream(
                            {"messages": loop_data.history}
                        ):
                            await self.handle_intervention(
                                agent_response
                            )  # wait for intervention and handle it, if paused

                            if isinstance(chunk, str):
                                content = chunk
                            elif hasattr(chunk, "content"):
                                content = str(chunk.content)
                            else:
                                content = str(chunk)

                            if content:
                                printer.stream(
                                    content
                                )  # output the agent response stream
                                agent_response += (
                                    content  # concatenate stream into the response
                                )
                                self.log_from_stream(agent_response, log)

                        self.rate_limiter.set_output_tokens(
                            int(len(agent_response) / 4)
                        )  # rough estimation

                        await self.handle_intervention(agent_response)

                        if (
                            self.last_message == agent_response
                        ):  # if assistant_response is the same as last message in history, let him know
                            await self.append_message(
                                agent_response
                            )  # Append the assistant's response to the history
                            warning_msg = self.read_prompt("fw.msg_repeat.md")
                            await self.append_message(
                                warning_msg, human=True
                            )  # Append warning message to the history
                            PrintStyle(font_color="orange", padding=True).print(
                                warning_msg
                            )
                            self.context.log.log(type="warning", content=warning_msg)

                        else:  # otherwise proceed with tool
                            await self.append_message(
                                agent_response
                            )  # Append the assistant's response to the history
                            tools_result = await self.process_tools(
                                agent_response
                            )  # process tools requested in agent message
                            if tools_result:  # final response of message loop available
                                return tools_result  # break the execution if the task is done

                    # exceptions inside message loop:
                    except InterventionException as e:
                        pass  # intervention message has been handled in handle_intervention(), proceed with conversation loop
                    except (
                        RepairableException
                    ) as e:  # Forward repairable errors to the LLM, maybe it can fix them
                        error_message = errors.format_error(e)
                        msg_response = self.read_prompt(
                            "fw.error.md", error=error_message
                        )  # error message template
                        await self.append_message(msg_response, human=True)
                        PrintStyle(font_color="red", padding=True).print(msg_response)
                        self.context.log.log(type="error", content=msg_response)
                    except Exception as e:  # Other exception kill the loop
                        self.handle_critical_exception(e)

                    finally:
                        # call message_loop_end extensions
                        await self.call_extensions(
                            "message_loop_end", loop_data=loop_data
                        )

            # exceptions outside message loop:
            except InterventionException as e:
                pass  # just start over
            except Exception as e:
                self.handle_critical_exception(e)
            finally:
                self.context.streaming_agent = None  # unset current streamer
                # call monologue_end extensions
                await self.call_extensions("monologue_end", loop_data=loop_data)  # type: ignore

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
            error_message = errors.format_error(exception)
            PrintStyle(font_color="red", padding=True).print(error_message)
            self.context.log.log(type="error", content=error_message)
            raise HandledException(exception)  # Re-raise the exception to kill the loop

    def read_prompt(self, file: str, **kwargs) -> str:
        prompt_dir = files.get_abs_path("prompts/default")
        backup_dir = []
        if (
            self.config.prompts_subdir
        ):  # if agent has custom folder, use it and use default as backup
            prompt_dir = files.get_abs_path("prompts", self.config.prompts_subdir)
            backup_dir.append(files.get_abs_path("prompts/default"))
        return files.read_file(
            files.get_abs_path(prompt_dir, file), backup_dirs=backup_dir, **kwargs
        )

    def get_data(self, field: str):
        return self.data.get(field, None)

    def set_data(self, field: str, value):
        self.data[field] = value

    async def append_message(self, msg: str, human: bool = False):
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

    def concat_messages(self, messages):
        return "\n".join([f"{msg.type}: {msg.content}" for msg in messages])

    async def call_utility_llm(
        self, system: str, msg: str, callback: Callable[[str], None] | None = None
    ):
        prompt = ChatPromptTemplate.from_messages(
            [SystemMessage(content=system), HumanMessage(content=msg)]
        )

        chain = prompt | self.config.utility_model
        response = ""

        formatted_inputs = prompt.format()
        tokens = int(len(formatted_inputs) / 4)
        self.rate_limiter.limit_call_and_input(tokens)

        async for chunk in chain.astream({}):
            await self.handle_intervention()  # wait for intervention and handle it, if paused

            if isinstance(chunk, str):
                content = chunk
            elif hasattr(chunk, "content"):
                content = str(chunk.content)
            else:
                content = str(chunk)

            if callback:
                callback(content)

            response += content

        self.rate_limiter.set_output_tokens(int(len(response) / 4))

        return response

    def get_last_message(self):
        if self.history:
            return self.history[-1]

    async def replace_middle_messages(self, middle_messages):
        cleanup_prompt = self.read_prompt("fw.msg_cleanup.md")
        log_item = self.context.log.log(
            type="util", heading="Mid messages cleanup summary"
        )

        PrintStyle(
            bold=True, font_color="orange", padding=True, background_color="white"
        ).print(f"{self.agent_name}: Mid messages cleanup summary")
        printer = PrintStyle(italic=True, font_color="orange", padding=False)

        def log_callback(content):
            printer.print(content)
            log_item.stream(content=content)

        summary = await self.call_utility_llm(
            system=cleanup_prompt,
            msg=self.concat_messages(middle_messages),
            callback=log_callback,
        )
        new_human_message = HumanMessage(content=summary)
        return [new_human_message]

    async def cleanup_history(self, max: int, keep_start: int, keep_end: int):
        if len(self.history) <= max:
            return self.history

        first_x = self.history[:keep_start]
        last_y = self.history[-keep_end:]

        # Identify the middle part
        middle_part = self.history[keep_start:-keep_end]

        # Ensure the first message in the middle is "human", if not, move one message back
        if middle_part and middle_part[0].type != "human":
            if len(first_x) > 0:
                middle_part.insert(0, first_x.pop())

        # Ensure the middle part has an odd number of messages
        if len(middle_part) % 2 == 0:
            middle_part = middle_part[:-1]

        # Replace the middle part using the replacement function
        new_middle_part = await self.replace_middle_messages(middle_part)

        self.history = first_x + new_middle_part + last_y

        return self.history

    async def handle_intervention(self, progress: str = ""):
        while self.context.paused:
            await asyncio.sleep(0.1)  # wait if paused
        if (
            self.intervention_message
        ):  # if there is an intervention message, but not yet processed
            msg = self.intervention_message
            self.intervention_message = ""  # reset the intervention message
            if progress.strip():
                await self.append_message(
                    progress
                )  # append the response generated so far
            user_msg = self.read_prompt(
                "fw.intervention.md", user_message=msg
            )  # format the user intervention template
            await self.append_message(
                user_msg, human=True
            )  # append the intervention message
            raise InterventionException(msg)

    async def process_tools(self, msg: str):
        # search for tool usage requests in agent message
        tool_request = extract_tools.json_parse_dirty(msg)

        if tool_request is not None:
            tool_name = tool_request.get("tool_name", "")
            tool_args = tool_request.get("tool_args", {})
            tool = self.get_tool(tool_name, tool_args, msg)

            await self.handle_intervention()  # wait if paused and handle intervention message if needed
            await tool.before_execution(**tool_args)
            await self.handle_intervention()  # wait if paused and handle intervention message if needed
            response = await tool.execute(**tool_args)
            await self.handle_intervention()  # wait if paused and handle intervention message if needed
            await tool.after_execution(response)
            await self.handle_intervention()  # wait if paused and handle intervention message if needed
            if response.break_loop:
                return response.message
        else:
            msg = self.read_prompt("fw.msg_misformat.md")
            await self.append_message(msg, human=True)
            PrintStyle(font_color="red", padding=True).print(msg)
            self.context.log.log(
                type="error", content=f"{self.agent_name}: Message misformat"
            )

    def log_from_stream(self, stream: str, logItem: Log.LogItem):
        try:
            if len(stream) < 25:
                return  # no reason to try
            response = DirtyJson.parse_string(stream)
            if isinstance(response, dict):
                logItem.update(
                    content=stream, kvps=response
                )  # log if result is a dictionary already
        except Exception as e:
            pass

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
