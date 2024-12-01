
import time
import inspect

from boltons.funcutils import wraps, FunctionBuilder


def wrappable_func(a, b):
    return a, b


def test_wraps_async():
    # from https://github.com/mahmoud/boltons/issues/194
    import asyncio

    def delayed(func):
        @wraps(func)
        async def wrapped(*args, **kw):
            await asyncio.sleep(1.0)
            return await func(*args, **kw)

        return wrapped


    async def f():
        await asyncio.sleep(0.1)

    assert asyncio.iscoroutinefunction(f)

    f2 = delayed(f)

    assert asyncio.iscoroutinefunction(f2)

    # from https://github.com/mahmoud/boltons/pull/195
    def yolo():
        def make_time_decorator(wrapped):
            @wraps(wrapped)
            async def decorator(*args, **kw):
                return (await wrapped(*args, **kw))
            return decorator

        return make_time_decorator


    @yolo()
    async def foo(x):
        await asyncio.sleep(x)

    start_time = time.monotonic()
    asyncio.run(foo(0.3))
    duration = time.monotonic() - start_time

    # lol windows py37 somehow completes this in under 0.3
    # "assert 0.29700000000002547 > 0.3" https://ci.appveyor.com/project/mahmoud/boltons/builds/22261051/job/3jfq1tq2233csqp6
    assert duration > 0.25


def test_wraps_hide_wrapped():
    new_func = wraps(wrappable_func, injected='b')(lambda a: wrappable_func(a, b=1))
    new_sig = inspect.signature(new_func, follow_wrapped=True)

    assert list(new_sig.parameters.keys()) == ['a', 'b']

    new_func = wraps(wrappable_func, injected='b', hide_wrapped=True)(lambda a: wrappable_func(a, b=1))
    new_sig = inspect.signature(new_func, follow_wrapped=True)

    assert list(new_sig.parameters.keys()) == ['a']

    new_func = wraps(wrappable_func, injected='b')(lambda a: wrappable_func(a, b=1))
    new_new_func = wraps(new_func, injected='a', hide_wrapped=True)(lambda: new_func(a=1))
    new_new_sig = inspect.signature(new_new_func, follow_wrapped=True)

    assert len(new_new_sig.parameters) == 0
