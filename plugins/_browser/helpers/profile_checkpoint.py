"""Coherent private Chromium profiles stored as authenticated encrypted chunks."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import stat
import tarfile
import tempfile

CHUNK = 4 * 1024 * 1024
MAX_PROFILE = 128 * 1024 * 1024
# Chromium's native session records may request POST resubmission on startup.
# Logical HTTP(S) tabs/sessionStorage are restored explicitly by the runtime.
_SKIP = {"SingletonLock", "SingletonSocket", "SingletonCookie", "DevToolsActivePort"}


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(directory):
    directory = Path(directory)
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if (relative.parts[0] in _SKIP | {"transfers"} or any(relative.parts[index:index + 2] == ("Default", "Sessions") for index in range(len(relative.parts)))
                or any(part.startswith("Singleton") for part in relative.parts)):
            continue
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Browser profile contains a link or special file")
        yield path, relative.as_posix(), info.st_size


def extension_identity(paths, previous=None):
    saved = {item["selection"]: item for item in previous or []}
    result = []
    for configured in paths:
        selection = hashlib.sha256(str(configured).encode()).hexdigest()
        directory = Path(configured).expanduser()
        if not directory.is_dir():
            if selection not in saved:
                raise ValueError("Configured browser extension is unavailable")
            result.append(saved[selection])
            continue
        manifest = json.loads((directory / "manifest.json").read_text())
        digest = hashlib.sha256()
        for file, name, size in _files(directory):
            digest.update(json.dumps([name, size, _hash_file(file)], separators=(",", ":")).encode())
        result.append({"selection": selection, "digest": digest.hexdigest(), "key": manifest.get("key")})
    return result


def identity(config, previous=None):
    from plugins._browser.helpers.playwright import get_playwright_binary
    binary = get_playwright_binary()
    if binary is None:
        raise ValueError("The configured Chromium binary is unavailable")
    return {"schema": 1, "platform": platform.system(), "machine": platform.machine(),
            "patchright": importlib.metadata.version("patchright"), "binary": _hash_file(binary),
            "extensions": extension_identity(config.get("extension_paths", []),
                                              (previous or {}).get("extensions"))}


def private_root():
    from helpers import files
    from helpers.durable.resources import private_directory
    base = private_directory(files.get_abs_path("tmp/durability/browser"))
    return Path(tempfile.mkdtemp(prefix="profile-", dir=base))


def package_extensions(root, config):
    """Copy exact unpacked code; a stable manifest key preserves extension IDs."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    result = []
    for position, configured in enumerate(config.get("extension_paths", [])):
        destination = Path(root) / "extensions" / str(position)
        if not destination.exists():
            list(_files(Path(configured).expanduser()))  # reject links before copying code
            shutil.copytree(Path(configured).expanduser(), destination, symlinks=False)
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            if not manifest.get("key"):
                key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
                import base64
                manifest["key"] = base64.b64encode(key.public_bytes(
                    serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
                manifest_path.write_text(json.dumps(manifest))
        result.append(str(destination))
    return result


def capture(manager, root):
    """The owning Chromium must be closed before calling this function."""
    root = Path(root)
    descriptor, total = [], 0
    fd, archive = tempfile.mkstemp(prefix=".checkpoint-", dir=root.parent)
    os.close(fd)
    try:
        with tarfile.open(archive, "w:gz", dereference=False) as target:
            for source, name, size in _files(root):
                total += size
                if total > MAX_PROFILE:
                    raise ValueError("Browser profile exceeds the 128 MiB checkpoint bound")
                info = target.gettarinfo(str(source), arcname=name)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o600
                descriptor_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(descriptor_fd, "rb") as data:
                    before = os.fstat(data.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
                        raise ValueError("Browser profile changed during checkpoint")
                    target.addfile(info, data)
                    after = os.fstat(data.fileno())
                    if any(getattr(before, key) != getattr(after, key) for key in ("st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
                        raise ValueError("Browser profile changed during checkpoint")
        if Path(archive).stat().st_size > MAX_PROFILE:
            raise ValueError("Compressed browser profile exceeds checkpoint bound")
        digest = _hash_file(archive)
        with open(archive, "rb") as source:
            index = 0
            while block := source.read(CHUNK):
                descriptor.append(manager.put_bytes("browser_profile", f"chunk-{index}", block, sensitive=True))
                index += 1
        return {"schema": 1, "chunks": descriptor, "digest": digest, "size": Path(archive).stat().st_size,
                "uncompressed_size": total}
    finally:
        Path(archive).unlink(missing_ok=True)


def restore(manager, descriptor, root):
    from helpers.durable.resources import private_directory
    if (descriptor.get("schema") != 1 or type(descriptor.get("chunks")) is not list
            or not 0 <= descriptor.get("size", -1) <= MAX_PROFILE
            or len(descriptor["chunks"]) > MAX_PROFILE // CHUNK + 1):
        raise ValueError("Invalid browser profile checkpoint")
    root = private_directory(root)
    fd, archive = tempfile.mkstemp(prefix=".restore-", dir=root.parent)
    os.close(fd)
    try:
        with open(archive, "wb") as target:
            for ref in descriptor["chunks"]:
                target.write(manager.get_bytes(ref))
        if Path(archive).stat().st_size != descriptor["size"] or _hash_file(archive) != descriptor["digest"]:
            raise ValueError("Browser profile checkpoint digest changed")
        total, seen = 0, set()
        with tarfile.open(archive, "r:gz") as source:
            for member in source:
                path = PurePosixPath(member.name)
                if (not member.isfile() or path.is_absolute() or ".." in path.parts
                        or not path.parts or path.parts[0] not in {"profile", "downloads", "extensions"}
                        or member.name in seen):
                    raise ValueError("Unsafe browser profile member")
                seen.add(member.name)
                if len(seen) > 20000:
                    raise ValueError("Browser profile has too many files")
                total += member.size
                if total > MAX_PROFILE:
                    raise ValueError("Browser profile expands beyond its checkpoint bound")
                destination = root.joinpath(*path.parts)
                private_directory(destination.parent)
                stream = source.extractfile(member)
                if stream is None:
                    raise ValueError("Missing browser profile member")
                with destination.open("xb") as out:
                    shutil.copyfileobj(stream, out)
                destination.chmod(0o600)
    finally:
        Path(archive).unlink(missing_ok=True)
    relocate_downloads(root)


def relocate_downloads(root, completed=None):
    """Repair Chromium history paths only after closing the profile database."""
    import sqlite3
    root = Path(root)
    history = root / "profile" / "Default" / "History"
    if not history.is_file():
        return
    mapping = {str(item["source"]): str(root / "downloads" / item["name"]) for item in completed or []}
    with sqlite3.connect(history) as database:
        if not database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='downloads'").fetchone():
            return
        for identity, target, current in database.execute("SELECT id,target_path,current_path FROM downloads").fetchall():
            replacement = mapping.get(target) or mapping.get(current)
            if replacement is None:
                candidate = root / "downloads" / Path(target or current).name
                replacement = str(candidate) if candidate.is_file() else None
            if replacement and Path(replacement).is_file():
                database.execute("UPDATE downloads SET target_path=?,current_path=? WHERE id=?", (replacement,replacement,identity))
