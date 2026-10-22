from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any

from helpers.ws_limits import peer_ws_max_payload_bytes
from helpers.ws_manager import WsPayloadTooLargeError, get_shared_ws_manager


@dataclass
class PendingFileOperation:
    sid: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]
    context_id: str | None = None


TRANSFER_PROTOCOL_VERSION = 1
TRANSFER_CHUNK_BYTES = 64 * 1024
TRANSFER_SPOOL_THRESHOLD_BYTES = 1024 * 1024
TRANSFER_SINGLE_FRAME_BYTES = 1024 * 1024
TRANSFER_IDLE_TIMEOUT_SECONDS = 30.0
MAX_INCOMING_TRANSFERS_PER_SID = 4
_TRANSFER_ENCODED_CHUNK_MAX = ((TRANSFER_CHUNK_BYTES + 2) // 3) * 4
_TRANSFER_RESULT_EVENTS = {
    "connector_file_op_result",
    "connector_exec_op_result",
    "connector_computer_use_op_result",
    "connector_browser_op_result",
    "connector_gateway_control_result",
}


@dataclass
class IncomingTransfer:
    transfer_id: str
    sid: str
    kind: str
    op_id: str
    context_id: str | None
    total_bytes: int
    sha256: str
    digest: Any
    updated_at: float
    buffer: bytearray | None = None
    temp_path: Path | None = None
    next_index: int = 0
    received_bytes: int = 0
    timeout: threading.Timer | None = None


@dataclass
class OutgoingTransfer:
    transfer_id: str
    sid: str
    kind: str
    op_id: str
    context_id: str | None
    cancel_reason: str = ""
    abort_sent: bool = False


@dataclass
class PendingExecOperation:
    sid: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]
    context_id: str | None = None


@dataclass
class PendingComputerUseOperation:
    sid: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]
    context_id: str | None = None


@dataclass
class PendingBrowserOperation:
    sid: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]
    context_id: str | None = None


@dataclass
class PendingGatewayControl:
    sid: str
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future[dict[str, Any]]


@dataclass(frozen=True)
class RemoteTreeSnapshot:
    sid: str
    payload: dict[str, Any]
    updated_at: float


@dataclass(frozen=True)
class ComputerUseMetadata:
    supported: bool
    enabled: bool
    trust_mode: str
    status: str
    last_error: str
    restore_token_present: bool
    artifact_root: str
    backend_id: str
    backend_family: str
    durable_instance_id: str
    features: tuple[str, ...]
    contract_version: int
    capabilities: dict[str, Any]
    support_reason: str
    updated_at: float


@dataclass(frozen=True)
class HostBrowserMetadata:
    supported: bool
    can_prepare: bool
    enabled: bool
    status: str
    browser_family: str
    profile_label: str
    profile_path: str
    cdp_endpoint: str
    browser_id: str
    browser_label: str
    available_browsers: tuple[dict[str, Any], ...]
    content_helper_sha256: str
    durable_instance_id: str
    features: tuple[str, ...]
    support_reason: str
    updated_at: float


@dataclass(frozen=True)
class RemoteFileMetadata:
    enabled: bool
    write_enabled: bool
    mode: str
    updated_at: float
    file_browser: bool = False
    root_path: str = ""


@dataclass(frozen=True)
class RemoteExecMetadata:
    enabled: bool
    updated_at: float


@dataclass(frozen=True)
class LauncherGatewayMetadata:
    gateway_id: str
    host_label: str
    state: str
    master_enabled: bool
    scopes: dict[str, bool]
    status: dict[str, Any]
    updated_at: float


_context_subscriptions: dict[str, set[str]] = {}
_sid_contexts: dict[str, set[str]] = {}
_pending_file_ops: dict[str, PendingFileOperation] = {}
_pending_exec_ops: dict[str, PendingExecOperation] = {}
_pending_computer_use_ops: dict[str, PendingComputerUseOperation] = {}
_pending_browser_ops: dict[str, PendingBrowserOperation] = {}
_pending_gateway_controls: dict[str, PendingGatewayControl] = {}
_remote_tree_snapshots: dict[str, RemoteTreeSnapshot] = {}
_sid_computer_use_metadata: dict[str, ComputerUseMetadata] = {}
_sid_host_browser_metadata: dict[str, HostBrowserMetadata] = {}
_sid_remote_file_metadata: dict[str, RemoteFileMetadata] = {}
_sid_remote_exec_metadata: dict[str, RemoteExecMetadata] = {}
_sid_launcher_gateway_metadata: dict[str, LauncherGatewayMetadata] = {}
_sid_ws_max_payload_bytes: dict[str, int] = {}
_sid_transfer_protocol: dict[str, int] = {}
_incoming_transfers: dict[str, IncomingTransfer] = {}
_outgoing_transfers: dict[str, OutgoingTransfer] = {}
_replaced_gateway_sids: set[str] = set()
_state_lock = threading.RLock()


def register_sid(sid: str) -> None:
    with _state_lock:
        _replaced_gateway_sids.discard(sid)
        _sid_contexts.setdefault(sid, set())
        _sid_ws_max_payload_bytes.setdefault(
            sid,
            peer_ws_max_payload_bytes(None),
        )
        _sid_transfer_protocol.setdefault(sid, 0)


def unregister_sid(sid: str) -> set[str]:
    transfer_ids: list[str] = []
    outgoing: list[OutgoingTransfer] = []
    with _state_lock:
        contexts = _sid_contexts.pop(sid, set())
        _remote_tree_snapshots.pop(sid, None)
        _sid_computer_use_metadata.pop(sid, None)
        _sid_host_browser_metadata.pop(sid, None)
        _sid_remote_file_metadata.pop(sid, None)
        _sid_remote_exec_metadata.pop(sid, None)
        _sid_launcher_gateway_metadata.pop(sid, None)
        _sid_ws_max_payload_bytes.pop(sid, None)
        _sid_transfer_protocol.pop(sid, None)
        transfer_ids = [
            transfer_id
            for transfer_id, transfer in _incoming_transfers.items()
            if transfer.sid == sid
        ]
        outgoing = [
            transfer
            for transfer in _outgoing_transfers.values()
            if transfer.sid == sid
        ]
        for transfer in outgoing:
            transfer.cancel_reason = "connector disconnected during transfer"
            transfer.abort_sent = True
            _outgoing_transfers.pop(transfer.transfer_id, None)
        _replaced_gateway_sids.discard(sid)
        for context_id in contexts:
            subscribers = _context_subscriptions.get(context_id)
            if not subscribers:
                continue
            subscribers.discard(sid)
            if not subscribers:
                _context_subscriptions.pop(context_id, None)
    for transfer_id in transfer_ids:
        abort_incoming_transfer(
            sid,
            {"transfer_id": transfer_id},
            reason="connector disconnected during transfer",
        )
    for transfer in outgoing:
        _fail_transfer_pending(
            transfer.kind,
            transfer.op_id,
            sid=sid,
            error=transfer.cancel_reason,
        )
    return contexts


