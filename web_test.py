from browser_use import Agent, Browser, BrowserConfig, Controller, ActionResult
from pydantic import BaseModel
import asyncio

import playwright
import models
from python.helpers import dotenv, files
from playwright.async_api import async_playwright


async def main():

    dotenv.load_dotenv()
    model = models.get_openai_chat("gpt-4o-mini")

    # Initialize controller first
    controller = Controller()

    # @controller.action("Ask user for information")
    # def ask_human(question: str, display_question: bool) -> str:
    #     return input(f"\n{question}\nInput: ")

    class DoneResult(BaseModel):
        title: str
        response: str
        what_do_i_see: str

    # we overwrite done() in this example to demonstrate the validator
    @controller.registry.action("Done with task", param_model=DoneResult)
    async def done(params: DoneResult):
        result = ActionResult(is_done=True, extracted_content=params.model_dump_json())
        print(result)
        return result

    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
        )
    )

    # Await the coroutine to get the browser context
    context = await browser.new_context()

    async with context:

        # Add init script to the context - this will be applied to all new pages
        pw_context = context.session.context # type: ignore
        js_override = files.get_abs_path("lib/browser/init_override.js")
        await pw_context.add_init_script(path=js_override)  # type: ignore

        agent = Agent(
            task="Go to weather.com",
            llm=model,
            browser=browser,
            browser_context=context,
            use_vision=True,
            controller=controller,
        )

        result = await agent.run()
        for out in result.model_outputs():
            print("-------------")
            print(out.current_state.memory)
            print(out.current_state.next_goal)
            print("-------------")


        agent = Agent(
            task="Search for berlin and tell me the temperature",
            llm=model,
            browser=browser,
            browser_context=context,
            use_vision=True,
            controller=controller,
        )

        result = await agent.run()
        # page = await agent.browser_context.get_current_page()
        print(result)


asyncio.run(main())

