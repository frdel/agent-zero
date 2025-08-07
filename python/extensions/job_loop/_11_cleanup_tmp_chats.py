from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
from python.helpers import persist_chat, files, runtime
from agent import LoopData, AgentContext, AgentContextType
import json


class CleanupTmpChats(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        """Clean up temporary chat files for BACKGROUND and MCP contexts that no longer exist"""
        try:
            # Use development function to check if chats directory exists
            if not await runtime.call_development_function(files.exists, "chats"):
                return

            # Get list of chat folders
            chat_folders = await runtime.call_development_function(files.list_files, "chats", "*")
            cleaned_count = 0

            for folder_name in chat_folders:
                chat_file_path = f"chats/{folder_name}/chat.json"
                if not await runtime.call_development_function(files.exists, chat_file_path):
                    continue

                try:
                    # Read chat data to get context type
                    chat_data = await runtime.call_development_function(files.read_file, chat_file_path)
                    data = json.loads(chat_data)

                    # Only clean up BACKGROUND and MCP contexts that no longer exist
                    context_type = data.get("type", AgentContextType.USER.value)
                    if context_type in [AgentContextType.BACKGROUND.value, AgentContextType.TASK.value]:
                        if not AgentContext.get(folder_name):
                            # BACKGROUND/MCP context no longer exists, remove its chat
                            await runtime.call_development_function(persist_chat.remove_chat, folder_name)
                            cleaned_count += 1
                            PrintStyle().debug(f"Cleaned up orphaned {context_type} context chat: {folder_name}")

                except Exception as e:
                    PrintStyle().debug(f"Error processing chat {folder_name}: {e}")
                    continue

            if cleaned_count > 0:
                PrintStyle().debug(f"Cleaned up {cleaned_count} orphaned BACKGROUND/MCP context chats")

        except Exception as e:
            PrintStyle().error(f"Error during tmp chats cleanup: {e}")
