"""Concrete typed plan document; updates commit with the tool body result."""
import json

from helpers.errors import RepairableException
from helpers.tool import Tool, Response


class DurablePlan(Tool):
    replay = "safe"  # Only private staged documents; no external body effect.

    async def execute(self, action="read", value=None, expected_revision=None, **kwargs):
        from helpers.durable.runtime import current
        if current(self.agent) is None:
            raise RepairableException("durable_plan requires local durability to be enabled")
        if action == "read":
            value, revision = await self.documents.read("todo")
            return Response(json.dumps({"kind": "todo", "revision": revision, "value": value}), False)
        if action != "replace":
            raise RepairableException("durable_plan action must be read or replace")
        revision = await self.documents.stage("todo", value, expected_revision=expected_revision)
        value, _ = await self.documents.read("todo")
        return Response(json.dumps({"kind": "todo", "revision": revision, "value": value}), False,
                        additional={"document_kind": "todo", "document_revision": revision})
