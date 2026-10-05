from helpers.extension import Extension
from plugins._context_window.helpers.output_speed import (
    finish_output_timing,
    record_output_speed,
)
from plugins._context_window.helpers.usage import capture_provider_usage


class RecordProviderUsage(Extension):
    def execute(self, data: dict | None = None, **kwargs):
        payload = data if isinstance(data, dict) else {}
        timing = finish_output_timing(self.agent, payload)
        if not payload.get("exception"):
            result = payload.get("result")
            capture_provider_usage(self.agent, result)
            record_output_speed(self.agent, result, timing)
