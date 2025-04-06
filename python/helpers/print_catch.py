import asyncio
import io
import sys
from typing import Callable, Any, Awaitable, Tuple

def capture_prints_async(
    func: Callable[..., Awaitable[Any]],
    *args,
    **kwargs
) -> Tuple[Awaitable[Any], Callable[[], str]]:
    # Create a StringIO object to capture the output
    captured_output = io.StringIO()
    original_stdout = sys.stdout

    # Define a function to get the current captured output
    def get_current_output() -> str:
        return captured_output.getvalue()

    async def wrapped_func() -> Any:
        nonlocal captured_output, original_stdout
        try:
            # Redirect sys.stdout to the StringIO object
            sys.stdout = captured_output
            # Await the provided function
            return await func(*args, **kwargs)
        finally:
            # Restore the original sys.stdout
            sys.stdout = original_stdout

    # Return the wrapped awaitable and the output retriever
    return asyncio.create_task(wrapped_func()), get_current_output