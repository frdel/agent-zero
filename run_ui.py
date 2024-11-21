import json
from functools import wraps
import os
from pathlib import Path
import threading
import uuid
from flask import Flask, request, jsonify, Response, send_file
from flask_basicauth import BasicAuth
from agent import AgentContext
from initialize import initialize
from python.helpers import files, git
from python.helpers.files import get_abs_path
from python.helpers.print_style import PrintStyle
from python.helpers.dotenv import load_dotenv
from python.helpers import persist_chat, settings, whisper, rfc, runtime, dotenv
import base64
from werkzeug.utils import secure_filename
from python.helpers.cloudflare_tunnel import CloudflareTunnel
from python.helpers.extract_tools import load_classes_from_folder
from python.helpers.api import ApiHandler
from python.helpers.file_browser import FileBrowser


# initialize the internal Flask server
app = Flask("app", static_folder=get_abs_path("./webui"), static_url_path="/")
app.config["JSON_SORT_KEYS"] = False  # Disable key sorting in jsonify

lock = threading.Lock()

# Set up basic authentication
basic_auth = BasicAuth(app)


# require authentication for handlers
def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        user = dotenv.get_dotenv_value("AUTH_LOGIN")
        password = dotenv.get_dotenv_value("AUTH_PASSWORD")
        if user and password:
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


# handle default address, load index
@app.route("/", methods=["GET"])
@requires_auth
async def serve_index():
    gitinfo = git.get_git_info()
    return files.read_file(
        "./webui/index.html",
        version_no=gitinfo["version"],
        version_time=gitinfo["commit_time"],
    )

def run():
    print("Initializing framework...")

    # Suppress only request logs but keep the startup messages
    from werkzeug.serving import WSGIRequestHandler

    class NoRequestLoggingWSGIRequestHandler(WSGIRequestHandler):
        def log_request(self, code="-", size="-"):
            pass  # Override to suppress request logging

    # Get configuration from environment
    port = runtime.get_arg("port") or int(os.environ.get("WEB_UI_PORT", 0)) or None
    host = runtime.get_arg("host") or os.environ.get("WEB_UI_HOST") or None
    use_cloudflare = (
        runtime.get_arg("cloudflare_tunnel")
        or os.environ.get("USE_CLOUDFLARE", "false").lower() == "true"
    )

    # Initialize and start Cloudflare tunnel if enabled
    tunnel = None
    if use_cloudflare and port:
        try:
            tunnel = CloudflareTunnel(port)
            tunnel.start()
        except Exception as e:
            print(f"Failed to start Cloudflare tunnel: {e}")
            print("Continuing without tunnel...")

    # initialize contexts from persisted chats
    persist_chat.load_tmp_chats()

    def register_api_handler(app, handler):
        name = handler.__module__.split(".")[-1]
        instance = handler(app, lock)
        @requires_auth
        async def handle_request():
            return await instance.handle_request(request=request)
        app.add_url_rule(
            f"/{name}",
            f"/{name}",
            handle_request,
            methods=["POST", "GET"],
        )
        
    # initialize and register API handlers
    handlers = load_classes_from_folder("python/api", "*.py", ApiHandler)
    for handler in handlers:
        register_api_handler(app, handler)
        



    try:
        # Run Flask app
        app.run(
            request_handler=NoRequestLoggingWSGIRequestHandler, port=port, host=host
        )
    finally:
        # Clean up tunnel if it was started
        if tunnel:
            tunnel.stop()


# run the internal server
if __name__ == "__main__":
    runtime.initialize()
    run()
