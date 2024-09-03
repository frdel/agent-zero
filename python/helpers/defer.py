import asyncio
import threading
from concurrent.futures import Future

class DeferredTask:
    def __init__(self, func, *args, **kwargs):
        self._loop = asyncio.new_event_loop()
        # self._thread = None
        self._task = None
        self._future = Future()
        self._start_task(func, *args, **kwargs)

    def _start_task(self, func, *args, **kwargs):
        def run_in_thread(loop, func, args, kwargs):
            asyncio.set_event_loop(loop)
            self._task = loop.create_task(self._run(func, *args, **kwargs))
            loop.run_forever()

        self._thread = threading.Thread(target=run_in_thread, args=(self._loop, func, args, kwargs))
        self._thread.start()

    async def _run(self, func, *args, **kwargs):
        try:
            result = await func(*args, **kwargs)
            self._future.set_result(result)
        except Exception as e:
            self._future.set_exception(e)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def is_ready(self):
        return self._future.done()

    async def result(self, timeout=None):
        if self._task is None:
            raise RuntimeError("Task was not initialized properly.")
        
        try:
            return await asyncio.wait_for(asyncio.wrap_future(self._future), timeout)
        except asyncio.TimeoutError:
            raise TimeoutError("The task did not complete within the specified timeout.")

    def result_sync(self, timeout=None):
        try:
            return self._future.result(timeout)
        except TimeoutError:
            raise TimeoutError("The task did not complete within the specified timeout.")

    def kill(self):
        if self._task and not self._task.done():
            self._loop.call_soon_threadsafe(self._task.cancel)

    def is_alive(self):
        return self._thread.is_alive() and not self._future.done()

    def __del__(self):
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread.is_alive():
            self._thread.join()
        self._loop.close()