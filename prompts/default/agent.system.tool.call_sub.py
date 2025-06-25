import json
from typing import Any
from python.helpers.files import VariablesPlugin
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CallSubordinate(VariablesPlugin):
    def get_variables(self) -> dict[str, Any]:

        # collect all prompt profiles from subdirectories (_context.md file)
        profiles = []
        prompt_subdirs = files.get_subdirectories("prompts")
        for prompt_subdir in prompt_subdirs:
            try:
                context = files.read_file(files.get_abs_path("prompts", prompt_subdir, "_context.md"))
                profiles.append({"name": prompt_subdir, "context": context})
            except Exception as e:
                PrintStyle().error(f"Error loading prompt profile '{prompt_subdir}': {e}")

        # in case of no profiles
        if not profiles:
            PrintStyle().error("No prompt profiles found")
            profiles = [{"name": "default", "context": "Default Agent-Zero AI Assistant"}]

        return {
            "prompt_profiles": profiles
        }
