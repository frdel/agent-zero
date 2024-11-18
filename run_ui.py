import json
from functools import wraps
import os
from pathlib import Path
import threading
import uuid
from flask import Flask, request, jsonify, Response
from flask_basicauth import BasicAuth
from agent import AgentContext
from initialize import initialize
from python.helpers import files
from python.helpers.files import get_abs_path
from python.helpers.print_style import PrintStyle
from python.helpers.dotenv import load_dotenv
from python.helpers import persist_chat, settings, whisper, rfc, runtime, dotenv
import base64
from werkzeug.utils import secure_filename
from python.helpers.cloudflare_tunnel import CloudflareTunnel


# initialize the internal Flask server
app = Flask("app", static_folder=get_abs_path("./webui"), static_url_path="/")
app.config["JSON_SORT_KEYS"] = False  # Disable key sorting in jsonify

lock = threading.Lock()

# Set up basic authentication
basic_auth = BasicAuth(app)


# get context to run agent zero in
def get_context(ctxid: str):
    with lock:
        if not ctxid:
            first = AgentContext.first()
            if first:
                return first
            return AgentContext(config=initialize())
        got = AgentContext.get(ctxid)
        if got:
            return got
        return AgentContext(config=initialize(), id=ctxid)


# Now you can use @requires_auth function decorator to require login on certain pages
def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        user = dotenv.get_dotenv_value("AUTH_LOGIN")
        password = dotenv.get_dotenv_value("AUTH_PASSWORD")
        if user and password:    
            auth = request.authorization
            if not auth or not (
                auth.username == user
                and auth.password == password
            ):
                return Response(
                    "Could not verify your access level for that URL.\n"
                    "You have to login with proper credentials",
                    401,
                    {"WWW-Authenticate": 'Basic realm="Login Required"'},
                )
        return await f(*args, **kwargs)

    return decorated


UPLOAD_FOLDER = os.path.join(os.getcwd(), "work_dir", "uploads")


@app.route("/upload", methods=["POST"])
@requires_auth
async def upload_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "No file part"}), 400

    files = request.files.getlist("file")  # Handle multiple files
    saved_filenames = []

    for file in files:
        if file and allowed_file(file.filename):  # Check file type
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            saved_filenames.append(filename)

    return jsonify({"ok": True, "filenames": saved_filenames})  # Return saved filenames


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "txt", "pdf", "csv", "html", "json", "md"}
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/import_knowledge", methods=["POST"])
@requires_auth
async def import_knowledge():
    if "files[]" not in request.files:
        return jsonify({"ok": False, "message": "No files part"}), 400

    files = request.files.getlist("files[]")
    KNOWLEDGE_FOLDER = os.path.join(os.getcwd(), "knowledge", "custom", "main")

    saved_filenames = []

    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(KNOWLEDGE_FOLDER, filename))
            saved_filenames.append(filename)

    return jsonify(
        {"ok": True, "message": "Knowledge Imported", "filenames": saved_filenames}
    )


@app.route("/work_dir", methods=["GET"])  # Correct route
@requires_auth
async def browse_work_dir():
    work_dir = os.path.join(os.getcwd(), "work_dir")
    try:
        files = [
            f for f in os.listdir(work_dir) if os.path.isfile(os.path.join(work_dir, f))
        ]
        return jsonify({"ok": True, "files": files})
    except FileNotFoundError:
        return jsonify({"ok": False, "message": "work_dir not found"}), 404
    except Exception as e:
        return (
            jsonify({"ok": False, "message": f"Error browsing work_dir: {str(e)}"}),
            500,
        )


# handle default address, show demo html page from ./test_form.html
@app.route("/", methods=["GET"])
@requires_auth
async def test_form():
    return Path(get_abs_path("./webui/index.html")).read_text()


# simple health check, just return OK to see the server is running
@app.route("/ok", methods=["GET", "POST"])
async def health_check():
    return "OK"

# send message to agent (async UI)
@app.route("/msg", methods=["POST"])
@requires_auth
async def handle_message_async():
    return await handle_message(False)


# send message to agent (synchronous API)
@app.route("/msg_sync", methods=["POST"])
@requires_auth
async def handle_msg_sync():
    return await handle_message(True)


async def handle_message(sync: bool):
    try:
        # Handle both JSON and multipart/form-data
        if request.content_type.startswith("multipart/form-data"):
            text = request.form.get("text", "")
            ctxid = request.form.get("context", "")
            message_id = request.form.get("message_id", None)
            attachments = request.files.getlist("attachments")
            attachment_paths = []

            upload_folder = files.get_abs_path("work_dir/uploads")

            if attachments:
                os.makedirs(upload_folder, exist_ok=True)
                for attachment in attachments:
                    filename = secure_filename(attachment.filename)
                    save_path = files.get_abs_path(upload_folder, filename)
                    attachment.save(save_path)
                    attachment_paths.append(save_path)
        else:
            # Handle JSON request as before
            input_data = request.get_json()
            text = input_data.get("text", "")
            ctxid = input_data.get("context", "")
            message_id = input_data.get("message_id", None)
            attachment_paths = []

        # Now process the message
        message = text

        # Obtain agent context
        context = get_context(ctxid)

        # Store attachments in agent data
        context.agent0.set_data("attachments", attachment_paths)

        # Prepare attachment filenames for logging
        attachment_filenames = (
            [os.path.basename(path) for path in attachment_paths]
            if attachment_paths
            else []
        )

        # Print to console and log
        PrintStyle(
            background_color="#6C3483", font_color="white", bold=True, padding=True
        ).print(f"User message:")
        PrintStyle(font_color="white", padding=False).print(f"> {message}")
        if attachment_filenames:
            PrintStyle(font_color="white", padding=False).print("Attachments:")
            for filename in attachment_filenames:
                PrintStyle(font_color="white", padding=False).print(f"- {filename}")

        # Log the message with message_id and attachments
        context.log.log(
            type="user",
            heading="User message",
            content=message,
            kvps={"attachments": attachment_filenames},
            id=message_id,
        )

        if sync:
            context.communicate(message)
            result = await context.process.result()  # type: ignore
            response = {
                "ok": True,
                "message": result,
                "context": context.id,
            }
        else:
            context.communicate(message)
            response = {
                "ok": True,
                "message": "Message received.",
                "context": context.id,
            }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# pausing/unpausing the agent
