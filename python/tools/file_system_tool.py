import os
import shutil
import stat
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers import files

class FileSystemTool(Tool):

    def __init__(self, agent=None, **kwargs):
        super().__init__(agent=agent, **kwargs)
        
    async def execute(self, **kwargs):
        await self.agent.handle_intervention()

        command = self.args.get("command", "").lower().strip()
        path = self.args.get("path")
        
        if not path:
            return Response(message="Error: 'path' argument is required for all file system commands.", break_loop=False)

        try:
            if command == "read":
                response = self._read_file(path)
            elif command == "write":
                content = self.args.get("content")
                append = self.args.get("append", False)
                response = self._write_file(path, content, append)
            elif command == "mkdir":
                recursive = self.args.get("recursive", False)
                response = self._create_directory(path, recursive)
            elif command == "ls":
                recursive = self.args.get("recursive", False)
                response = self._list_directory(path, recursive)
            elif command == "rm":
                recursive = self.args.get("recursive", False)
                response = self._delete_path(path, recursive)
            elif command == "mv":
                new_path = self.args.get("new_path")
                response = self._move_path(path, new_path)
            elif command == "cp":
                new_path = self.args.get("new_path")
                response = self._copy_path(path, new_path)
            elif command == "chmod":
                permissions = self.args.get("permissions")
                response = self._change_permissions(path, permissions)
            elif command == "stat":
                response = self._get_stats(path)
            elif command == "exists":
                response = self._check_existence(path)
            elif command == "symlink":
                target_path = self.args.get("target_path")
                response = self._create_symlink(path, target_path)
            else:
                response = f"Error: Unknown command '{command}'. Supported commands: read, write, mkdir, ls, rm, mv, cp, chmod, stat, exists, symlink. Note: 'chown' is not supported on Windows."
            
            return Response(message=response, break_loop=False)

        except FileNotFoundError:
            return Response(message=f"Error: Path not found - {path}", break_loop=False)
        except IsADirectoryError:
            return Response(message=f"Error: Expected a file but got a directory - {path}", break_loop=False)
        except NotADirectoryError:
            return Response(message=f"Error: Expected a directory but got a file - {path}", break_loop=False)
        except PermissionError:
            return Response(message=f"Error: Permission denied for operation on {path}", break_loop=False)
        except Exception as e:
            return Response(message=f"An unexpected error occurred: {e}", break_loop=False)

    def _read_file(self, path):
        with open(path, 'r') as f:
            content = f.read()
        return f"Content of {path}:\n{content}"

    def _write_file(self, path, content, append):
        mode = 'a' if append else 'w'
        with open(path, mode) as f:
            f.write(content)
        return f"Content written to {path} (append={append})."

    def _create_directory(self, path, recursive):
        if recursive:
            os.makedirs(path, exist_ok=True)
        else:
            os.mkdir(path)
        return f"Directory {path} created (recursive={recursive})."

    def _list_directory(self, path, recursive):
        if not os.path.isdir(path):
            raise NotADirectoryError(f"{path} is not a directory.")
        
        if recursive:
            output = []
            for root, dirs, files in os.walk(path):
                level = root.replace(path, '').count(os.sep)
                indent = ' ' * 4 * (level)
                output.append(f"{indent}{os.path.basename(root)}/")
                subindent = ' ' * 4 * (level + 1)
                for f in files:
                    output.append(f"{subindent}{f}")
            return "\n".join(output)
        else:
            return "\n".join(os.listdir(path))

    def _delete_path(self, path, recursive):
        if os.path.isfile(path):
            os.remove(path)
            return f"File {path} deleted."
        elif os.path.isdir(path):
            if recursive:
                shutil.rmtree(path)
                return f"Directory {path} and its contents deleted recursively."
            else:
                os.rmdir(path)
                return f"Empty directory {path} deleted."
        else:
            raise FileNotFoundError(f"{path} does not exist.")

    def _move_path(self, path, new_path):
        shutil.move(path, new_path)
        return f"Moved {path} to {new_path}."

    def _copy_path(self, path, new_path):
        if os.path.isfile(path):
            shutil.copy2(path, new_path)
            return f"Copied file {path} to {new_path}."
        elif os.path.isdir(path):
            shutil.copytree(path, new_path)
            return f"Copied directory {path} to {new_path}."
        else:
            raise FileNotFoundError(f"{path} does not exist.")

    def _change_permissions(self, path, permissions):
        if isinstance(permissions, str):
            # Convert octal string (e.g., "755") to integer
            permissions = int(permissions, 8)
        os.chmod(path, permissions)
        return f"Permissions of {path} changed to {oct(permissions)}."

    def _get_stats(self, path):
        stats = os.stat(path)
        return (
            f"Stats for {path}:\n"
            f"  Size: {stats.st_size} bytes\n"
            f"  Last modified: {stats.st_mtime} (timestamp)\n"
            f"  Last accessed: {stats.st_atime} (timestamp)\n"
            f"  Creation time: {stats.st_ctime} (timestamp)\n"
            f"  Mode: {oct(stats.st_mode)} (permissions)\n"
            f"  Inode: {stats.st_ino}\n"
            f"  Device: {stats.st_dev}\n"
            f"  Number of links: {stats.st_nlink}\n"
            f"  User ID of owner: {stats.st_uid}\n"
            f"  Group ID of owner: {stats.st_gid}"
        )

    def _check_existence(self, path):
        exists = os.path.exists(path)
        return f"Path {path} exists: {exists}."

    def _create_symlink(self, path, target_path):
        os.symlink(target_path, path)
        return f"Symbolic link from {path} to {target_path} created."

    def get_log_object(self):
        return self.agent.context.log.log(
            type="info",
            heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
            content="",
            kvps=self.args,
        )

    async def after_execution(self, response, **kwargs):
        self.agent.hist_add_tool_result(self.name, response.message)
