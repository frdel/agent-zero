import select
import subprocess
import time
import sys
from typing import Optional, Tuple
from python.helpers import tty_session
from python.helpers.shell_ssh import clean_string

class LocalInteractiveSession:
    def __init__(self):
        self.session: tty_session.TTYSession|None = None
        self.full_output = ''

    async def connect(self):
        self.session = tty_session.TTYSession("/bin/bash")
        await self.session.start()
        await self.session.read_full_until_idle(idle_timeout=1, total_timeout=1)

    async def close(self):
        if self.session:
            self.session.kill()
            # self.session.wait()

    async def send_command(self, command: str):
        if not self.session:
            raise Exception("Shell not connected")
        self.full_output = ""
        await self.session.sendline(command)
 
    async def read_output(self, timeout: float = 0, reset_full_output: bool = False) -> Tuple[str, Optional[str]]:
        if not self.session:
            raise Exception("Shell not connected")

        if reset_full_output:
            self.full_output = ""

        # get output from terminal
        partial_output = await self.session.read_full_until_idle(idle_timeout=0.01, total_timeout=timeout)
        self.full_output += partial_output

        # clean output
        partial_output = clean_string(partial_output)
        clean_full_output = clean_string(self.full_output)

        if not partial_output:
            return clean_full_output, None
        return clean_full_output, partial_output