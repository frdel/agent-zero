"""Versioned resource adapters, encrypted shared bytes and private materializations.

Resource IDs identify immutable bytes inside one context. Adapters own the
meaning of a manifest; a filename or plugin's replay label grants no authority.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Protocol

from helpers.durable.resource_store import MAX_RESOURCE
from helpers.durable.store import IntegrityError, OwnershipError, _identity, _json

SCHEME = "a0-resource://"
_ID = re.compile(r"[a-f0-9]{64}\Z")


class ResourceHeld(RuntimeError):
    """A resource cannot be captured/restored under its declared contract."""


class ResourceAdapter(Protocol):
    kind: str
    version: int

    def capture(self, manager, source) -> dict: ...
    def validate(self, manifest: dict) -> None: ...
    def restore(self, manager, manifest: dict, destination: Path): ...


@dataclass(frozen=True)
class AdapterRegistration:
    adapter: ResourceAdapter
    identity: dict


_ADAPTERS: dict[str, AdapterRegistration] = {}


def register_adapter(adapter):
    """Explicit registration pins inspectable adapter source, kind and version."""
    from helpers.durable.codec import identity
    _identity(adapter.kind, "adapter kind")
    if type(adapter.version) is not int or adapter.version < 1:
        raise ValueError("Invalid resource adapter version")
    registration = AdapterRegistration(adapter, identity(adapter))
    previous = _ADAPTERS.get(adapter.kind)
    if previous:
        if (previous.identity != registration.identity or previous.adapter.version != adapter.version
                or vars(previous.adapter) != vars(adapter)):
            raise ValueError("Resource adapter already registered")
        return previous
    _ADAPTERS[adapter.kind] = registration
    return registration


def adapter(kind, version, implementation=None):
    _builtin(kind)
    registered = _ADAPTERS.get(kind)
    if (registered is None or registered.adapter.version != version
            or implementation is not None and registered.identity != implementation):
        raise ResourceHeld("resource_adapter_missing_or_changed:" + str(kind))
    return registered.adapter


def cipher():
    from cryptography.fernet import Fernet
    value = os.environ.get("A0_DURABILITY_RESOURCE_KEY", "")
    try:
        if not value:
            raise ValueError()
        return Fernet(value.encode("ascii"))
    except (ValueError, UnicodeError):
        raise ResourceHeld("Shared resources require a valid A0_DURABILITY_RESOURCE_KEY on every worker") from None


def private_directory(path):
    """Create private regular directories; never follow a symlink ancestor."""
    path = Path(path).absolute()
    for parent in (*reversed(path.parents), path):
        try:
            info = parent.lstat()
        except FileNotFoundError:
            try:
                parent.mkdir(mode=0o700)
            except FileExistsError:
                pass
            info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ResourceHeld("Resource destination contains a non-directory or symlink")
    if hasattr(os, "getuid") and path.stat().st_uid != os.getuid():
        raise ResourceHeld("Resource directory has a different owner")
    path.chmod(0o700)
    return path


class ResourceManager:
    def __init__(self, owner, context_id, run_id=None, *, job_id=None, job_token=None):
        _identity(context_id, "resource context")
        self.owner, self.context_id, self.run_id = owner, context_id, run_id
        self.job_id, self.job_token = job_id, job_token

    def put_bytes(self, kind, name, data, sensitive=False):
        _identity(kind, "resource kind")
        if not isinstance(data, bytes) or len(data) > MAX_RESOURCE:
            raise ResourceHeld("Resource exceeds the 8 MiB per-object bound")
        if not isinstance(name, str) or len(name) > 240 or any(c in name for c in "\x00\r\n"):
            raise ValueError("Invalid resource name")
        digest = hashlib.sha256(data).hexdigest()
        resource_id = hashlib.sha256(_json([self.context_id, kind, name, digest]).encode()).hexdigest()
        ref = {"id": resource_id, "kind": kind, "name": name, "digest": digest, "size": len(data)}
        # Authenticated envelope binds ciphertext to context and complete metadata.
        envelope = _json({"context": self.context_id, "ref": ref, "data": base64.b64encode(data).decode()})
        encrypted = cipher().encrypt(envelope.encode())
        return self.owner.sync("put_resource", self.context_id, ref, encrypted, run_id=self.run_id,
                               job_id=self.job_id, job_token=self.job_token)

    def get_bytes(self, ref):
        if type(ref) is not dict or not _ID.fullmatch(str(ref.get("id", ""))):
            raise ValueError("Invalid resource reference")
        stored = self.owner.sync("get_resource", self.context_id, ref["id"])
        try:
            decoded = json.loads(cipher().decrypt(stored["body"]))
            data = base64.b64decode(decoded["data"], validate=True)
            if (stored["metadata"] != ref or decoded["context"] != self.context_id or decoded["ref"] != ref
                    or len(data) != ref["size"] or hashlib.sha256(data).hexdigest() != ref["digest"]):
                raise ValueError()
        except ResourceHeld:
            raise
        except Exception:
            raise IntegrityError("Resource authentication or integrity check failed") from None
        return data

    def reference(self, uri):
        if not isinstance(uri, str) or not uri.startswith(SCHEME) or not _ID.fullmatch(uri[len(SCHEME):]):
            raise ResourceHeld("Attachment requires a registered shared resource reference")
        return self.owner.sync("get_resource", self.context_id, uri[len(SCHEME):])["metadata"]

    def get_manifest(self, kind):
        return self.owner.sync("get_resource_manifest", self.context_id, kind)

    def publish_manifest(self, kind, manifest, expected_version):
        return self.owner.sync("publish_resource_manifest", self.context_id, kind, manifest, expected_version, self.run_id)

    def capture(self, kind, source):
        _builtin(kind)
        registered = _ADAPTERS.get(kind)
        if registered is None:
            raise ResourceHeld("resource_adapter_missing:" + str(kind))
        value = registered.adapter.capture(self, source)
        registered.adapter.validate(value)
        return {"kind": kind, "version": registered.adapter.version,
                "implementation": registered.identity, "value": value}

    def restore(self, manifest, destination):
        implementation = adapter(manifest["kind"], manifest["version"], manifest["implementation"])
        implementation.validate(manifest["value"])
        if not self.run_id:
            raise OwnershipError("Resource restoration requires a claimed run")
        self.owner.sync("assert_owner", self.run_id)
        return implementation.restore(self, manifest["value"], Path(destination))

    def materialize(self, ref, destination=None):
        from helpers import files
        if self.run_id:
            self.owner.sync("assert_owner", self.run_id)
        if destination is None:
            scope = hashlib.sha256(self.context_id.encode()).hexdigest()
            destination = Path(files.get_abs_path("usr/durability/resources")) / scope / ref["id"] / safe_name(ref["name"])
        destination = Path(destination)
        private_directory(destination.parent)
        data = self.get_bytes(ref)
        fd, staging = tempfile.mkstemp(prefix=".resource-", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            try:
                os.link(staging, destination, follow_symlinks=False)
            except FileExistsError:
                if read_regular(destination) != data:
                    raise IntegrityError("Materialized resource has different bytes")
        finally:
            os.unlink(staging)
        if self.run_id:
            self.owner.sync("assert_owner", self.run_id)
        return destination


def read_regular(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_RESOURCE:
            raise ResourceHeld("Resources require bounded regular files without links")
        result = stream.read(MAX_RESOURCE + 1)
        after = os.fstat(stream.fileno())
        if len(result) > MAX_RESOURCE or any(getattr(after, field) != getattr(info, field)
                                           for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
            raise ResourceHeld("Resource changed during capture")
        return result


def safe_name(name):
    from helpers.security import safe_filename
    return safe_filename(str(name).replace("\\", "/").split("/")[-1]) or "resource"


def capture_attachments(manager, attachments):
    manifest = manager.capture("attachments", attachments)
    return [SCHEME + ref["id"] for ref in manifest["value"]["files"]]


def _capture_attachments(manager, attachments):
    result = []
    for attachment in attachments:
        if isinstance(attachment, str) and attachment.startswith(SCHEME):
            reference = manager.reference(attachment)
            manager.get_bytes(reference)
            manager.owner.sync("stage_resource", manager.context_id, reference["id"])
            result.append(attachment)
        else:
            ref = manager.put_bytes("attachment", safe_name(attachment), read_regular(attachment))
            result.append(SCHEME + ref["id"])
    return result


class AttachmentAdapter:
    kind, version = "attachments", 1

    def capture(self, manager, source):
        return {"files": [manager.reference(uri) for uri in _capture_attachments(manager, source)]}

    def validate(self, manifest):
        if type(manifest) is not dict or set(manifest) != {"files"} or type(manifest["files"]) is not list:
            raise ResourceHeld("attachment_manifest_unsupported")
        if len(manifest["files"]) > 64 or any(type(ref) is not dict or ref.get("kind") != "attachment" for ref in manifest["files"]):
            raise ResourceHeld("attachment_manifest_unsupported")

    def restore(self, manager, manifest, destination):
        return [manager.materialize(ref, destination / ref["id"] / safe_name(ref["name"])) for ref in manifest["files"]]


def _builtin(kind):
    if kind == "attachments" and kind not in _ADAPTERS:
        register_adapter(AttachmentAdapter())


def materialize_attachments(manager, payload, context=None):
    result = dict(payload)
    references = [manager.reference(uri) for uri in payload.get("attachments", [])]
    result["attachments"] = [str(manager.materialize(ref)) for ref in references]
    if context is not None:
        state = getattr(context, "_durable_resources", {"version": 1})
        retained = {ref["id"]: ref for ref in state.get("attachments", [])}
        retained.update({ref["id"]: ref for ref in references})
        state["attachments"] = list(retained.values())
        context._durable_resources = state
        paths = getattr(context, "_durable_resource_paths", {})
        paths.update({path: SCHEME + ref["id"] for path, ref in zip(result["attachments"], references)})
        context._durable_resource_paths = paths
    return result


def portable_attachments(attachments):
    return isinstance(attachments, list) and all(isinstance(uri, str) and uri.startswith(SCHEME)
                                                and _ID.fullmatch(uri[len(SCHEME):]) for uri in attachments)


def capture_context(owner, context, message=None):
    """Capture before admission; only immutable objects may be written here."""
    manager = ResourceManager(owner, context.id)
    state = getattr(context, "_durable_resources", {"version": 1})
    context._durable_resources = state
    if message is not None and message.attachments:
        message.attachments = capture_attachments(manager, list(message.attachments))
        state["attachments"] = [manager.reference(uri) for uri in message.attachments]
    project = context.get_data("project")
    if project and "workspace" not in state:
        from helpers import projects
        from helpers.durable import workspaces
        root = projects.get_project_folder(project)
        state["workspace"] = workspaces.capture(manager, root)
        context._durable_workspace_path = Path(root)
        context._durable_workspace_origin = state["workspace"]
    return state


def snapshot_context(owner, context, run_id):
    """Capture filesystem changes before their checkpoint becomes visible."""
    state = getattr(context, "_durable_resources", None)
    if state and state.get("workspace"):
        from helpers.durable import workspaces
        from helpers import projects
        manager = ResourceManager(owner, context.id, run_id)
        project = context.get_data("project")
        state["workspace"] = workspaces.capture(manager, projects.get_project_folder(project))
    return state


def adopt_workspace_result(manager, context, manifest):
    """Import a broker's verified files before publishing a successor checkpoint."""
    from helpers.durable import workspaces
    from helpers import files
    import uuid
    manager.owner.sync("assert_owner", manager.run_id)
    project = context.get_data("project")
    if not project or manifest.get("project_name") != project:
        raise ResourceHeld("workspace_result_project_changed")
    previous = getattr(context, "_durable_resources", {}).get("workspace")
    path = getattr(context, "_durable_workspace_path", None)
    if path is not None and Path(path).exists():
        current = workspaces.capture(manager, path)
        if current["digest"] == manifest["digest"]:
            context._durable_workspace_origin = manifest
            context._durable_resources["workspace"] = manifest
            return Path(path)
        if previous is None or current["digest"] != previous["digest"]:
            raise ResourceHeld("workspace_result_conflicts_with_local_edits")
    root = Path(files.get_abs_path("tmp", "durable-workspaces", hashlib.sha256(context.id.encode()).hexdigest()))
    destination = root / (manifest["digest"][:16] + "-" + uuid.uuid4().hex)
    restored = workspaces.restore(manager, manifest, destination)
    workspaces.rebind_project(project, restored, manifest=manifest)
    context._durable_workspace_path = restored
    context._durable_workspace_origin = manifest
    context._durable_resources["workspace"] = manifest
    context._durable_managed_workspace = True
    return restored


