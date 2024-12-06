import asyncio
from python.helpers import runtime, whisper, settings

print("Running preload...")
runtime.initialize()


async def preload():
    try:
        set = settings.get_default_settings()

        # async tasks to preload
        tasks = [whisper.preload(set["stt_model_size"])]

        return asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error in preload: {e}")


# preload transcription model
asyncio.run(preload())