def subscribe_sid_to_context(sid: str, context_id: str) -> None:
    with _state_lock:
        _sid_contexts.setdefault(sid, set()).add(context_id)
        _context_subscriptions.setdefault(context_id, set()).add(sid)


def unsubscribe_sid_from_context(sid: str, context_id: str) -> None:
    with _state_lock:
        contexts = _sid_contexts.get(sid)
        if contexts is not None:
            contexts.discard(context_id)
            if not contexts:
                _sid_contexts.pop(sid, None)

        subscribers = _context_subscriptions.get(context_id)
        if subscribers is not None:
            subscribers.discard(sid)
            if not subscribers:
                _context_subscriptions.pop(context_id, None)


def subscribed_contexts_for_sid(sid: str) -> set[str]:
    with _state_lock:
        return set(_sid_contexts.get(sid, set()))


def subscribed_sids_for_context(context_id: str) -> set[str]:
    with _state_lock:
        return set(_context_subscriptions.get(context_id, set()))


def connected_sids() -> set[str]:
    with _state_lock:
        return set(_sid_contexts.keys())


def store_sid_connector_capabilities(sid: str, payload: Any) -> int:
    capabilities = payload if isinstance(payload, dict) else {}
    limit = peer_ws_max_payload_bytes(capabilities.get("ws_max_payload_bytes"))
    try:
        transfer_protocol = int(capabilities.get("transfer_protocol") or 0)
    except (TypeError, ValueError):
        transfer_protocol = 0
    if transfer_protocol != TRANSFER_PROTOCOL_VERSION:
        transfer_protocol = 0
    with _state_lock:
        _sid_ws_max_payload_bytes[sid] = limit
        _sid_transfer_protocol[sid] = transfer_protocol
    return limit


def ws_max_payload_bytes_for_sid(sid: str) -> int:
    with _state_lock:
        return _sid_ws_max_payload_bytes.get(sid, peer_ws_max_payload_bytes(None))


def transfer_protocol_for_sid(sid: str) -> int:
    with _state_lock:
        return _sid_transfer_protocol.get(sid, 0)


async def emit_connector_event(
    sid: str,
    event: str,
    payload: dict[str, Any],
    *,
    handler_id: str,
    manager: Any | None = None,
) -> None:
    ws_manager = manager or get_shared_ws_manager()
    limit = ws_max_payload_bytes_for_sid(sid)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > TRANSFER_SINGLE_FRAME_BYTES:
        if (
            transfer_protocol_for_sid(sid) == TRANSFER_PROTOCOL_VERSION
            and len(raw) <= limit
        ):
            await _emit_connector_transfer(
                ws_manager,
                sid=sid,
                kind=event,
                payload=payload,
                raw=raw,
                handler_id=handler_id,
                limit=limit,
            )
            return
        raise WsPayloadTooLargeError(
            event,
            len(raw),
            min(limit, TRANSFER_SINGLE_FRAME_BYTES),
        )
    try:
        await ws_manager.emit_to(
            "/ws",
            sid,
            event,
            payload,
            handler_id=handler_id,
            max_payload_bytes=limit,
        )
        return
    except WsPayloadTooLargeError:
        if transfer_protocol_for_sid(sid) != TRANSFER_PROTOCOL_VERSION:
            raise

    if len(raw) > limit:
        raise WsPayloadTooLargeError(event, len(raw), limit)
    await _emit_connector_transfer(
        ws_manager,
        sid=sid,
        kind=event,
        payload=payload,
        raw=raw,
        handler_id=handler_id,
        limit=limit,
    )


