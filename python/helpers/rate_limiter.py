import time
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple
from .print_style import PrintStyle
from .log import Log

@dataclass
class CallRecord:
    timestamp: float
    input_tokens: int
    output_tokens: int = 0  # Default to 0, will be set separately

class RateLimiter:
    def __init__(self, logger: Log, max_calls: int, max_input_tokens: int, max_output_tokens: int, window_seconds: int = 60):
        self.logger = logger
        self.max_calls = max_calls
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.window_seconds = window_seconds
        self.call_records: deque = deque()

    def _clean_old_records(self, current_time: float):
        while self.call_records and current_time - self.call_records[0].timestamp > self.window_seconds:
            self.call_records.popleft()

    def _get_counts(self) -> Tuple[int, int, int]:
        calls = len(self.call_records)
        input_tokens = sum(record.input_tokens for record in self.call_records)
        output_tokens = sum(record.output_tokens for record in self.call_records)
        return calls, input_tokens, output_tokens

    def _wait_if_needed(self, current_time: float, new_input_tokens: int):
        while True:
            self._clean_old_records(current_time)
            calls, input_tokens, output_tokens = self._get_counts()
            
            wait_reasons = []
            if self.max_calls > 0 and calls >= self.max_calls:
                wait_reasons.append("max calls")
            if self.max_input_tokens > 0 and input_tokens + new_input_tokens > self.max_input_tokens:
                wait_reasons.append("max input tokens")
            if self.max_output_tokens > 0 and output_tokens >= self.max_output_tokens:
                wait_reasons.append("max output tokens")
            
            if not wait_reasons:
                break
            
            oldest_record = self.call_records[0]
            wait_time = oldest_record.timestamp + self.window_seconds - current_time
            if wait_time > 0:
                PrintStyle(font_color="yellow", padding=True).print(f"Rate limit exceeded. Waiting for {wait_time:.2f} seconds due to: {', '.join(wait_reasons)}")
                self.logger.log("rate_limit","Rate limit exceeded",f"Rate limit exceeded. Waiting for {wait_time:.2f} seconds due to: {', '.join(wait_reasons)}")
                time.sleep(wait_time)
            current_time = time.time()

    def limit_call_and_input(self, input_token_count: int) -> CallRecord:
        current_time = time.time()
        self._wait_if_needed(current_time, input_token_count)
        new_record = CallRecord(current_time, input_token_count)
        self.call_records.append(new_record)
        return new_record

    def set_output_tokens(self, output_token_count: int):
        if self.call_records:
            self.call_records[-1].output_tokens += output_token_count
        return self