@app.route("/pause", methods=["POST"])
@requires_auth
async def pause():
    try:

        # data sent to the server
        input = request.get_json()
        paused = input.get("paused", False)
        ctxid = input.get("context", "")

        # context instance - get or create
        context = get_context(ctxid)

        context.paused = paused

        response = {
            "ok": True,
            "message": "Agent paused." if paused else "Agent unpaused.",
            "pause": paused,
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# load chats from json
@app.route("/loadChats", methods=["POST"])
@requires_auth
async def load_chats():
    try:
        # data sent to the server
        input = request.get_json()
        chats = input.get("chats", [])
        if not chats:
            raise Exception("No chats provided")

        ctxids = persist_chat.load_json_chats(chats)

        response = {
            "ok": True,
            "message": "Chats loaded.",
            "ctxids": ctxids,
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# save chats to json
@app.route("/exportChat", methods=["POST"])
@requires_auth
async def export_chat():
    try:
        # data sent to the server
        input = request.get_json()
        ctxid = input.get("ctxid", "")
        if not ctxid:
            raise Exception("No context id provided")

        context = get_context(ctxid)
        content = persist_chat.export_json_chat(context)

        response = {
            "ok": True,
            "message": "Chats exported.",
            "ctxid": context.id,
            "content": content,
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# restarting with new agent0
@app.route("/reset", methods=["POST"])
@requires_auth
async def reset():
    try:

        # data sent to the server
        input = request.get_json()
        ctxid = input.get("context", "")

        # context instance - get or create
        context = get_context(ctxid)
        context.reset()
        persist_chat.save_tmp_chat(context)

        response = {
            "ok": True,
            "message": "Agent restarted.",
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# killing context
@app.route("/remove", methods=["POST"])
@requires_auth
async def remove():
    try:

        # data sent to the server
        input = request.get_json()
        ctxid = input.get("context", "")

        # context instance - get or create
        AgentContext.remove(ctxid)
        persist_chat.remove_chat(ctxid)

        response = {
            "ok": True,
            "message": "Context removed.",
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# Web UI polling
@app.route("/poll", methods=["POST"])
@requires_auth
async def poll():
    try:

        # data sent to the server
        input = request.get_json()
        ctxid = input.get("context", None)
        from_no = input.get("log_from", 0)

        # context instance - get or create
        context = get_context(ctxid)

        logs = context.log.output(start=from_no)

        # loop AgentContext._contexts
        ctxs = []
        for ctx in AgentContext._contexts.values():
            ctxs.append(
                {
                    "id": ctx.id,
                    "no": ctx.no,
                    "log_guid": ctx.log.guid,
                    "log_version": len(ctx.log.updates),
                    "log_length": len(ctx.log.logs),
                    "paused": ctx.paused,
                }
            )

        # data from this server
        response = {
            "ok": True,
            "context": context.id,
            "contexts": ctxs,
            "logs": logs,
            "log_guid": context.log.guid,
            "log_version": len(context.log.updates),
            "log_progress": context.log.progress,
            "paused": context.paused,
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # serialize json with json.dumps to preserve OrderedDict order
    response_json = json.dumps(response)
    return Response(response=response_json, status=200, mimetype="application/json")
    # return jsonify(response)


# get current settings
@app.route("/getSettings", methods=["POST"])
@requires_auth
async def get_settings():
    try:

        # data sent to the server
        input = request.get_json()

        set = settings.convert_out(settings.get_settings())

        response = {"ok": True, "settings": set}

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# set current settings
@app.route("/setSettings", methods=["POST"])
@requires_auth
async def set_settings():
    try:

        # data sent to the server
        input = request.get_json()

        set = settings.convert_in(input)
        set = settings.set_settings(set)

        response = {"ok": True, "settings": set}

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# transcribe audio
@app.route("/transcribe", methods=["POST"])
@requires_auth
async def transcribe():
    try:

        # data sent to the server
        input = request.get_json()
        audio = input.get("audio")

        # transcribe audio
        result = await whisper.transcribe(audio)

        response = {
            "ok": True,
            "text": result["text"],
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }
        PrintStyle.error(str(e))

    # respond with json
    return jsonify(response)


# remote function call
@app.route("/rfc", methods=["POST"])
@requires_auth
async def handle_rfc():
    # data sent to the server
    input = json.loads(request.get_json())

    # handle RFC
    result = await runtime.handle_rfc(input)
    return jsonify(result)


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
