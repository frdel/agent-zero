import fnmatch
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import glob
import json
import os
import tempfile
import threading
from typing import Any

from helpers.files import get_abs_path

_runtime_lock = threading.RLock()
_runtime_store: dict[str, Any] = {}

_persistent_lock = threading.RLock()


@dataclass
class _ScopedStore:
    context_id: str
    values: dict
    allowed: frozenset
    guard: Any


_scope: ContextVar[_ScopedStore | None] = ContextVar("durable_kvp_scope", default=None)


@contextmanager
def context_scope(context_id: str, values: dict, allowed, *, guard):
    """Route declared keys to context-local checkpoint state, never global files.

    Keys are namespaced as ``runtime:<key>`` / ``persistent:<key>``. Unknown
    access fails closed while scoped. Caller commits this map with its checkpoint.
    Child async tasks inherit this scope; the supplied claim/generation guard
    must reject writes after run ownership ends.
    """
    if not context_id or type(values) is not dict or not callable(guard):
        raise ValueError("Invalid context KVP scope")
    allowed = frozenset(allowed)
    for qualified in allowed:
        if not isinstance(qualified, str) or ":" not in qualified:
            raise ValueError("Invalid declared KVP key")
        kind, key = qualified.split(":", 1)
        if kind not in {"runtime", "persistent"}:
            raise ValueError("Invalid declared KVP kind")
        _validate_key(key)
    if set(values) - allowed:
        raise ValueError("Undeclared context KVP state")
    guard()
    token = _scope.set(_ScopedStore(context_id, values, allowed, guard))
    try:
        yield values
    finally:
        _scope.reset(token)


def _scoped(kind: str, key: str):
    scope = _scope.get()
    if scope is None:
        return None
    _validate_key(key)
    qualified = kind + ":" + key
    if qualified not in scope.allowed:
        raise RuntimeError("Durable KVP key requires an explicit state adapter")
    scope.guard()
    return scope, qualified


def _scoped_find(kind: str, pattern: str):
    scope = _scope.get()
    if scope is None:
        return None
    scope.guard()
    prefix = kind + ":"
    return sorted(key[len(prefix):] for key in scope.values
                  if key.startswith(prefix) and fnmatch.fnmatch(key[len(prefix):], pattern))


def _scoped_value(value):
    # Persistent and runtime scoped values share the strict checkpoint contract.
    from helpers.durable.state_adapters import _json
    return json.loads(_json(value))


def _persistent_dir() -> str:
    return get_abs_path("usr", "kvp")


def _validate_key(key: str) -> None:
    if not key:
        raise ValueError("key must not be empty")
    if "\x00" in key:
        raise ValueError("key contains NUL")
    if "/" in key or os.path.sep in key or (os.path.altsep and os.path.altsep in key):
        raise ValueError("key must not contain path separators")


def _key_to_path(key: str) -> str:
    _validate_key(key)
    return os.path.join(_persistent_dir(), f"{key}.json")


def get_runtime(key: str, default: Any = None) -> Any:
    scoped = _scoped("runtime", key)
    if scoped:
        scope, qualified = scoped
        return _scoped_value(scope.values[qualified]) if qualified in scope.values else default
    with _runtime_lock:
        return _runtime_store.get(key, default)


def set_runtime(key: str, value: Any) -> None:
    scoped = _scoped("runtime", key)
    if scoped:
        scope, qualified = scoped
        scope.values[qualified] = _scoped_value(value)
        return
    _validate_key(key)
    with _runtime_lock:
        _runtime_store[key] = value


def remove_runtime(key: str) -> None:
    scoped = _scoped("runtime", key)
    if scoped:
        scope, qualified = scoped
        scope.values.pop(qualified, None)
        return
    with _runtime_lock:
        _runtime_store.pop(key, None)


def find_runtime(pattern: str) -> list[str]:
    scoped = _scoped_find("runtime", pattern)
    if scoped is not None:
        return scoped
    if not pattern:
        return []
    with _runtime_lock:
        return sorted([k for k in _runtime_store.keys() if fnmatch.fnmatch(k, pattern)])


def get_persistent(key: str, default: Any = None) -> Any:
    scoped = _scoped("persistent", key)
    if scoped:
        scope, qualified = scoped
        return _scoped_value(scope.values[qualified]) if qualified in scope.values else default
    path = _key_to_path(key)
    with _persistent_lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default


def set_persistent(key: str, value: Any) -> None:
    scoped = _scoped("persistent", key)
    if scoped:
        scope, qualified = scoped
        scope.values[qualified] = _scoped_value(value)
        return
    path = _key_to_path(key)
    dir_path = os.path.dirname(path)

    with _persistent_lock:
        os.makedirs(dir_path, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(prefix=f"{key}.", suffix=".tmp", dir=dir_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass


def remove_persistent(key: str) -> None:
    scoped = _scoped("persistent", key)
    if scoped:
        scope, qualified = scoped
        scope.values.pop(qualified, None)
        return
    path = _key_to_path(key)
    with _persistent_lock:
        try:
            os.unlink(path)
        except FileNotFoundError:
            return


def find_persistent(pattern: str) -> list[str]:
    scoped = _scoped_find("persistent", pattern)
    if scoped is not None:
        return scoped
    if not pattern:
        return []

    dir_path = _persistent_dir()
    with _persistent_lock:
        if not os.path.isdir(dir_path):
            return []

        search = os.path.join(dir_path, f"{pattern}.json")
        paths = glob.glob(search)
        keys = [os.path.basename(p)[: -len(".json")] for p in paths]
        keys.sort()
        return keys
