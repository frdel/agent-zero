import os
import sys
from python.helpers import runtime
from python.helpers.print_style import PrintStyle

_server = None

def set_server(server):
    global _server
    _server = server

def get_server(server):
    global _server
    return _server

def stop_server():
    global _server
    if _server:
        _server.shutdown()
        _server = None

def reload():
    stop_server()
    if runtime.is_dockerized():
        exit_process()
    else:
        restart_process()

def restart_process():
    PrintStyle.standard("Restarting process...")
    python = sys.executable
    os.execv(python, [python] + sys.argv)

def exit_process():
    PrintStyle.standard("Exiting process...")
    sys.exit(0)