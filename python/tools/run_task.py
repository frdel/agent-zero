import asyncio
import uuid
import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from agent import Agent, AgentContext, AgentContextType, LoopData


class RunTask(Tool):
    """
    Wrapper tool for executing other tools in background contexts.

    This tool takes another tool call as parameters and executes it in an isolated
    background context, returning a task ID that can be used with wait_for_tasks
    to retrieve the results.
    """

    async def execute(self, tool_name: str = "", method: str = "", args: str = "{}", message: str = "", **kwargs) -> Response:
        """
        Execute a tool in a background context.

        Args:
            tool_name: Name of the tool to execute
            method: Optional method to call on the tool
            args: JSON string containing arguments for the target tool
            message: Optional message context for the tool
        """

        if not tool_name:
            return Response(
                message="Error: tool_name parameter is required",
                break_loop=False
            )

        # Parse tool arguments
        try:
            tool_args = json.loads(args) if args else {}
            if not isinstance(tool_args, dict):
                return Response(
                    message="Error: args must be a JSON object",
                    break_loop=False
                )
        except json.JSONDecodeError as e:
            return Response(
                message=f"Error: Invalid JSON in args parameter: {str(e)}",
                break_loop=False
            )

        # Generate task ID
        task_id = str(uuid.uuid4())

        # Create async task for tool execution in temporary context
        async def execute_tool_async():
            # Create temporary context for isolated execution
            temp_context = AgentContext(
                config=self.agent.config,
                type=AgentContextType.BACKGROUND
            )

            # Create temporary agent in the isolated context
            temp_agent = Agent(self.agent.number + 1000, self.agent.config, temp_context)
            temp_agent.config.profile = self.agent.config.profile  # Keep same profile

            try:
                # Create tool instance in temporary context
                # Ensure temp agent has loop_data
                if not hasattr(temp_agent, 'loop_data') or temp_agent.loop_data is None:
                    temp_agent.loop_data = LoopData()

                # Try to get the tool from the temporary agent
                temp_tool = temp_agent.get_tool(
                    name=tool_name,
                    method=method,
                    args=tool_args,
                    message=message or "",
                    loop_data=temp_agent.loop_data
                )

                if not temp_tool:
                    raise Exception(f"Tool '{tool_name}' not found or could not be initialized")

                # Update tool to use temporary agent
                temp_tool.agent = temp_agent

                # Execute tool in isolated context
                await temp_agent.handle_intervention()
                await temp_tool.before_execution(**tool_args)
                await temp_agent.handle_intervention()
                response = await temp_tool.execute(**tool_args)
                await temp_agent.handle_intervention()
                await temp_tool.after_execution(response)
                await temp_agent.handle_intervention()

                # Store result persistently in main agent's storage
                completed_tasks = self.agent.get_data("completed_tool_tasks") or {}
                completed_tasks[task_id] = {
                    "tool_name": tool_name + (f":{method}" if method else ""),
                    "result": response.message if response else "No result",
                    "success": True,
                    "started_at": datetime.now().isoformat(),
                    "context_id": temp_context.id
                }
                self.agent.set_data("completed_tool_tasks", completed_tasks)

                return response

            except Exception as e:
                # Store error result persistently
                completed_tasks = self.agent.get_data("completed_tool_tasks") or {}
                completed_tasks[task_id] = {
                    "tool_name": tool_name + (f":{method}" if method else ""),
                    "result": f"Tool execution failed: {str(e)}",
                    "success": False,
                    "started_at": datetime.now().isoformat(),
                    "context_id": temp_context.id
                }
                self.agent.set_data("completed_tool_tasks", completed_tasks)

                # Log error but don't re-raise to prevent unhandled background exceptions
                PrintStyle(font_color="red", padding=True).print(
                    f"Tool execution failed in task {task_id}: {str(e)}"
                )

            finally:
                # Always clean up temporary context
                try:
                    temp_context.reset()
                    AgentContext.remove(temp_context.id)
                except Exception as cleanup_error:
                    PrintStyle(font_color="red", padding=True).print(
                        f"Warning: Failed to clean up temporary context {temp_context.id}: {cleanup_error}"
                    )

        # Create the asyncio task
        asyncio_task = asyncio.create_task(execute_tool_async())

        # Store task information in agent data
        active_tasks = self.agent.get_data("active_tool_tasks") or {}
        active_tasks[task_id] = {
            "tool_name": tool_name + (f":{method}" if method else ""),
            "task": asyncio_task,
            "started_at": datetime.now().isoformat(),
            "args": tool_args
        }
        self.agent.set_data("active_tool_tasks", active_tasks)

        # Add task start info to history
        tool_display_name = tool_name + (f":{method}" if method else "")
        task_message = f"Started tool '{tool_display_name}' with task ID: {task_id} (isolated context)"
        PrintStyle(font_color="green", padding=True).print(task_message)
        # self.agent.context.log.log(
        #     type="tool", content=f"{self.agent.agent_name}: {task_message}"
        # )

        # Return task information
        response_message = (f"Task '{tool_display_name}' is now running in background with task ID: {task_id}. "
                            f"You can continue with other actions or use wait_for_tasks to retrieve the result when needed.")

        return Response(message=response_message, break_loop=False)
