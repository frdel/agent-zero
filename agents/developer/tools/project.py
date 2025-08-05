import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers import files, runtime


class ProjectTool(Tool):

    async def execute(self, **kwargs):
        if self.method == "select_or_create":
            return await self.select_or_create(**kwargs)
        else:
            return Response(message=f"Unknown method '{self.name}:{self.method}'", break_loop=False)

    async def select_or_create(self, **kwargs) -> Response:
        """
        Select or create a project directory and store the path in agent data.

        Args:
            path: The project directory path (can be relative or absolute)
            description: Optional project description
            instructions: Optional initial development instructions
        """
        path = kwargs.get("path", None)
        description = kwargs.get("description", "")
        instructions = kwargs.get("instructions", "")

        if not path:
            return Response(message="Project path is required", break_loop=False)

        # Get absolute path using the files helper for RFC compatibility
        abs_path = await runtime.call_development_function(files.get_abs_path, path)

        # Check if directory exists
        is_new_project = not await runtime.call_development_function(files.exists, abs_path)

        # Create directory if it doesn't exist - use a simple text file creation to ensure directory exists
        if is_new_project:
            try:
                # Create a temporary file to ensure directory structure exists, then remove it
                temp_file_path = f"{abs_path}/.temp_dir_creation"
                await runtime.call_development_function(files.write_file, temp_file_path, "")
                created_msg = f"Created project directory: {abs_path}"
            except Exception as e:
                return Response(message=f"Failed to create project directory: {e}", break_loop=False)
        else:
            created_msg = f"Using existing project directory: {abs_path}"

        # Create or update .metadata file
        metadata_path = f"{abs_path}/.metadata"

        if is_new_project or not await runtime.call_development_function(files.exists, metadata_path):
            # Create initial metadata
            project_name = await runtime.call_development_function(files.basename, abs_path)
            metadata = {
                "project_name": project_name,
                "description": description or f"Development project: {project_name}",
                "initial_instructions": instructions or "Standard development project setup and implementation.",
                "created_at": datetime.now().isoformat(),
                "edit_history": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "project_created",
                        "description": await self._generate_summary(f"Project initialized at {abs_path}"),
                        "agent": getattr(self.agent, 'number', 'unknown')
                    }
                ]
            }

            try:
                metadata_content = json.dumps(metadata, indent=2, ensure_ascii=False)
                await runtime.call_development_function(files.write_file, metadata_path, metadata_content)
                metadata_msg = "\nCreated .metadata file with project information."
            except Exception as e:
                metadata_msg = f"\nWarning: Could not create .metadata file: {e}"
        else:
            # Update existing metadata with selection info
            try:
                content = await runtime.call_development_function(files.read_file, metadata_path)
                metadata = json.loads(content)

                # Add selection event to history
                metadata["edit_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "project_selected",
                    "description": await self._generate_summary(f"Project selected by agent {getattr(self.agent, 'number', 'unknown')}"),
                    "agent": getattr(self.agent, 'number', 'unknown')
                })

                updated_content = json.dumps(metadata, indent=2, ensure_ascii=False)
                await runtime.call_development_function(files.write_file, metadata_path, updated_content)
                metadata_msg = "\nUpdated .metadata file with selection information."
            except Exception as e:
                metadata_msg = f"\nWarning: Could not update .metadata file: {e}"

                # Store project path in agent data
        self.agent.set_data("project_path", abs_path)

        return Response(
            message=f"{created_msg}{metadata_msg}\nProject path stored in agent data.",
            break_loop=False
        )

    async def _generate_summary(self, description: str) -> str:
        """Generate a concise one-sentence summary using the utility model."""
        try:
            summary = await self.agent.call_utility_model(
                system="You are a concise summarizer. Create a single sentence summary (max 80 characters) that captures the essential action.",
                message=f"Summarize this development action: {description}"
            )
            return summary.strip()
        except Exception:
            # Fallback to original description if summary generation fails
            return description
