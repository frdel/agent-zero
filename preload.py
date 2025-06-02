import asyncio
from python.helpers import runtime, whisper, settings
from python.helpers.print_style import PrintStyle
import models

PrintStyle().print("Running preload...")
runtime.initialize()


async def preload():
    try:
        set = settings.get_settings()

        # preload whisper model
        async def preload_whisper():
            try:
                return await whisper.preload(set["stt_model_size"])
            except Exception as e:
                PrintStyle().error(f"Error in preload_whisper: {e}")

        # preload embedding model
        async def preload_embedding():
            # if set["embed_model_provider"] == models.ModelProvider.HUGGINGFACE.name:
            try:
                provider = models.ModelProvider[set["embed_model_provider"]]
                emb_mod = models.get_model(
                    type=models.ModelType.EMBEDDING, 
                    provider=provider,
                    name=set["embed_model_name"],
                    **set["embed_model_kwargs"],
                )
                emb_txt = await emb_mod.aembed_query("test")
                return emb_txt
            except Exception as e:
                PrintStyle().error(f"Error in preload_embedding: {e}")


        # async tasks to preload
        tasks = [preload_whisper(), preload_embedding()]

        await asyncio.gather(*tasks, return_exceptions=True)
        PrintStyle().print("Preload completed")
    except Exception as e:
        PrintStyle().error(f"Error in preload: {e}")


# preload transcription model
asyncio.run(preload())
