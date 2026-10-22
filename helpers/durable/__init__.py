"""Opt-in local recovery primitives; importing this package opens no storage."""

from .store import (
    ConflictError,
    DurableStoreError,
    IntegrityError,
    LocalStore,
    OwnershipError,
    StaleRunError,
)

__all__ = [
    "ConflictError", "DurableStoreError", "IntegrityError", "LocalStore",
    "OwnershipError", "StaleRunError",
]
