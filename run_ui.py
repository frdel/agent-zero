from functools import wraps
import os
from pathlib import Path
import threading
from flask import Flask, request, jsonify, Response
from flask_basicauth import BasicAuth
from agent import Agent
from initialize import initialize
from python.helpers.files import get_abs_path
from python.helpers.print_style import PrintStyle
from python.helpers.log import Log
from dotenv import load_dotenv

#global agent instance
agent0: Agent|None = None

#initialize the internal Flask server
app = Flask("app",static_folder=get_abs_path("./webui"),static_url_path="/")

# Set up basic authentication, name and password from .env variables
app.config['BASIC_AUTH_USERNAME'] = os.environ.get('BASIC_AUTH_USERNAME') or "admin" #default name
app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('BASIC_AUTH_PASSWORD') or "admin" #default pass
basic_auth = BasicAuth(app)

# get global agent
def get_agent(reset: bool = False) -> Agent:
    global agent0
    if agent0 is None or reset:
        agent0 = initialize()
    return agent0

# Now you can use @requires_auth function decorator to require login on certain pages
def requires_auth(f):
    @wraps(f)
    async def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == app.config['BASIC_AUTH_USERNAME'] and auth.password == app.config['BASIC_AUTH_PASSWORD']):
            return Response(
                'Could not verify your access level for that URL.\n'
                'You have to login with proper credentials', 401,
                {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return await f(*args, **kwargs)
    return decorated

# handle default address, show demo html page from ./test_form.html
@app.route('/', methods=['GET'])
async def test_form():
    return Path(get_abs_path("./webui/index.html")).read_text()

# simple health check, just return OK to see the server is running
@app.route('/ok', methods=['GET','POST'])
async def health_check():
    return "OK"

# # secret page, requires authentication
# @app.route('/secret', methods=['GET'])
# @requires_auth
# async def secret_page():
#     return Path("./secret_page.html").read_text()

# send message to agent
@app.route('/msg', methods=['POST'])
async def handle_message():
    try:
        
        #agent instance
        agent = get_agent()

        #data sent to the server
        input = request.get_json()
        text = input.get("text", "")

        # print to console and log
        PrintStyle(background_color="#6C3483", font_color="white", bold=True, padding=True).print(f"User message:")        
        PrintStyle(font_color="white", padding=False).print(f"> {text}")
        Log.log(type="user", heading="User message", content=text)
        
        #pass the message to the agent
        threading.Thread(target=agent.communicate, args=(text,)).start()
        
        #data from this server    
        response = {
            "ok": True,
            "message": "Message received.",
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }

    #respond with json
    return jsonify(response)

# pausing/unpausing the agent
@app.route('/pause', methods=['POST'])
async def pause():
    try:
        
        #data sent to the server
        input = request.get_json()
        paused = input.get("paused", False)

        Agent.paused = paused

        response = {
            "ok": True,
            "message": "Agent paused." if paused else "Agent unpaused.",
            "pause": paused
        }        
        
    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }

    #respond with json
    return jsonify(response)

# restarting with new agent0
@app.route('/reset', methods=['POST'])
async def reset():
    try:
        
        agent = get_agent(reset=True)
        Log.reset()

        response = {
            "ok": True,
            "message": "Agent restarted.",
        }        
        
    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }

    #respond with json
    return jsonify(response)

# Web UI polling
@app.route('/poll', methods=['POST'])
async def poll():
    try:
        
        #data sent to the server
        input = request.get_json()
        from_no = input.get("log_from", "")

        logs = Log.logs[int(from_no):]
        to = Log.last_updated #max(0, len(Log.logs)-1)
        
        #data from this server    
        response = {
            "ok": True,
            "logs": logs,
            "log_to": to,
            "log_guid": Log.guid,
            "log_version": Log.version,
            "paused": Agent.paused
        }

    except Exception as e:
        response = {
            "ok": False,
            "message": str(e),
        }

    #respond with json
    return jsonify(response)



#run the internal server
if __name__ == "__main__":

    load_dotenv()
    
    get_agent() #initialize

    # Suppress only request logs but keep the startup messages
    from werkzeug.serving import WSGIRequestHandler
    class NoRequestLoggingWSGIRequestHandler(WSGIRequestHandler):
        def log_request(self, code='-', size='-'):
            pass  # Override to suppress request logging

    # run the server on port from .env
    port = int(os.environ.get("WEB_UI_PORT", 0)) or None
    app.run(request_handler=NoRequestLoggingWSGIRequestHandler,port=port)
