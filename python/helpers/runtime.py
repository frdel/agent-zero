import argparse
import inspect
from typing import Any, Callable
from python.helpers import dotenv, rfc, settings

parser = argparse.ArgumentParser()
args = {}
dockerman = None


def initialize():
    global args
    if args:
        return
    parser.add_argument("--port", type=int, default=None, help="Web UI port")
    parser.add_argument("--host", type=str, default=None, help="Web UI host")
    parser.add_argument(
        "--cloudflare_tunnel",
        type=bool,
        default=False,
        help="Use cloudflare tunnel for public URL",
    )
    parser.add_argument(
        "--development", type=bool, default=False, help="Development mode"
    )

    known, unknown = parser.parse_known_args()
    args = vars(known)
    for arg in unknown:
        if "=" in arg:
            key, value = arg.split("=", 1)
            key = key.lstrip("-")
            args[key] = value


def get_arg(name: str):
    global args
    return args.get(name, None)

def has_arg(name: str):
    global args
    return name in args

def is_dockerized() -> bool:
    return get_arg("dockerized")

def is_development() -> bool:
    return not is_dockerized()

def get_local_url():
    if is_dockerized():
        return "host.docker.internal"
    return "127.0.0.1"

async def call_development_function(func: Callable, *args, **kwargs):
    if is_development():
        url = _get_rfc_url()
        password = _get_rfc_password()
        return await rfc.call_rfc(
            url=url,
            password=password,
            module=func.__module__,
            function_name=func.__name__,
            args=list(args),
            kwargs=kwargs,
        )
    else:
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)


async def handle_rfc(rfc_call: rfc.RFCCall):
    return await rfc.handle_rfc(rfc_call=rfc_call, password=_get_rfc_password())


def _get_rfc_password() -> str:
    password = dotenv.get_dotenv_value(dotenv.KEY_RFC_PASSWORD)
    if not password:
        raise Exception("No RFC password, cannot handle RFC calls.")
    return password


def _get_rfc_url() -> str:
    set = settings.get_settings()
    url = set["rfc_url"]
    if not "://" in url:
        url = "http://"+url
    if url.endswith("/"):
        url = url[:-1]
    url = url+":"+str(set["rfc_port_http"])
    url += "/rfc"
    return url
