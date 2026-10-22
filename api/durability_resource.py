"""Authenticated, context-scoped download of a verified shared resource."""
from helpers.api import ApiHandler, Request, Response


class DurabilityResource(ApiHandler):
    async def process(self, input: dict, request: Request):
        from helpers.durable.runtime import service
        from helpers.durable.resources import ResourceManager, SCHEME, safe_name
        owner = service()
        if owner is None or owner.failed or not getattr(owner, "distributed", False):
            return Response("Shared resources are unavailable", status=503)
        manager = ResourceManager(owner, input.get("context"))
        if input.get("action") == "workspace":
            return {"workspace": manager.get_manifest("workspace")}
        ref = manager.reference(SCHEME + str(input.get("resource_id", "")))
        return Response(manager.get_bytes(ref), mimetype="application/octet-stream",
                        headers={"Content-Disposition": "attachment; filename=\"" + safe_name(ref["name"]).replace('"', '') + "\"",
                                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
