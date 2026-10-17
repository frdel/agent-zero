import base64
import os
import uuid
from datetime import datetime, timezone
from agent import AgentContext, UserMessage, AgentContextType
from helpers.api import ApiHandler, Request, Response
from helpers import files, projects
from helpers.print_style import PrintStyle
from helpers.projects import activate_project
from helpers.security import safe_filename
from initialize import initialize_agent


class ApiMessage(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return False  # No web auth required

    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # No CSRF required

    @classmethod
    def requires_api_key(cls) -> bool:
        return True  # Require API key

    async def process(self, input: dict, request: Request) -> dict | Response:
        # Extract parameters
        context_id = input.get("context_id", "")
        message = input.get("message", "")
        attachments = input.get("attachments", [])
        lifetime_hours = input.get("lifetime_hours", 24)  # Default 24 hours
        project_name = input.get("project_name", None)
        agent_profile = input.get("agent_profile", None)
        try:
            lifetime_hours = float(lifetime_hours)
            if lifetime_hours <= 0:
                raise ValueError("lifetime_hours must be greater than 0")
        except (TypeError, ValueError):
            return Response(
                '{"error": "lifetime_hours must be a positive number"}',
                status=400,
                mimetype="application/json",
            )
        
        # Set an agent if profile provided
        override_settings = {}
        if agent_profile:
            override_settings["agent_profile"] = agent_profile

        if not message:
            return Response('{"error": "Message is required"}', status=400, mimetype="application/json")

        # Handle attachments (base64 encoded)
        attachment_paths = []
        if attachments:
            upload_folder_int = "/a0/usr/uploads"
            upload_folder_ext = files.get_abs_path("usr/uploads")
            os.makedirs(upload_folder_ext, exist_ok=True)

            for attachment in attachments:
                if not isinstance(attachment, dict) or "filename" not in attachment or "base64" not in attachment:
                    continue

                try:
                    filename = safe_filename(attachment["filename"])
                    if not filename:
                        raise ValueError("Invalid filename")

                    # Decode base64 content
                    file_content = base64.b64decode(attachment["base64"])

                    # Save to temp file
                    save_path = os.path.join(upload_folder_ext, filename)
                    with open(save_path, "wb") as f:
                        f.write(file_content)

                    attachment_paths.append(os.path.join(upload_folder_int, filename))
                except Exception as e:
                    PrintStyle.error(f"Failed to process attachment {attachment.get('filename', 'unknown')}: {e}")
                    continue

        # Get or create context
        if context_id:
            context = AgentContext.use(context_id)
            if not context:
                return Response('{"error": "Context not found"}', status=404, mimetype="application/json")

            # Validation: if agent profile is provided, it must match the exising
            if agent_profile and context.agent0.config.profile != agent_profile:
                return Response('{"error": "Cannot override agent profile on existing context"}', status=400, mimetype="application/json")
            

            # Validation: if project is provided but context already has different project
            existing_project = context.get_data(projects.CONTEXT_DATA_KEY_PROJECT)
            if project_name and existing_project and existing_project != project_name:
                return Response('{"error": "Project can only be set on first message"}', status=400, mimetype="application/json")
        else:
            config = initialize_agent(override_settings=override_settings)
            context = AgentContext(config=config, type=AgentContextType.USER)
            AgentContext.use(context.id)
            context_id = context.id
            if agent_profile:
                context.set_data("agent_profile_manually_set", True)
            # Activate project if provided
            if project_name:
                try:
                    activate_project(context_id, project_name)
                except Exception as e:
                    # Handle project or context errors more gracefully
                    error_msg = str(e)
                    PrintStyle.error(f"Failed to activate project '{project_name}' for context '{context_id}': {error_msg}")
                    return Response(
                        f'{{"error": "Failed to activate project \\"{project_name}\\""}}',
                        status=500,
                        mimetype="application/json",
                    )

            # Activate project if provided
            if project_name:
                try:
                    projects.activate_project(context_id, project_name)
                except Exception as e:
                    return Response(f'{{"error": "Failed to activate project: {str(e)}"}}', status=400, mimetype="application/json")

        # Persist API chat lifetime in context data so cleanup survives restarts.
        context.set_data("lifetime_hours", lifetime_hours)
        context.last_message = datetime.now(timezone.utc)

        # Process message
        try:
            # Log the message
            attachment_filenames = [os.path.basename(path) for path in attachment_paths] if attachment_paths else []

            PrintStyle(
                background_color="#6C3483", font_color="white", bold=True, padding=True
            ).print("External API message:")
            PrintStyle(font_color="white", padding=False).print(f"> {message}")
            if attachment_filenames:
                PrintStyle(font_color="white", padding=False).print("Attachments:")
                for filename in attachment_filenames:
                    PrintStyle(font_color="white", padding=False).print(f"- {filename}")

            # Add user message to chat history so it's visible in the UI
            msg_id = str(uuid.uuid4())
            context.log.log(
                type="user",
                heading="",
                content=message,
                kvps={"attachments": attachment_filenames},
                id=msg_id,
            )

            # Send message to agent
            task = context.communicate(UserMessage(message=message, attachments=attachment_paths, id=msg_id))
            result = await task.result()

            return {
                "context_id": context_id,
                "response": result
            }

        except Exception as e:
            PrintStyle.error(f"External API error: {e}")
            return Response(f'{{"error": "{str(e)}"}}', status=500, mimetype="application/json")
