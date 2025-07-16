import asyncio
from python.helpers import runtime, whisper, settings
from python.helpers.print_style import PrintStyle
from python.helpers import kokoro_tts
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
            if set["embed_model_provider"] == "HuggingFace":
                try:
                    # Use the new LiteLLM-based model system
                    emb_mod = models.get_embedding_model(
                        "HuggingFace", set["embed_model_name"]
                    )
                    emb_txt = await emb_mod.aembed_query("test")
                    return emb_txt
                except Exception as e:
                    PrintStyle().error(f"Error in preload_embedding: {e}")

        # preload kokoro tts model if enabled
        async def preload_kokoro():
            try:
                return await kokoro_tts.preload()
            except Exception as e:
                PrintStyle().error(f"Error in preload_kokoro: {e}")

        # async tasks to preload
        tasks = [
            preload_embedding(),
            # preload_whisper(),
            # preload_kokoro()
        ] # no longer preload kokoro and whisper, do it JIT

        await asyncio.gather(*tasks, return_exceptions=True)
        PrintStyle().print("Preload completed")
    except Exception as e:
        PrintStyle().error(f"Error in preload: {e}")


# preload transcription model
asyncio.run(preload())
