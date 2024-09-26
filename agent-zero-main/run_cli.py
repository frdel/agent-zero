from config import MODEL_SPECS, DEFAULT_MODEL
from agent import Agent
import asyncio


async def main():
    agent = Agent()
    selected_model = MODEL_SPECS.get("gpt-4", DEFAULT_MODEL)
    # Proceed with CLI operations using the selected model
    agent.append_message(f"Using model: {selected_model}")
    response = await agent.generate_response("Hello, Agent!")  # Await the async method
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