async def _emit_connector_transfer(
    manager: Any,
    *,
    sid: str,
    kind: str,
    payload: dict[str, Any],
    raw: bytes,
    handler_id: str,
    limit: int,
) -> None:
    transfer_id = uuid.uuid4().hex
    op_id = str(payload.get("op_id") or payload.get("request_id") or "")
    context_id = _transfer_context_id(payload.get("context_id"))
    state = OutgoingTransfer(
        transfer_id=transfer_id,
        sid=sid,
        kind=kind,
        op_id=op_id,
        context_id=context_id,
    )
    with _state_lock:
        _outgoing_transfers[transfer_id] = state
    common = {
        "handler_id": handler_id,
        "max_payload_bytes": limit,
    }
    try:
        start = {
            "transfer_id": transfer_id,
            "op_id": op_id,
            "kind": kind,
            "total_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        if context_id:
            start["context_id"] = context_id
        await manager.emit_to(
            "/ws",
            sid,
            "connector_transfer_start",
            start,
            **common,
        )
        if state.cancel_reason:
            return
        for index, offset in enumerate(range(0, len(raw), TRANSFER_CHUNK_BYTES)):
            if state.cancel_reason:
                return
            await manager.emit_to(
                "/ws",
                sid,
                "connector_transfer_chunk",
                {
                    "transfer_id": transfer_id,
                    "index": index,
                    "data": base64.b64encode(
                        raw[offset : offset + TRANSFER_CHUNK_BYTES]
                    ).decode("ascii"),
                },
                **common,
            )
            if state.cancel_reason:
                return
        await manager.emit_to(
            "/ws",
            sid,
            "connector_transfer_end",
            {"transfer_id": transfer_id},
            **common,
        )
    except Exception as exc:
        if not state.abort_sent:
            state.abort_sent = True
            with contextlib.suppress(Exception):
                await manager.emit_to(
                    "/ws",
                    sid,
                    "connector_transfer_abort",
                    {
                        "transfer_id": transfer_id,
                        "op_id": op_id,
                        "kind": kind,
                        "reason": str(exc)[:512],
                    },
                    **common,
                )
        raise
    finally:
        with _state_lock:
            _outgoing_transfers.pop(transfer_id, None)


def payload_too_large_result(
    exc: WsPayloadTooLargeError,
    *,
    op_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "code": "PAYLOAD_TOO_LARGE",
        "error": str(exc),
        "details": exc.details(),
    }
    if op_id:
        result["op_id"] = op_id
    if request_id:
        result["request_id"] = request_id
    return result


_GATEWAY_STATES = {
    "connecting",
    "connected",
    "paused",
    "needs_action",
    "error",
    "disconnected",
}
_GATEWAY_SCOPE_KEYS = ("files", "file_write", "code_execution", "browser", "computer_use")


def _bounded_gateway_status(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, str):
        return value[:2048]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    if depth >= 5:
        return None
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:64]:
            result[str(key)[:80]] = _bounded_gateway_status(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [
            _bounded_gateway_status(item, depth=depth + 1)
            for item in list(value)[:64]
        ]
    return str(value)[:2048]


def store_sid_launcher_gateway_metadata(
    sid: str,
    payload: dict[str, Any],
) -> LauncherGatewayMetadata | None:
    """Store a validated Launcher gateway declaration for one connector socket."""
    if str(payload.get("kind", "") or "").strip().lower() != "launcher":
        clear_sid_launcher_gateway_metadata(sid)
        return None
    try:
        version = int(payload.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    gateway_id = str(payload.get("id", "") or "").strip()[:128]
    if version != 1 or not gateway_id:
        clear_sid_launcher_gateway_metadata(sid)
        return None

    raw_scopes = payload.get("scopes")
    scopes = {
        key: bool(
            raw_scopes.get(key, raw_scopes.get("files") if key == "file_write" else False)
        ) if isinstance(raw_scopes, dict) else False
        for key in _GATEWAY_SCOPE_KEYS
    }
    if not scopes["files"]:
        scopes["file_write"] = False
    if not scopes["file_write"]:
        scopes["code_execution"] = False
    master_enabled = bool(payload.get("master_enabled", True))
    state = str(payload.get("state", "connected") or "").strip().lower()
    if state not in _GATEWAY_STATES:
        state = "connected" if master_enabled else "paused"
    if not master_enabled and state not in {"error", "needs_action", "disconnected"}:
        state = "paused"
    status_value = payload.get("status")
    status = _bounded_gateway_status(status_value) if isinstance(status_value, dict) else {}
    metadata = LauncherGatewayMetadata(
        gateway_id=gateway_id,
        host_label=str(payload.get("host_label", "") or "").strip()[:128],
        state=state,
        master_enabled=master_enabled,
        scopes=scopes,
        status=status,
        updated_at=time.time(),
    )
    with _state_lock:
        if sid in _replaced_gateway_sids:
            return None
        for other_sid, other in list(_sid_launcher_gateway_metadata.items()):
            if other_sid != sid and other.gateway_id == gateway_id:
                _sid_launcher_gateway_metadata.pop(other_sid, None)
                _replaced_gateway_sids.add(other_sid)
        _sid_launcher_gateway_metadata[sid] = metadata
    return metadata


def clear_sid_launcher_gateway_metadata(sid: str) -> None:
    with _state_lock:
        _sid_launcher_gateway_metadata.pop(sid, None)


def launcher_gateway_metadata_for_sid(sid: str) -> dict[str, Any] | None:
    with _state_lock:
        metadata = _sid_launcher_gateway_metadata.get(sid)
    if metadata is None:
        return None
    return _launcher_gateway_metadata_dict(metadata, sid=sid)


def _launcher_gateway_metadata_dict(
    metadata: LauncherGatewayMetadata,
    *,
    sid: str | None = None,
) -> dict[str, Any]:
    result = {
        "version": 1,
        "kind": "launcher",
        "id": metadata.gateway_id,
        "host_label": metadata.host_label,
        "state": metadata.state,
        "master_enabled": metadata.master_enabled,
        "scopes": dict(metadata.scopes),
        "status": copy.deepcopy(metadata.status),
        "updated_at": metadata.updated_at,
    }
    if sid is not None:
        result["sid"] = sid
    return result


def _active_launcher_gateways_locked() -> list[tuple[str, LauncherGatewayMetadata]]:
    return sorted(
        (
            (sid, metadata)
            for sid, metadata in _sid_launcher_gateway_metadata.items()
            if sid in _sid_contexts and sid not in _replaced_gateway_sids
        ),
        key=lambda item: item[1].updated_at,
        reverse=True,
    )


def _active_launcher_gateway_sid_locked() -> str | None:
    gateways = _active_launcher_gateways_locked()
    if len({metadata.gateway_id for _sid, metadata in gateways}) != 1:
        return None
    return gateways[0][0] if gateways else None


def active_launcher_gateway_sid() -> str | None:
    with _state_lock:
        return _active_launcher_gateway_sid_locked()


def launcher_gateway_status() -> dict[str, Any]:
    with _state_lock:
        gateways = _active_launcher_gateways_locked()
        distinct_ids = {metadata.gateway_id for _sid, metadata in gateways}
        rows = [
            _launcher_gateway_metadata_dict(metadata)
            for _sid, metadata in gateways
        ]
    if not rows:
        return {
            "state": "disconnected",
            "connected": False,
            "multiple_hosts": False,
            "gateway": None,
            "gateways": [],
        }
    if len(distinct_ids) > 1:
        return {
            "state": "multiple_hosts",
            "connected": False,
            "multiple_hosts": True,
            "gateway": None,
            "gateways": rows,
            "error": "Multiple Launcher hosts are connected; host tools are disabled.",
        }
    gateway = rows[0]
    return {
        "state": gateway["state"],
        "connected": gateway["state"] not in {"disconnected", "error"},
        "multiple_hosts": False,
        "gateway": gateway,
        "gateways": rows,
    }


def _candidate_sids_for_context_locked(context_id: str) -> list[str]:
    context_sids = sorted(_context_subscriptions.get(context_id, set()))
    context_set = set(context_sids)
    gateway_sid = _active_launcher_gateway_sid_locked()
    gateway_sids = [gateway_sid] if gateway_sid and gateway_sid not in context_set else []
    global_sids = sorted(
        sid
        for sid in _sid_contexts
        if sid not in context_set
        and sid not in _sid_launcher_gateway_metadata
        and sid not in _replaced_gateway_sids
    )
    return context_sids + gateway_sids + global_sids


def remote_tool_sids_for_context(context_id: str) -> list[str]:
    """Return connected CLI candidates, preferring clients subscribed to context_id."""
    with _state_lock:
        return _candidate_sids_for_context_locked(context_id)


def store_remote_tree_snapshot(
    sid: str,
    payload: dict[str, Any],
) -> RemoteTreeSnapshot:
    snapshot = RemoteTreeSnapshot(
        sid=sid,
        payload=dict(payload),
        updated_at=time.time(),
    )
    with _state_lock:
        _remote_tree_snapshots[sid] = snapshot
    return snapshot


def clear_remote_tree_snapshot(sid: str) -> None:
    with _state_lock:
        _remote_tree_snapshots.pop(sid, None)


def latest_remote_tree_for_context(
    context_id: str,
    *,
    max_age_seconds: float = 90.0,
) -> dict[str, Any] | None:
    now = time.time()
    with _state_lock:
        candidates = _candidate_sids_for_context_locked(context_id)
        context_sids = set(_context_subscriptions.get(context_id, set()))
        snapshot_groups = [
            [_remote_tree_snapshots[sid] for sid in candidates if sid in context_sids and sid in _remote_tree_snapshots],
            [_remote_tree_snapshots[sid] for sid in candidates if sid not in context_sids and sid in _remote_tree_snapshots],
        ]

    for snapshots in snapshot_groups:
        snapshots.sort(key=lambda item: item.updated_at, reverse=True)
        for snapshot in snapshots:
            if max_age_seconds > 0 and now - snapshot.updated_at > max_age_seconds:
                continue
            payload = dict(snapshot.payload)
            payload["sid"] = snapshot.sid
            payload["updated_at"] = snapshot.updated_at
            return payload
    return None


def select_target_sid(context_id: str) -> str | None:
    with _state_lock:
        subscribers = _context_subscriptions.get(context_id, set())
        if not subscribers:
            return None
        return sorted(subscribers)[0]


def store_sid_remote_file_metadata(sid: str, payload: dict[str, Any]) -> RemoteFileMetadata:
    write_enabled = bool(payload.get("write_enabled"))
    mode = str(payload.get("mode", "") or "").strip().lower()
    if mode not in {"read_only", "read_write"}:
        mode = "read_write" if write_enabled else "read_only"
    metadata = RemoteFileMetadata(
        enabled=bool(payload.get("enabled", True)),
        write_enabled=write_enabled,
        mode=mode,
        updated_at=time.time(),
        file_browser=payload.get("file_browser") == 1,
        root_path=str(payload.get("root_path") or "")[:4096],
    )
    with _state_lock:
        _sid_remote_file_metadata[sid] = metadata
    return metadata


def clear_sid_remote_file_metadata(sid: str) -> None:
    with _state_lock:
        _sid_remote_file_metadata.pop(sid, None)


def remote_file_metadata_for_sid(sid: str) -> dict[str, Any] | None:
    with _state_lock:
        metadata = _sid_remote_file_metadata.get(sid)
        snapshot = _remote_tree_snapshots.get(sid)
    if metadata is None:
        return None
    return {
        "file_browser": metadata.file_browser,
        "root_path": metadata.root_path or (str(snapshot.payload.get("root_path") or "") if snapshot else ""),
        "enabled": metadata.enabled,
        "write_enabled": metadata.write_enabled,
        "mode": metadata.mode,
        "updated_at": metadata.updated_at,
    }


def select_remote_file_target_sid(context_id: str, *, require_writes: bool = False) -> str | None:
    with _state_lock:
        for sid in _candidate_sids_for_context_locked(context_id):
            metadata = _sid_remote_file_metadata.get(sid)
            if metadata is None:
                continue
            if not metadata.enabled:
                continue
            if require_writes and not metadata.write_enabled:
                continue
            return sid
    return None


def store_sid_remote_exec_metadata(sid: str, payload: dict[str, Any]) -> RemoteExecMetadata:
    metadata = RemoteExecMetadata(
        enabled=bool(payload.get("enabled")),
        updated_at=time.time(),
    )
    with _state_lock:
        _sid_remote_exec_metadata[sid] = metadata
    return metadata


def clear_sid_remote_exec_metadata(sid: str) -> None:
    with _state_lock:
        _sid_remote_exec_metadata.pop(sid, None)


def remote_exec_metadata_for_sid(sid: str) -> dict[str, Any] | None:
    with _state_lock:
        metadata = _sid_remote_exec_metadata.get(sid)
    if metadata is None:
        return None
    return {
        "enabled": metadata.enabled,
        "updated_at": metadata.updated_at,
    }


def select_remote_exec_target_sid(context_id: str, *, require_writes: bool = False) -> str | None:
    with _state_lock:
        for sid in _candidate_sids_for_context_locked(context_id):
            metadata = _sid_remote_exec_metadata.get(sid)
            if metadata is None:
                continue
            if metadata.enabled:
                if require_writes:
                    file_metadata = _sid_remote_file_metadata.get(sid)
                    if file_metadata is None or (
                        not file_metadata.enabled or not file_metadata.write_enabled
                    ):
                        continue
                return sid
    return None


def store_sid_computer_use_metadata(sid: str, payload: dict[str, Any]) -> ComputerUseMetadata:
    features_value = payload.get("features")
    if isinstance(features_value, (list, tuple)):
        features = tuple(str(item).strip() for item in features_value if str(item).strip())
    else:
        features = ()
    capabilities_value = payload.get("capabilities")
    capabilities = copy.deepcopy(capabilities_value) if isinstance(capabilities_value, dict) else {}
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except (TypeError, ValueError):
        contract_version = 0
    metadata = ComputerUseMetadata(
        supported=bool(payload.get("supported")),
        enabled=bool(payload.get("supported")) and bool(payload.get("enabled")),
        trust_mode=str(payload.get("trust_mode", "") or "").strip(),
        status=str(payload.get("status", "") or "").strip(),
        last_error=str(payload.get("last_error", "") or "").strip(),
        restore_token_present=bool(payload.get("restore_token_present")),
        artifact_root=str(payload.get("artifact_root", "") or "").strip(),
        backend_id=str(payload.get("backend_id", "") or "").strip(),
        backend_family=str(payload.get("backend_family", "") or "").strip(),
        durable_instance_id=_durable_browser_instance(payload.get("durable_instance_id")),
        features=features,
        contract_version=contract_version,
        capabilities=capabilities,
        support_reason=str(payload.get("support_reason", "") or "").strip(),
        updated_at=time.time(),
    )
    with _state_lock:
        _sid_computer_use_metadata[sid] = metadata
    return metadata


def clear_sid_computer_use_metadata(sid: str) -> None:
    with _state_lock:
        _sid_computer_use_metadata.pop(sid, None)


def computer_use_metadata_for_sid(sid: str) -> dict[str, Any] | None:
    with _state_lock:
        metadata = _sid_computer_use_metadata.get(sid)
    if metadata is None:
        return None
    return {
        "supported": metadata.supported,
        "enabled": metadata.enabled,
        "trust_mode": metadata.trust_mode,
        "status": metadata.status,
        "last_error": metadata.last_error,
        "restore_token_present": metadata.restore_token_present,
        "artifact_root": metadata.artifact_root,
        "backend_id": metadata.backend_id,
        "backend_family": metadata.backend_family,
        "durable_instance_id": metadata.durable_instance_id,
        "features": list(metadata.features),
        "contract_version": metadata.contract_version,
        "capabilities": copy.deepcopy(metadata.capabilities),
        "support_reason": metadata.support_reason,
        "updated_at": metadata.updated_at,
    }


def _durable_browser_instance(value):
    return value if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value) else ""


def store_sid_host_browser_metadata(sid: str, payload: dict[str, Any]) -> HostBrowserMetadata:
    features_value = payload.get("features")
    if isinstance(features_value, (list, tuple)):
        features = tuple(str(item).strip() for item in features_value if str(item).strip())
    else:
        features = ()
    support_reason = str(payload.get("support_reason", "") or "").strip()
    metadata = HostBrowserMetadata(
        supported=bool(payload.get("supported")),
        can_prepare=_host_browser_can_prepare(payload, features=features, support_reason=support_reason),
        enabled=bool(payload.get("supported")) and bool(payload.get("enabled")),
        status=str(payload.get("status", "") or "").strip(),
        browser_family=str(payload.get("browser_family", "") or "").strip(),
        profile_label=str(payload.get("profile_label", "") or "").strip(),
        profile_path=str(payload.get("profile_path", "") or "").strip(),
        cdp_endpoint=str(payload.get("cdp_endpoint", "") or "").strip(),
        browser_id=str(payload.get("browser_id", payload.get("browser_selection", "")) or "").strip(),
        browser_label=str(payload.get("browser_label", "") or "").strip(),
        available_browsers=_normalize_available_host_browsers(payload.get("available_browsers")),
        content_helper_sha256=str(payload.get("content_helper_sha256", "") or "").strip().lower(),
        durable_instance_id=_durable_browser_instance(payload.get("durable_instance_id")),
        features=features,
        support_reason=support_reason,
        updated_at=time.time(),
    )
    with _state_lock:
        _sid_host_browser_metadata[sid] = metadata
    return metadata


def _host_browser_can_prepare(
    payload: dict[str, Any],
    *,
    features: tuple[str, ...],
    support_reason: str,
) -> bool:
    if "can_prepare" in payload:
        return bool(payload.get("can_prepare"))
    if "ensure" not in features:
        return False
    reason = support_reason.lower()
    return (
        "python playwright" in reason
        or "a0-controlled local profile" in reason
        or "chrome-a0" in reason
        or "remote debugging" in reason
    )


def _normalize_available_host_browsers(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    browsers: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        browser_id = str(item.get("id", item.get("browser_id", item.get("selection", ""))) or "").strip()
        family = str(item.get("family", item.get("browser_family", "")) or "").strip()
        label = str(item.get("label", item.get("name", "")) or "").strip()
        cdp_endpoint = str(item.get("cdp_endpoint", "") or "").strip()
        status = str(item.get("status", "") or "").strip()
        enabled = bool(item.get("enabled", True))
        if not any((browser_id, family, label, cdp_endpoint)):
            continue
        browsers.append({
            "id": browser_id or family or cdp_endpoint,
            "family": family,
            "label": label or family or browser_id or cdp_endpoint,
            "cdp_endpoint": cdp_endpoint,
            "status": status,
            "enabled": enabled,
        })
    return tuple(browsers)


def clear_sid_host_browser_metadata(sid: str) -> None:
    with _state_lock:
        _sid_host_browser_metadata.pop(sid, None)


def host_browser_metadata_for_sid(sid: str) -> dict[str, Any] | None:
    with _state_lock:
        metadata = _sid_host_browser_metadata.get(sid)
    if metadata is None:
        return None
    return {
        "supported": metadata.supported,
        "can_prepare": metadata.can_prepare,
        "enabled": metadata.enabled,
        "status": metadata.status,
        "browser_family": metadata.browser_family,
        "profile_label": metadata.profile_label,
        "profile_path": metadata.profile_path,
        "cdp_endpoint": metadata.cdp_endpoint,
        "browser_id": metadata.browser_id,
        "browser_label": metadata.browser_label,
        "available_browsers": copy.deepcopy(list(metadata.available_browsers)),
        "content_helper_sha256": metadata.content_helper_sha256,
        "durable_instance_id": metadata.durable_instance_id,
        "features": list(metadata.features),
        "support_reason": metadata.support_reason,
        "updated_at": metadata.updated_at,
    }


def select_host_browser_target_sid(context_id: str) -> str | None:
    with _state_lock:
        fallback: str | None = None
        for sid in _candidate_sids_for_context_locked(context_id):
            metadata = _sid_host_browser_metadata.get(sid)
            if not metadata:
                continue
            if not metadata.supported:
                continue
            if metadata.enabled and metadata.status in {"ready", "active"}:
                return sid
            if metadata.enabled and fallback is None:
                fallback = sid
    return fallback


def select_host_browser_candidate_sid(context_id: str) -> str | None:
    with _state_lock:
        fallback: str | None = None
        for sid in _candidate_sids_for_context_locked(context_id):
            metadata = _sid_host_browser_metadata.get(sid)
            if not metadata or not (metadata.supported or metadata.can_prepare):
                continue
            if metadata.enabled and metadata.status in {"ready", "active"}:
                return sid
            if metadata.enabled and fallback is None:
                fallback = sid
            elif fallback is None:
                fallback = sid
    return fallback


def host_browser_metadata_for_context(context_id: str) -> list[dict[str, Any]]:
    with _state_lock:
        candidates = _candidate_sids_for_context_locked(context_id)
    rows: list[dict[str, Any]] = []
    for sid in candidates:
        metadata = host_browser_metadata_for_sid(sid)
        if metadata is not None:
            metadata["sid"] = sid
            rows.append(metadata)
    return rows


def all_host_browser_metadata() -> list[dict[str, Any]]:
    with _state_lock:
        items = sorted(_sid_host_browser_metadata.items())
    rows: list[dict[str, Any]] = []
    for sid, metadata in items:
        rows.append(
            {
                "sid": sid,
                "supported": metadata.supported,
                "enabled": metadata.enabled,
                "status": metadata.status,
                "browser_family": metadata.browser_family,
                "profile_label": metadata.profile_label,
                "profile_path": metadata.profile_path,
                "cdp_endpoint": metadata.cdp_endpoint,
                "browser_id": metadata.browser_id,
                "browser_label": metadata.browser_label,
                "available_browsers": copy.deepcopy(list(metadata.available_browsers)),
                "content_helper_sha256": metadata.content_helper_sha256,
                "durable_instance_id": metadata.durable_instance_id,
                "features": list(metadata.features),
                "support_reason": metadata.support_reason,
                "updated_at": metadata.updated_at,
            }
        )
    return rows


def select_computer_use_target_sid(context_id: str) -> str | None:
    with _state_lock:
        for sid in _candidate_sids_for_context_locked(context_id):
            metadata = _sid_computer_use_metadata.get(sid)
            if metadata and metadata.supported and metadata.enabled:
                return sid
    return None


def start_incoming_transfer(
    sid: str,
    payload: dict[str, Any],
    *,
    max_bytes: int,
) -> str:
    transfer_id = str(payload.get("transfer_id") or "")
    kind = str(payload.get("kind") or "")
    op_id = str(payload.get("op_id") or "")
    raw_context_id = payload.get("context_id")
    context_id = _transfer_context_id(raw_context_id)
    try:
        total_bytes = int(payload.get("total_bytes"))
    except (TypeError, ValueError):
        total_bytes = -1
    sha256 = str(payload.get("sha256") or "").lower()

    with _state_lock:
        concurrent = sum(
            1 for transfer in _incoming_transfers.values() if transfer.sid == sid
        )
        duplicate = transfer_id in _incoming_transfers
    if not transfer_id or len(transfer_id) > 128:
        return "transfer_id must be a non-empty string up to 128 characters"
    if duplicate:
        return "transfer_id is already active"
    if concurrent >= MAX_INCOMING_TRANSFERS_PER_SID:
        return "too many concurrent transfers"
    if kind not in _TRANSFER_RESULT_EVENTS:
        return f"unsupported transfer kind: {kind or '<missing>'}"
    if not op_id or len(op_id) > 256:
        return "op_id must be a non-empty string up to 256 characters"
    if raw_context_id is not None and (
        not isinstance(raw_context_id, str)
        or (str(raw_context_id).strip() and context_id is None)
    ):
        return "context_id must be a string up to 256 characters"
    if total_bytes < 0:
        return "total_bytes must be a non-negative integer"
    if total_bytes > max_bytes:
        return f"declared transfer size {total_bytes} exceeds the receiver limit {max_bytes}"
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        return "sha256 must be a 64-character hexadecimal digest"

    temp_path: Path | None = None
    buffer: bytearray | None = bytearray()
    if total_bytes > TRANSFER_SPOOL_THRESHOLD_BYTES:
        fd, temp_name = tempfile.mkstemp(prefix="a0-transfer-")
        os.close(fd)
        temp_path = Path(temp_name)
        buffer = None
    transfer = IncomingTransfer(
        transfer_id=transfer_id,
        sid=sid,
        kind=kind,
        op_id=op_id,
        context_id=_pending_transfer_context_id(kind, op_id, sid=sid) or context_id,
        total_bytes=total_bytes,
        sha256=sha256,
        digest=hashlib.sha256(),
        updated_at=time.monotonic(),
        buffer=buffer,
        temp_path=temp_path,
    )
    with _state_lock:
        _incoming_transfers[transfer_id] = transfer
        _arm_transfer_timeout(transfer)
    return ""


def append_incoming_transfer(
    sid: str,
    payload: dict[str, Any],
) -> str:
    transfer_id = str(payload.get("transfer_id") or "")
    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
    if transfer is None or transfer.sid != sid:
        return "transfer is not active"
    try:
        index = int(payload.get("index"))
    except (TypeError, ValueError):
        return "chunk index must be an integer"
    encoded = payload.get("data")
    if not isinstance(encoded, str) or len(encoded) > _TRANSFER_ENCODED_CHUNK_MAX:
        return "chunk data exceeds the 64 KiB limit"
    try:
        chunk = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error):
        return "chunk data is not valid base64"

    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
        if transfer is None or transfer.sid != sid:
            return "transfer is not active"
        expected_bytes = min(
            TRANSFER_CHUNK_BYTES,
            transfer.total_bytes - transfer.received_bytes,
        )
        if index != transfer.next_index:
            return f"chunk index {index} arrived; expected {transfer.next_index}"
        if len(chunk) != expected_bytes:
            return f"chunk {index} has {len(chunk)} bytes; expected {expected_bytes}"
        try:
            if transfer.buffer is not None:
                transfer.buffer.extend(chunk)
            elif transfer.temp_path is not None:
                with transfer.temp_path.open("ab") as handle:
                    handle.write(chunk)
        except OSError as exc:
            return f"could not spool transfer: {exc}"
        transfer.digest.update(chunk)
        transfer.received_bytes += len(chunk)
        transfer.next_index += 1
        transfer.updated_at = time.monotonic()
    return ""


def finish_incoming_transfer(
    sid: str,
    payload: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None, str]:
    transfer_id = str(payload.get("transfer_id") or "")
    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
    if transfer is None or transfer.sid != sid:
        return None, None, "transfer is not active"
    if transfer.received_bytes != transfer.total_bytes:
        return (
            None,
            None,
            f"transfer ended at {transfer.received_bytes} of {transfer.total_bytes} bytes",
        )
    if transfer.digest.hexdigest() != transfer.sha256:
        return None, None, "transfer SHA-256 mismatch"
    try:
        raw = (
            bytes(transfer.buffer)
            if transfer.buffer is not None
            else transfer.temp_path.read_bytes() if transfer.temp_path is not None else b""
        )
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("decoded transfer is not a JSON object")
        result_op_id = str(result.get("op_id") or result.get("request_id") or "")
        if result_op_id != transfer.op_id:
            raise ValueError("decoded operation id does not match transfer_start")
    except Exception as exc:
        return None, None, f"invalid transferred payload: {exc}"

    kind = transfer.kind
    _drop_incoming_transfer(transfer_id)
    return kind, result, ""


def abort_incoming_transfer(
    sid: str,
    payload: dict[str, Any],
    *,
    reason: str = "",
) -> bool:
    transfer_id = str(payload.get("transfer_id") or "")
    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
        outgoing = _outgoing_transfers.get(transfer_id)
    if transfer is not None and transfer.sid != sid:
        return False
    if outgoing is not None and outgoing.sid != sid:
        return False
    active = transfer or outgoing
    kind = active.kind if active is not None else str(payload.get("kind") or "")
    op_id = active.op_id if active is not None else str(payload.get("op_id") or "")
    dropped = _drop_incoming_transfer(transfer_id)
    failure = reason or str(payload.get("reason") or "transfer aborted")
    if outgoing is not None:
        outgoing.cancel_reason = failure[:512]
        outgoing.abort_sent = True
        with _state_lock:
            _outgoing_transfers.pop(transfer_id, None)
    failed_pending = _fail_transfer_pending(kind, op_id, sid=sid, error=failure)
    return dropped or outgoing is not None or failed_pending


def incoming_transfer_metadata(
    sid: str,
    transfer_id: str,
) -> dict[str, str]:
    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
    if transfer is None or transfer.sid != sid:
        return {}
    return {"op_id": transfer.op_id, "kind": transfer.kind}


def abort_incoming_transfers_for_sid(sid: str, *, reason: str) -> None:
    with _state_lock:
        transfer_ids = [
            transfer_id
            for transfer_id, transfer in _incoming_transfers.items()
            if transfer.sid == sid
        ]
    for transfer_id in transfer_ids:
        abort_incoming_transfer(
            sid,
            {"transfer_id": transfer_id},
            reason=reason,
        )


def _take_context_transfers(context_id: str, reason: str) -> list:
    normalized_context_id = _transfer_context_id(context_id)
    if normalized_context_id is None:
        return []
    with _state_lock:
        incoming = [
            transfer
            for transfer in _incoming_transfers.values()
            if transfer.context_id == normalized_context_id
        ]
        outgoing = [
            transfer
            for transfer in _outgoing_transfers.values()
            if transfer.context_id == normalized_context_id
        ]
        for transfer in outgoing:
            transfer.cancel_reason = reason[:512]
            transfer.abort_sent = True
            _outgoing_transfers.pop(transfer.transfer_id, None)

    for transfer in incoming:
        _drop_incoming_transfer(transfer.transfer_id)
    for transfer in [*incoming, *outgoing]:
        _fail_transfer_pending(
            transfer.kind,
            transfer.op_id,
            sid=transfer.sid,
            error=reason,
        )

    return [*incoming, *outgoing]


async def _notify_transfer_aborts(transfers: list, reason: str, manager: Any = None) -> None:
    if not transfers:
        return
    ws_manager = manager or get_shared_ws_manager()
    for transfer in transfers:
        with contextlib.suppress(Exception):
            await ws_manager.emit_to(
                "/ws",
                transfer.sid,
                "connector_transfer_abort",
                {
                    "transfer_id": transfer.transfer_id,
                    "op_id": transfer.op_id,
                    "kind": transfer.kind,
                    "reason": reason[:512],
                },
                handler_id="plugins/_a0_connector/api/ws_connector",
                max_payload_bytes=ws_max_payload_bytes_for_sid(transfer.sid),
            )


async def abort_transfers_for_context(context_id: str, *, reason: str, manager: Any = None) -> int:
    transfers = _take_context_transfers(context_id, reason)
    await _notify_transfer_aborts(transfers, reason, manager)
    return len(transfers)


def cancel_context_transfers(context_id: str) -> None:
    """Release transfer state before a synchronous context shutdown kills its task."""
    from helpers.defer import DeferredTask, THREAD_BACKGROUND
    reason = "chat stopped during transfer"
    transfers = _take_context_transfers(context_id, reason)
    if transfers:
        DeferredTask(thread_name=THREAD_BACKGROUND).start_task(_notify_transfer_aborts, transfers, reason)


def _transfer_context_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    context_id = value.strip()
    return context_id if context_id and len(context_id) <= 256 else None


def _pending_transfer_context_id(
    kind: str,
    op_id: str,
    *,
    sid: str,
) -> str | None:
    pending_by_kind = {
        "connector_file_op_result": _pending_file_ops,
        "connector_exec_op_result": _pending_exec_ops,
        "connector_computer_use_op_result": _pending_computer_use_ops,
        "connector_browser_op_result": _pending_browser_ops,
    }
    with _state_lock:
        pending = pending_by_kind.get(kind, {}).get(op_id)
        if pending is None or pending.sid != sid:
            return None
        return _transfer_context_id(getattr(pending, "context_id", None))


def _arm_transfer_timeout(transfer: IncomingTransfer, delay: float | None = None) -> None:
    timeout = threading.Timer(
        delay if delay is not None else TRANSFER_IDLE_TIMEOUT_SECONDS,
        _expire_incoming_transfer,
        args=(transfer.transfer_id,),
    )
    timeout.daemon = True
    transfer.timeout = timeout
    timeout.start()


def _expire_incoming_transfer(transfer_id: str) -> None:
    with _state_lock:
        transfer = _incoming_transfers.get(transfer_id)
        if transfer is None:
            return
        remaining = TRANSFER_IDLE_TIMEOUT_SECONDS - (
            time.monotonic() - transfer.updated_at
        )
        if remaining > 0:
            _arm_transfer_timeout(transfer, remaining)
            return
        sid = transfer.sid
        kind = transfer.kind
        op_id = transfer.op_id
    _drop_incoming_transfer(transfer_id)
    _fail_transfer_pending(
        kind,
        op_id,
        sid=sid,
        error=f"transfer idle timeout after {TRANSFER_IDLE_TIMEOUT_SECONDS:g} seconds",
    )


def _drop_incoming_transfer(transfer_id: str) -> bool:
    with _state_lock:
        transfer = _incoming_transfers.pop(transfer_id, None)
    if transfer is None:
        return False
    if transfer.timeout is not None:
        transfer.timeout.cancel()
    if transfer.temp_path is not None:
        with contextlib.suppress(FileNotFoundError):
            transfer.temp_path.unlink()
    return True


def _fail_transfer_pending(
    kind: str,
    op_id: str,
    *,
    sid: str,
    error: str,
) -> bool:
    pending_by_kind = {
        "connector_file_op": _pending_file_ops,
        "connector_file_op_result": _pending_file_ops,
        "connector_exec_op": _pending_exec_ops,
        "connector_exec_op_result": _pending_exec_ops,
        "connector_computer_use_op": _pending_computer_use_ops,
        "connector_computer_use_op_result": _pending_computer_use_ops,
        "connector_browser_op": _pending_browser_ops,
        "connector_browser_op_result": _pending_browser_ops,
        "connector_gateway_control": _pending_gateway_controls,
        "connector_gateway_control_result": _pending_gateway_controls,
    }
    pending = pending_by_kind.get(kind)
    if pending is None or not op_id:
        return False
    return _fail_pending(pending, op_id, sid=sid, error=error)


def store_pending_file_op(
    op_id: str,
    *,
    sid: str,
    future: asyncio.Future[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
    context_id: str | None = None,
) -> None:
    with _state_lock:
        _pending_file_ops[op_id] = PendingFileOperation(
            sid=sid,
            loop=loop,
            future=future,
            context_id=context_id,
        )


def clear_pending_file_op(op_id: str) -> None:
    with _state_lock:
        _pending_file_ops.pop(op_id, None)


def resolve_pending_file_op(
    op_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    if payload.get("chunked") is True:
        return _fail_pending(
            _pending_file_ops,
            op_id,
            sid=sid,
            error=(
                "Legacy chunked file results are not supported. Upgrade the CLI so it "
                "can negotiate transfer_protocol=1."
            ),
        )
    return _resolve_pending(_pending_file_ops, op_id, sid=sid, payload=payload)


def fail_pending_file_op(
    op_id: str,
    *,
    sid: str | None = None,
    error: str,
) -> bool:
    return _fail_pending(_pending_file_ops, op_id, sid=sid, error=error)


def fail_pending_file_ops_for_sid(sid: str, *, error: str) -> None:
    _fail_pending_for_sid(_pending_file_ops, sid=sid, error=error)


def store_pending_exec_op(
    op_id: str,
    *,
    sid: str,
    future: asyncio.Future[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
    context_id: str | None = None,
) -> None:
    with _state_lock:
        _pending_exec_ops[op_id] = PendingExecOperation(
            sid=sid,
            loop=loop,
            future=future,
            context_id=context_id,
        )


def clear_pending_exec_op(op_id: str) -> None:
    with _state_lock:
        _pending_exec_ops.pop(op_id, None)


def resolve_pending_exec_op(
    op_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    return _resolve_pending(_pending_exec_ops, op_id, sid=sid, payload=payload)


def fail_pending_exec_op(
    op_id: str,
    *,
    sid: str | None = None,
    error: str,
) -> bool:
    return _fail_pending(_pending_exec_ops, op_id, sid=sid, error=error)


def fail_pending_exec_ops_for_sid(sid: str, *, error: str) -> None:
    _fail_pending_for_sid(_pending_exec_ops, sid=sid, error=error)


def store_pending_computer_use_op(
    op_id: str,
    *,
    sid: str,
    future: asyncio.Future[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
    context_id: str | None = None,
) -> None:
    with _state_lock:
        _pending_computer_use_ops[op_id] = PendingComputerUseOperation(
            sid=sid,
            loop=loop,
            future=future,
            context_id=context_id,
        )


def clear_pending_computer_use_op(op_id: str) -> None:
    with _state_lock:
        _pending_computer_use_ops.pop(op_id, None)


def resolve_pending_computer_use_op(
    op_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    return _resolve_pending(_pending_computer_use_ops, op_id, sid=sid, payload=payload)


def fail_pending_computer_use_op(
    op_id: str,
    *,
    sid: str | None = None,
    error: str,
) -> bool:
    return _fail_pending(_pending_computer_use_ops, op_id, sid=sid, error=error)


def fail_pending_computer_use_ops_for_sid(sid: str, *, error: str) -> None:
    _fail_pending_for_sid(_pending_computer_use_ops, sid=sid, error=error)


def store_pending_browser_op(
    op_id: str,
    *,
    sid: str,
    future: asyncio.Future[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
    context_id: str | None = None,
) -> None:
    with _state_lock:
        _pending_browser_ops[op_id] = PendingBrowserOperation(
            sid=sid,
            loop=loop,
            future=future,
            context_id=context_id,
        )


def clear_pending_browser_op(op_id: str) -> None:
    with _state_lock:
        _pending_browser_ops.pop(op_id, None)


def resolve_pending_browser_op(
    op_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    return _resolve_pending(_pending_browser_ops, op_id, sid=sid, payload=payload)


def fail_pending_browser_op(
    op_id: str,
    *,
    sid: str | None = None,
    error: str,
) -> bool:
    return _fail_pending(_pending_browser_ops, op_id, sid=sid, error=error)


def fail_pending_browser_ops_for_sid(sid: str, *, error: str) -> None:
    _fail_pending_for_sid(_pending_browser_ops, sid=sid, error=error)


def store_pending_gateway_control(
    request_id: str,
    *,
    sid: str,
    future: asyncio.Future[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
) -> None:
    with _state_lock:
        _pending_gateway_controls[request_id] = PendingGatewayControl(
            sid=sid,
            loop=loop,
            future=future,
        )


def clear_pending_gateway_control(request_id: str) -> None:
    with _state_lock:
        _pending_gateway_controls.pop(request_id, None)


def resolve_pending_gateway_control(
    request_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    gateway = payload.get("gateway")
    if isinstance(gateway, dict):
        stored = store_sid_launcher_gateway_metadata(sid, gateway)
        if stored is not None:
            active = stored.master_enabled and stored.state != "disconnected"
            files_enabled = active and stored.scopes["files"]
            writes_enabled = files_enabled and stored.scopes["file_write"]
            store_sid_remote_file_metadata(
                sid,
                {
                    **(remote_file_metadata_for_sid(sid) or {}),
                    "enabled": files_enabled,
                    "write_enabled": writes_enabled,
                    "mode": "read_write" if writes_enabled else "read_only",
                },
            )
            store_sid_remote_exec_metadata(
                sid,
                {"enabled": active and stored.scopes["code_execution"]},
            )
    return _resolve_pending(_pending_gateway_controls, request_id, sid=sid, payload=payload)


def fail_pending_gateway_controls_for_sid(sid: str, *, error: str) -> None:
    _fail_pending_for_sid(_pending_gateway_controls, sid=sid, error=error)


def _resolve_pending(
    registry: dict[
        str,
        PendingFileOperation
        | PendingExecOperation
        | PendingComputerUseOperation
        | PendingBrowserOperation
        | PendingGatewayControl,
    ],
    op_id: str,
    *,
    sid: str,
    payload: dict[str, Any],
) -> bool:
    with _state_lock:
        pending = registry.get(op_id)
        if pending is None or pending.sid != sid:
            return False
        registry.pop(op_id, None)

    pending.loop.call_soon_threadsafe(_set_future_result, pending.future, dict(payload))
    return True


def _fail_pending(
    registry: dict[
        str,
        PendingFileOperation
        | PendingExecOperation
        | PendingComputerUseOperation
        | PendingBrowserOperation
        | PendingGatewayControl,
    ],
    op_id: str,
    *,
    sid: str | None,
    error: str,
) -> bool:
    with _state_lock:
        pending = registry.get(op_id)
        if pending is None:
            return False
        if sid is not None and pending.sid != sid:
            return False
        registry.pop(op_id, None)

    pending.loop.call_soon_threadsafe(
        _set_future_result,
        pending.future,
        {"op_id": op_id, "ok": False, "error": error},
    )
    return True


def _fail_pending_for_sid(
    registry: dict[
        str,
        PendingFileOperation
        | PendingExecOperation
        | PendingComputerUseOperation
        | PendingBrowserOperation
        | PendingGatewayControl,
    ],
    *,
    sid: str,
    error: str,
) -> None:
    with _state_lock:
        matches = [
            (op_id, pending)
            for op_id, pending in registry.items()
            if pending.sid == sid
        ]
        for op_id, _pending in matches:
            registry.pop(op_id, None)

    for op_id, pending in matches:
        pending.loop.call_soon_threadsafe(
            _set_future_result,
            pending.future,
            {"op_id": op_id, "ok": False, "error": error},
        )


def _set_future_result(
    future: asyncio.Future[dict[str, Any]],
    payload: dict[str, Any],
) -> None:
    if not future.done():
        future.set_result(payload)
