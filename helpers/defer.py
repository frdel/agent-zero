import asyncio
from dataclasses import dataclass
import threading
from concurrent.futures import Future, InvalidStateError
from typing import Any, Callable, Optional, Coroutine, TypeVar, Awaitable

T = TypeVar("T")

THREAD_BACKGROUND = "Background"


class EventLoopThread:
    _instances: dict[str, "EventLoopThread"] = {}
    _lock = threading.Lock()

    def __init__(self, thread_name: str = THREAD_BACKGROUND) -> None:
        """Initialize the event loop thread."""
        self.thread_name = thread_name
        self._start()

    def __new__(cls, thread_name: str = THREAD_BACKGROUND):
        with cls._lock:
            if thread_name not in cls._instances:
                instance = super(EventLoopThread, cls).__new__(cls)
                cls._instances[thread_name] = instance
            return cls._instances[thread_name]

    def _start(self):
        with self._lock:
            if not hasattr(self, "loop") or not self.loop:
                self.loop = asyncio.new_event_loop()
            if not hasattr(self, "thread") or not self.thread:
                self.thread = threading.Thread(
                    target=self._run_event_loop, daemon=True, name=self.thread_name
                )
                self.thread.start()

    def _run_event_loop(self):
        if not self.loop:
            raise RuntimeError("Event loop is not initialized")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def terminate(self):
        loop = getattr(self, "loop", None)
        thread = getattr(self, "thread", None)

        if not loop:
            return

        if loop.is_running():
            if thread and thread is threading.current_thread():
                loop.stop()
            else:
                loop.call_soon_threadsafe(loop.stop)
                if thread:
                    thread.join()
        elif thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join()

        if not loop.is_closed():
            loop.close()

        with self.__class__._lock:
            if self.thread_name in self.__class__._instances:
                del self.__class__._instances[self.thread_name]

        self.loop = None
        self.thread = None

    def run_coroutine(self, coro):
        self._start()
        if not self.loop:
            raise RuntimeError("Event loop is not initialized")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


@dataclass
class ChildTask:
    task: "DeferredTask"
    terminate_thread: bool


class DeferredTask:
    def __init__(
        self,
        thread_name: str = THREAD_BACKGROUND,
    ):
        self.event_loop_thread = EventLoopThread(thread_name)
        self._future: Optional[Future] = None
        self.children: list[ChildTask] = []
        self.func: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None
        self.args: tuple[Any, ...] = ()
        self.kwargs: dict[str, Any] = {}

    def start_task(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any
    ):
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._start_task()
        return self

    def add_done_callback(self, callback: Callable[[Future], Any]) -> None:
        if not self._future:
            raise RuntimeError("Task hasn't been started")
        self._future.add_done_callback(callback)

    def __del__(self):
        self.kill()

    def _start_task(self):
        if self.func is None:
            raise RuntimeError("Task callable is no longer available")

        self._future = self.event_loop_thread.run_coroutine(
            self._run(self.func, self.args, self.kwargs)
        )
        if self._future:
            self._future.add_done_callback(self._on_task_done)

    def _on_task_done(self, future: Future):
        # Ensure child background tasks are always cleaned up once the parent finishes
        if future is self._future:
            self.kill_children()
            self._clear_call()

    def _clear_call(self) -> None:
        self.func = None
        self.args = ()
        self.kwargs = {}

    @staticmethod
    async def _run(func, args, kwargs):
        return await func(*args, **kwargs)

    def is_ready(self) -> bool:
        return self._future.done() if self._future else False

    def result_sync(self, timeout: Optional[float] = None) -> Any:
        if not self._future:
            raise RuntimeError("Task hasn't been started")
        try:
            return self._future.result(timeout)
        except TimeoutError:
            raise TimeoutError(
                "The task did not complete within the specified timeout."
            )

    async def result(self, timeout: Optional[float] = None) -> Any:
        if not self._future:
            raise RuntimeError("Task hasn't been started")

        loop = asyncio.get_running_loop()

        def _get_result():
            try:
                result = self._future.result(timeout)  # type: ignore
                # self.kill()
                return result
            except TimeoutError:
                raise TimeoutError(
                    "The task did not complete within the specified timeout."
                )

        return await loop.run_in_executor(None, _get_result)

    async def result_async(self, timeout: Optional[float] = None) -> Any:
        """Await across event-loop threads without occupying an executor worker.

        Cancelling/timing out a waiter leaves the owned invocation running;
        explicit kill/ancestor controls remain responsible for cancellation.
        """
        if self._future is None:
            raise RuntimeError("Task hasn't been started")
        awaited = asyncio.shield(asyncio.wrap_future(self._future))
        if timeout is None:
            return await awaited
        return await asyncio.wait_for(awaited, timeout)

    def kill(self, terminate_thread: bool = False) -> None:
        """Kill the task and optionally terminate its thread."""
        self.kill_children()
        if self._future and not self._future.done():
            self._future.cancel()
        self._clear_call()

        if terminate_thread and self.event_loop_thread.loop:
            if self.event_loop_thread.loop.is_running():
                try:
                    cleanup_future = asyncio.run_coroutine_threadsafe(
                        self._drain_event_loop_tasks(), self.event_loop_thread.loop
                    )
                    cleanup_future.result()
                except Exception:
                    pass

            self.event_loop_thread.terminate()

    def kill_children(self) -> None:
        for child in self.children:
            child.task.kill(terminate_thread=child.terminate_thread)
        self.children = []

    def is_alive(self) -> bool:
        return self._future and not self._future.done()  # type: ignore

    def restart(self, terminate_thread: bool = False) -> None:
        if self.func is None:
            raise RuntimeError("Completed task cannot be restarted")
        func, args, kwargs = self.func, self.args, self.kwargs
        self.kill(terminate_thread=terminate_thread)
        self.start_task(func, *args, **kwargs)

    def add_child_task(
        self, task: "DeferredTask", terminate_thread: bool = False
    ) -> None:
        self.children.append(ChildTask(task, terminate_thread))

    async def _execute_in_task_context(
        self, func: Callable[..., T], *args, **kwargs
    ) -> T:
        """Execute a function in the task's context and return its result."""
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result

    def execute_inside(self, func: Callable[..., T], *args, **kwargs) -> Awaitable[T]:
        if not self.event_loop_thread.loop:
            raise RuntimeError("Event loop is not initialized")

        future: Future = Future()

        def set_result(result: Any) -> None:
            try:
                future.set_result(result)
            except InvalidStateError:
                pass

        def set_exception(exception: BaseException) -> None:
            try:
                future.set_exception(exception)
            except InvalidStateError:
                pass

        async def wrapped():
            if not self.event_loop_thread.loop:
                raise RuntimeError("Event loop is not initialized")
            try:
                result = await self._execute_in_task_context(func, *args, **kwargs)
                # Keep awaiting until we get a concrete value
                while isinstance(result, Awaitable):
                    result = await result
                self.event_loop_thread.loop.call_soon_threadsafe(
                    set_result, result
                )
            except Exception as e:
                self.event_loop_thread.loop.call_soon_threadsafe(
                    set_exception, e
                )

        asyncio.run_coroutine_threadsafe(wrapped(), self.event_loop_thread.loop)
        return asyncio.wrap_future(future)

    @staticmethod
    async def _drain_event_loop_tasks():
        """Cancel and await all pending tasks on the current event loop."""
        loop = asyncio.get_running_loop()
        current_task = asyncio.current_task(loop=loop)
        pending = [
            task
            for task in asyncio.all_tasks(loop=loop)
            if task is not current_task
        ]
        if not pending:
            return
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
