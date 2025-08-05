import os
import subprocess
import json
from python.helpers.extension import Extension
from python.helpers import runtime, files
from agent import LoopData


class InjectProjectInfo(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # Get project path from agent data
        project_path = self.agent.get_data("project_path")

        if not project_path:
            # No project path set, skip injection
            return

        # Check if project path exists using development-aware function
        try:
            project_exists = await runtime.call_development_function(files.exists, project_path)
            if not project_exists:
                return
        except Exception:
            # If we can't check existence, skip injection
            return

        try:
            # Generate comprehensive project information
            project_layout = await self._generate_directory_tree(project_path)
            git_status = await self._get_git_status(project_path)
            project_metadata = await self._get_project_metadata(project_path)

            # Get system information
            os_info = self._get_os_info()
            shell_info = self._get_shell_info()

            # Get the current user message
            user_query = ""
            if loop_data.user_message and loop_data.user_message.content:
                user_query = str(loop_data.user_message.content)

            # Prepare role and rules information
            role_info = (
                "Full-Stack Developer with expert-level proficiency in Python, JavaScript/TypeScript, React, "
                "Node.js, Docker, SQL/NoSQL databases, cloud platforms (AWS/GCP/Azure), REST/GraphQL APIs, Git, "
                "Linux/Unix systems, and modern development frameworks including Flask, FastAPI, Express, "
                "Next.js, Vue.js, Angular, and DevOps tools"
            )

            user_rules = (
                "Follow project development best practices, write clean and maintainable code, implement proper "
                "error handling, use appropriate design patterns, ensure security best practices, optimize for "
                "performance, and maintain comprehensive documentation."
            )

            # Read and parse the framework prompt injection template
            fw_prompt = self.agent.read_prompt(
                "fw.system_prompt_inject.md",
                project_layout=project_layout,
                git_status=git_status,
                project_metadata=project_metadata,
                os_info=os_info,
                shell_info=shell_info,
                workspace_path=project_path,
                role_info=role_info,
                user_rules=user_rules,
                user_query=user_query
            )

            # Add the parsed framework prompt to extras_temporary
            loop_data.extras_temporary["project_framework"] = fw_prompt

        except Exception:
            # If there's an error, silently skip injection to avoid breaking the agent
            pass

    async def _generate_directory_tree(self, project_path: str) -> str:
        """Generate a directory tree representation of the project."""
        try:
            # Use files.list_files for basic listing
            file_list = await runtime.call_development_function(files.list_files, project_path, "*")
            if not file_list:
                return f"Project directory: {project_path}\n(empty or no accessible files)"

            # Create a simple tree view with truncation
            tree_lines = [f"Project directory: {project_path}"]
            max_files = 20

            for file in file_list[:max_files]:
                tree_lines.append(f"  {file}")

            if len(file_list) > max_files:
                tree_lines.append(f"  ... and {len(file_list) - max_files} more files")

            return "\n".join(tree_lines)

        except Exception:
            return f"Project directory: {project_path}\n(Error reading directory)"

    async def _get_git_status(self, project_path: str) -> str:
        """Get git status if available."""
        try:
            # Check if .git directory exists
            git_dir = f"{project_path}/.git"
            git_exists = await runtime.call_development_function(files.exists, git_dir)

            if not git_exists:
                return "No git repository detected"

            # Try to get git status (this might not work in all environments)
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                if result.stdout.strip():
                    return f"Git repository with changes:\n{result.stdout.strip()}"
                else:
                    return "Git repository (clean working directory)"
            else:
                return "Git repository detected (status unavailable)"

        except Exception:
            return "Git status unavailable"

    async def _get_project_metadata(self, project_path: str) -> str:
        """Get project metadata from .metadata file and other sources."""
        metadata_sections = []

        # Try to read .metadata file
        try:
            metadata_file_path = f"{project_path}/.metadata"
            metadata_exists = await runtime.call_development_function(files.exists, metadata_file_path)

            if metadata_exists:
                content = await runtime.call_development_function(files.read_file, metadata_file_path)
                project_metadata = json.loads(content)

                metadata_sections.append("## Project Information")
                metadata_sections.append(f"**Name**: {project_metadata.get('project_name', 'Unknown')}")
                metadata_sections.append(f"**Description**: {project_metadata.get('description', 'No description')}")
                metadata_sections.append(f"**Created**: {project_metadata.get('created_at', 'Unknown')}")

                if project_metadata.get('initial_instructions'):
                    metadata_sections.append(f"**Instructions**: {project_metadata.get('initial_instructions')}")

                # Show recent activity
                edit_history = project_metadata.get('edit_history', [])
                if edit_history:
                    metadata_sections.append("\n## Recent Activity")
                    recent_edits = edit_history[-20:]  # Last 20 activities
                    for edit in recent_edits:
                        timestamp = edit.get('timestamp', 'Unknown time')
                        action = edit.get('action', 'unknown')
                        description = edit.get('description', 'No description')
                        metadata_sections.append(f"- **{timestamp}** [{action}] {description}")
            else:
                metadata_sections.append("## Project Information")
                metadata_sections.append("No .metadata file found - use project:select_or_create to initialize project metadata")

        except Exception:
            metadata_sections.append("## Project Information")
            metadata_sections.append("Error reading project metadata")

        # Try to read README file
        try:
            readme_files = ['README.md', 'README.txt', 'README']
            for readme in readme_files:
                readme_path = f"{project_path}/{readme}"
                readme_exists = await runtime.call_development_function(files.exists, readme_path)

                if readme_exists:
                    content = await runtime.call_development_function(files.read_file, readme_path)
                    preview = content[:500] + "..." if len(content) > 500 else content
                    metadata_sections.append(f"\n## Documentation ({readme})")
                    metadata_sections.append(preview)
                    break
        except Exception:
            pass

        return "\n".join(metadata_sections) if metadata_sections else "No project metadata available"

    def _get_os_info(self) -> str:
        """Get OS information."""
        try:
            import platform
            return f"{platform.system()} {platform.release()}"
        except Exception:
            return "Unknown OS"

    def _get_shell_info(self) -> str:
        """Get shell information."""
        try:
            return os.environ.get('SHELL', 'Unknown shell')
        except Exception:
            return "Unknown shell"
