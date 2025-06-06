import json
from typing import Any
from python.helpers.files import VariablesPlugin
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CallSubordinate(VariablesPlugin):
    def get_variables(self) -> dict[str, Any]:
        meta = files.read_file(files.get_abs_path("prompts", "meta.json"))
        profiles = ""
        try:
            for profile in json.loads(meta):
                profiles += f"- {profile['name']}: {profile['description']}\n"
        except Exception as e:
            PrintStyle().error(f"Error loading prompt profiles: {e}")
            profiles = "- default: Default Agent-Zero AI Assistant"
        return {
            "prompt_profiles": profiles
        }
