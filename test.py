import asyncio
from os import sep
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
import models
from python.helpers import dotenv


async def test():

    dotenv.load_dotenv()

    # model_name = "moonshotai/kimi-dev-72b:free"
    # model_name = "qwen/qwq-32b"
    # model_name = "qwen/qwen3-32b"
    # model_name = "anthropic/claude-3.7-sonnet:thinking"
    model_name = "openai/gpt-4.1-nano"
    system = ""
    message = "hello"

    model = models.get_chat_model(models.ModelProvider.OPENROUTER, model_name)

    async def response_callback(chunk: str, full: str):
        if chunk == full:
            print("\n")
            print("Response:")
        print(chunk, end="", flush=True)

    async def reasoning_callback(chunk: str, full: str):
        if chunk == full:
            print("\n")
            print("Reasoning:")
        print(chunk, end="", flush=True)

    response, reasoning = await model.unified_call(
        system_message=system,
        user_message=message,
        response_callback=response_callback,
        reasoning_callback=reasoning_callback,
    )

    print("\n")
    print("Final:")
    print("Reasoning:", reasoning)
    print("Response:", response)


async def test2():
    
    dotenv.load_dotenv()

    import initialize
    config = initialize.initialize_agent()

    model = models.get_browser_model(
        provider=config.browser_model.provider,
        name=config.browser_model.name,
        **config.browser_model.kwargs,
    )

    response, reasoning = await model.unified_call(
        system_message="",
        user_message="hi",
    )

    print("\n")
    print("Final:")
    print("Reasoning:", reasoning)
    print("Response:", response)


if __name__ == "__main__":
    # asyncio.run(test())
    asyncio.run(test2())