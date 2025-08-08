from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle


class MaskResponseStreamEnd(Extension):
    async def execute(self, **kwargs):
        agent = self.agent
        filter_key = "_resp_stream_filter"
        filt = agent.get_data(filter_key)
        if filt:
            tail = filt.finalize()
            if tail:
                PrintStyle().stream(tail)
            agent.set_data(filter_key, None)
        return None
