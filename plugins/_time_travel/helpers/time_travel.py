from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import os
import posixpath
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from helpers import files
from helpers.localization import Localization
from helpers.print_style import PrintStyle


PLUGIN_NAME = "_time_travel"
USR_DISPLAY_ROOT = "/a0/usr"
SHADOW_DISPLAY_ROOT = "/a0/usr/.time_travel/workspaces"
CURRENT_REF = "refs/heads/current"
PRESERVED_REF_PREFIX = "refs/a0-time-travel/preserved"
METADATA_PREFIX = "A0-Time-Travel-Metadata:"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
MAX_RENDERED_PATCH_BYTES = 1_000_000
GIT_TIMEOUT_SECONDS = 20
AUTO_SNAPSHOT_DEBOUNCE_SECONDS = 10.0
WATCHDOG_ID = "time_travel_usr"
WATCHDOG_DEBOUNCE_SECONDS = 1.0
SHADOW_REPO_BACKUP_PREFIX = "repo.git.invalid"

_AUTO_SNAPSHOT_LOCK = threading.RLock()
_AUTO_SNAPSHOT_TIMERS: dict[str, threading.Timer] = {}
_AUTO_SNAPSHOT_PAYLOADS: dict[str, dict[str, Any]] = {}

STATUS_LABELS = {
    "A": "added",
    "C": "copied",
    "D": "deleted",
    "M": "modified",
    "R": "renamed",
    "T": "type_changed",
    "U": "unmerged",
    "X": "unknown",
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".time_travel",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    "coverage",
    "htmlcov",
    ".parcel-cache",
}

EXCLUDED_DIR_PATTERNS = {
    "*.egg-info",
}

EXCLUDED_FILE_PATTERNS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".env",
    ".env.*",
    "*.class",
}

USR_ROOT_EXCLUDED_DIR_NAMES = {
    "plugins",
}

SAFE_A0PROJ_FILES = {
    ".a0proj/project.json",
    ".a0proj/agents.json",
}

SAFE_A0PROJ_DIRS = {
    ".a0proj/instructions/",
    ".a0proj/knowledge/",
    ".a0proj/skills/",
}

SAFE_PLUGIN_ASSET_NAMES = {
    "config.json",
    "presets.yaml",
    ".toggle-0",
    ".toggle-1",
}


class TimeTravelError(RuntimeError):
    """Base error for user-visible Time Travel failures."""


class WorkspaceRejectedError(TimeTravelError):
    """Raised when a workspace is outside the /a0/usr kernel boundary."""


class TimeTravelConflictError(TimeTravelError):
    """Raised when an operation cannot safely mutate the workspace."""


class GitCommandError(TimeTravelError):
    def __init__(self, message: str, *, stdout: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class WorkspaceInfo:
    id: str
    display_path: str
    real_path: Path
    shadow_path: Path
    repo_git_path: Path
    context_id: str = ""
    project_name: str = ""

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.display_path,
            "display_path": self.display_path,
            "real_path": str(self.real_path),
            "shadow_path": normalize_display_path(str(self.shadow_path)),
            "repo_git_path": normalize_display_path(str(self.repo_git_path)),
            "context_id": self.context_id,
            "project_name": self.project_name,
            "available": True,
            "locked": False,
        }


@dataclass(frozen=True)
class SnapshotResult:
    created: bool
    hash: str
    short_hash: str
    tree_hash: str
    message: str
    files: list[dict[str, Any]]
    metadata: dict[str, Any]


def now_iso() -> str:
    return Localization.get().now_iso()


def normalize_display_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    if raw.startswith("/a0"):
        normalized = posixpath.normpath(raw.replace("\\", "/"))
        return "/" if normalized == "." else normalized

    resolved = Path(raw).expanduser().resolve(strict=False)
    normalized = files.normalize_a0_path(str(resolved))
    if normalized.startswith("/a0"):
        return posixpath.normpath(normalized.replace("\\", "/"))
    return str(resolved)


def is_inside_usr_display(display_path: str) -> bool:
    normalized = normalize_display_path(display_path)
    return normalized == USR_DISPLAY_ROOT or normalized.startswith(USR_DISPLAY_ROOT + "/")


