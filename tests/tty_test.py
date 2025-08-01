"""
tty_spawn.py – drive any console program through a real TTY
cross-platform (Windows via pywinpty, POSIX via pty).

API (async):
    term = TTYSpawn(cmd, *, cwd=None, env=None, encoding="utf-8")
    await term.start()             # launch child
    chunk = await term.read(timeout=1.0)     # None on timeout
    await term.send("data")        # raw bytes
    await term.sendline("text")    # adds '\n'
    await term.wait()              # exit code
    term.kill()                    # abort
"""
# ──────────────────  NO ORIGINAL LINES REMOVED – ONLY APPENDED CODE  ──────────────────

import asyncio, os, sys, platform, errno

_IS_WIN = platform.system() == "Windows"
if _IS_WIN:
    import winpty        # pip install pywinpty
    import msvcrt


#  Make stdin / stdout tolerant to broken UTF-8 so input() never aborts
try:
    # Python 3.7+ has reconfigure()
    sys.stdin .reconfigure(errors="replace")
    sys.stdout.reconfigure(errors="replace")
except AttributeError:
    # Older Pythons: wrap them manually
    import io
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,
                                  encoding=sys.stdin.encoding or "utf-8",
                                  errors="replace",
                                  line_buffering=True)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,
                                  encoding=sys.stdout.encoding or "utf-8",
                                  errors="replace",
                                  line_buffering=True)
#  ─────────────────────────────────────────────────────────────────────


# ──────────────────────────── PUBLIC CLASS ────────────────────────────

class TTYSpawn:
    def __init__(self, cmd, *, cwd=None, env=None,
                 encoding="utf-8", echo=True):          # ← NEW kw-arg `echo`
        self.cmd = cmd if isinstance(cmd, str) else " ".join(cmd)
        self.cwd = cwd
        self.env = env or os.environ.copy()
        self.encoding = encoding
        self.echo = echo                                # ← store preference
        self._proc = None
        self._buf = asyncio.Queue()

    # ── user-facing coroutines ────────────────────────────────────────
    async def start(self):
        if _IS_WIN:
            self._proc = await _spawn_winpty(
                self.cmd, self.cwd, self.env, self.echo)     # ← pass echo
        else:
            self._proc = await _spawn_posix_pty(
                self.cmd, self.cwd, self.env, self.echo)     # ← pass echo
        asyncio.create_task(self._pump_stdout())

    async def read(self, timeout=None):
        # Return any decoded text the child produced, or None on timeout
        try:
            return await asyncio.wait_for(self._buf.get(), timeout)
        except asyncio.TimeoutError:
            return None

    # backward-compat alias:
    readline = read

    async def send(self, data: str | bytes):
        if isinstance(data, str):
            data = data.encode(self.encoding)
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()

    async def sendline(self, line: str):
        await self.send(line + "\n")

    async def wait(self):
        return await self._proc.wait()

    def kill(self):
        self._proc.kill()

    async def read_until_idle(self, idle_timeout, total_timeout):
        # Collect child output using iter_until_idle to avoid duplicate logic
        return "".join([chunk async for chunk in self.iter_until_idle(idle_timeout, total_timeout)])

    async def iter_until_idle(self, idle_timeout, total_timeout):
        # Yield each chunk as soon as it arrives until idle or total timeout
        import time
        start = time.monotonic()
        while True:
            if time.monotonic() - start > total_timeout:
                break
            chunk = await self.read(timeout=idle_timeout)
            if chunk is None:
                break
            yield chunk

    # ── internal: stream raw output into the queue ────────────────────
    async def _pump_stdout(self):
        reader = self._proc.stdout
        while True:
            chunk = await reader.read(4096)      # grab whatever is ready
            if not chunk:
                break
            self._buf.put_nowait(chunk.decode(self.encoding, "replace"))

# ──────────────────────────── POSIX IMPLEMENTATION ────────────────────

