"""Bounded project snapshots backed by encrypted context resources.

Capture stores immutable file references only; the coordinator explicitly commits
the returned manifest with its checkpoint/CAS. No Git objects/configuration or
archives travel between hosts. Restore exclusively creates a private directory,
never merges into an owner checkout. Unsupported files, credentials, changing
inputs, missing resource keys and stale execution claims hold the workflow.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import shutil
import stat
import subprocess
import time
import uuid

MAX_FILES = 2000
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_DEPTH = 32
_EXCLUDED = frozenset((".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
                       ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"))
_CREDENTIAL_NAMES = frozenset((".netrc", ".npmrc", ".pypirc", ".git-credentials", "credentials", "credentials.json",
                             "credentials.yaml", "credentials.yml", "secrets.json", "secrets.yaml", "secrets.yml",
                             "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "token.json", "service-account.json"))
_CREDENTIAL_DIRS = frozenset((".ssh", ".aws", ".azure", ".gcloud", ".gnupg"))
_PRIVATE_CONTENT = re.compile(
    rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    rb"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|"
    rb"(?:api[_-]?key|password|secret|access[_-]?token)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_+/=-]{12,}", re.I)
_OVERRIDE = ContextVar("durable_project_workspace", default=None)


class WorkspaceHeld(RuntimeError):
    """Fixed, payload-free reason for unsupported or unsafe workspace state."""


def _hold(reason):
    raise WorkspaceHeld(reason)


def _path(value):
    try:
        valid = isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 1024
    except UnicodeError:
        valid = False
    if not valid or "\\" in value or "\x00" in value:
        _hold("workspace_invalid_path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(part in ("", ".", "..") for part in path.parts) or len(path.parts) > MAX_DEPTH:
        _hold("workspace_invalid_path")
    return path


def _root(value, *, exists=True):
    path = Path(os.path.abspath(value))
    for component in (path, *path.parents):
        if component.is_symlink():
            _hold("workspace_symlink_unsupported")
        if component.exists() and not component.is_dir():
            _hold("workspace_directory_required")
    if exists and not path.is_dir():
        _hold("workspace_directory_required")
    return path


def _claim(manager, *, required=False):
    if not os.environ.get("A0_DURABILITY_RESOURCE_KEY"):
        _hold("workspace_resource_key_required")
    run_id = getattr(manager, "run_id", None)
    if run_id:
        manager.owner.sync("assert_owner", run_id)
    elif required:
        _hold("workspace_execution_claim_required")


def _key():
    from helpers.durable.resources import cipher, ResourceHeld
    try:
        cipher()
    except ResourceHeld:
        raise WorkspaceHeld("workspace_resource_key_required") from None


def _git(root, *args, optional=False):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_OPTIONAL_LOCKS="0")
    process = None
    try:
        process = subprocess.Popen(["git", "-c", "core.fsmonitor=false", "-c", f"core.hooksPath={os.devnull}",
                                    "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=environment)
        output, deadline = bytearray(), time.monotonic() + 30
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    _hold("workspace_git_unavailable")
                block = os.read(process.stdout.fileno(), 65536)
                if not block:
                    break
                output.extend(block)
                if len(output) > 4 * 1024 * 1024:
                    _hold("workspace_inventory_limit")
        code = process.wait(timeout=max(.01, deadline - time.monotonic()))
    except (OSError, subprocess.TimeoutExpired):
        _hold("workspace_git_unavailable")
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            process.stdout.close()
    if code:
        if optional:
            return None
        _hold("workspace_git_state_unsupported")
    return bytes(output)


def _names(raw):
    try:
        return [part.decode("utf-8") for part in raw.split(b"\0") if part]
    except UnicodeDecodeError:
        _hold("workspace_filename_encoding_unsupported")


def _inventory(root):
    top = _git(root, "rev-parse", "--show-toplevel", optional=True)
    revision, tracked, dirty = None, [], []
    if top is not None:
        try:
            if Path(top.decode("utf-8").strip()).resolve() != root:
                _hold("workspace_git_root_mismatch")
        except UnicodeDecodeError:
            _hold("workspace_filename_encoding_unsupported")
        revision = _git(root, "rev-parse", "--verify", "HEAD", optional=True)
        revision = revision.decode("ascii").strip() if revision is not None else None
        for entry in _names(_git(root, "ls-files", "--stage", "-z")):
            metadata, name = entry.split("\t", 1)
            mode, _object, stage = metadata.split()
            if mode not in ("100644", "100755") or stage != "0":
                _hold("workspace_git_links_or_merge_unsupported")
            tracked.append(name)
        dirty = _names(_git(root, "diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "HEAD", "--")) if revision else tracked
    elif os.path.lexists(root / ".git"):
        _hold("workspace_git_state_unsupported")
    # Include safe ignored working files too: an ignored runtime input must not
    # silently disappear during handoff. Only the explicit cache/VCS exclusions
    # are omitted. In particular, ignored credentials still cause a hold.
    names, excluded, directories = [], [], []
    for directory, folders, file_names in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in tuple(folders):
            relative = (current / name).relative_to(root).as_posix()
            if name in _EXCLUDED:
                excluded.append(relative)
                folders.remove(name)
            elif name in _CREDENTIAL_DIRS:
                _hold("workspace_credentials_unsupported")
            elif (current / name).is_symlink():
                _hold("workspace_symlink_unsupported")
            elif len(PurePosixPath(relative).parts) > MAX_DEPTH:
                _hold("workspace_depth_limit")
            else:
                directories.append(relative)
        for name in file_names:
            relative = (current / name).relative_to(root).as_posix()
            if name in _EXCLUDED:
                excluded.append(relative)
            else:
                names.append(relative)
        if len(names) + len(excluded) + len(directories) > MAX_FILES:
            _hold("workspace_file_count_limit")
    names = sorted(set(names + [name for name in tracked if not any(part in _EXCLUDED for part in _path(name).parts)]))
    if len(names) > MAX_FILES:
        _hold("workspace_file_count_limit")
    return {"revision": revision, "tracked": sorted(tracked), "dirty": sorted(dirty),
            "untracked": sorted(set(names) - set(tracked)), "names": names, "excluded": sorted(excluded), "directories": sorted(directories)}


def _check_content(path, data):
    if _PRIVATE_CONTENT.search(data):
        _hold("workspace_credentials_unsupported")
    lower = path.name.lower()
    environment = lower.startswith(".env") or lower.endswith(".env")
    if environment and any(line.strip() and not line.lstrip().startswith(b"#") for line in data.splitlines()):
        _hold("workspace_credentials_unsupported")
    if lower in _CREDENTIAL_NAMES or lower.endswith((".pem", ".key", ".p12", ".pfx", ".kdbx", ".keystore")):
        _hold("workspace_credentials_unsupported")
    if path.as_posix() == ".a0proj/mcp_servers.json":
        try:
            safe = json.loads(data) in ({}, {"mcpServers": {}})
        except (ValueError, UnicodeDecodeError):
            safe = False
        if not safe:
            _hold("workspace_connection_config_unsupported")


def _read_file(root, name):
    path = _path(name)
    if any(part in _CREDENTIAL_DIRS for part in path.parts):
        _hold("workspace_credentials_unsupported")
    if os.name != "posix":
        _hold("workspace_platform_unsupported")
    descriptors = []
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
        descriptors.append(descriptor)
        for component in path.parts[:-1]:
            descriptor = os.open(component, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
            descriptors.append(descriptor)
        try:
            descriptor = os.open(path.name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), dir_fd=descriptor)
        except FileNotFoundError:
            return None
        descriptors.append(descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            _hold("workspace_special_or_linked_file_unsupported")
        if before.st_size > MAX_FILE_BYTES:
            _hold("workspace_file_size_limit")
        with os.fdopen(os.dup(descriptor), "rb") as source:
            data = source.read(MAX_FILE_BYTES + 1)
        after = os.fstat(descriptor)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_nlink)
        if signature(before) != signature(after) or len(data) != after.st_size:
            _hold("workspace_changed_during_capture")
        _check_content(path, data)
        return data, bool(after.st_mode & 0o111), signature(after)
    except FileNotFoundError:
        return None
    except OSError:
        raise WorkspaceHeld("workspace_file_access_unsupported") from None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _digest_manifest(manifest):
    semantic = {key: value for key, value in manifest.items() if key not in ("digest", "files")}
    semantic["files"] = [{"path": row["path"], "executable": row["executable"],
                          "digest": row["ref"]["digest"], "size": row["ref"]["size"]} for row in manifest["files"]]
    return hashlib.sha256(json.dumps(semantic, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def capture(manager, root):
    """Gather immutable encrypted refs; caller explicitly publishes the manifest."""
    _key()  # Reject missing/malformed custody keys before reading project bytes.
    _claim(manager)
    root = _root(root)
    before = _inventory(root)
    content, deleted, total = {}, [], 0
    for name in before["names"]:
        value = _read_file(root, name)
        if value is None:
            if name in before["tracked"]:
                deleted.append(name)
            continue
        total += len(value[0])
        if total > MAX_TOTAL_BYTES:
            _hold("workspace_total_size_limit")
        content[name] = value
    if _inventory(root) != before:
        _hold("workspace_changed_during_capture")
    for name, (_data, _executable, signature) in content.items():
        current = _read_file(root, name)
        if current is None or current[2] != signature:
            _hold("workspace_changed_during_capture")
    active = _OVERRIDE.get()
    previous = active[2] if active and active[1] == root else None
    stored = manager.get_manifest("workspace") if previous is None else None
    previous = previous or (stored["value"] if stored else None)
    if previous:
        _validate(previous)
        deleted.extend(row["path"] for row in previous["files"] if row["path"] not in content)
        if active and active[1] == root and before["revision"] is None:
            original = {row["path"]: row for row in previous["files"]}
            modified = {name for name, (data, executable, _signature) in content.items() if name in original and (
                original[name]["ref"]["digest"] != hashlib.sha256(data).hexdigest() or original[name]["executable"] != executable)}
            before["revision"] = previous["revision"]
            before["untracked"] = sorted((set(previous["untracked"]) & content.keys()) | (content.keys() - original.keys()))
            before["dirty"] = sorted(set(previous["dirty"]) | (modified - set(previous["untracked"])) | set(deleted))
            before["excluded"] = sorted(set(before["excluded"]) | set(previous["excluded"]))
            deleted.extend(previous["deleted"])
    project_name = active[0] if active and active[1] == root else root.name
    manifest = {"version": 1, "project_name": project_name, "revision": before["revision"], "files": [], "directories": before["directories"],
                "deleted": sorted(set(deleted)), "dirty": before["dirty"], "untracked": before["untracked"], "excluded": before["excluded"]}
    for name, (data, executable, _signature) in sorted(content.items()):
        _claim(manager)
        reference = manager.put_bytes("workspace_file", "file-" + hashlib.sha256(name.encode()).hexdigest(), data, sensitive=True)
        manifest["files"].append({"path": name, "executable": executable, "ref": reference})
    _claim(manager)
    manifest["digest"] = _digest_manifest(manifest)
    return manifest


def _validate(manifest):
    fields = {"version", "project_name", "revision", "files", "directories", "deleted", "dirty", "untracked", "excluded", "digest"}
    if type(manifest) is not dict or set(manifest) != fields or type(manifest["version"]) is not int or manifest["version"] != 1:
        _hold("workspace_manifest_unsupported")
    name = manifest["project_name"]
    if not isinstance(name, str) or not name or len(_path(name).parts) != 1:
        _hold("workspace_invalid_project_name")
    if manifest["revision"] is not None and (not isinstance(manifest["revision"], str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", manifest["revision"]) is None):
        _hold("workspace_invalid_revision")
    if type(manifest["files"]) is not list or len(manifest["files"]) > MAX_FILES:
        _hold("workspace_file_count_limit")
    paths, total = set(), 0
    for row in manifest["files"]:
        if type(row) is not dict or set(row) != {"path", "executable", "ref"} or type(row["executable"]) is not bool:
            _hold("workspace_manifest_unsupported")
        path = _path(row["path"])
        if row["path"] in paths or any(part in _EXCLUDED or part in _CREDENTIAL_DIRS for part in path.parts):
            _hold("workspace_invalid_path")
        paths.add(row["path"])
        reference = row["ref"]
        if type(reference) is not dict or reference.get("kind") != "workspace_file" or type(reference.get("size")) is not int or not 0 <= reference["size"] <= MAX_FILE_BYTES or re.fullmatch(r"[0-9a-f]{64}", str(reference.get("digest"))) is None:
            _hold("workspace_invalid_resource_ref")
        total += reference["size"]
    if any(parent.as_posix() in paths for path in paths for parent in PurePosixPath(path).parents if parent.as_posix() != "."):
        _hold("workspace_invalid_path")
    if total > MAX_TOTAL_BYTES:
        _hold("workspace_total_size_limit")
    if type(manifest["directories"]) is not list or len(manifest["directories"]) + len(paths) > MAX_FILES:
        _hold("workspace_file_count_limit")
    for directory in manifest["directories"]:
        value = _path(directory)
        if directory in paths or any(parent.as_posix() in paths for parent in value.parents) or any(part in _EXCLUDED or part in _CREDENTIAL_DIRS for part in value.parts):
            _hold("workspace_invalid_path")
    for field in ("deleted", "dirty", "untracked", "excluded"):
        if type(manifest[field]) is not list or len(manifest[field]) > MAX_FILES:
            _hold("workspace_manifest_unsupported")
        for path in manifest[field]:
            _path(path)
    if paths.intersection(manifest["deleted"]) or _digest_manifest(manifest) != manifest["digest"]:
        _hold("workspace_manifest_integrity_failed")


def restore(manager, manifest, destination):
    """Exclusively create an isolated directory; existing paths are never merged."""
    _key()
    _claim(manager, required=True)
    _validate(manifest)
    destination = _root(destination, exists=False)
    if os.path.lexists(destination):
        _hold("workspace_destination_exists")
    values = []
    for row in manifest["files"]:
        data = manager.get_bytes(row["ref"])
        if len(data) != row["ref"]["size"] or hashlib.sha256(data).hexdigest() != row["ref"]["digest"]:
            _hold("workspace_resource_integrity_failed")
        _check_content(_path(row["path"]), data)
        values.append((row, data))
    _claim(manager, required=True)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _root(destination.parent)
    try:
        destination.mkdir(mode=0o700)
    except FileExistsError:
        _hold("workspace_destination_exists")
    created = destination.stat()
    try:
        for directory in manifest["directories"]:
            (destination / directory).mkdir(mode=0o700, parents=True, exist_ok=True)
        for row, data in values:
            path = destination / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o700 if row["executable"] else 0o600)
            os.fchmod(descriptor, 0o700 if row["executable"] else 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        _claim(manager, required=True)
        for directory, _folders, _files in os.walk(destination, topdown=False):
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        _claim(manager, required=True)
        return destination
    except BaseException as exc:
        if not destination.is_symlink() and destination.exists() and destination.stat().st_ino == created.st_ino:
            shutil.rmtree(destination)
        if isinstance(exc, OSError):
            raise WorkspaceHeld("workspace_restore_storage_failed") from None
        raise


@contextmanager
def project_override(project_name, path, *, manifest=None):
    """Redirect one execution context's matching project lookup, never globals."""
    if len(_path(project_name).parts) != 1:
        _hold("workspace_invalid_project_name")
    token = _OVERRIDE.set((project_name, _root(path), manifest))
    try:
        yield Path(path)
    finally:
        _OVERRIDE.reset(token)


def project_folder(project_name):
    """Return a scoped override or None for the ordinary projects helper."""
    current = _OVERRIDE.get()
    return str(current[1]) if current and current[0] == project_name else None


@contextmanager
def managed_project(manager, manifest):
    """Restore a fresh per-context worker directory for this execution scope."""
    _claim(manager, required=True)
    from helpers import files
    context_key = hashlib.sha256(manager.context_id.encode()).hexdigest()
    parent = Path(files.get_abs_path("tmp", "durable-workspaces", context_key))
    destination = parent / (manifest["digest"][:16] + "-" + uuid.uuid4().hex)
    path = restore(manager, manifest, destination)
    with project_override(manifest["project_name"], path, manifest=manifest):
        yield path
