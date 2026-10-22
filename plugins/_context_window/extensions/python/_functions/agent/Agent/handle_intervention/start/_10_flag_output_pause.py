from helpers.extension import Extension
from plugins._context_window.helpers.output_speed import flag_output_pause


class FlagOutputPause(Extension):
    def execute(self, data: dict | None = None, **kwargs):
        flag_output_pause(self.agent)
