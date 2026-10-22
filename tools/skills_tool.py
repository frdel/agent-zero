from __future__ import annotations

import uuid
from pathlib import Path
from typing import List

from helpers.tool import Tool, Response
from helpers.strings import truncate_text
from helpers import skills as skills_helper
from helpers.print_style import PrintStyle


DATA_NAME_LOADED_SKILLS = skills_helper.CONTEXT_DATA_NAME_LOADED_SKILLS


class SkillsTool(Tool):
    """
    Manage and use SKILL.md-based Skills (Anthropic open standard).

    Actions (tool_args.action):
      - list
      - search (query)
      - load (skill_name)
      - read_file (skill_name, file_path)

    Script execution is handled by code_execution_tool directly.
    """

    @staticmethod
    def _normalize_action(action: object) -> str:
        return (
            str(
                action
                or "list"
            )
            .strip()
            .lower()
            .replace("-", "_")
        )

    def _current_action(self, **kwargs) -> str:
        return self._normalize_action(
            kwargs.get("action")
            or self.args.get("action")
            or kwargs.get("method")
            or self.args.get("method")
        )

    @staticmethod
    def _normalize_skill_name(skill_name: str) -> str:
        skill_name = skill_name.strip()
        if skill_name.startswith("**") and skill_name.endswith("**"):
            skill_name = skill_name[2:-2]
        return skill_name.strip()

    def get_log_object(self):
        return self.agent.context.log.log(
            type="skills_tool",
            heading=self.get_heading(),
            content="",
            kvps=self.args,
            id=str(uuid.uuid4()),
        )

    def get_heading(self):
        action = self._current_action()
        if action == "load":
            skill_name = self._normalize_skill_name(
                str(self.args.get("skill_name") or "")
            )
            text = f"Loading skill: {truncate_text(skill_name, 60)}" if skill_name else "Loading skill"
        elif action == "search":
            query = str(self.args.get("query") or "").strip()
            text = f"Searching skills: {truncate_text(query, 60)}" if query else "Searching skills"
        elif action == "read_file":
            skill_name = self._normalize_skill_name(
                str(self.args.get("skill_name") or "")
            )
            file_path = str(self.args.get("file_path") or "").strip()
            target = f"{skill_name}/{file_path}" if skill_name and file_path else file_path or skill_name
            text = f"Reading skill: {truncate_text(target, 60)}" if target else "Reading skill"
        else:
            text = "Listing skills"
        return f"icon://school {text}"

    async def before_execution(self, **kwargs):
        if self._current_action(**kwargs) != "load":
            await super().before_execution(**kwargs)
            return

        skill_name = self._normalize_skill_name(
            str(kwargs.get("skill_name") or self.args.get("skill_name") or "")
        )
        label = f"{self.name} action {self._current_action(**kwargs)}"
        if skill_name:
            PrintStyle(
                font_color="#1B4F72",
                padding=True,
                background_color="white",
                bold=True,
            ).print(f"{self.agent.agent_name}: Loading skill '{skill_name}'")
        else:
            PrintStyle(
                font_color="#1B4F72",
                padding=True,
                background_color="white",
                bold=True,
            ).print(f"{self.agent.agent_name}: Using tool '{label}'")
        self.log = self.get_log_object()

    async def execute(self, **kwargs) -> Response:
        action = self._current_action(**kwargs)

        query = str(kwargs.get("query") or self.args.get("query") or "").strip()
        skill_name = self._normalize_skill_name(
            str(kwargs.get("skill_name") or self.args.get("skill_name") or "")
        )
        file_path = str(
            kwargs.get("file_path") or self.args.get("file_path") or ""
        ).strip()

        if "action" not in kwargs and "action" not in self.args and "method" in kwargs:
            kwargs["action"] = action
        if "action" not in self.args and "method" in self.args:
            self.args["action"] = action

        try:
            if action == "list":
                return Response(message=self._list(), break_loop=False)
            if action == "search":
                return Response(message=self._search(query), break_loop=False)
            if action == "load":
                return self._load(skill_name)
            if action == "read_file":
                return Response(
                    message=self._read_file(skill_name, file_path),
                    break_loop=False,
                )

            return Response(
                message=(
                    "Error: missing/invalid 'action'. Supported actions: "
                    "list, search, load, read_file."
                ),
                break_loop=False,
            )
        except (
            Exception
        ) as e:  # keep tool robust; return error instead of crashing loop
            return Response(message=f"Error in skills_tool: {e}", break_loop=False)

    def _list(self) -> str:
        skills = skills_helper.list_skills(
            agent=self.agent,
            include_content=False,
        )
        if not skills:
            return "No skills found."

        skills_sorted = sorted(skills, key=lambda s: s.name.lower())
        lines = [f"Available skills ({len(skills_sorted)}):"]
        for s in skills_sorted:
            tags = f" tags={','.join(s.tags)}" if s.tags else ""
            ver = f" v{s.version}" if s.version else ""
            desc = (s.description or "").strip()
            if len(desc) > 200:
                desc = desc[:200].rstrip() + "..."
            lines.append(f"- {s.name}{ver}{tags}: {desc}")
        lines.append("")
        lines.append("Tip: use skills_tool action=search or action=load for details.")
        return "\n".join(lines)

    def _search(self, query: str) -> str:
        if not query:
            return "Error: 'query' is required for action=search."

        results = skills_helper.search_skills(
            query,
            limit=25,
            agent=self.agent,
        )
        if not results:
            return f"No skills matched query: {query!r}"

        lines: List[str] = []
        lines.append(f"Skills matching {query!r} ({len(results)}):")
        for s in results:
            desc = (s.description or "").strip()
            if len(desc) > 200:
                desc = desc[:200].rstrip() + "…"
            lines.append(f"- {s.name}: {desc}")
        lines.append("")
        lines.append(
            "Tip: use skills_tool action=load skill_name=<name> to load full instructions."
        )
        return "\n".join(lines)

    def _load(self, skill_name: str) -> Response:
        skill_name = self._normalize_skill_name(skill_name)

        if not skill_name:
            return Response(
                message="Error: 'skill_name' is required for action=load.",
                break_loop=False,
            )

        # Verify skill exists
        skill = skills_helper.find_skill(
            skill_name,
            include_content=False,
            agent=self.agent,
        )
        if not skill:
            return Response(
                message=(
                    f"Error: skill not found: {skill_name!r}. "
                    "Try skills_tool action=list or action=search."
                ),
                break_loop=False,
            )

        skill_data = skills_helper.load_skill_for_agent(
            skill_name=skill.name,
            agent=self.agent,
        )
        metadata = {
            "name": skill.name,
            "path": str(skill.path),
            "source": "skills_tool:load",
            "content_included": True,
        }

        skills_helper.add_loaded_skill_name(
            self.agent,
            skill.name,
            limit=max_loaded_skills(),
        )

        if self._visible_skill_loaded(skill.name):
            return Response(
                message=(
                    f"Skill '{skill.name}' is already loaded in visible "
                    "chat history."
                ),
                break_loop=False,
                additional={
                    "skill_instructions": {
                        **metadata,
                        "content_included": False,
                        "already_loaded": True,
                    }
                },
            )

        return Response(
            message=skill_data,
            break_loop=False,
            additional={"skill_instructions": metadata},
        )

    def _visible_skill_loaded(self, skill_name: str) -> bool:
        history_obj = getattr(self.agent, "history", None)
        output = getattr(history_obj, "output", None)
        if not callable(output):
            return False

        return any(
            skills_helper.skill_instruction_name(message) == skill_name
            for message in output()
        )

    def _read_file(self, skill_name: str, file_path: str) -> str:
        if not skill_name:
            return "Error: 'skill_name' is required for action=read_file."
        if not file_path:
            return "Error: 'file_path' is required for action=read_file."

        skill = skills_helper.find_skill(
            skill_name,
            include_content=False,
            agent=self.agent,
        )
        if not skill:
            return f"Error: skill not found: {skill_name!r}."

        skill_root = skill.path.resolve()
        target = Path(file_path)
        if not target.is_absolute():
            target = skill_root / target

        try:
            resolved = target.resolve()
            resolved.relative_to(skill_root)
        except Exception:
            return "Error: file_path must stay inside the skill directory."

        if not resolved.is_file():
            return f"Error: skill file not found: {file_path!r}."

        content = resolved.read_text(encoding="utf-8", errors="replace")
        if len(content) > 24000:
            content = content[:24000].rstrip() + "\n\n[truncated]"

        return (
            f"Skill file: {skill.name}/{resolved.relative_to(skill_root)}\n\n"
            f"{content}"
        )


def max_loaded_skills() -> int:
    return skills_helper.MAX_ACTIVE_SKILLS
