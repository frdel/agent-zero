import time
from collections import deque
from .print_style import PrintStyle

def rate_limiter(max_requests_per_minute, max_tokens_per_minute):
    execution_times = deque()
    token_counts = deque()

    def limit(tokens):
        if tokens > max_tokens_per_minute:
            raise ValueError("Number of tokens exceeds the maximum allowed per minute.")

        current_time = time.time()
        
        # Cleanup old execution times and token counts
        while execution_times and current_time - execution_times[0] > 60:
            execution_times.popleft()
            token_counts.popleft()

        total_tokens = sum(token_counts)
        
        if len(execution_times) < max_requests_per_minute and total_tokens + tokens <= max_tokens_per_minute:
            execution_times.append(current_time)
            token_counts.append(tokens)
        else:
            sleep_time = max(
                60 - (current_time - execution_times[0]),
                60 - (current_time - execution_times[0]) if total_tokens + tokens > max_tokens_per_minute else 0
            )
            PrintStyle(font_color="yellow", padding=True).print(f"Rate limiter: sleeping for {sleep_time} seconds...")
            time.sleep(sleep_time)
            current_time = time.time()
            execution_times.append(current_time)
            token_counts.append(tokens)

    return limit