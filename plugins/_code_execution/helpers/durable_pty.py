"""Standalone, private PTY receipt daemon. Contains no database credentials.

The relay publishes immutable ordered requests. A send intent is fsynced before
the first byte; restarting this daemon never resends an unfinished request.
This file is also copied to a host-key-pinned SSH execution target.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import select
import shlex
import signal
import stat
import subprocess
import sys
import termios
import time

LIMIT = 8 * 1024 * 1024
IGNORED = re.compile(r"^(?:__a0_|BASH|COMP|READLINE|HIST|PS[0-9]|EUID$|UID$|PPID$|SHELLOPTS$|SHLVL$|PWD$|OLDPWD$|_$|COLUMNS$|LINES$|PIPESTATUS$|DIRSTACK$|GROUPS$|RANDOM$|SECONDS$|EPOCH)")
FRAMING_COMMANDS = frozenset({"builtin", "command", "set", "shopt", "declare", "alias",
    "cd", "unset", "source", "mv", "readlink", "/bin/mv", "/usr/bin/readlink"})


def framing_safe(state):
    """A state restore must never invoke user code as its own machinery."""
    if (type(state) is not dict or type(state.get("functions")) is not str
            or type(state.get("aliases")) is not str or type(state.get("variables")) is not dict
            or type(state.get("unset")) is not list):
        return False
    functions = re.findall(r"(?m)^([^\s()]+)\s*\(\)\s*$", state["functions"])
    aliases = re.findall(r"(?m)^alias ([^=]+)=", state["aliases"])
    if any(name in FRAMING_COMMANDS or name.startswith("__a0_") for name in functions + aliases):
        return False
    # An array PROMPT_COMMAND survives assignment to element zero and would
    # execute old prompt actions again after reconstruction. It is framing
    # state, never a replayable user declaration.
    return "PROMPT_COMMAND" not in state["variables"] and "PROMPT_COMMAND" not in state["unset"]


def write(path, value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    temporary = path.with_name(path.name + "." + secrets.token_hex(8))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data); out.flush(); os.fsync(out.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as inp:
        info = os.fstat(inp.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError("Unsafe PTY receipt")
        return json.load(inp)


def _declarations(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r"declare -([^ ]*) ([a-zA-Z_][a-zA-Z0-9_]*)(?:=|$)", line)
        if match and "r" not in match[1] and not IGNORED.match(match[2]):
            result[match[2]] = line
    return result


def snapshot(path, baseline=None):
    raw = path.read_bytes()
    if len(raw) > LIMIT:
        raise ValueError("Shell snapshot exceeds bound")
    parts = raw.decode(errors="strict").split("\0")
    if len(parts) != 11:
        raise ValueError("Incomplete shell snapshot")
    code, cwd, variables, functions, aliases, options, shopt, traps, jobs, descriptors, _ = parts
    readonly = {}
    for line in variables.splitlines():
        match = re.match(r"declare -([^ ]*) ([a-zA-Z_][a-zA-Z0-9_]*)(?:=|$)", line)
        if match and "r" in match[1] and not IGNORED.match(match[2]):
            readonly[match[2]] = line
    variables = _declarations(variables)
    base = (baseline or {}).get("variables", {})
    removed = sorted(set(base) - set(variables))
    # Internal framing functions never enter portable user state.
    functions = re.sub(r"(?ms)^__a0_[a-zA-Z0-9_]+ \(\)\s*\n\{.*?^\}\s*\n?", "", functions)
    if baseline is not None:
        variables = {name: value for name, value in variables.items() if base.get(name) != value}
    inherited_traps = {"trap -- '' SIGINT", "trap -- '' SIGQUIT"}
    safe_traps = (set(traps.splitlines()) <= inherited_traps if baseline is None else traps == baseline["traps"])
    state = {"exit_code": int(code), "cwd": cwd, "variables": variables,
            "unset": removed, "functions": functions,
            "aliases": aliases, "options": options, "shopt": shopt,
            "portable": (safe_traps and not jobs.strip() and bool(descriptors.strip())
                         and (baseline is None or descriptors == baseline["descriptors"]
                              and readonly == baseline["readonly"])),
            "traps": traps, "jobs": jobs, "descriptors": descriptors, "readonly": readonly}
    if baseline is not None:
        state["portable"] = state["portable"] and framing_safe(state)
    return state


class Shell:
    def __init__(self, root, spec):
        restore = spec.get("restore")
        # Revalidate the actual declarations before starting any shell. Old
        # receipts and a stored portable=True flag cannot grant bootstrap code
        # permission to call a user-overridden framing/restore command.
        if restore and (not restore.get("portable") or not framing_safe(restore)):
            raise ValueError("Shell snapshot overrides framing or contains unsupported state")
        self.root, self.spec = root, spec
        self.secret = secrets.token_hex(24)
        self.marker = b"\x1eA0:" + self.secret.encode() + b":"
        self.output = bytearray()
        self.pending = b""
        self.ready = False
        self.baseline = None
        self.state = None
        self.master, slave = os.openpty()
        attrs = termios.tcgetattr(slave)
        attrs[3] &= ~termios.ECHO
        attrs[1] &= ~termios.OPOST
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
        environment = {k: v for k, v in os.environ.items() if not k.startswith("A0_DURABILITY_")}
        environment.update(PAGER="cat", GIT_PAGER="cat", TERM="dumb", PS1="", PS2="")
        def terminal():
            os.setsid()
            fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
        self.process = subprocess.Popen(["/bin/bash", "--noprofile", "--norc", "-i"],
            cwd=spec["cwd"], env=environment, stdin=slave, stdout=slave, stderr=slave,
            preexec_fn=terminal, close_fds=True)
        os.close(slave)
        os.set_blocking(self.master, False)
        temporary = shlex.quote(str(root / "state.tmp"))
        final = shlex.quote(str(root / "state.raw"))
        # Captured at an actual shell prompt, after the foreground command.
        capture = ("__a0_capture() { __a0_status=$?; { builtin printf '%s\\0' \"$__a0_status\" \"$PWD\"; "
            "while IFS= builtin read -r __a0_name; do builtin declare -p \"$__a0_name\"; done < <(builtin compgen -v); "
            "builtin printf '\\0'; builtin declare -f; builtin printf '\\0'; "
            "builtin alias -p; builtin printf '\\0'; builtin set +o; builtin printf '\\0'; "
            "builtin shopt -p; builtin printf '\\0'; builtin trap -p; builtin printf '\\0'; "
            "builtin jobs -p; builtin printf '\\0'; "
            "if [[ -d /proc/$$/fd && -x /usr/bin/readlink ]]; then "
            "for __a0_fd in /proc/$$/fd/*; do builtin printf '%s=' \"${__a0_fd##*/}\"; /usr/bin/readlink -- \"$__a0_fd\"; done; fi; "
            "builtin printf '\\0'; } > " + temporary + "; /bin/mv -- " + temporary + " " + final + "; "
            "builtin printf '\\036A0:" + self.secret + ":%s\\037' \"$__a0_status\"; }; "
            "PROMPT_COMMAND=__a0_capture; PS1=''; PS2=''; builtin shopt -s expand_aliases; "
            "builtin set +o history\n")
        self.send(capture.encode())
        self.wait_ready(10)
        self.baseline = self.state
        if restore:
            script = "builtin cd -- " + shlex.quote(restore["cwd"]) + "\n"
            script += "\n".join("builtin unset -- " + shlex.quote(k) for k in restore.get("unset", [])) + "\n"
            script += "\n".join(restore.get("variables", {}).values()) + "\n"
            script += restore.get("functions", "") + "\n" + restore.get("aliases", "") + "\n"
            # Job control and history remain broker-owned; the other shell
            # options and shopt flags are captured rather than guessed.
            script += restore.get("options", "") + "\n" + restore.get("shopt", "") + "\n"
            script += "PROMPT_COMMAND=__a0_capture; PS1=''; PS2=''\n"
            self.ready = False
            restore_path = root / ("restore-" + secrets.token_hex(8) + ".sh")
            fd = os.open(restore_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(script.encode()); out.flush(); os.fsync(out.fileno())
            self.send(("builtin source -- " + shlex.quote(str(restore_path)) + "\n").encode())
            self.wait_ready(10)
        else:
            self.state = snapshot(self.root / "state.raw", self.baseline)
        self.output.clear()

    def send(self, data):
        offset, deadline = 0, time.monotonic() + 30
        while offset < len(data):
            if self.process.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("PTY send outcome unknown")
            _, writable, _ = select.select([], [self.master], [], .1)
            if writable:
                try:
                    offset += os.write(self.master, data[offset:offset + 4096])
                except BlockingIOError:
                    pass

    def pump(self, timeout=.02):
        readable, _, _ = select.select([self.master], [], [], timeout)
        if not readable:
            return
        try:
            chunk = os.read(self.master, 65536)
        except OSError as exc:
            if exc.errno == errno.EIO:
                return
            raise
        self.pending += chunk
        while True:
            start = self.pending.find(self.marker)
            if start < 0:
                keep = min(len(self.pending), len(self.marker))
                self.output.extend(self.pending[:-keep] if keep else self.pending)
                self.pending = self.pending[-keep:] if keep else b""
                break
            end = self.pending.find(b"\x1f", start)
            if end < 0:
                break
            self.output.extend(self.pending[:start])
            self.pending = self.pending[end + 1:]
            self.state = snapshot(self.root / "state.raw", self.baseline)
            self.ready = True
        if len(self.output) > LIMIT:
            del self.output[:-LIMIT]

    def wait_ready(self, timeout):
        deadline = time.monotonic() + timeout
        while not self.ready:
            if time.monotonic() >= deadline or self.process.poll() is not None:
                raise RuntimeError("Shell prompt unavailable")
            self.pump(.05)

    def close(self):
        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.wait(timeout=5)
        os.close(self.master)


def serve(directory):
    root = Path(directory).absolute()
    for path in (root, root / "queue", root / "receipts"):
        if path.is_symlink():
            raise ValueError("Unsafe PTY directory")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    lock = os.open(root / "daemon.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    # A prior daemon's unfinished send has no repeat permission. Its shell may
    # have completed effects before dying; only a real receipt can settle it.
    if any(not path.with_suffix(".result").exists() for path in (root / "receipts").glob("*.intent")):
        write(root / "blocked.json", {"reason": "pty_send_outcome_unknown"})
        return
    spec = read(root / "session.json")
    # If only the daemon was lost at a settled prompt, reconstruct the actual
    # captured shell declarations. An unfinished intent above forbids this.
    for path in sorted((root / "queue").glob("*.json")):
        operation = read(path)
        receipt_path = root / "receipts" / (operation["id"] + ".result")
        if receipt_path.exists() and operation["kind"] != "read":
            receipt = read(receipt_path)
            spec["restore"] = receipt.get("state")
    shell, active, handled = None, [], set()
    try:
        shell = Shell(root, spec)
        write(root / "ready.json", {"pid": os.getpid(), "shell_pid": shell.process.pid, "session": spec["id"]})
        write(root / "prompt.json", {"state": shell.state, "workspace": spec.get("workspace")})
        while True:
            shell.pump()
            cancelled = read(root / "cancel.json") if (root / "cancel.json").exists() else []
            if active and any(item["id"] in cancelled for item in active):
                shell.close()
                for item in active:
                    write(root / "receipts" / (item["id"] + ".result"), {
                        "id": item["id"], "fingerprint": item["fingerprint"], "status": "completed",
                        "output": bytes(shell.output).decode(errors="replace"), "exit_code": -9,
                        "cancelled": True, "state": None})
                active.clear()
                shell = Shell(root, dict(spec, restore=None))
            if active and (shell.ready or shell.process.poll() is not None):
                state = shell.state if shell.ready else None
                if state:
                    write(root / "prompt.json", {"state": state, "workspace": spec.get("workspace")})
                for item in active:
                    write(root / "receipts" / (item["id"] + ".result"), {
                        "id": item["id"], "fingerprint": item["fingerprint"], "status": "completed",
                        "output": bytes(shell.output + shell.pending).decode(errors="replace"),
                        "exit_code": state["exit_code"] if state else shell.process.returncode,
                        "cancelled": False, "state": state})
                active.clear()
                if shell.process.poll() is not None:
                    shell.close()
                    shell = Shell(root, dict(spec, restore=None))
                    write(root / "prompt.json", {"state": shell.state, "workspace": spec.get("workspace")})
            for path in sorted((root / "queue").glob("*.json")):
                item = read(path)
                identity = item["id"]
                if identity in handled or (root / "receipts" / (identity + ".result")).exists():
                    handled.add(identity)
                    continue
                if item["kind"] == "command" and active:
                    continue
                intent = root / "receipts" / (identity + ".intent")
                if intent.exists():
                    continue  # never re-send, even within the same daemon
                if item["kind"] == "read":
                    handled.add(identity)
                    write(intent.with_suffix(".result"), {"id": identity, "fingerprint": item["fingerprint"],
                        "status": "completed" if not active else "running", "output": bytes(shell.output + shell.pending).decode(errors="replace"),
                        "exit_code": shell.state["exit_code"] if not active and shell.state else None,
                        "state": shell.state if not active else None, "cancelled": False})
                    continue
                write(intent, {"id": identity, "fingerprint": item["fingerprint"]})
                handled.add(identity)
                if item["kind"] == "reset":
                    shell.close()
                    for operation in active:
                        write(root / "receipts" / (operation["id"] + ".result"), {
                            "id": operation["id"], "fingerprint": operation["fingerprint"], "status": "completed",
                            "output": bytes(shell.output).decode(errors="replace"), "exit_code": -9,
                            "state": None, "cancelled": True})
                    active.clear()
                    shell = Shell(root, dict(spec, restore=None))
                    write(intent.with_suffix(".result"), {"id": identity, "fingerprint": item["fingerprint"],
                        "status": "completed", "output": "Session reset; previous effects were not undone.",
                        "exit_code": 0, "state": shell.state, "cancelled": False})
                    continue
                if item["kind"] == "command":
                    if item.get("rebind"):
                        replacement = item["rebind"]
                        if not shell.ready or not replacement["restore"].get("portable"):
                            raise RuntimeError("PTY workspace rebind requires a settled portable prompt")
                        shell.close()
                        spec.update(workspace=replacement["workspace"], restore=replacement["restore"],
                                    cwd=replacement["restore"]["cwd"])
                        write(root / "session.json", spec)
                        shell = Shell(root, spec)
                        write(root / "workspace.json", {"workspace": spec["workspace"]})
                        write(root / "ready.json", {"pid": os.getpid(), "shell_pid": shell.process.pid, "session": spec["id"]})
                    shell.output.clear(); shell.pending = b""; shell.ready = False
                    # A private sourced file keeps multiline input and commands
                    # larger than the terminal's canonical-line limit intact.
                    script = root / (identity + ".sh")
                    fd = os.open(script, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    with os.fdopen(fd, "wb") as out:
                        out.write(item["data"].encode()); out.flush(); os.fsync(out.fileno())
                    data = ("builtin source -- " + shlex.quote(str(script)) + "\n").encode()
                elif item["kind"] == "input":
                    data = item["data"].encode() + b"\n"
                    shell.ready = False
                else:
                    raise ValueError("Unknown PTY operation")
                active.append(item)
                shell.send(data)
            if (root / "shutdown").exists() and not active:
                return
            time.sleep(.02)
    finally:
        if shell:
            shell.close()
        os.close(lock)


if __name__ == "__main__":
    serve(sys.argv[1])
