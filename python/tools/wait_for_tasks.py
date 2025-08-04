import asyncio
import uuid
from typing import Dict, Any
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class WaitForTasks(Tool):
    """
    Tool for retrieving results from parallel tool execution tasks.
    This is the only tool that executes synchronously to gather results.
    """

    async def execute(self, tool_call_ids: str = "", **kwargs) -> Response:
        """
        Wait for and retrieve results from specified tool call IDs.

        Args:
            tool_call_ids: Comma-separated list of tool call IDs to wait for
        """

        if not tool_call_ids:
            return Response(
                message="No tool call IDs provided. Please specify tool_call_ids parameter.",
                break_loop=False
            )

        # Parse tool call IDs
        task_ids = [tid.strip() for tid in tool_call_ids.split(",") if tid.strip()]

        if not task_ids:
            return Response(
                message="No valid tool call IDs found in the provided list.",
                break_loop=False
            )

        # Get active tasks from agent data
        active_tasks = self.agent.get_data("active_tool_tasks") or {}
        completed_tasks = self.agent.get_data("completed_tool_tasks") or {}

        results = {}
        not_found = []

        for task_id in task_ids:
            # Check if task is already completed (results stored directly by async execution)
            if task_id in completed_tasks:
                results[task_id] = completed_tasks[task_id]
                continue

            # Check if task is still running
            if task_id in active_tasks:
                task_info = active_tasks[task_id]
                asyncio_task = task_info.get("task")

                if asyncio_task and not asyncio_task.done():
                    try:
                        # Wait for the task to complete
                        PrintStyle(font_color="yellow").print(f"Waiting for task {task_id} to complete...")
                        await asyncio_task

                        # Task should have stored its result in completed_tasks
                        # Check if result is now available
                        if task_id in completed_tasks:
                            results[task_id] = completed_tasks[task_id]
                        else:
                            # Fallback if result wasn't stored properly
                            results[task_id] = {
                                "tool_name": task_info["tool_name"],
                                "result": "Task completed but result not found",
                                "success": False,
                                "started_at": task_info["started_at"]
                            }

                        # Remove from active tasks
                        del active_tasks[task_id]

                    except Exception as e:
                        # Task failed - check if error was already stored
                        if task_id in completed_tasks:
                            results[task_id] = completed_tasks[task_id]
                        else:
                            # Store error result if not already stored
                            error_result = {
                                "tool_name": task_info["tool_name"],
                                "result": f"Task failed with error: {str(e)}",
                                "success": False,
                                "started_at": task_info["started_at"]
                            }
                            completed_tasks[task_id] = error_result
                            results[task_id] = error_result

                        # Remove from active tasks
                        if task_id in active_tasks:
                            del active_tasks[task_id]

                elif asyncio_task and asyncio_task.done():
                    # Task is done, result should be in completed_tasks
                    if task_id in completed_tasks:
                        results[task_id] = completed_tasks[task_id]
                    else:
                        # Fallback - try to get result from task
                        try:
                            result = asyncio_task.result()
                            fallback_result = {
                                "tool_name": task_info["tool_name"],
                                "result": result.message if result else "No result",
                                "success": True,
                                "started_at": task_info["started_at"]
                            }
                            completed_tasks[task_id] = fallback_result
                            results[task_id] = fallback_result
                        except Exception as e:
                            error_result = {
                                "tool_name": task_info["tool_name"],
                                "result": f"Task failed with error: {str(e)}",
                                "success": False,
                                "started_at": task_info["started_at"]
                            }
                            completed_tasks[task_id] = error_result
                            results[task_id] = error_result

                    # Remove from active tasks
                    del active_tasks[task_id]
            else:
                not_found.append(task_id)

        # Update agent data
        self.agent.set_data("active_tool_tasks", active_tasks)
        self.agent.set_data("completed_tool_tasks", completed_tasks)

        # Format response
        response_parts = []

        if results:
            response_parts.append("## Task Results:")
            for task_id, result in results.items():
                status = "✅ SUCCESS" if result["success"] else "❌ FAILED"
                response_parts.append(f"\n**Task ID**: {task_id}")
                response_parts.append(f"**Tool**: {result['tool_name']}")
                response_parts.append(f"**Status**: {status}")
                response_parts.append(f"**Result**: {result['result']}")
                response_parts.append("---")

        if not_found:
            response_parts.append(f"\n## Not Found: {', '.join(not_found)}")
            response_parts.append("These task IDs were not found in active or completed tasks.")

        response_message = "\n".join(response_parts) if response_parts else "No results found."

        return Response(message=response_message, break_loop=False)
