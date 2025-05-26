import asyncio
import json
import time
from agent import Agent, InterventionException

import models
from python.helpers.tool import Tool, Response
from python.helpers import files, defer, persist_chat
from python.helpers.browser_use import browser_use
from python.extensions.message_loop_start._10_iteration_no import get_iter_no
from pydantic import BaseModel
import uuid
from python.helpers.dirty_json import DirtyJson
from langchain_core.messages import SystemMessage

class State:
    @staticmethod
    async def create(agent: Agent):
        state = State(agent)
        return state

    def __init__(self, agent: Agent):
        self.agent = agent
        self.context = None
        self.task = None
        self.use_agent = None
        self.browser = None
        self.iter_no = 0


    def __del__(self):
        self.kill_task()

    async def _initialize(self):
        if self.context:
            return

        self.browser = browser_use.Browser(
            config=browser_use.BrowserConfig(
                headless=True,
                disable_security=True,
            )
        )

        # Await the coroutine to get the browser context
        self.context = await self.browser.new_context()

        # override async methods to create hooks
        self.override_hooks()

        # Add init script to the context - this will be applied to all new pages
        await self.context._initialize_session()
        pw_context = self.context.session.context  # type: ignore
        js_override = files.get_abs_path("lib/browser/init_override.js")
        await pw_context.add_init_script(path=js_override)  # type: ignore

    def start_task(self, task: str):
        if self.task and self.task.is_alive():
            self.kill_task()

        if not self.task:
            self.task = defer.DeferredTask(
                thread_name="BrowserAgent" + self.agent.context.id
            )
            if self.agent.context.task:
                self.agent.context.task.add_child_task(self.task, terminate_thread=True)
        self.task.start_task(self._run_task, task)
        return self.task

    def kill_task(self):
        if self.task:
            self.task.kill(terminate_thread=True)
            self.task = None
            self.context = None
            self.use_agent = None
            self.browser = None
            self.iter_no = 0

    async def _run_task(self, task: str):

        agent = self.agent

        await self._initialize()

        class CustomSystemPrompt(browser_use.SystemPrompt):
            def get_system_message(self) -> SystemMessage:
                existing_rules = super().get_system_message().text()
                new_rules = agent.read_prompt("prompts/browser_agent.system.md")
                return SystemMessage(content=f"{existing_rules}\n{new_rules}".strip())

        # Model of task result
        class DoneResult(BaseModel):
            title: str
            response: str
            page_summary: str

        # Initialize controller
        controller = browser_use.Controller()

        # we overwrite done() in this example to demonstrate the validator
        @controller.registry.action("Done with task", param_model=DoneResult)
        async def done(params: DoneResult):
            result = browser_use.ActionResult(
                is_done=True, extracted_content=params.model_dump_json()
            )
            return result

        # @controller.action("Ask user for information")
        # def ask_user(question: str) -> str:
        #     return "..."

        model = models.get_model(
            type=models.ModelType.CHAT,
            provider=self.agent.config.browser_model.provider,
            name=self.agent.config.browser_model.name,
            **self.agent.config.browser_model.kwargs,
        )

        self.use_agent = browser_use.Agent(
            task=task,
            browser_context=self.context,
            llm=model,
            use_vision=self.agent.config.browser_model.vision,
            system_prompt_class=CustomSystemPrompt,
            controller=controller,
        )

        self.iter_no = get_iter_no(self.agent)

        # orig_err_hnd = self.use_agent._handle_step_error
        # def new_err_hnd(*args, **kwargs):
        #     if isinstance(args[0], InterventionException):
        #         raise args[0]
        #     return orig_err_hnd(*args, **kwargs)
        # self.use_agent._handle_step_error = new_err_hnd

        result = await self.use_agent.run()
        return result

    def override_hooks(self):
        # override async function to create a hook
        def override_hook(func):
            async def wrapper(*args, **kwargs):
                await self.agent.wait_if_paused()
                if self.iter_no != get_iter_no(self.agent):
                    raise InterventionException("Task cancelled")
                return await func(*args, **kwargs)
            return wrapper

        if self.context:
            self.context.get_state = override_hook(self.context.get_state)
            self.context.get_session = override_hook(self.context.get_session)
            self.context.remove_highlights = override_hook(self.context.remove_highlights)

    async def get_page(self):
        if self.use_agent:
            return await self.use_agent.browser_context.get_current_page()


