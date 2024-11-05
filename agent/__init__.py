import asyncio
from typing import Any, Optional, Dict, List
import uuid
from python.helpers import extract_tools, rate_limiter, files, errors
from python.helpers.print_style import PrintStyle
from langchain import (
    AIMessage,
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessage,
    SystemMessage,
)
import python.helpers.log as Log
from python.helpers.dirty_json import DirtyJson
from python.helpers.defer import DeferredTask
from .agent_types import AgentException, LoopData
from .config import ConfigValidator, AgentConfig


class AgentContext:
    _contexts: Dict[str, "AgentContext"] = {}
    _counter: int = 0

    def __init__(
        self,
        config: AgentConfig,
        id: Optional[str] = None,
        name: Optional[str] = None,
        agent0: Optional["Agent"] = None,
        log: Optional[Log.Log] = None,
        paused: bool = False,
        streaming_agent: Optional["Agent"] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.name = name
        self.config = config
        self.log = log or Log.Log()
        self.agent0 = agent0 or Agent(0, self.config, self)
        self.paused = paused
        self.streaming_agent = streaming_agent
        self.process: Optional[DeferredTask] = None
        AgentContext._counter += 1
        self.no = AgentContext._counter
        self._contexts[self.id] = self

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

    def reset(self):
        if self.process:
            self.process.kill()
        self.log.reset()
        self.agent0 = Agent(0, self.config, self)
        self.streaming_agent = None
        self.paused = False

    def communicate(self, msg: str, broadcast_level: int = 1):
        self.paused = False

        if self.streaming_agent:
            current_agent = self.streaming_agent
        else:
            current_agent = self.agent0

        if self.process and self.process.is_alive():
            intervention_agent = current_agent
            while intervention_agent and broadcast_level != 0:
                intervention_agent.intervention_message = msg
                broadcast_level -= 1
                intervention_agent = intervention_agent.data.get("superior", None)
        else:
            self.process = DeferredTask(self._process_chain, current_agent, msg)

        return self.process

    async def _process_chain(self, agent: "Agent", msg: str, user: bool = True):
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


class Agent:
    def __init__(
        self, number: int, config: AgentConfig, context: Optional[AgentContext] = None
    ):
        if config is None:
            raise AgentException("AgentConfig must be provided")

        self.config = config
        self.context = context or AgentContext(config)
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
        self.data: Dict[str, Any] = {}

    def initialize(self, config: Optional[AgentConfig] = None):
        if config:
            self.config = ConfigValidator.validate_config(config)
        else:
            self.config = ConfigValidator.validate_config(self.config)

    def read_prompt(self, file: str, **kwargs) -> str:
        prompt_dir = files.get_abs_path("prompts/default")
        backup_dir = []
        if hasattr(self.config, 'prompts_subdir') and self.config.prompts_subdir:
            prompt_dir = files.get_abs_path("prompts", self.config.prompts_subdir)
            backup_dir.append(files.get_abs_path("prompts/default"))
        return files.read_file(
            files.get_abs_path(prompt_dir, file), backup_dirs=backup_dir, **kwargs
        )

    def get_data(self, field: str) -> Any:
        return self.data.get(field, None)

    def set_data(self, field: str, value: Any):
        self.data[field] = value

    async def append_message(self, msg: str, human: bool = False):
        message_type = "human" if human else "ai"
        if self.history and self.history[-1].type == message_type:
            self.history[-1].content += "\n\n" + msg
        else:
            new_message = HumanMessage(content=msg) if human else AIMessage(content=msg)
            self.history.append(new_message)
        if message_type == "ai":
            self.last_message = msg

    async def monologue(self, msg: str):
        while True:
            try:
                loop_data = LoopData()
                loop_data.message = msg
                loop_data.history_from = len(self.history)

                await self.call_extensions("monologue_start", loop_data=loop_data)

                printer = PrintStyle(italic=True, font_color="#b3ffd9", padding=False)
                user_message = loop_data.message
                await self.append_message(user_message, human=True)

                while True:
                    self.context.streaming_agent = self
                    agent_response = ""
                    loop_data.iteration += 1

                    try:
                        loop_data.system = []
                        loop_data.history = self.history

                        await self.call_extensions(
                            "message_loop_prompts", loop_data=loop_data
                        )

                        prompt = ChatPromptTemplate.from_messages(
                            [
                                SystemMessage(content="\n\n".join(loop_data.system)),
                                MessagesPlaceholder(variable_name="messages"),
                            ]
                        )
                        chain = prompt | self.config.chat_model

                        formatted_inputs = prompt.format(messages=self.history)
                        tokens = int(len(formatted_inputs) / 4)
                        self.rate_limiter.limit_call_and_input(tokens)

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
                            await self.handle_intervention(agent_response)

                            if isinstance(chunk, str):
                                content = chunk
                            elif hasattr(chunk, "content"):
                                content = str(chunk.content)
                            else:
                                content = str(chunk)

                            if content:
                                printer.stream(content)
                                agent_response += content
                                self.log_from_stream(agent_response, log)

                        self.rate_limiter.set_output_tokens(int(len(agent_response) / 4))

                        await self.handle_intervention(agent_response)

                        if self.last_message == agent_response:
                            await self.append_message(agent_response)
                            warning_msg = self.read_prompt("fw.msg_repeat.md")
                            await self.append_message(warning_msg, human=True)
                            PrintStyle(font_color="orange", padding=True).print(warning_msg)
                            self.context.log.log(type="warning", content=warning_msg)
                        else:
                            await self.append_message(agent_response)
                            tools_result = await self.process_tools(agent_response)
                            if tools_result:
                                return tools_result

                    except InterventionException:
                        pass
                    except RepairableException as e:
                        error_message = errors.format_error(e)
                        msg_response = self.read_prompt("fw.error.md", error=error_message)
                        await self.append_message(msg_response, human=True)
                        PrintStyle(font_color="red", padding=True).print(msg_response)
                        self.context.log.log(type="error", content=msg_response)
                    except Exception as e:
                        self.handle_critical_exception(e)
                    finally:
                        await self.call_extensions(
                            "message_loop_end", loop_data=loop_data
                        )

            except InterventionException:
                pass
            except Exception as e:
                self.handle_critical_exception(e)
            finally:
                self.context.streaming_agent = None
                await self.call_extensions("monologue_end", loop_data=loop_data)

    def handle_critical_exception(self, exception: Exception):
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

    async def handle_intervention(self, progress: str = ""):
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

    def log_from_stream(self, stream: str, logItem: Log.LogItem):
        try:
            if len(stream) < 25:
                return
            response = DirtyJson.parse_string(stream)
            if isinstance(response, dict):
                logItem.update(
                    content=stream, kvps=response
                )
        except Exception:
            pass

    async def process_tools(self, msg: str):
        tool_request = extract_tools.json_parse_dirty(msg)

        if tool_request is not None:
            tool_name = tool_request.get("tool_name", "")
            tool_args = tool_request.get("tool_args", {})
            try:
                tool = self.get_tool(tool_name, tool_args, msg)
                await self.handle_intervention()
                await tool.before_execution(**tool_args)
                await self.handle_intervention()
                response = await tool.execute(**tool_args)
                await self.handle_intervention()
                await tool.after_execution(response)
                await self.handle_intervention()
                if hasattr(response, "break_loop"):
                    if response.break_loop:
                        return response.message
            except Exception:
                pass
        else:
            msg = self.read_prompt("fw.msg_misformat.md")
            await self.append_message(msg, human=True)
            PrintStyle(font_color="red", padding=True).print(msg)
            self.context.log.log(
                type="error", content=f"{self.agent_name}: Message misformat"
            )

    def get_tool(self, name: str, args: Dict[str, Any], message: str, **kwargs) -> Any:
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


class InterventionException(Exception):
    pass


class RepairableException(Exception):
    pass


class HandledException(Exception):
    pass


__all__ = ["Agent", "AgentContext", "AgentConfig", "LoopData"]
