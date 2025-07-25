import json
from typing import Any
from python.helpers.files import VariablesPlugin
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CallSubordinate(VariablesPlugin):
    def get_variables(self, file: str, backup_dirs: list[str] | None = None) -> dict[str, Any]:

        # collect all prompt profiles from subdirectories (_context.md file)
        profiles = []
        agent_subdirs = files.get_subdirectories("agents", exclude=["_example"])
        for agent_subdir in agent_subdirs:
            try:
                context = files.read_file(
                    files.get_abs_path("agents", agent_subdir, "_context.md")
                )
                profiles.append({"name": agent_subdir, "context": context})
            except Exception as e:
                PrintStyle().error(f"Error loading agent profile '{agent_subdir}': {e}")

        # in case of no profiles
        if not profiles:
            # PrintStyle().error("No agent profiles found")
            profiles = [
                {"name": "default", "context": "Default Agent-Zero AI Assistant"}
            ]

        return {"agent_profiles": profiles}
