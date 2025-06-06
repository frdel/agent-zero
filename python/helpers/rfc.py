import inspect
import json
from typing import Any, TypedDict
import aiohttp
from python.helpers import crypto

from python.helpers import dotenv


# Remote Function Call library
# Call function via http request
# Secured by pre-shared key


import importlib
import re
from typing import Set, Optional

# Define allowed modules whitelist
ALLOWED_MODULES: Set[str] = {
    'json',
    'os',
    'sys',
    'datetime',
    'collections',
    'itertools',
    'functools',
    'operator',
    'math',
    'random',
    'string',
    'urllib.parse',
    'base64',
    'hashlib',
    'uuid',
    'pathlib',
    'typing'
}

def safe_import_module(module_name: str, package: Optional[str] = None):
    """
    Safely import a module using a whitelist approach.
    
    Args:
        module_name: Name of the module to import
        package: Package name for relative imports
        
    Returns:
        The imported module
        
    Raises:
        SecurityError: If module is not in whitelist
        ImportError: If module cannot be imported
    """
    # Validate module name format
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*$', module_name):
        raise SecurityError(f"Invalid module name format: {module_name}")
    
    # Check against whitelist
    if module_name not in ALLOWED_MODULES:
        raise SecurityError(f"Module '{module_name}' is not in the allowed whitelist")
    
    return importlib.import_module(module_name, package)

class SecurityError(Exception):
    """Custom exception for security-related errors"""
    pass


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
    imp = safe_import_module(module)
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
