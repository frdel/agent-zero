import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Callable, Optional, Coroutine

class EventLoopThread:
    _instance = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self.thread: threading.Thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

    def __new__(cls) -> 'EventLoopThread':
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.__init__()
        return cls._instance

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_coroutine(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

class DeferredTask:
    def __init__(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> None:
        self._event_loop_thread = EventLoopThread()
        self._future: Future[Any] = self._event_loop_thread.run_coroutine(self._run(func, *args, **kwargs))

    async def _run(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> Any:
        return await func(*args, **kwargs)

    def is_ready(self) -> bool:
        return self._future.done()

    async def result(self, timeout: Optional[float] = None) -> Any:
        try:
            return await asyncio.wait_for(asyncio.wrap_future(self._future), timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("The task did not complete within the specified timeout.")

    def result_sync(self, timeout: Optional[float] = None) -> Any:
        try:
            return self._future.result(timeout)
        except TimeoutError:
            raise TimeoutError("The task did not complete within the specified timeout.")

    def kill(self) -> None:
        if not self._future.done():
            self._future.cancel()

    def is_alive(self) -> bool:
        return not self._future.done()

# Helper function to run async code
async def run_async(func, *args, **kwargs):
    return await func(*args, **kwargs)