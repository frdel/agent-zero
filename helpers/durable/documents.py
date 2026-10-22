"""Typed, context-scoped documents and isolated per-tool drafts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Callable

from helpers.durable import codec

MAX_BYTES = 64 * 1024


@dataclass(frozen=True)
class DocumentKind:
    kind: str
    schema_version: int
    initializer: Callable[[], dict]
    validator: Callable[[dict], None]
    migrate: Callable[[dict, int], dict] | None = None

    def validate(self, value):
        # No caller can retain a mutable reference into a committed/draft value.
        from helpers.durable.store import _json
        encoded = _json(value)
        if len(encoded.encode("utf-8")) > MAX_BYTES:
            raise ValueError("Document exceeds the 64 KiB limit")
        value = json.loads(encoded)
        self.validator(value)
        return value

    def decode(self, stored):
        if stored is None:
            return self.validate(self.initializer()), 0, False
        version = stored["schema_version"]
        if version > self.schema_version:
            raise ValueError("Document uses a newer unsupported schema")
        value = deepcopy(stored["value"])
        if version != self.schema_version:
            if self.migrate is None:
                raise ValueError("Document migration is unavailable")
            value = self.migrate(value, version)
        return self.validate(value), stored["revision"], version != self.schema_version


def _validate_todo(value):
    if type(value) is not dict or set(value) != {"title", "items"}:
        raise ValueError("Plan must contain title and items")
    if type(value["title"]) is not str or len(value["title"]) > 160:
        raise ValueError("Plan title must be at most 160 characters")
    if type(value["items"]) is not list or len(value["items"]) > 100:
        raise ValueError("Plan supports at most 100 items")
    seen = set()
    for item in value["items"]:
        if type(item) is not dict or set(item) != {"id", "text", "done"}:
            raise ValueError("Plan items require id, text and done")
        if type(item["id"]) is not str or not item["id"] or len(item["id"]) > 64 or item["id"] in seen:
            raise ValueError("Plan item IDs must be unique nonempty strings up to 64 characters")
        seen.add(item["id"])
        if type(item["text"]) is not str or not item["text"].strip() or len(item["text"]) > 2000:
            raise ValueError("Plan item text must contain 1 to 2000 characters")
        if type(item["done"]) is not bool:
            raise ValueError("Plan item done must be boolean")


KINDS = {"todo": DocumentKind("todo", 1, lambda: {"title": "Plan", "items": []}, _validate_todo)}


def definition(kind):
    if kind not in KINDS:
        raise ValueError("Unknown document kind")
    return KINDS[kind]


def read(owner, context, kind):
    declared = definition(kind)
    stored = owner.sync("read_document", context.id, kind)
    value, revision, migration = declared.decode(stored)
    return {"kind": kind, "schema_version": declared.schema_version, "revision": revision,
            "value": codec.masked(context.agent0, value), "migration_required": migration}


def update(owner, context, kind, value, expected_revision, request_id):
    declared = definition(kind)
    # Validate existing schema as well: a v1 client cannot overwrite a future v2.
    generation = owner.sync("document_generation", context.id)
    stored = owner.sync("read_document", context.id, kind)
    declared.decode(stored)
    value = declared.validate(codec.masked(context.agent0, declared.validate(value)))
    return owner.sync("write_document", context.id, kind, declared.schema_version, value,
                      expected_revision, request_id, expected_generation=generation)


class DocumentSession:
    """Drafts are private to one body invocation; only tool_body commits them."""

    def __init__(self, turn, call_id):
        self.turn, self.call_id = turn, call_id
        self._edits = {}

    async def read(self, kind):
        declared = definition(kind)
        if kind in self._edits:
            edit = self._edits[kind]
            return deepcopy(edit["value"]), edit["expected_revision"]
        stored = await self.turn.owner.io("read_document", self.turn.agent.context.id, kind)
        value, revision, _migration = declared.decode(stored)
        return codec.masked(self.turn.agent, value), revision

    async def stage(self, kind, value, *, expected_revision):
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Expected document revision must be a nonnegative integer")
        declared = definition(kind)
        stored = await self.turn.owner.io("read_document", self.turn.agent.context.id, kind)
        declared.decode(stored)
        value = declared.validate(codec.masked(self.turn.agent, declared.validate(value)))
        existing = self._edits.get(kind)
        if existing and existing["expected_revision"] != expected_revision:
            raise ValueError("One invocation cannot stage two base revisions for a document")
        self._edits[kind] = {"kind": kind, "schema_version": declared.schema_version,
                             "expected_revision": expected_revision, "value": value}
        return expected_revision + 1

    def edits(self):
        return deepcopy(list(self._edits.values()))
