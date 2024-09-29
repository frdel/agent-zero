import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Optional, Coroutine

class EventLoopThread:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventLoopThread, cls).__new__(cls)
                cls._instance.loop = asyncio.new_event_loop() # type: ignore
                cls._instance.thread = threading.Thread(target=cls._instance._run_event_loop, daemon=True) # type: ignore
                cls._instance.thread.start() # type: ignore
            return cls._instance

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop) # type: ignore
        self.loop.run_forever() # type: ignore

    def run_coroutine(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop) # type: ignore

class DeferredTask:
    def __init__(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.event_loop_thread = EventLoopThread()
        self._future: Optional[Future] = None
        self._start_task()

    def _start_task(self):
        self._future = self.event_loop_thread.run_coroutine(self._run())

    async def _run(self):
        return await self.func(*self.args, **self.kwargs)

    def is_ready(self) -> bool:
        return self._future.done() if self._future else False

    def result_sync(self, timeout: Optional[float] = None) -> Any:
        if not self._future:
            raise RuntimeError("Task hasn't been started")
        try:
            return self._future.result(timeout)
        except TimeoutError:
            raise TimeoutError("The task did not complete within the specified timeout.")

    async def result(self, timeout: Optional[float] = None) -> Any:
        if not self._future:
            raise RuntimeError("Task hasn't been started")
        
        loop = asyncio.get_running_loop()
        
        def _get_result():
            try:
                return self._future.result(timeout) # type: ignore
            except TimeoutError:
                raise TimeoutError("The task did not complete within the specified timeout.")
        
        return await loop.run_in_executor(None, _get_result)

    def kill(self) -> None:
        if self._future and not self._future.done():
            self._future.cancel()

    def is_alive(self) -> bool:
        return self._future and not self._future.done() # type: ignore

    def restart(self) -> None:
        self._start_task()

def run_in_background(func, *args, **kwargs):
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)
    return wrapper