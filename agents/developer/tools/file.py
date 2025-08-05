import difflib
import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers import files, runtime


class FileTool(Tool):
    async def execute(self, **kwargs) -> Response:
        # Routing method based on self.method from Tool base class
        if self.method == "read_file":
            return await self.read_file(**kwargs)
        elif self.method == "edit_file":
            return await self.edit_file(**kwargs)
        elif self.method == "create_file":
            return await self.create_file(**kwargs)
        elif self.method == "delete_file":
            return await self.delete_file(**kwargs)
        elif self.method == "rename_file":
            return await self.rename_file(**kwargs)
        elif self.method == "copy_file":
            return await self.copy_file(**kwargs)
        elif self.method == "list_files":
            return await self.list_files(**kwargs)
        else:
            return Response(message=f"Unknown file method: {self.method}", break_loop=False)

    async def read_file(self, **kwargs) -> Response:
        """
        Read file content with optional line range.

        Args:
            path: File path to read
            start_line: Starting line number (1-based, optional)
            end_line: Ending line number (1-based, optional)
        """
        path = kwargs.get("path", None)
        if not path:
            return Response(message="File path is required", break_loop=False)

        start_line = kwargs.get("start_line", None)
        end_line = kwargs.get("end_line", None)

        try:
            if not await runtime.call_development_function(files.exists, path):
                return Response(message=f"File not found: {path}", break_loop=False)

            content = await runtime.call_development_function(files.read_file, path)
            lines = content.splitlines()

            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else len(lines)

                # Validate line numbers
                if start_line and (start_line < 1 or start_line > len(lines)):
                    return Response(message=f"Start line {start_line} is out of range (1-{len(lines)})", break_loop=False)
                if end_line and (end_line < 1 or end_line > len(lines)):
                    return Response(message=f"End line {end_line} is out of range (1-{len(lines)})", break_loop=False)

                selected_lines = lines[start_idx:end_idx]

                # Add line numbers to selected content
                numbered_lines = []
                for i, line in enumerate(selected_lines):
                    line_num = start_idx + i + 1
                    numbered_lines.append(f"{line_num:4d}│ {line}")

                numbered_content = "\n".join(numbered_lines)

                return Response(
                    message=f"Content of {path} (lines {start_line or 1}-{end_line or len(lines)}):\n```\n{numbered_content}\n```",
                    break_loop=False
                )
            else:
                # Add line numbers to entire file content
                numbered_lines = []
                for i, line in enumerate(lines):
                    numbered_lines.append(f"{i + 1:4d}│ {line}")

                numbered_content = "\n".join(numbered_lines)

                return Response(
                    message=f"Content of {path} ({len(lines)} lines):\n```\n{numbered_content}\n```",
                    break_loop=False
                )

        except Exception as e:
            return Response(message=f"Error reading file: {e}", break_loop=False)

    async def edit_file(self, **kwargs) -> Response:
        """
        Edit file content by replacing content between specific line numbers.
        Supports multiple edits in one call - edits are applied bottom-to-top to preserve line numbers.

        Args:
            path: File path to edit
            edits: List of edit operations (for multi-edit)
            start_line: Starting line number for single edit (1-based, inclusive)
            end_line: Ending line number for single edit (1-based, inclusive)
            new_content: New content to replace specified lines
        """
        path = kwargs.get("path", None)
        edits = kwargs.get("edits", None)

        if not path:
            return Response(message="File path is required", break_loop=False)

        # Handle backward compatibility for single edit
        if edits is None:
            start_line = kwargs.get("start_line", None)
            end_line = kwargs.get("end_line", None)
            new_content = kwargs.get("new_content", "")

            if start_line is None or end_line is None:
                return Response(message="Either 'edits' list or 'start_line' and 'end_line' are required", break_loop=False)

            edits = [{"start_line": start_line, "end_line": end_line, "new_content": new_content}]

        if not isinstance(edits, list) or not edits:
            return Response(message="Edits must be a non-empty list", break_loop=False)

        # Validate all edits
        for i, edit in enumerate(edits):
            if not isinstance(edit, dict):
                return Response(message=f"Edit {i + 1} must be a dictionary", break_loop=False)
            if "start_line" not in edit or "end_line" not in edit:
                return Response(message=f"Edit {i + 1} must have 'start_line' and 'end_line'", break_loop=False)

        try:
            if not await runtime.call_development_function(files.exists, path):
                return Response(message=f"File not found: {path}", break_loop=False)

            original_content = await runtime.call_development_function(files.read_file, path)
            original_lines = original_content.splitlines()

            # Validate line numbers for all edits
            for i, edit in enumerate(edits):
                start_line = edit["start_line"]
                end_line = edit["end_line"]

                if start_line < 1 or start_line > len(original_lines):
                    return Response(message=f"Edit {i + 1}: Start line {start_line} is out of range (1-{len(original_lines)})", break_loop=False)
                if end_line < 1 or end_line > len(original_lines):
                    return Response(message=f"Edit {i + 1}: End line {end_line} is out of range (1-{len(original_lines)})", break_loop=False)
                if start_line > end_line:
                    return Response(message=f"Edit {i + 1}: Start line {start_line} cannot be greater than end line {end_line}", break_loop=False)

            # Sort edits by start_line in descending order (bottom-to-top)
            sorted_edits = sorted(edits, key=lambda x: x["start_line"], reverse=True)

            # Apply edits
            new_lines = original_lines.copy()
            edit_descriptions = []

            for edit in sorted_edits:
                start_line = edit["start_line"]
                end_line = edit["end_line"]
                new_content = edit.get("new_content", "")

                # Split new content into lines
                replacement_lines = new_content.splitlines() if new_content.strip() else []

                # Replace the lines
                new_lines[start_line - 1:end_line] = replacement_lines

                edit_descriptions.append(f"Lines {start_line}-{end_line}: {len(original_lines[start_line - 1:end_line])} → {len(replacement_lines)}")

            # Write the new file content
            new_file_content = "\n".join(new_lines)
            await runtime.call_development_function(files.write_file, path, new_file_content)

            # Update project metadata
            await self._update_project_metadata(path, f"File edited: {', '.join(edit_descriptions)}")

            # Generate diff
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                new_file_content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm=""
            )
            diff_text = "".join(diff)

            # Add line numbers to updated content
            numbered_lines = []
            for i, line in enumerate(new_lines):
                numbered_lines.append(f"{i + 1:4d}│ {line}")
            numbered_content = "\n".join(numbered_lines)

            return Response(
                message=f"File {path} edited successfully. Applied {len(edits)} edit(s).\n\n" +
                        f"Edits applied: {', '.join(edit_descriptions)}\n\n" +
                        f"Updated content:\n```\n{numbered_content}\n```\n\n" +
                        f"Diff:\n```diff\n{diff_text}\n```",
                break_loop=False
            )

        except Exception as e:
            return Response(message=f"Error editing file: {e}", break_loop=False)

    async def create_file(self, **kwargs) -> Response:
        """Create a new file with specified content."""
        path = kwargs.get("path", None)
        content = kwargs.get("content", "")

        if not path:
            return Response(message="File path is required", break_loop=False)

        try:
            if await runtime.call_development_function(files.exists, path):
                return Response(message=f"File already exists: {path}", break_loop=False)

            await runtime.call_development_function(files.write_file, path, content)
            await self._update_project_metadata(path, f"File created with {len(content.splitlines())} lines")

            return Response(message=f"File {path} created successfully", break_loop=False)

        except Exception as e:
            return Response(message=f"Error creating file: {e}", break_loop=False)

    async def delete_file(self, **kwargs) -> Response:
        """Delete an existing file."""
        path = kwargs.get("path", None)

        if not path:
            return Response(message="File path is required", break_loop=False)

        try:
            if not await runtime.call_development_function(files.exists, path):
                return Response(message=f"File not found: {path}", break_loop=False)

            # Use delete_file helper if available, otherwise construct path manually
            abs_path = await runtime.call_development_function(files.get_abs_path, path)
            await runtime.call_development_function(self._delete_file_helper, abs_path)
            await self._update_project_metadata(path, "File deleted")

            return Response(message=f"File {path} deleted successfully", break_loop=False)

        except Exception as e:
            return Response(message=f"Error deleting file: {e}", break_loop=False)

    async def rename_file(self, **kwargs) -> Response:
        """Rename or move a file."""
        old_path = kwargs.get("old_path", None)
        new_path = kwargs.get("new_path", None)

        if not old_path or not new_path:
            return Response(message="Both old_path and new_path are required", break_loop=False)

        try:
            if not await runtime.call_development_function(files.exists, old_path):
                return Response(message=f"Source file not found: {old_path}", break_loop=False)

            # Read the source file and write to new location
            content = await runtime.call_development_function(files.read_file, old_path)
            await runtime.call_development_function(files.write_file, new_path, content)

            # Delete the old file
            abs_old_path = await runtime.call_development_function(files.get_abs_path, old_path)
            await runtime.call_development_function(self._delete_file_helper, abs_old_path)

            await self._update_project_metadata(new_path, f"File moved from {old_path}")

            return Response(message=f"File moved from {old_path} to {new_path}", break_loop=False)

        except Exception as e:
            return Response(message=f"Error renaming file: {e}", break_loop=False)

    async def copy_file(self, **kwargs) -> Response:
        """Copy a file to a new location."""
        source_path = kwargs.get("source_path", None)
        dest_path = kwargs.get("dest_path", None)

        if not source_path or not dest_path:
            return Response(message="Both source_path and dest_path are required", break_loop=False)

        try:
            if not await runtime.call_development_function(files.exists, source_path):
                return Response(message=f"Source file not found: {source_path}", break_loop=False)

            # Read source file and write to destination
            content = await runtime.call_development_function(files.read_file, source_path)
            await runtime.call_development_function(files.write_file, dest_path, content)

            await self._update_project_metadata(dest_path, f"File copied from {source_path}")

            return Response(message=f"File copied from {source_path} to {dest_path}", break_loop=False)

        except Exception as e:
            return Response(message=f"Error copying file: {e}", break_loop=False)

    async def list_files(self, **kwargs) -> Response:
        """List files in a directory."""
        path = kwargs.get("path", None)
        filter_pattern = kwargs.get("filter", "*")
        # Note: recursive parameter available but not currently used with files.list_files

        if not path:
            # Use project path if available
            project_path = self.agent.get_data("project_path")
            if project_path:
                path = project_path
            else:
                path = "."

        try:
            if not await runtime.call_development_function(files.exists, path):
                return Response(message=f"Directory not found: {path}", break_loop=False)

            # Use files.list_files helper function
            file_list = await runtime.call_development_function(files.list_files, path, filter_pattern)

            if not file_list:
                return Response(message=f"No files found matching pattern '{filter_pattern}' in {path}", break_loop=False)

            file_count = len(file_list)
            file_listing = "\n".join(f"  {file}" for file in file_list)

            return Response(
                message=f"Found {file_count} file(s) in {path}:\n{file_listing}",
                break_loop=False
            )

        except Exception as e:
            return Response(message=f"Error listing files: {e}", break_loop=False)

    async def _delete_file_helper(self, abs_path: str):
        """Helper function to delete a file - can be called via development function."""
        import os
        if os.path.exists(abs_path):
            os.remove(abs_path)

    async def _update_project_metadata(self, file_path: str, description: str):
        """Update project metadata with file edit information."""
        try:
            project_path = self.agent.get_data("project_path")
            if not project_path:
                return  # No project selected

            metadata_path = f"{project_path}/.metadata"

            if await runtime.call_development_function(files.exists, metadata_path):
                content = await runtime.call_development_function(files.read_file, metadata_path)
                metadata = json.loads(content)

                metadata["edit_history"].append({
                    "timestamp": datetime.now().isoformat(),
                    "action": "file_edit",
                    "file_path": file_path,
                    "description": await self._generate_summary(description),
                    "agent": getattr(self.agent, 'number', 'unknown')
                })

                updated_content = json.dumps(metadata, indent=2, ensure_ascii=False)
                await runtime.call_development_function(files.write_file, metadata_path, updated_content)
        except Exception:
            # Silently fail if metadata update fails
            pass

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
