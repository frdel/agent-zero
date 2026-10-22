"""Authenticated operator review and context-scoped typed document operations."""
import json

from helpers.api import ApiHandler, Request, Response
from helpers.durable import documents, review, runtime
from helpers.durable.store import ConflictError, DurableStoreError, StaleRunError, _identity


def _text(data, name, *, required=True):
    value = data.get(name)
    if value is None and not required:
        return None
    return _identity(value, name)


class Durability(ApiHandler):
    # ApiHandler defaults retain authentication, same-origin and CSRF protection.
    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            if type(input) is not dict:
                raise ValueError("Expected an object")
            action = input.get("action", "status")
            owner = runtime.service()
            if action == "status":
                return review.status(owner, _text(input, "context", required=False), input.get("offset", 0))
            if owner is None or owner.failed:
                return self.error("Local durability storage is unavailable.", 503)
            request_id = _text(input, "request_id", required=action != "document_read")
            if action == "restore_select":
                return review.restore_select(owner, input.get("run_ids"), input.get("versions"),
                                             _text(input, "epoch"), request_id)
            context_id = _text(input, "context")
            if action == "command_status":
                return review.command_status(owner, context_id, _text(input, "run_id"), request_id)
            if action == "resolve":
                return review.resolve(owner, context_id, _text(input, "run_id"), _text(input, "version"),
                                      input.get("decision"), input.get("note", ""), request_id,
                                      _text(input, "call_id", required=False))
            if review.distributed(owner):
                if action == "document_read":
                    return {"document": review.read_shared_document(owner, context_id, _text(input, "kind"))}
                from agent import AgentContext
                candidate = AgentContext.get(context_id)
                turn = getattr(candidate, "_durable_turn", None) if candidate else None
                if not turn or not owner.sync("owns", turn.run_id):
                    return self.error("Shared document edits require the execution owner's masking and policy context. Your draft was not saved.", 409)
            context = review.context_for(context_id)
            if action == "document_read":
                return {"document": documents.read(owner, context, _text(input, "kind"))}
            if action == "document_update":
                with owner.lock:
                    documents.update(owner, context, _text(input, "kind"), input.get("value"),
                                     input.get("expected_revision"), request_id)
                    document = documents.read(owner, context, input["kind"])
                review._dirty((context_id,))
                return {"document": document}
            if action == "document_conflict":
                run_id = _text(input, "run_id")
                with owner.lock:
                    review.scoped_run(owner, context_id, run_id)
                    conflict = next((item for item in owner.sync("list_document_conflicts", run_id)
                                     if item["conflict_id"] == _text(input, "conflict_id")), None)
                    if not conflict:
                        raise KeyError("Unknown conflict")
                    declared = documents.definition(conflict["kind"])
                    declared.decode(owner.sync("read_document", context_id, conflict["kind"]))
                    if conflict["schema_version"] != declared.schema_version:
                        raise ValueError("Unsupported proposed document schema")
                    declared.validate(conflict["proposed"])
                    result = owner.sync("resolve_document_conflict", run_id, conflict["conflict_id"],
                                        input.get("decision"), input.get("expected_revision"),
                                        _text(input, "version"), request_id)
                review._dirty((context_id,))
                return result
            raise ValueError("Unknown durability action")
        except review.ReviewError as exc:
            return self.error(str(exc), exc.status, required_ids=exc.required_ids)
        except ConflictError:
            return self.error("The saved version changed. Refresh and review the current state.", 409)
        except StaleRunError:
            return self.error("This run was stopped, reset, deleted or replaced. Refresh its details.", 409)
        except KeyError:
            return self.error("The requested chat, run or conflict is unavailable.", 404)
        except (ValueError, TypeError):
            return self.error("Invalid durability request or unsupported document schema.", 400)
        except (DurableStoreError, runtime.RecoveryHeld):
            return self.error("Recovery storage needs attention. Refresh before taking another action.", 503)
        except Exception:
            # ApiHandler's generic traceback response is unsuitable for private
            # recovery/provider data and arbitrary plugin callback exceptions.
            return self.error("Recovery request failed safely. Refresh before taking another action.", 503)

    @staticmethod
    def error(message, status, **extra):
        return Response(json.dumps({"error": message, **extra}), status=status, mimetype="application/json")
