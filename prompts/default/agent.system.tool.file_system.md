file_system_tool:
  Description: Provides general file system access for CRUD operations, permissions, and file/directory statistics.
  Arguments:
    command (string): The file system operation to perform. Supported commands:
      - "read": Read content of a file.
        Arguments:
          path (string): The path to the file.
      - "write": Write content to a file.
        Arguments:
          path (string): The path to the file.
          content (string): The content to write.
          append (boolean, optional): If true, append to the file; otherwise, overwrite. Defaults to false.
      - "mkdir": Create a new directory.
        Arguments:
          path (string): The path to the new directory.
          recursive (boolean, optional): If true, create parent directories as needed. Defaults to false.
      - "ls": List contents of a directory.
        Arguments:
          path (string): The path to the directory.
          recursive (boolean, optional): If true, list contents recursively. Defaults to false.
      - "rm": Delete a file or directory.
        Arguments:
          path (string): The path to the file or directory.
          recursive (boolean, optional): If true, delete directory and its contents recursively. Required for non-empty directories. Defaults to false.
      - "mv": Move or rename a file/directory.
        Arguments:
          path (string): The current path to the file/directory.
          new_path (string): The new path/name for the file/directory.
      - "cp": Copy a file/directory.
        Arguments:
          path (string): The source path to the file/directory.
          new_path (string): The destination path for the copy.
      - "chmod": Change file/directory permissions.
        Arguments:
          path (string): The path to the file/directory.
          permissions (string/integer): The permissions in octal string (e.g., "755") or integer format.
      - "stat": Get file/directory statistics.
        Arguments:
          path (string): The path to the file/directory.
      - "exists": Check if a file or directory exists.
        Arguments:
          path (string): The path to the file/directory.
      - "symlink": Create a symbolic link.
        Arguments:
          path (string): The path to the symbolic link to create.
          target_path (string): The target path the symbolic link points to.
  Returns:
    string: A message indicating the success or failure of the operation, or the requested data (e.g., file content, directory listing, stats).
