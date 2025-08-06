from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
from python.helpers.tasklist import TaskList
from python.helpers import files, runtime
from agent import AgentContext, LoopData


class CleanupTasklists(Extension):

    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Clean up orphaned tasklists that no longer have associated contexts"""
        try:
            tasklists_dir = "tmp/tasklists"

            # Check if tasklists directory exists
            if not await runtime.call_development_function(files.exists, tasklists_dir):
                return

            # Get all tasklist files
            file_list = await runtime.call_development_function(files.list_files, tasklists_dir, "*.json")

            for file in file_list:
                context_id = file.replace(".json", "")

                # Skip global tasklist
                if context_id == TaskList.GLOBAL_TASKLIST_UID:
                    continue

                # Check if context still exists
                if not AgentContext.get(context_id):
                    PrintStyle().debug(f"Tasklist {context_id} - context not found - removing")

                    # Delete from memory
                    TaskList.delete_instance(context_id)

                    # Delete from storage
                    file_path = f"tmp/tasklists/{file}"
                    if await runtime.call_development_function(files.exists, file_path):
                        await runtime.call_development_function(self._delete_file_helper, file_path)

        except Exception as e:
            PrintStyle().error(f"Error during tasklist cleanup: {e}")

    async def _delete_file_helper(self, file_path: str):
        """Helper function to delete a file using RFC calls"""
        import os
        abs_path = f"/a0/{file_path}"  # Convert relative to absolute
        if os.path.exists(abs_path):
            os.remove(abs_path)
