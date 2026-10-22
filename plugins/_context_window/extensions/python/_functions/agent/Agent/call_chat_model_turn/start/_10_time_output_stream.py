from helpers.extension import Extension
from plugins._context_window.helpers.output_speed import start_output_timing


class TimeOutputStream(Extension):
    def execute(self, data: dict | None = None, **kwargs):
        if isinstance(data, dict):
            start_output_timing(self.agent, data)