async def _spawn_posix_pty(cmd, cwd, env, echo):
    import pty, asyncio, os, termios
    master, slave = pty.openpty()

    # ── Disable ECHO on the slave side if requested ──
    if not echo:
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO          # lflag
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=cwd,
        env=env,
        close_fds=True,
    )
    os.close(slave)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()

    def _on_data():
        try:
            data = os.read(master, 1 << 16)
        except OSError as e:
            if e.errno != errno.EIO:  # EIO == EOF on some systems
                raise
            data = b""
        if data:
            reader.feed_data(data)
        else:
            reader.feed_eof()
            loop.remove_reader(master)

    loop.add_reader(master, _on_data)

    class _Stdin:
        def write(self, d): os.write(master, d)
        async def drain(self): await asyncio.sleep(0)

    proc.stdin = _Stdin()
    proc.stdout = reader
    return proc

# ──────────────────────────── WINDOWS IMPLEMENTATION ──────────────────

async def _spawn_winpty(cmd, cwd, env, echo):
    # A quick way to silence command echo in cmd.exe is /Q (quiet)
    if not echo and cmd.strip().lower().startswith("cmd") and "/q" not in cmd.lower():
        cmd = cmd.replace("cmd.exe", "cmd.exe /Q")

    cols, rows = 80, 25
    pty = winpty.PTY(cols, rows)
    child = pty.spawn(cmd, cwd=cwd or os.getcwd(), env=env)

    master_r_fd = msvcrt.open_osfhandle(child.conout_pipe, os.O_RDONLY)
    master_w_fd = msvcrt.open_osfhandle(child.conin_pipe, 0)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()

    def _on_data():
        try:
            data = os.read(master_r_fd, 1 << 16)
        except OSError:
            data = b""
        if data:
            reader.feed_data(data)
        else:
            reader.feed_eof()
            loop.remove_reader(master_r_fd)

    loop.add_reader(master_r_fd, _on_data)

    class _Stdin:
        def write(self, d): os.write(master_w_fd, d)
        async def drain(self): await asyncio.sleep(0)

    class _Proc(asyncio.subprocess.Process):
        def __init__(self):
            self.stdin = _Stdin()
            self.stdout = reader
            self.pid = child.pid
        async def wait(self):
            while child.isalive():
                await asyncio.sleep(0.2)
            return 0
        def kill(self):
            child.kill()

    return _Proc()

# ───────────────────────── INTERACTIVE DRIVER ─────────────────────────

async def interactive_shell():
    shell_cmd, prompt_hint = (
        ("cmd.exe", "$") if _IS_WIN else ("/bin/bash", "$")
    )

    # echo=False → suppress the shell’s own echo of commands
    term = TTYSpawn(shell_cmd, echo=False)
    await term.start()

    timeout = 1.0

    print(f"Connected to {shell_cmd}.")
    print("Type commands for the shell.")
    print("• t=<seconds>  → change idle timeout")
    print("• exit         → quit helper\n")

    await term.sendline(" ")
    print(await term.read_until_idle(timeout, timeout), end="", flush=True)

    while True:
        try:
            user = input(f"(timeout={timeout}) {prompt_hint} ")
        except (EOFError, KeyboardInterrupt):
            print("\nLeaving…")
            break

        if user.lower() == "/exit":
            break
        if user.startswith("/t="):
            try:
                timeout = float(user.split("=", 1)[1])
                print(f"[helper] idle timeout set to {timeout}s")
            except ValueError:
                print("[helper] invalid number")
            continue

        idle_timeout = timeout
        total_timeout = 10 * idle_timeout
        if user == "":
            # Just read output, do not send empty line
            async for chunk in term.iter_until_idle(idle_timeout, total_timeout):
                print(chunk, end="", flush=True)
        else:
            await term.sendline(user)
            async for chunk in term.iter_until_idle(idle_timeout, total_timeout):
                print(chunk, end="", flush=True)

    await term.sendline("exit")
    await term.wait()

if __name__ == "__main__":
    asyncio.run(interactive_shell())
