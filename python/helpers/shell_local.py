import select
import subprocess
import time
import sys
from typing import Optional, Tuple

class LocalInteractiveSession:
    def __init__(self):
        self.process = None
        self.full_output = ''

    def connect(self):
        # Start a new subprocess with the appropriate shell for the OS
        if sys.platform.startswith('win'):
            # Windows
            self.process = subprocess.Popen(
                ['cmd.exe'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        else:
            # macOS and Linux
            self.process = subprocess.Popen(
                ['/bin/bash'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

    def close(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

    def send_command(self, command: str):
        if not self.process:
            raise Exception("Shell not connected")
        self.full_output = ""
        self.process.stdin.write(command + '\n') # type: ignore
        self.process.stdin.flush() # type: ignore
 
    def read_output(self) -> Tuple[str, Optional[str]]:
        if not self.process:
            raise Exception("Shell not connected")

        partial_output = ''
        while True:
            rlist, _, _ = select.select([self.process.stdout], [], [], 0.1)
            if rlist:
                line = self.process.stdout.readline()  # type: ignore
                if line:
                    partial_output += line
                    self.full_output += line
                    time.sleep(0.1)
                else:
                    break  # No more output
            else:
                break  # No data available

        if not partial_output:
            return self.full_output, None
        
        return self.full_output, partial_output