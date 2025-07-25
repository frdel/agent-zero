import os
from typing import Any
from python.helpers.files import VariablesPlugin
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CallSubordinate(VariablesPlugin):
    def get_variables(self, file: str, backup_dirs: list[str] | None = None) -> dict[str, Any]:

        # collect all prompt folders in order of their priority
        folder = files.get_abs_path(os.path.dirname(file))
        folders = [folder]
        if backup_dirs:
            for backup_dir in backup_dirs:
                folders.append(files.get_abs_path(backup_dir))

        # collect all tool instruction files
        prompt_files = files.get_unique_filenames_in_dirs(folders, "agent.system.tool.*.md")
        
        # load tool instructions
        tools = []
        for prompt_file in prompt_files:
            try:
                tool = files.read_file(prompt_file)
                tools.append(tool)
            except Exception as e:
                PrintStyle().error(f"Error loading tool '{prompt_file}': {e}")

        return {"tools": "\n\n".join(tools)}
