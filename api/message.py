from agent import AgentContext, UserMessage
from helpers.api import ApiHandler, Request, Response

from helpers import files, extension, message_queue as mq
import os
from helpers.security import safe_filename
from helpers.defer import DeferredTask


class Message(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        task, context = await self.communicate(input=input, request=request)
        return await self.respond(task, context)

    async def respond(self, task: DeferredTask, context: AgentContext):
        if task is None:
            return {
                "message": "Model not configured.",
                "model_not_configured": True,
                "context": context.id,
            }
        result = await task.result()  # type: ignore
        return {
            "message": result,
            "context": context.id,
        }

    async def communicate(self, input: dict, request: Request):
        from helpers.durable.runtime import service
        owner = service()
        new_shared_context_id = None
        shared_attachments = []
        if owner and getattr(owner, "distributed", False):
            multipart = (request.content_type or "").startswith("multipart/form-data")
            data = request.form if multipart else (request.get_json() or {})
            ctxid = data.get("context", "")
            if not ctxid:
                import uuid
                initial_id = data.get("message_id")
                new_shared_context_id = (uuid.uuid5(uuid.NAMESPACE_URL, "agent-zero/shared-ui/" + initial_id).hex
                                         if isinstance(initial_id, str) and initial_id else uuid.uuid4().hex)
                ctxid = new_shared_context_id
            from helpers.durable.resources import ResourceManager, SCHEME, MAX_RESOURCE, safe_name
            manager = ResourceManager(owner, ctxid)
            if multipart:
                for upload in request.files.getlist("attachments"):
                    if upload.filename:
                        ref = manager.put_bytes("attachment", safe_name(upload.filename), upload.stream.read(MAX_RESOURCE + 1))
                        shared_attachments.append(SCHEME + ref["id"])
            else:
                shared_attachments = data.get("resources", [])
                if not isinstance(shared_attachments, list):
                    raise ValueError("Expected resource references")
                for uri in shared_attachments:
                    manager.get_bytes(manager.reference(uri))
            if ctxid and (owner.sync("list_run_headers", context_id=ctxid) or owner.sync("get_projection", "genesis:" + ctxid)):
                from types import SimpleNamespace
                message = UserMessage(message=data.get("text", ""), attachments=shared_attachments, id=data.get("message_id") or "")
                # Remote owners apply message hooks/logging at their own safe
                # boundary. Never run them against a stale requester-side chat.
                return owner.communicate_remote(ctxid, message, ui=True), SimpleNamespace(id=ctxid)
        # Handle both JSON and multipart/form-data
        if request.content_type.startswith("multipart/form-data"):
            text = request.form.get("text", "")
            ctxid = request.form.get("context", "")
            message_id = request.form.get("message_id", None)
            attachments = request.files.getlist("attachments")
            attachment_paths = []

            upload_folder_int = "/a0/usr/uploads"
            upload_folder_ext = files.get_abs_path("usr/uploads") # for development environment

            if owner and getattr(owner, "distributed", False):
                attachment_paths = shared_attachments
            elif attachments:
                os.makedirs(upload_folder_ext, exist_ok=True)
                for attachment in attachments:
                    if attachment.filename is None:
                        continue
                    filename = safe_filename(attachment.filename)
                    if not filename:
                        continue
                    save_path = files.get_abs_path(upload_folder_ext, filename)
                    attachment.save(save_path)
                    attachment_paths.append(os.path.join(upload_folder_int, filename))
        else:
            # Handle JSON request as before
            input_data = request.get_json()
            text = input_data.get("text", "")
            ctxid = input_data.get("context", "")
            message_id = input_data.get("message_id", None)
            attachment_paths = shared_attachments

        # Now process the message
        message = text

        # Obtain agent context
        if new_shared_context_id and not ctxid:
            ctxid = new_shared_context_id
        context = self.use_context(ctxid)

        if owner and getattr(owner, "distributed", False):
            return owner.admit_from_context(context, UserMessage(message=message, attachments=attachment_paths,
                                                               id=message_id or ""), ui=True), context

        # call extension point, alow it to modify data
        data = { "message": message, "attachment_paths": attachment_paths }
        await extension.call_extensions_async("user_message_ui", agent=context.get_agent(), data=data)
        message = data.get("message", "")
        attachment_paths = data.get("attachment_paths", [])
        if data.get("model_not_configured"):
            return None, context

        # Store attachments in agent data
        # context.agent0.set_data("attachments", attachment_paths)

        # Log to console and UI using helper function
        mq.log_user_message(context, message, attachment_paths, message_id)

        return context.communicate(UserMessage(message=message, attachments=attachment_paths, id=message_id or "")), context
