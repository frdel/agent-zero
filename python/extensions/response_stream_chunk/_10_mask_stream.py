from python.helpers.extension import Extension
from python.helpers.secrets import SecretsManager
from python.helpers.print_style import PrintStyle


class MaskResponseStreamChunk(Extension):
    async def execute(self, **kwargs):
        chunk: str = kwargs.get("text", "")
        if not chunk:
            return None

        agent = self.agent
        filter_key = "_resp_stream_filter"
        filt = agent.get_data(filter_key)
        if not filt:
            filt = SecretsManager.get_instance().create_streaming_filter()
            agent.set_data(filter_key, filt)

        masked_emit = filt.process_chunk(chunk)
        if masked_emit:
            PrintStyle().stream(masked_emit)
        return None
