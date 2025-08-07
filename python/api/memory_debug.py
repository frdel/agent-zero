from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager
from python.helpers.memory import get_database_name
from python.helpers import files
import os
import time
import threading


class MemoryDebug(ApiHandler):

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST", "GET"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        """Debug endpoint for memory system issues"""
        debug_info = {
            "timestamp": time.time(),
            "thread_id": threading.get_ident(),
            "user_context": {},
            "memory_paths": {},
            "database_info": {},
            "file_access": {},
            "errors": []
        }

        try:
            # Test user context
            try:
                from flask import session
                username = session.get('username', 'unknown')
                is_admin = session.get('is_admin', False)

                # Get full user details if needed
                user_manager = get_user_manager()
                user = user_manager.get_user(username) if username != 'unknown' else None

                debug_info["user_context"] = {
                    "username": username,
                    "is_admin": is_admin,
                    "system_username": user.system_username if user else None,
                    "has_context": True
                }
            except Exception as e:
                debug_info["user_context"] = {
                    "has_context": False,
                    "error": str(e)
                }
                debug_info["errors"].append(f"User context error: {e}")

            # Test database name generation
            try:
                db_name = get_database_name()
                debug_info["database_info"] = {
                    "database_name": db_name,
                    "generation_success": True
                }
            except Exception as e:
                debug_info["database_info"] = {
                    "generation_success": False,
                    "error": str(e)
                }
                debug_info["errors"].append(f"Database name error: {e}")

            # Test memory path resolution
            try:
                memory_path = files.get_abs_path('memory', 'default')
                debug_info["memory_paths"] = {
                    "memory_default_path": memory_path,
                    "path_resolution_success": True
                }

                # Test file access
                debug_info["file_access"]["path_exists"] = os.path.exists(memory_path)
                if os.path.exists(memory_path):
                    try:
                        contents = os.listdir(memory_path)
                        debug_info["file_access"]["can_list"] = True
                        debug_info["file_access"]["item_count"] = len(contents)
                    except Exception as e:
                        debug_info["file_access"]["can_list"] = False
                        debug_info["file_access"]["list_error"] = str(e)
                        debug_info["errors"].append(f"Directory listing error: {e}")
                else:
                    # Try to create directory
                    try:
                        os.makedirs(memory_path, exist_ok=True)
                        debug_info["file_access"]["created_directory"] = True
                    except Exception as e:
                        debug_info["file_access"]["created_directory"] = False
                        debug_info["file_access"]["create_error"] = str(e)
                        debug_info["errors"].append(f"Directory creation error: {e}")

            except Exception as e:
                debug_info["memory_paths"] = {
                    "path_resolution_success": False,
                    "error": str(e)
                }
                debug_info["errors"].append(f"Path resolution error: {e}")

            # Additional system info
            debug_info["system_info"] = {
                "process_id": os.getpid(),
                "working_directory": os.getcwd(),
                "base_directory": files.get_base_dir()
            }

            return {
                "success": True,
                "debug_info": debug_info,
                "has_errors": len(debug_info["errors"]) > 0,
                "error_count": len(debug_info["errors"])
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "debug_info": debug_info
            }