def workspace_id_for(display_path: str) -> str:
    normalized = canonical_workspace_display_path(display_path).rstrip("/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def real_path_for_display(display_path: str) -> Path:
    normalized = normalize_display_path(display_path)
    if normalized == "/a0":
        return Path(files.get_base_dir()).resolve(strict=False)
    if normalized.startswith("/a0/"):
        return Path(files.get_base_dir(), normalized.removeprefix("/a0/")).resolve(strict=False)
    return Path(normalized).expanduser().resolve(strict=False)


def canonical_workspace_display_path(display_path: str) -> str:
    normalized = normalize_display_path(display_path)
    real_path = real_path_for_display(normalized)
    canonical = normalize_display_path(str(real_path))
    return (canonical if canonical.startswith("/a0") else normalized).rstrip("/") or canonical


def configured_workdir_display_path() -> str:
    from helpers import settings

    configured = str(settings.get_settings().get("workdir_path") or "")
    fallback = files.normalize_a0_path(files.get_abs_path("usr/workdir"))
    return canonical_workspace_display_path(configured or fallback)


def _workspace_option(
    *,
    kind: str,
    display_path: str,
    label: str,
    name: str = "",
    title: str = "",
    project_name: str = "",
    color: str = "",
) -> dict[str, Any]:
    normalized = canonical_workspace_display_path(display_path)
    available = is_inside_usr_display(normalized)
    error = (
        "" if available else "Time Travel is only available for workspaces inside /a0/usr."
    )
    return {
        "id": workspace_id_for(normalized),
        "kind": kind,
        "name": name,
        "title": title or label,
        "label": label,
        "display_path": normalized.rstrip("/") or normalized,
        "path": normalized.rstrip("/") or normalized,
        "project_name": project_name,
        "color": color,
        "available": available,
        "locked": not available,
        "error": error,
    }


def list_selectable_workspaces(
    context_id: str = "",
    *,
    context_loader=None,
) -> dict[str, Any]:
    from helpers import projects

    context_id = str(context_id or "").strip()
    workspaces: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add_workspace(option: dict[str, Any]) -> None:
        option_id = str(option.get("id") or "")
        if not option_id or option_id in seen_ids:
            return
        seen_ids.add(option_id)
        workspaces.append(option)

    add_workspace(
        _workspace_option(
            kind="workdir",
            display_path=configured_workdir_display_path(),
            label="User working directory",
            name="workdir",
            title="User working directory",
        )
    )

    for project in projects.get_active_projects_list() or []:
        project_name = str(project.get("name") or "").strip()
        if not project_name:
            continue
        title = str(project.get("title") or project_name)
        add_workspace(
            _workspace_option(
                kind="project",
                display_path=files.normalize_a0_path(
                    projects.get_project_folder(project_name)
                ),
                label=title,
                name=project_name,
                title=title,
                project_name=project_name,
                color=str(project.get("color") or ""),
            )
        )

    default_workspace_id = ""
    try:
        default_workspace_id = _resolve_context_workspace(
            context_id,
            context_loader=context_loader,
        ).id
    except TimeTravelError:
        default_workspace_id = ""

    if default_workspace_id not in seen_ids:
        default_workspace_id = ""
    if not default_workspace_id and workspaces:
        default_workspace_id = str(workspaces[0].get("id") or "")

    return {
        "context_id": context_id,
        "workspaces": workspaces,
        "default_workspace_id": default_workspace_id,
    }


def _selectable_workspace_by_id(
    workspace_id: str,
    context_id: str = "",
    *,
    context_loader=None,
) -> dict[str, Any] | None:
    wanted = str(workspace_id or "").strip()
    if not wanted:
        return None
    for workspace in list_selectable_workspaces(
        context_id,
        context_loader=context_loader,
    )["workspaces"]:
        if str(workspace.get("id") or "") == wanted:
            return workspace
    return None


def _resolve_context_workspace(context_id: str = "", *, context_loader=None) -> WorkspaceInfo:
    from helpers import projects, settings

    context_id = str(context_id or "").strip()
    project_name = ""
    display_path = ""

    if context_id:
        context = context_loader(context_id) if context_loader else None
        if context is not None:
            project_name = projects.get_context_project_name(context) or ""
            if project_name:
                display_path = files.normalize_a0_path(projects.get_project_folder(project_name))

    if not display_path:
        configured = str(settings.get_settings().get("workdir_path") or "")
        display_path = configured or files.normalize_a0_path(files.get_abs_path("usr/workdir"))

    normalized = canonical_workspace_display_path(display_path)
    if not is_inside_usr_display(normalized):
        raise WorkspaceRejectedError("Time Travel is only available for workspaces inside /a0/usr.")

    workspace_id = workspace_id_for(normalized)
    shadow_display = f"{SHADOW_DISPLAY_ROOT}/{workspace_id}"
    shadow_path = real_path_for_display(shadow_display)
    return WorkspaceInfo(
        id=workspace_id,
        display_path=normalized.rstrip("/") or normalized,
        real_path=real_path_for_display(normalized),
        shadow_path=shadow_path,
        repo_git_path=shadow_path / "repo.git",
        context_id=context_id,
        project_name=project_name,
    )


def resolve_workspace(
    context_id: str = "",
    *,
    workspace_id: str = "",
    context_loader=None,
) -> WorkspaceInfo:
    workspace_id = str(workspace_id or "").strip()
    if not workspace_id:
        return _resolve_context_workspace(context_id, context_loader=context_loader)

    selected = _selectable_workspace_by_id(
        workspace_id,
        context_id,
        context_loader=context_loader,
    )
    if not selected:
        raise WorkspaceRejectedError("Selected Time Travel workspace is not available.")
    if selected.get("locked") or selected.get("available") is False:
        raise WorkspaceRejectedError(
            str(selected.get("error") or "Selected Time Travel workspace is not available.")
        )

    return _workspace_from_display(
        str(selected.get("display_path") or selected.get("path") or ""),
        project_name=str(selected.get("project_name") or ""),
        context_id=str(context_id or "").strip(),
    )


def resolve_workspace_for_path_hint(path_hint: str) -> WorkspaceInfo | None:
    normalized = canonical_workspace_display_path(path_hint)
    if not is_inside_usr_display(normalized):
        return None

    parts = [part for part in normalized.split("/") if part]
    if len(parts) >= 4 and parts[0] == "a0" and parts[1] == "usr" and parts[2] == "projects":
        project_display = f"/a0/usr/projects/{parts[3]}"
        return _workspace_from_display(project_display, project_name=parts[3])

    workdir_display = configured_workdir_display_path()
    if normalized == workdir_display or normalized.startswith(workdir_display.rstrip("/") + "/"):
        return _workspace_from_display(workdir_display)

    return None


def _workspace_from_display(display_path: str, *, project_name: str = "", context_id: str = "") -> WorkspaceInfo:
    normalized = canonical_workspace_display_path(display_path)
    if not is_inside_usr_display(normalized):
        raise WorkspaceRejectedError("Time Travel is only available for workspaces inside /a0/usr.")
    workspace_id = workspace_id_for(normalized)
    shadow_path = real_path_for_display(f"{SHADOW_DISPLAY_ROOT}/{workspace_id}")
    return WorkspaceInfo(
        id=workspace_id,
        display_path=normalized.rstrip("/") or normalized,
        real_path=real_path_for_display(normalized),
        shadow_path=shadow_path,
        repo_git_path=shadow_path / "repo.git",
        context_id=context_id,
        project_name=project_name,
    )


def unavailable_payload(context_id: str, error: str) -> dict[str, Any]:
    return {
        "ok": True,
        "context_id": context_id,
        "workspace": {
            "available": False,
            "locked": True,
            "path": "",
            "display_path": "",
            "error": error,
        },
        "current_hash": "",
        "present": clean_summary(),
        "commits": [],
        "has_more": False,
    }


def clean_summary() -> dict[str, Any]:
    return {
        "dirty": False,
        "files_count": 0,
        "additions": 0,
        "deletions": 0,
        "files": [],
    }


def snapshot_for_agent(
    agent: Any,
    *,
    trigger: str,
    metadata: dict[str, Any] | None = None,
    debounced: bool = True,
) -> SnapshotResult | None:
    if not agent:
        return None

    context_id = str(getattr(getattr(agent, "context", None), "id", "") or "")
    try:
        workspace = resolve_workspace(context_id, context_loader=lambda _ctxid: agent.context)
        full_metadata = _agent_metadata(agent, metadata)
        if debounced:
            schedule_debounced_snapshot(
                workspace,
                trigger=trigger,
                metadata=full_metadata,
                changed_path_hints=_extract_changed_path_hints(full_metadata),
            )
            return None
        return TimeTravelService(workspace).snapshot(trigger=trigger, metadata=full_metadata)
    except WorkspaceRejectedError:
        return None
    except Exception as exc:
        PrintStyle.error(f"Time Travel snapshot failed: {exc}")
        return None


def snapshot_for_path_hint(
    path_hint: str,
    *,
    trigger: str,
    metadata: dict[str, Any] | None = None,
    debounced: bool = True,
) -> SnapshotResult | None:
    try:
        workspace = resolve_workspace_for_path_hint(path_hint)
        if workspace is None:
            return None
        full_metadata = metadata or {}
        if debounced:
            schedule_debounced_snapshot(
                workspace,
                trigger=trigger,
                metadata=full_metadata,
                changed_path_hints=_extract_changed_path_hints(full_metadata),
            )
            return None
        return TimeTravelService(workspace).snapshot(trigger=trigger, metadata=full_metadata)
    except Exception as exc:
        PrintStyle.error(f"Time Travel file-browser snapshot failed: {exc}")
        return None


def register_watchdogs() -> None:
    from helpers import watchdog

    root = real_path_for_display(USR_DISPLAY_ROOT)
    if not root.exists() or not root.is_dir():
        return

    watchdog.add_watchdog(
        id=WATCHDOG_ID,
        roots=[str(root)],
        patterns=["**/*"],
        ignore_patterns=[
            "**/.time_travel/**",
            "**/.pytest_cache/**",
            "**/.mypy_cache/**",
            "**/.ruff_cache/**",
            "**/.cache/**",
            "**/dist/**",
            "**/build/**",
        ],
        events=["create", "modify", "delete", "move"],
        debounce=WATCHDOG_DEBOUNCE_SECONDS,
        handler=_handle_usr_watchdog_events,
    )


def schedule_debounced_snapshot(
    workspace: WorkspaceInfo,
    *,
    trigger: str,
    metadata: dict[str, Any] | None = None,
    changed_path_hints: list[str] | None = None,
    delay: float | None = None,
) -> None:
    clean_metadata = dict(metadata or {})
    metadata_hints = _extract_changed_path_hints(clean_metadata)
    clean_metadata.pop("changed_path_hints", None)
    hints = _merge_hints(metadata_hints, changed_path_hints or [])
    delay_seconds = AUTO_SNAPSHOT_DEBOUNCE_SECONDS if delay is None else max(0.0, float(delay))
    with _AUTO_SNAPSHOT_LOCK:
        payload = _AUTO_SNAPSHOT_PAYLOADS.get(workspace.id)
        if payload is None:
            payload = {
                "workspace": workspace,
                "trigger": trigger,
                "metadata": clean_metadata,
                "changed_path_hints": hints,
            }
            _AUTO_SNAPSHOT_PAYLOADS[workspace.id] = payload
            timer = threading.Timer(delay_seconds, _flush_debounced_snapshot, args=(workspace.id,))
            timer.daemon = True
            _AUTO_SNAPSHOT_TIMERS[workspace.id] = timer
            timer.start()
            return

        payload["trigger"] = trigger
        payload["metadata"] = {**payload.get("metadata", {}), **clean_metadata}
        payload["changed_path_hints"] = _merge_hints(
            payload.get("changed_path_hints", []),
            hints,
        )


def flush_debounced_snapshots() -> None:
    with _AUTO_SNAPSHOT_LOCK:
        workspace_ids = list(_AUTO_SNAPSHOT_PAYLOADS)
        for workspace_id in workspace_ids:
            timer = _AUTO_SNAPSHOT_TIMERS.pop(workspace_id, None)
            timer and timer.cancel()
    for workspace_id in workspace_ids:
        _flush_debounced_snapshot(workspace_id)


def clear_debounced_snapshots() -> None:
    with _AUTO_SNAPSHOT_LOCK:
        timers = list(_AUTO_SNAPSHOT_TIMERS.values())
        _AUTO_SNAPSHOT_TIMERS.clear()
        _AUTO_SNAPSHOT_PAYLOADS.clear()
    for timer in timers:
        timer.cancel()


def _flush_debounced_snapshot(workspace_id: str) -> None:
    with _AUTO_SNAPSHOT_LOCK:
        _AUTO_SNAPSHOT_TIMERS.pop(workspace_id, None)
        payload = _AUTO_SNAPSHOT_PAYLOADS.pop(workspace_id, None)
    if not payload:
        return

    try:
        workspace = payload["workspace"]
        if not workspace.real_path.is_dir():
            return
        TimeTravelService(workspace).snapshot(
            trigger=str(payload.get("trigger") or "watchdog"),
            metadata=payload.get("metadata") or {},
            changed_path_hints=payload.get("changed_path_hints") or None,
        )
    except WorkspaceRejectedError:
        return
    except Exception as exc:
        PrintStyle.error(f"Time Travel debounced snapshot failed: {exc}")


def _handle_usr_watchdog_events(items: list[Any]) -> None:
    by_workspace: dict[str, tuple[WorkspaceInfo, list[str]]] = {}
    for path, _event in items:
        display_path = normalize_display_path(str(path or ""))
        if not _is_watchdog_snapshot_candidate(display_path):
            continue
        workspace = resolve_workspace_for_path_hint(display_path)
        if workspace is None:
            continue
        hints = by_workspace.setdefault(workspace.id, (workspace, []))[1]
        hints.append(display_path)

    for workspace, hints in by_workspace.values():
        schedule_debounced_snapshot(
            workspace,
            trigger="watchdog",
            metadata={
                "source": "watchdog",
                "changed_path_hints": _merge_hints(hints),
            },
            changed_path_hints=hints,
        )


def _agent_metadata(agent: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    from helpers import projects

    result = dict(metadata or {})
    context = getattr(agent, "context", None)
    if context is not None:
        result.setdefault("context_id", str(getattr(context, "id", "") or ""))
        project_name = projects.get_context_project_name(context) or ""
        if project_name:
            result.setdefault("project_name", project_name)
    tool = getattr(getattr(agent, "loop_data", None), "current_tool", None)
    if tool is not None:
        result.setdefault("tool_name", str(getattr(tool, "name", "") or ""))
        args = getattr(tool, "args", None)
        if isinstance(args, dict):
            result.setdefault("runtime", str(args.get("runtime") or ""))
        log = getattr(tool, "log", None)
        if log is not None:
            result.setdefault("log_item_id", str(getattr(log, "id", "") or ""))
            result.setdefault("log_item_no", getattr(log, "no", None))
    return {key: value for key, value in result.items() if value not in (None, "")}


def _extract_changed_path_hints(metadata: dict[str, Any]) -> list[str]:
    hints = metadata.get("changed_path_hints")
    if not isinstance(hints, list):
        return []
    return [str(path) for path in hints if path]


def _merge_hints(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for path in group:
            normalized = normalize_display_path(str(path or ""))
            if not normalized or normalized in seen:
                continue
            merged.append(normalized)
            seen.add(normalized)
    return merged


def _is_watchdog_snapshot_candidate(display_path: str) -> bool:
    normalized = normalize_display_path(display_path)
    if not is_inside_usr_display(normalized):
        return False
    if normalized == "/a0/usr/plugins" or normalized.startswith("/a0/usr/plugins/"):
        return False
    parts = [part for part in normalized.split("/") if part]
    return ".git" not in parts and ".time_travel" not in parts


class TimeTravelService:
    def __init__(self, workspace: WorkspaceInfo):
        self.workspace = workspace

    def ensure_repo(self) -> None:
        self.workspace.shadow_path.mkdir(parents=True, exist_ok=True)
        if not self._shadow_repo_valid():
            self._repair_shadow_repo_head()
        if not self._shadow_repo_valid():
            self._initialize_shadow_repo(quarantine_existing=True)
        self._ensure_current_head_ref()

        self._git("config", "user.name", "Agent Zero Time Travel")
        self._git("config", "user.email", "time-travel@agent-zero.local")
        self._git("config", "core.autocrlf", "false")
        self._git("config", "core.filemode", "true")

    def current_hash(self) -> str:
        self.ensure_repo()
        completed = self._git("rev-parse", "--verify", "HEAD", check=False)
        return completed.stdout.strip() if completed.returncode == 0 else ""

    def current_short_hash(self) -> str:
        current = self.current_hash()
        return current[:12] if current else ""

    def snapshot(
        self,
        *,
        trigger: str = "manual",
        message: str = "",
        metadata: dict[str, Any] | None = None,
        changed_path_hints: list[str] | None = None,
    ) -> SnapshotResult:
        self._ensure_workspace_dir()
        self.ensure_repo()
        previous_hash = self.current_hash()
        tree_hash, included_paths = self._stage_current_tree()

        if previous_hash and self._commit_tree(previous_hash) == tree_hash:
            return SnapshotResult(
                created=False,
                hash=previous_hash,
                short_hash=previous_hash[:12],
                tree_hash=tree_hash,
                message=message or self._default_snapshot_message(trigger),
                files=[],
                metadata=self._metadata(trigger, metadata, changed_path_hints),
            )

        if not previous_hash and not included_paths:
            return SnapshotResult(
                created=False,
                hash="",
                short_hash="",
                tree_hash=tree_hash,
                message=message or self._default_snapshot_message(trigger),
                files=[],
                metadata=self._metadata(trigger, metadata, changed_path_hints),
            )

        full_metadata = self._metadata(trigger, metadata, changed_path_hints)
        commit_message = self._commit_message(message or self._default_snapshot_message(trigger), full_metadata)
        args = ["commit-tree", tree_hash]
        if previous_hash:
            args.extend(["-p", previous_hash])
        args.extend(["-F", "-"])
        env = self._git_env()
        if timestamp := str(full_metadata.get("timestamp") or ""):
            env["GIT_AUTHOR_DATE"] = timestamp
            env["GIT_COMMITTER_DATE"] = timestamp
        commit = self._git(*args, input=commit_message, env=env).stdout.strip()
        self._git("update-ref", "HEAD", commit)
        diff_base = previous_hash or EMPTY_TREE
        return SnapshotResult(
            created=True,
            hash=commit,
            short_hash=commit[:12],
            tree_hash=tree_hash,
            message=message or self._default_snapshot_message(trigger),
            files=self.diff_files(diff_base, commit),
            metadata=full_metadata,
        )

    def history_list(self, *, limit: int = 100, offset: int = 0, file_filter: str = "") -> dict[str, Any]:
        self._ensure_workspace_dir()
        self.ensure_repo()
        limit = min(max(int(limit or 100), 1), 200)
        offset = max(int(offset or 0), 0)
        file_filter = str(file_filter or "").strip().lower()
        current = self.current_hash()
        present = self.present_summary()

        all_hashes = self._rev_list_all()
        if file_filter:
            all_hashes = [
                commit_hash
                for commit_hash in all_hashes
                if any(
                    file_filter in str(item.get("path") or "").lower()
                    or file_filter in str(item.get("old_path") or "").lower()
                    for item in self.commit_files(commit_hash)
                )
            ]

        window = all_hashes[offset : offset + limit + 1]
        visible = window[:limit]
        return {
            "ok": True,
            "context_id": self.workspace.context_id,
            "workspace": self.workspace.public(),
            "current_hash": current,
            "present": present,
            "commits": [self.commit_object(commit_hash, current_hash=current) for commit_hash in visible],
            "has_more": len(window) > limit,
        }

    def history_diff(self, *, commit_hash: str, path: str, mode: str = "commit") -> dict[str, Any]:
        self.ensure_repo()
        path = self._safe_rel_path(path)
        mode = str(mode or "commit").strip().lower()

        if mode in {"present", "current"}:
            base = self.current_hash() or EMPTY_TREE
            target, _paths = self._current_tree()
        else:
            commit_hash = self._validate_commit(commit_hash)
            base = self._first_parent(commit_hash) or EMPTY_TREE
            target = commit_hash

        return self._patch_payload(base, target, path)

    def preview(self, *, operation: str, commit_hash: str) -> dict[str, Any]:
        self.ensure_repo()
        operation = str(operation or "").strip().lower()
        commit_hash = self._validate_commit(commit_hash)
        current = self.current_hash() or EMPTY_TREE

        if operation == "travel":
            base = current
            target = commit_hash
        elif operation == "revert":
            base = commit_hash
            target = self._first_parent(commit_hash) or EMPTY_TREE
        else:
            raise TimeTravelError("Unsupported preview operation.")

        files_changed = self.diff_files(base, target)
        previews = []
        for item in files_changed[:12]:
            rel_path = str(item.get("path") or item.get("old_path") or "")
            if not rel_path:
                continue
            previews.append(self._patch_payload(base, target, rel_path))

        return {
            "ok": True,
            "operation": operation,
            "commit_hash": commit_hash,
            "short_hash": commit_hash[:12],
            "files": files_changed,
            "previews": previews,
        }

    def travel(self, *, commit_hash: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_workspace_dir()
        self.ensure_repo()
        target = self._validate_commit(commit_hash)
        before = self.snapshot(trigger="before_travel", metadata=metadata or {})
        previous = self.current_hash()
        if previous:
            self._preserve_ref(previous, reason="travel")
        affected = self.diff_files(previous or EMPTY_TREE, target)
        self._apply_commit_tree(previous or EMPTY_TREE, target, affected)
        self._git("update-ref", "HEAD", target)
        return {
            "ok": True,
            "operation": "travel",
            "current_hash": target,
            "previous_hash": previous,
            "preserved_hash": previous,
            "auto_snapshot": _snapshot_public(before),
            "affected_files": affected,
        }

    def revert(self, *, commit_hash: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_workspace_dir()
        self.ensure_repo()
        target = self._validate_commit(commit_hash)
        before = self.snapshot(trigger="before_revert", metadata=metadata or {})
        parent = self._first_parent(target) or EMPTY_TREE
        patch = self._git_bytes("diff", "--binary", parent, target).stdout
        if patch:
            checked = self._git_bytes("apply", "--reverse", "--check", "--binary", "--whitespace=nowarn", input=patch, check=False)
            if checked.returncode != 0:
                raise TimeTravelConflictError(_compact_git_error(checked.stderr.decode("utf-8", "replace")))
            applied = self._git_bytes("apply", "--reverse", "--binary", "--whitespace=nowarn", input=patch, check=False)
            if applied.returncode != 0:
                raise TimeTravelConflictError(_compact_git_error(applied.stderr.decode("utf-8", "replace")))

        after = self.snapshot(
            trigger="revert",
            message=f"Revert {target[:12]}",
            metadata={
                **(metadata or {}),
                "reverted_commit": target,
            },
        )
        return {
            "ok": True,
            "operation": "revert",
            "current_hash": after.hash,
            "auto_snapshot": _snapshot_public(before),
            "snapshot": _snapshot_public(after),
            "affected_files": after.files,
        }

    def present_summary(self) -> dict[str, Any]:
        self.ensure_repo()
        current_tree, _paths = self._current_tree()
        current = self.current_hash()
        base = current or EMPTY_TREE
        base_tree = self._commit_tree(current) if current else EMPTY_TREE
        if base_tree == current_tree:
            return clean_summary()
        changed = self.diff_files(base, current_tree)
        return {
            "dirty": bool(changed),
            "files_count": len(changed),
            "additions": sum(int(item.get("additions") or 0) for item in changed),
            "deletions": sum(int(item.get("deletions") or 0) for item in changed),
            "files": changed,
        }

    def commit_object(self, commit_hash: str, *, current_hash: str = "") -> dict[str, Any]:
        commit_hash = self._validate_commit(commit_hash)
        show = self._git("show", "-s", "--format=%H%x00%h%x00%cI%x00%s%x00%B", commit_hash).stdout
        parts = show.split("\0", 4)
        full_hash = parts[0].strip()
        short_hash = parts[1].strip() if len(parts) > 1 else full_hash[:12]
        timestamp = parts[2].strip() if len(parts) > 2 else ""
        subject = parts[3].strip() if len(parts) > 3 else ""
        body = parts[4] if len(parts) > 4 else ""
        metadata = self._parse_metadata(body)
        return {
            "hash": full_hash,
            "short_hash": short_hash,
            "timestamp": timestamp,
            "message": subject,
            "is_current": bool(current_hash and full_hash == current_hash),
            "metadata": metadata,
            "files": self.commit_files(full_hash),
        }

    def commit_files(self, commit_hash: str) -> list[dict[str, Any]]:
        commit_hash = self._validate_commit(commit_hash)
        parent = self._first_parent(commit_hash) or EMPTY_TREE
        return self.diff_files(parent, commit_hash)

    def diff_files(self, base: str, target: str, *, path_filter: str = "") -> list[dict[str, Any]]:
        args = ["diff", "--name-status", "-z", "--find-renames", base, target]
        path_filter = str(path_filter or "").strip()
        if path_filter:
            args.extend(["--", path_filter])
        output = self._git(*args).stdout
        entries = _parse_name_status(output)
        result: list[dict[str, Any]] = []
        for entry in entries:
            path = entry["path"]
            old_path = entry.get("old_path", "")
            additions, deletions, binary = self._numstat(base, target, [p for p in (old_path, path) if p])
            action = STATUS_LABELS.get(entry["status"], entry["status"].lower())
            result.append(
                {
                    "path": path,
                    "old_path": old_path,
                    "status": action,
                    "action": action,
                    "additions": additions,
                    "deletions": deletions,
                    "binary": binary,
                }
            )
        return result

    def _current_tree(self) -> tuple[str, list[str]]:
        return self._stage_current_tree()

    def _stage_current_tree(self) -> tuple[str, list[str]]:
        self.ensure_repo()
        self._git("read-tree", "--empty")
        paths = list(iter_snapshot_paths(self.workspace.real_path, display_path=self.workspace.display_path))
        if paths:
            payload = "\0".join(paths).encode("utf-8") + b"\0"
            self._git_bytes(
                "add",
                "-f",
                "-A",
                "--pathspec-from-file=-",
                "--pathspec-file-nul",
                input=payload,
            )
        tree_hash = self._git("write-tree").stdout.strip()
        return tree_hash, paths

    def _apply_commit_tree(self, base: str, target: str, affected: list[dict[str, Any]]) -> None:
        delete_paths: list[str] = []
        write_paths: list[str] = []
        for item in affected:
            action = str(item.get("action") or item.get("status") or "")
            old_path = str(item.get("old_path") or "")
            path = str(item.get("path") or "")
            if old_path and old_path != path:
                delete_paths.append(old_path)
            if action == "deleted":
                delete_paths.append(path)
            else:
                write_paths.append(path)

        for rel_path in sorted(set(delete_paths), key=lambda value: value.count("/"), reverse=True):
            self._delete_workspace_entry(rel_path)
        for rel_path in sorted(set(write_paths)):
            self._materialize_tree_path(target, rel_path)
        self._prune_empty_dirs()

    def _materialize_tree_path(self, commit_hash: str, rel_path: str) -> None:
        rel_path = self._safe_rel_path(rel_path)
        entry = self._tree_entry(commit_hash, rel_path)
        if entry is None:
            self._delete_workspace_entry(rel_path)
            return
        mode, obj_type, obj_hash = entry
        if obj_type != "blob":
            return
        target_path = self._workspace_child(rel_path)
        data = self._git_bytes("cat-file", "-p", obj_hash).stdout
        self._prepare_parent(target_path)
        if target_path.exists() or target_path.is_symlink():
            self._remove_for_replacement(target_path)
        if mode == "120000":
            os.symlink(data.decode("utf-8", errors="replace"), target_path)
        else:
            target_path.write_bytes(data)
            if mode == "100755":
                target_path.chmod(0o755)

    def _delete_workspace_entry(self, rel_path: str) -> None:
        rel_path = self._safe_rel_path(rel_path)
        target_path = self._workspace_child(rel_path)
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
        elif target_path.exists():
            if target_path.is_dir() and not any(target_path.iterdir()):
                target_path.rmdir()
            else:
                raise TimeTravelConflictError(
                    f"Cannot safely replace non-empty directory: {rel_path}"
                )

    def _prepare_parent(self, target_path: Path) -> None:
        current = self.workspace.real_path
        rel_parts = target_path.relative_to(self.workspace.real_path).parts[:-1]
        for part in rel_parts:
            current = current / part
            if current.is_symlink() or current.is_file():
                self._remove_for_replacement(current)
            current.mkdir(exist_ok=True)

    def _remove_for_replacement(self, target_path: Path) -> None:
        if target_path.is_symlink() or target_path.is_file():
            target_path.unlink()
            return
        if target_path.is_dir():
            if any(target_path.iterdir()):
                raise TimeTravelConflictError(
                    f"Cannot safely replace non-empty directory: {self._rel_from_workspace(target_path)}"
                )
            target_path.rmdir()

    def _prune_empty_dirs(self) -> None:
        for root, dirs, _filenames in os.walk(self.workspace.real_path, topdown=False, followlinks=False):
            root_path = Path(root)
            if root_path == self.workspace.real_path:
                continue
            if not is_snapshot_candidate(root_path.relative_to(self.workspace.real_path).as_posix(), is_dir=True):
                continue
            try:
                root_path.rmdir()
            except OSError:
                pass

    def _tree_entry(self, commit_hash: str, rel_path: str) -> tuple[str, str, str] | None:
        completed = self._git("ls-tree", "-z", commit_hash, "--", rel_path, check=False)
        if completed.returncode != 0 or not completed.stdout:
            return None
        record = completed.stdout.split("\0", 1)[0]
        meta, _sep, _name = record.partition("\t")
        parts = meta.split()
        if len(parts) < 3:
            return None
        return parts[0], parts[1], parts[2]

    def _patch_payload(self, base: str, target: str, path: str) -> dict[str, Any]:
        path = self._safe_rel_path(path)
        additions, deletions, binary = self._numstat(base, target, [path])
        completed = self._git_bytes("diff", "--binary", "--patch", base, target, "--", path, check=False)
        data = completed.stdout or b""
        too_large = len(data) > MAX_RENDERED_PATCH_BYTES
        rendered = data[:MAX_RENDERED_PATCH_BYTES].decode("utf-8", errors="replace")
        return {
            "ok": completed.returncode == 0,
            "path": path,
            "patch": "" if binary else rendered,
            "binary": binary,
            "too_large": too_large,
            "additions": additions,
            "deletions": deletions,
            "error": "" if completed.returncode == 0 else completed.stderr.decode("utf-8", errors="replace"),
        }

    def _numstat(self, base: str, target: str, paths: list[str]) -> tuple[int, int, bool]:
        if not paths:
            return 0, 0, False
        output = self._git("diff", "--numstat", "--find-renames", base, target, "--", *paths, check=False).stdout
        additions = 0
        deletions = 0
        binary = False
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            if parts[0] == "-" or parts[1] == "-":
                binary = True
                continue
            additions += _safe_int(parts[0])
            deletions += _safe_int(parts[1])
        return additions, deletions, binary

    def _rev_list_all(self) -> list[str]:
        completed = self._git("rev-list", "--date-order", "--all", check=False)
        if completed.returncode != 0:
            return []
        seen: set[str] = set()
        result: list[str] = []
        for line in completed.stdout.splitlines():
            commit = line.strip()
            if commit and commit not in seen:
                result.append(commit)
                seen.add(commit)
        return result

    def _validate_commit(self, commit_hash: str) -> str:
        candidate = str(commit_hash or "").strip()
        if not candidate:
            raise TimeTravelError("Commit hash is required.")
        completed = self._git("rev-parse", "--verify", f"{candidate}^{{commit}}", check=False)
        if completed.returncode != 0:
            raise TimeTravelError("Unknown Time Travel commit.")
        return completed.stdout.strip()

    def _first_parent(self, commit_hash: str) -> str:
        completed = self._git("rev-list", "--parents", "-n", "1", commit_hash)
        parts = completed.stdout.strip().split()
        return parts[1] if len(parts) > 1 else ""

    def _commit_tree(self, commit_hash: str) -> str:
        return self._git("show", "-s", "--format=%T", commit_hash).stdout.strip()

    def _preserve_ref(self, commit_hash: str, *, reason: str) -> str:
        stamp = Localization.get().now().strftime("%Y%m%d%H%M%S")
        base_ref = f"{PRESERVED_REF_PREFIX}/{stamp}-{reason}-{commit_hash[:12]}"
        ref = base_ref
        counter = 2
        while self._git("show-ref", "--verify", "--quiet", ref, check=False).returncode == 0:
            ref = f"{base_ref}-{counter}"
            counter += 1
        self._git("update-ref", ref, commit_hash)
        return ref

    def _commit_message(self, message: str, metadata: dict[str, Any]) -> str:
        encoded = base64.b64encode(json.dumps(metadata, sort_keys=True).encode("utf-8")).decode("ascii")
        return f"{message.strip() or 'Snapshot'}\n\n{METADATA_PREFIX} {encoded}\n"

    def _parse_metadata(self, body: str) -> dict[str, Any]:
        for line in body.splitlines():
            if line.startswith(METADATA_PREFIX):
                encoded = line.removeprefix(METADATA_PREFIX).strip()
                try:
                    return json.loads(base64.b64decode(encoded).decode("utf-8"))
                except Exception:
                    return {}
        return {}

    def _metadata(
        self,
        trigger: str,
        metadata: dict[str, Any] | None,
        changed_path_hints: list[str] | None,
    ) -> dict[str, Any]:
        result = dict(metadata or {})
        result.setdefault("context_id", self.workspace.context_id)
        result.setdefault("project_name", self.workspace.project_name)
        result.setdefault("trigger", trigger)
        result.setdefault("timestamp", now_iso())
        hints = [normalize_display_path(path) for path in (changed_path_hints or []) if path]
        if hints:
            result.setdefault("changed_path_hints", hints)
        return {key: value for key, value in result.items() if value not in (None, "")}

    def _default_snapshot_message(self, trigger: str) -> str:
        label = str(trigger or "snapshot").replace("_", " ").strip().title()
        return f"Snapshot: {label}"

    def _ensure_workspace_dir(self) -> None:
        if not self.workspace.real_path.exists():
            raise TimeTravelError("Workspace path does not exist.")
        if not self.workspace.real_path.is_dir():
            raise TimeTravelError("Workspace path is not a directory.")

    def _safe_rel_path(self, path: str) -> str:
        rel = str(path or "").replace("\\", "/").lstrip("/")
        normalized = posixpath.normpath(rel)
        if not normalized or normalized == "." or normalized.startswith("../") or normalized == "..":
            raise TimeTravelError("Invalid path.")
        return normalized

    def _workspace_child(self, rel_path: str) -> Path:
        rel = self._safe_rel_path(rel_path)
        path = self.workspace.real_path.joinpath(*rel.split("/"))
        try:
            path.relative_to(self.workspace.real_path)
        except ValueError:
            raise TimeTravelError("Invalid path.")
        return path

    def _rel_from_workspace(self, path: Path) -> str:
        try:
            return path.relative_to(self.workspace.real_path).as_posix()
        except ValueError:
            return str(path)

    def _git_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_OPTIONAL_LOCKS"] = "0"
        return env

    def _run_git_dir(self, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", f"--git-dir={self.workspace.repo_git_path}", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._git_env(),
            timeout=GIT_TIMEOUT_SECONDS,
            check=check,
        )

    def _shadow_repo_valid(self) -> bool:
        if not self.workspace.repo_git_path.is_dir():
            return False
        completed = self._run_git_dir("rev-parse", "--git-dir")
        return completed.returncode == 0

    def _repair_shadow_repo_head(self) -> None:
        if not self.workspace.repo_git_path.is_dir():
            return
        if not (self.workspace.repo_git_path / "objects").is_dir() or not (self.workspace.repo_git_path / "refs").is_dir():
            return
        target_ref = CURRENT_REF if self._loose_ref_exists(CURRENT_REF) else self._first_loose_head_ref()
        try:
            (self.workspace.repo_git_path / "HEAD").write_text(f"ref: {target_ref}\n", encoding="utf-8")
        except OSError:
            return

    def _initialize_shadow_repo(self, *, quarantine_existing: bool = False) -> None:
        if quarantine_existing and self.workspace.repo_git_path.exists():
            backup_path = self._next_invalid_repo_backup_path()
            shutil.move(str(self.workspace.repo_git_path), str(backup_path))
        completed = subprocess.run(
            ["git", "init", "--bare", str(self.workspace.repo_git_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self._git_env(),
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            raise GitCommandError(
                (completed.stderr or completed.stdout or "Could not initialize shadow Git repository.").strip(),
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        updated = self._run_git_dir("symbolic-ref", "HEAD", CURRENT_REF)
        if updated.returncode != 0:
            raise GitCommandError(
                (updated.stderr or updated.stdout or "Could not initialize shadow Git HEAD.").strip(),
                stdout=updated.stdout,
                stderr=updated.stderr,
            )

    def _loose_ref_exists(self, ref: str) -> bool:
        return self.workspace.repo_git_path.joinpath(*ref.split("/")).is_file()

    def _first_loose_head_ref(self) -> str:
        heads_dir = self.workspace.repo_git_path / "refs" / "heads"
        try:
            refs = sorted(path for path in heads_dir.rglob("*") if path.is_file())
        except OSError:
            refs = []
        if not refs:
            return CURRENT_REF
        return "refs/heads/" + refs[0].relative_to(heads_dir).as_posix()

    def _next_invalid_repo_backup_path(self) -> Path:
        stamp = Localization.get().now().strftime("%Y%m%d%H%M%S")
        base_path = self.workspace.shadow_path / f"{SHADOW_REPO_BACKUP_PREFIX}-{stamp}"
        backup_path = base_path
        counter = 2
        while backup_path.exists():
            backup_path = self.workspace.shadow_path / f"{base_path.name}-{counter}"
            counter += 1
        return backup_path

    def _ensure_current_head_ref(self) -> None:
        current_ref = self._run_git_dir("symbolic-ref", "-q", "HEAD")
        if current_ref.returncode == 0 and current_ref.stdout.strip() == CURRENT_REF:
            return

        current_commit = self._run_git_dir("rev-parse", "--verify", "HEAD^{commit}")
        if current_commit.returncode == 0:
            self._run_git_dir("update-ref", CURRENT_REF, current_commit.stdout.strip())

        updated = self._run_git_dir("symbolic-ref", "HEAD", CURRENT_REF)
        if updated.returncode != 0:
            raise GitCommandError(
                (updated.stderr or updated.stdout or "Could not repair shadow Git HEAD.").strip(),
                stdout=updated.stdout,
                stderr=updated.stderr,
            )

    def _git(self, *args: str, input: str | None = None, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
        self.workspace.shadow_path.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "git",
                f"--git-dir={self.workspace.repo_git_path}",
                f"--work-tree={self.workspace.real_path}",
                "-c",
                "core.bare=false",
                *args,
            ],
            input=input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env or self._git_env(),
            cwd=str(self.workspace.real_path) if self.workspace.real_path.exists() else None,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if check and completed.returncode != 0:
            raise GitCommandError(
                (completed.stderr or completed.stdout or "Git command failed.").strip(),
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    def _git_bytes(self, *args: str, input: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
        self.workspace.shadow_path.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "git",
                f"--git-dir={self.workspace.repo_git_path}",
                f"--work-tree={self.workspace.real_path}",
                "-c",
                "core.bare=false",
                *args,
            ],
            input=input,
            capture_output=True,
            env=self._git_env(),
            cwd=str(self.workspace.real_path) if self.workspace.real_path.exists() else None,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if check and completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")
            stdout = completed.stdout.decode("utf-8", errors="replace")
            raise GitCommandError((stderr or stdout or "Git command failed.").strip(), stdout=stdout, stderr=stderr)
        return completed


def iter_snapshot_paths(workspace: Path, *, display_path: str = "") -> Iterable[str]:
    workspace = workspace.resolve(strict=False)
    if display_path:
        root_is_usr = normalize_display_path(display_path) == USR_DISPLAY_ROOT
    else:
        root_is_usr = workspace == real_path_for_display(USR_DISPLAY_ROOT)

    def walk(folder: Path, rel_prefix: str = "") -> Iterable[str]:
        try:
            with os.scandir(folder) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError:
            return
        for entry in entries:
            rel = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            rel = rel.replace("\\", "/")
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_file = entry.is_file(follow_symlinks=False)
                is_link = entry.is_symlink()
            except OSError:
                continue
            if is_dir:
                if root_is_usr and not rel_prefix and entry.name in USR_ROOT_EXCLUDED_DIR_NAMES:
                    continue
                if _is_nested_git_worktree_dir(Path(entry.path), workspace):
                    continue
                if not is_snapshot_candidate(rel, is_dir=True):
                    continue
                yield from walk(Path(entry.path), rel)
            elif (is_file or is_link) and is_snapshot_candidate(rel, is_dir=False):
                yield rel

    yield from walk(workspace)


def _is_nested_git_worktree_dir(folder: Path, workspace: Path) -> bool:
    try:
        if folder.resolve(strict=False) == workspace.resolve(strict=False):
            return False
    except OSError:
        return False
    dot_git = folder / ".git"
    return dot_git.exists() or dot_git.is_symlink()


def is_snapshot_candidate(rel_path: str, *, is_dir: bool) -> bool:
    rel = rel_path.replace("\\", "/").strip("/")
    if not rel:
        return False
    parts = rel.split("/")
    name = parts[-1]

    if name == ".git" or ".git" in parts:
        return False
    if name == ".time_travel" or ".time_travel" in parts:
        return False
    if name in {"secrets.env", "variables.env"}:
        return False

    if rel.startswith(".a0proj/"):
        return _is_safe_a0proj_candidate(rel, is_dir=is_dir)

    if is_dir:
        if name in EXCLUDED_DIR_NAMES:
            return False
        if any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_DIR_PATTERNS):
            return False
        return True

    if any(fnmatch.fnmatch(name, pattern) for pattern in EXCLUDED_FILE_PATTERNS):
        return False
    return True


def _is_safe_a0proj_candidate(rel: str, *, is_dir: bool) -> bool:
    if rel in {".a0proj/secrets.env", ".a0proj/variables.env"}:
        return False
    if rel == ".a0proj/memory" or rel.startswith(".a0proj/memory/"):
        return False
    if is_dir:
        return (
            rel == ".a0proj"
            or any(prefix.startswith(rel.rstrip("/") + "/") or rel.startswith(prefix) for prefix in SAFE_A0PROJ_DIRS)
            or rel.startswith(".a0proj/plugins")
            or rel.startswith(".a0proj/agents")
        )
    if rel in SAFE_A0PROJ_FILES:
        return True
    if any(rel.startswith(prefix) for prefix in SAFE_A0PROJ_DIRS):
        return True
    return _is_safe_plugin_asset(rel)


def _is_safe_plugin_asset(rel: str) -> bool:
    parts = rel.split("/")
    if len(parts) < 4:
        return False
    for index, part in enumerate(parts):
        if part != "plugins":
            continue
        tail = parts[index + 1 :]
        if len(tail) == 2 and tail[1] in SAFE_PLUGIN_ASSET_NAMES:
            return True
    return False


def _parse_name_status(output: str) -> list[dict[str, str]]:
    parts = [part for part in output.split("\0") if part]
    entries: list[dict[str, str]] = []
    index = 0
    while index < len(parts):
        raw_status = parts[index]
        index += 1
        status = raw_status[:1]
        if status in {"R", "C"} and index + 1 < len(parts):
            old_path = parts[index].replace("\\", "/")
            new_path = parts[index + 1].replace("\\", "/")
            index += 2
            entries.append({"status": status, "old_path": old_path, "path": new_path})
            continue
        if index < len(parts):
            path = parts[index].replace("\\", "/")
            index += 1
            entries.append({"status": status, "old_path": "", "path": path})
    entries.sort(key=lambda item: item.get("path") or item.get("old_path") or "")
    return entries


def _safe_int(value: str) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _snapshot_public(snapshot: SnapshotResult) -> dict[str, Any]:
    return {
        "created": snapshot.created,
        "hash": snapshot.hash,
        "short_hash": snapshot.short_hash,
        "message": snapshot.message,
        "files": snapshot.files,
        "metadata": snapshot.metadata,
    }


def _compact_git_error(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return "The patch could not be applied cleanly."
    return "\n".join(lines[:8])
