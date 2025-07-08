from functools import wraps
from flask import request, Response
from python.helpers import dotenv

# NOTE: If is_loopback_address is also needed by other decorators,
# it should be moved here or to another common network utility helper.
# For now, requires_auth only depends on dotenv, Response, request, wraps.

def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        user = dotenv.get_dotenv_value("AUTH_LOGIN")
        password = dotenv.get_dotenv_value("AUTH_PASSWORD")
        if user and password: # Only enforce auth if .env has credentials
            auth = request.authorization
            if not auth or not (auth.username == user and auth.password == password):
                return Response(
                    "Could not verify your access level for that URL.\n"
                    "You have to login with proper credentials",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Login Required"'},
                )
        return await f(*args, **kwargs)
    return decorated

# Placeholder for other decorators if they were to be moved:
# def requires_api_key(f): ...
# def requires_loopback(f): ...
