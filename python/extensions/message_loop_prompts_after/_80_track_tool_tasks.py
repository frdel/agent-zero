from typing import Any
from python.helpers.extension import Extension
from agent import Agent, LoopData


class TrackToolTasks(Extension):
    """
    Extension that tracks active tool tasks and adds them to the system prompt extras.
    This allows the agent to see what tool calls are currently in progress.
    """

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs: Any):
        """
        Add information about active tool tasks to the system prompt extras.
        """

        # Get active tasks from agent data
        active_tasks = self.agent.get_data("active_tool_tasks") or {}

        if not active_tasks:
            # No active tasks, nothing to add
            return

        # Build the tasks in progress section
        tasks_info = []
        tasks_info.append("## Tasks in Progress")
        tasks_info.append("")
        tasks_info.append("The following tool calls are currently running in parallel in isolated temporary contexts:")
        tasks_info.append("")

        for task_id, task_info in active_tasks.items():
            tool_name = task_info.get("tool_name", "unknown")
            started_at = task_info.get("started_at", "unknown")

            tasks_info.append(f"- **Task ID**: `{task_id}`")
            tasks_info.append(f"  - **Tool**: {tool_name}")
            tasks_info.append(f"  - **Started**: {started_at}")
            tasks_info.append(f"  - **Context**: Isolated temporary context (auto-cleanup)")
            tasks_info.append("")

        tasks_info.append("**Important**: Each tool runs in its own temporary context that is automatically")
        tasks_info.append("cleaned up after execution. Only the results are preserved.")
        tasks_info.append("")
        tasks_info.append("To retrieve results from these tasks, use the `wait_for_tasks` tool with the task IDs.")
        tasks_info.append("Example: `wait_for_tasks` with `tool_call_ids` parameter containing comma-separated task IDs.")

        # Add to extras_temporary so it appears in the system prompt
        loop_data.extras_temporary["tasks_in_progress"] = "\n".join(tasks_info)
