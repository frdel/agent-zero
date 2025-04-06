import importlib
import inspect
import json
from typing import Any, TypedDict
import aiohttp
from python.helpers import crypto

from python.helpers import dotenv


# Remote Function Call library
# Call function via http request
# Secured by pre-shared key


class RFCInput(TypedDict):
    module: str
    function_name: str
    args: list[Any]
    kwargs: dict[str, Any]


class RFCCall(TypedDict):
    rfc_input: str
    hash: str


async def call_rfc(
    url: str, password: str, module: str, function_name: str, args: list, kwargs: dict
):
    input = RFCInput(
        module=module,
        function_name=function_name,
        args=args,
        kwargs=kwargs,
    )
    call = RFCCall(
        rfc_input=json.dumps(input), hash=crypto.hash_data(json.dumps(input), password)
    )
    result = await _send_json_data(url, call)
    return result


async def handle_rfc(rfc_call: RFCCall, password: str):
    if not crypto.verify_data(rfc_call["rfc_input"], rfc_call["hash"], password):
        raise Exception("Invalid RFC hash")

    input: RFCInput = json.loads(rfc_call["rfc_input"])
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


async def _send_json_data(url: str, data):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=data,
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result
            else:
                error = await response.text()
                raise Exception(error)