def checkpoint_state(context):
    return getattr(context, "_durable_resources", {"version": 1})


def restore_state(context, state):
    context._durable_resources = state or {"version": 1}


def _replace(value, replacements):
    if isinstance(value, str):
        for source, target in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
            workspace = source.startswith("a0-workspace://") or target.startswith("a0-workspace://")
            suffix = r"(?=$|[\s\"'`;\]\[(){}=<>|&,]" + (r"|[/:]" if workspace else "") + ")"
            value = re.sub(r"(?<![\w./:%+~-])" + re.escape(source) + suffix, lambda _: target, value)
        return value
    if isinstance(value, dict):
        return {key: _replace(child, replacements) for key, child in value.items()}
    if isinstance(value, list):
        return [_replace(child, replacements) for child in value]
    return value


def canonical_value(context, value):
    """Journal portable identities instead of whichever worker's cache path."""
    replacements = dict(getattr(context, "_durable_resource_paths", {}))
    path = getattr(context, "_durable_workspace_path", None)
    workspace = getattr(context, "_durable_workspace_origin", None)
    if path and workspace:
        replacements[str(path)] = "a0-workspace://" + workspace["project_name"]
    return _replace(value, replacements)


def local_value(context, value):
    replacements = {uri: path for path, uri in getattr(context, "_durable_resource_paths", {}).items()}
    path = getattr(context, "_durable_workspace_path", None)
    workspace = getattr(context, "_durable_workspace_origin", None)
    if path and workspace:
        replacements["a0-workspace://" + workspace["project_name"]] = str(path)
    return _replace(value, replacements)


def restore_attachment_paths(manager, context):
    references = getattr(context, "_durable_resources", {}).get("attachments", [])
    context._durable_resource_paths = {str(manager.materialize(ref)): SCHEME + ref["id"] for ref in references}
