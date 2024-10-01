from agent import Agent, AgentConfig
import asyncio


async def async_generate_response(agent, user_input):
    return agent.generate_response(user_input)


async def main():
    config = AgentConfig(
        chat_model=None,  # You need to provide appropriate models here
        utility_model=None,
        embeddings_model=None,
    )
    agent = Agent(number=1, config=config)

    while True:
        # Example of interacting with the agent
        user_input = input("Enter your message (or 'quit' to exit): ")
        if user_input.lower() == "quit":
            break

        try:
            response = await async_generate_response(agent, user_input)
            print("Agent response:", response)
        except Exception as e:
            print(f"An error occurred: {e}")

    print("Conversation ended.")


if __name__ == "__main__":
    asyncio.run(main())
