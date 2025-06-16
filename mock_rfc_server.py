#!/usr/bin/env python3
from flask import Flask, request, jsonify
import time
import json # Import json for parsing nested data

# This is the password that the code_execution_tool needs to receive.
# It must match the host's actual root password.
KNOWN_ROOT_PASSWORD = "macGYVER5935!!"

app = Flask(__name__)

@app.route('/rfc', methods=['POST'])
def handle_rfc():
    outer_payload = request.get_json()
    print(f"--- Mock RFC Server ---")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Received full outer payload:")
    print(json.dumps(outer_payload, indent=2))

    # Check if 'rfc_input' key exists and is a string
    if outer_payload and 'rfc_input' in outer_payload and isinstance(outer_payload['rfc_input'], str):
        try:
            # Parse the inner JSON string
            inner_payload = json.loads(outer_payload['rfc_input'])
            print("Successfully parsed inner JSON payload.")

            # Check if the function name matches the one we need to handle
            if inner_payload.get('function_name') == '_provide_root_password':
                print("-> Detected '_provide_root_password' request. Responding with known password.")

                # Based on the code, the response should be a simple dict with the result
                response_payload = {
                    "result": KNOWN_ROOT_PASSWORD
                }
                print(f"-> Sending success response: {response_payload}")
                print(f"----------------------")
                return jsonify(response_payload)

        except json.JSONDecodeError:
            print("-> FAILED to parse inner 'rfc_input' string as JSON.")

    print(f"-> Received unhandled function call or bad request. Returning error.")
    print(f"----------------------")
    return jsonify({"error": "Mock server did not handle this function call"}), 400

if __name__ == '__main__':
    print("Starting FINAL Mock RFC Server on http://127.0.0.1:50080...")
    app.run(host='127.0.0.1', port=50080, debug=False)
