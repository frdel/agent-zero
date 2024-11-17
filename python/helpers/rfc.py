import importlib
import inspect
import json
from typing import Any, TypedDict
import aiohttp

# Remote Function Call library
# Call function via http request

class RFCInput(TypedDict):
    module: str
    function_name: str
    args: list[Any]
    kwargs: dict[str, Any]


async def call_rfc(url: str, module: str, function_name: str, args: list, kwargs: dict):
    input = {
        "module": module,
        "function_name": function_name,
        "args": args,
        "kwargs": kwargs,
    }
    input_json = json.dumps(input)
    result = await _send_json_data(url, input_json)
    return result


async def handle_rfc(input: RFCInput):
    return await _call_function(
        input["module"], input["function_name"], *input["args"], **input["kwargs"]
    )


async def _call_function(module: str, function_name: str, *args, **kwargs):
    func = _get_function(module, function_name)
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    else:
        return func(*args, **kwargs)


def _get_function(module: str, function_name: str):
    # import module
    imp = importlib.import_module(module)
    # get function by the name
    func = getattr(imp, function_name)
    return func


async def _send_json_data(url: str, data: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as response:
            return await response.json()