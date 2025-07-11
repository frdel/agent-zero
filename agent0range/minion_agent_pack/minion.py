#!/usr/bin/env python3
import os
import sys
import time
import json
import ssl
import threading
import websocket  # pip install websocket-client

CONFIG_PATH = os.path.expanduser('~/minion_config.json')

# Load config
def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f'Config load error: {e}')
        sys.exit(1)

def log(msg):
    with open(os.path.expanduser('~/.minion.log'), 'a') as f:
        f.write(f"{time.ctime()} | {msg}
")
    print(msg)

def execute_command(cmd):
    log(f"Executing: {cmd}")
    try:
        output = os.popen(cmd).read()
        log(f"Output: {output}")
        return output
    except Exception as e:
        log(f"Error: {e}")
        return str(e)

def heartbeat(ws, interval=60):
    while True:
        try:
            ws.send(json.dumps({"type": "heartbeat"}))
        except Exception as e:
            log(f"Heartbeat error: {e}")
        time.sleep(interval)

def main():
    config = load_config()
    ws_url = config['server_url']
    token = config['token']
    sslopt = {"cert_reqs": ssl.CERT_NONE}
    ws = websocket.create_connection(ws_url, sslopt=sslopt, header=[f"Authorization: Bearer {token}"])
    log("Connected to Agent Zero server.")
    threading.Thread(target=heartbeat, args=(ws,)).start()
    while True:
        try:
            msg = ws.recv()
            data = json.loads(msg)
            if data.get('type') == 'command':
                cmd = data['command']
                output = execute_command(cmd)
                ws.send(json.dumps({"type": "result", "output": output}))
        except Exception as e:
            log(f"Main loop error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
