import threading
from flask import Flask, request
from python.helpers import runtime, dotenv, process
from python.helpers.print_style import PrintStyle

from python.api.tunnel import Tunnel

# initialize the internal Flask server
app = Flask("app")
app.config["JSON_SORT_KEYS"] = False  # Disable key sorting in jsonify


def run():
    # Suppress only request logs but keep the startup messages
    from werkzeug.serving import WSGIRequestHandler
    from werkzeug.serving import make_server

    PrintStyle().print("Starting tunnel server...")

    class NoRequestLoggingWSGIRequestHandler(WSGIRequestHandler):
        def log_request(self, code="-", size="-"):
            pass  # Override to suppress request logging

    # Get configuration from environment
    tunnel_api_port = runtime.get_tunnel_api_port()
    host = (
        runtime.get_arg("host") or dotenv.get_dotenv_value("WEB_UI_HOST") or "localhost"
    )
    server = None
    lock = threading.Lock()
    tunnel = Tunnel(app, lock)

    # handle api request
    @app.route("/", methods=["POST"])
    async def handle_request():
        return await tunnel.handle_request(request=request)  # type: ignore

    try:
        server = make_server(
            host=host,
            port=tunnel_api_port,
            app=app,
            request_handler=NoRequestLoggingWSGIRequestHandler,
            threaded=True,
        )
        
        process.set_server(server)
        # server.log_startup()
        server.serve_forever()
    finally:
        # Clean up tunnel if it was started
        if tunnel:
            tunnel.stop()


# run the internal server
if __name__ == "__main__":
    runtime.initialize()
    dotenv.load_dotenv()
    run()
