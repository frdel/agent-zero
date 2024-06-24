import time
from collections import deque
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class CallRecord:
    timestamp: float
    input_tokens: int
    output_tokens: int

class RateLimiter:
    def __init__(self, max_calls: int, max_input_tokens: int, max_output_tokens: int, window_seconds: int = 60):
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

    def _wait_if_needed(self, current_time: float):
        while True:
            self._clean_old_records(current_time)
            calls, input_tokens, output_tokens = self._get_counts()
            
            if calls < self.max_calls and input_tokens < self.max_input_tokens and output_tokens < self.max_output_tokens:
                break
            
            oldest_record = self.call_records[0]
            wait_time = oldest_record.timestamp + self.window_seconds - current_time
            if wait_time > 0:
                time.sleep(wait_time)
            current_time = time.time()

    def limit(self, input_token_count: int, output_token_count: int):
        current_time = time.time()
        self._wait_if_needed(current_time)
        self.call_records.append(CallRecord(current_time, input_token_count, output_token_count))

