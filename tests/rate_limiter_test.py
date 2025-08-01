
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import models

provider = "openai"
name = "gpt-4.1-mini"

model = models.get_chat_model(
    provider=provider,
    name=name,
    model_config=models.ModelConfig(
        type=models.ModelType.CHAT,
        provider=provider,
        name=name,
        limit_requests = 5,
        limit_input = 15000,
        limit_output = 1000,
    )
    )

async def run():
    response, reasoning = await model.unified_call(
        user_message="Tell me a joke"
    )
    print("Response: ", response)
    print("Reasoning: ", reasoning)


import asyncio
asyncio.run(run())