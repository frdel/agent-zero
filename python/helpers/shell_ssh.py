import paramiko
import time
import re
from typing import Optional, Tuple

class SSHInteractiveSession:
    def __init__(self, hostname: str, port: int, username: str, password: str):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.full_output = ''

    def connect(self):
        # try 3 times with wait and then except
        errors = 0
        while True:
            try:
                self.client.connect(self.hostname, self.port, self.username, self.password)
                self.shell = self.client.invoke_shell()
                while True: # wait for end of initial output
                    full, part = self.read_output()
                    if full and not part: return
                    time.sleep(0.1)
            except Exception as e:
                errors += 1
                if errors < 3:
                    print(f"SSH Connection attempt {errors}...")
                    time.sleep(5)
                else:
                    raise e

    def close(self):
        if self.shell:
            self.shell.close()
        if self.client:
            self.client.close()

    def send_command(self, command: str):
        if not self.shell:
            raise Exception("Shell not connected")
        self.full_output = ""
        self.shell.send((command + '\n').encode())

    def read_output(self) -> Tuple[str, str]:
        if not self.shell:
            raise Exception("Shell not connected")

        partial_output = ''
        while self.shell.recv_ready():
            data = self.shell.recv(1024).decode('utf-8')
            data = self.clean_string(data)
            partial_output += data
            self.full_output += data
            time.sleep(0.1)  # Prevent busy waiting

        self.full_output = self.clean_string(self.full_output)
        return self.full_output, partial_output

    def clean_string(self, input_string):
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', input_string)
        
        # Replace '\r\n' with '\n'
        cleaned = cleaned.replace('\r\n', '\n')
        
        return cleaned