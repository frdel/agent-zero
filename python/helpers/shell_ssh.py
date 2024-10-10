import asyncio
import paramiko
import time
import re
from typing import Tuple
from python.helpers.log import Log
from python.helpers.strings import calculate_valid_match_lengths

class SSHInteractiveSession:

    # end_comment = "# @@==>> SSHInteractiveSession End-of-Command  <<==@@"
    # ps1_label = "SSHInteractiveSession CLI>"
    
    def __init__(self, logger: Log, hostname: str, port: int, username: str, password: str):
        self.logger = logger
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.shell = None
        self.full_output = b''
        self.last_command = b''
        self.trimmed_command_length = 0  # Initialize trimmed_command_length


    async def connect(self):
        # try 3 times with wait and then except
        errors = 0
        while True:
            try:
                self.client.connect(self.hostname, self.port, self.username, self.password)
                self.shell = self.client.invoke_shell(width=160,height=48)
                # self.shell.send(f'PS1="{SSHInteractiveSession.ps1_label}"'.encode())
                # return
                while True: # wait for end of initial output
                    full, part = await self.read_output()
                    if full and not part: return
                    time.sleep(0.1)
            except Exception as e:
                errors += 1
                if errors < 3:
                    print(f"SSH Connection attempt {errors}...")
                    self.logger.log(type="info", content=f"SSH Connection attempt {errors}...", temp=True)
                    
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
        self.full_output = b""
        # if len(command) > 10: # if command is long, add end_comment to split output
        #     command = (command + " \\\n" +SSHInteractiveSession.end_comment + "\n")
        # else:
        command = command + "\n"
        self.last_command = command.encode()
        self.trimmed_command_length = 0
        self.shell.send(self.last_command)

    async def read_output(self, timeout: float = 0) -> Tuple[str, str]:
        if not self.shell:
            raise Exception("Shell not connected")

        partial_output = b''
        leftover = b''
        start_time = time.time()

        while self.shell.recv_ready() and (timeout <= 0 or time.time() - start_time < timeout):

            data = self.shell.recv(1024)

            # Trim own command from output
            if self.last_command and len(self.last_command) > self.trimmed_command_length:
                command_to_trim = self.last_command[self.trimmed_command_length:]
                data_to_trim = leftover + data
                
                trim_com, trim_out = calculate_valid_match_lengths(
                    command_to_trim, data_to_trim, deviation_threshold=8, deviation_reset=2, 
                    ignore_patterns = [
                        rb'\x1b\[\?\d{4}[a-zA-Z](?:> )?',  # ANSI escape sequences
                        rb'\r',                            # Carriage return
                        rb'>\s',                             # Greater-than symbol
                    ], debug=False)

                leftover = b''
                if(trim_com > 0 and trim_out > 0):
                    data = data_to_trim[trim_out:]
                    leftover = data
                    self.trimmed_command_length += trim_com
            
            partial_output += data
            self.full_output += data
            await asyncio.sleep(0.1)  # Prevent busy waiting

        # Decode once at the end
        decoded_partial_output = partial_output.decode('utf-8', errors='replace')
        decoded_full_output = self.full_output.decode('utf-8', errors='replace')

        decoded_partial_output = self.clean_string(decoded_partial_output)
        decoded_full_output = self.clean_string(decoded_full_output)

        return decoded_full_output, decoded_partial_output


    def clean_string(self, input_string):
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', input_string)
        
        # Replace '\r\n' with '\n'
        cleaned = cleaned.replace('\r\n', '\n')

        # Split the string by newline characters to process each segment separately
        lines = cleaned.split('\n')

        for i in range(len(lines)):
            # Handle carriage returns '\r' by splitting and taking the last part
            parts = [part for part in lines[i].split('\r') if part.strip()]
            if parts: lines[i] = parts[-1].rstrip()  # Overwrite with the last part after the last '\r'

        return '\n'.join(lines)

