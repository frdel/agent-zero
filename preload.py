import asyncio
from python.helpers import runtime, whisper, settings
from python.helpers.print_style import PrintStyle
import models

PrintStyle().print("Running preload...")
runtime.initialize()


async def preload():
    try:
        set = settings.get_default_settings()

        # preload whisper model
        async def preload_whisper():
            try:
                return await whisper.preload(set["stt_model_size"])
            except Exception as e:
                PrintStyle().error(f"Error in preload_whisper: {e}")

        # preload embedding model
        async def preload_embedding():
            if set["embed_model_provider"] == models.ModelProvider.HUGGINGFACE.name:
                try:
                    # Use the new LiteLLM-based model system
                    emb_mod = models.get_embedding_model(
                        models.ModelProvider.HUGGINGFACE,
                        set["embed_model_name"]
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
