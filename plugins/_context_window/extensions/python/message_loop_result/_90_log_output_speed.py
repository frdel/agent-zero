from helpers.extension import Extension
from plugins._context_window.helpers.output_speed import log_output_speed


class LogOutputSpeed(Extension):
    """Attach the output speed to the finished generation log item.

    Runs after the core and Context Doctor result extensions, which rewrite the
    generation item's kvps.
    """

    def execute(self, loop_data=None, **kwargs):
        log_output_speed(loop_data)