class BrowserAgent(Tool):

    async def execute(self, message="", reset="", **kwargs):
        self.guid = str(uuid.uuid4())
        reset = str(reset).lower().strip() == "true"
        await self.prepare_state(reset=reset)
        task = self.state.start_task(message)

        # wait for browser agent to finish and update progress
        while not task.is_ready():
            await self.agent.handle_intervention()
            await asyncio.sleep(1)
            try:
                update = await self.get_update()
                log = update.get("log")
                if log:
                    self.update_progress("\n".join(log))
                screenshot = update.get("screenshot", None)
                if screenshot:
                    self.log.update(screenshot=screenshot)
            except Exception as e:
                pass

        # collect result
        result = await task.result()
        answer = result.final_result()
        try:
            answer_data = DirtyJson.parse_string(answer)
            answer_text = strings.dict_to_text(answer_data)  # type: ignore
        except Exception as e:
            answer_text = answer
        self.log.update(answer=answer_text)
        return Response(message=answer, break_loop=False)

    def get_log_object(self):
        return self.agent.context.log.log(
            type="browser",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    # async def after_execution(self, response, **kwargs):
    #     await self.agent.hist_add_tool_result(self.name, response.message)

    async def get_update(self):
        await self.prepare_state()

        result = {}
        agent = self.agent
        ua = self.state.use_agent
        page = await self.state.get_page()
        ctx = self.state.context

        if ua and page:
            try:

                async def _get_update():

                    await agent.wait_if_paused()

                    log = []

                    # dom_service = browser_use.DomService(page)
                    # dom_state = await browser_use.utils.time_execution_sync('get_clickable_elements')(
                    #     dom_service.get_clickable_elements
                    # )()
                    # elements = dom_state.element_tree
                    # selector_map = dom_state.selector_map
                    # el_text = elements.clickable_elements_to_string()

                    for message in ua.message_manager.get_messages():
                        if message.type == "system":
                            continue
                        if message.type == "ai":
                            try:
                                data = json.loads(message.content)  # type: ignore
                                cs = data.get("current_state")
                                if cs:
                                    log.append("AI:" + cs["memory"])
                                    log.append("AI:" + cs["next_goal"])
                            except Exception:
                                pass
                        if message.type == "human":
                            content = str(message.content).strip()
                            part = content.split("\n", 1)[0].split(",", 1)[0]
                            if part:
                                if len(part) > 150:
                                    part = part[:150] + "..."
                                log.append("FW:" + part)
                    result["log"] = log

                    path = files.get_abs_path(
                        persist_chat.get_chat_folder_path(agent.context.id),
                        "browser",
                        "screenshots",
                        f"{self.guid}.png",
                    )
                    files.make_dirs(path)
                    await page.screenshot(path=path, full_page=False, timeout=3000)
                    result["screenshot"] = f"img://{path}&t={str(time.time())}"

                if self.state.task:
                    await self.state.task.execute_inside(_get_update)

            except Exception as e:
                pass

        return result

    async def prepare_state(self, reset=False):
        self.state = self.agent.get_data("_browser_agent_state")
        if not self.state or reset:
            self.state = await State.create(self.agent)
        self.agent.set_data("_browser_agent_state", self.state)

    def update_progress(self, text):
        short = text.split("\n")[-1]
        if len(short) > 50:
            short = short[:50] + "..."
        progress = f"Browser: {short}"

        self.log.update(progress=text)
        self.agent.context.log.set_progress(progress)

    # def __del__(self):
    #     if self.state:
    #         self.state.kill_task()
