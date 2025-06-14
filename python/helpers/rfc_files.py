import os
import shutil
import fnmatch
import base64
import tempfile
import zipfile
from python.helpers import runtime


def get_abs_path(*relative_paths):
    """Convert relative paths to absolute paths based on the base directory."""
    if not relative_paths:
        return os.path.abspath(os.path.dirname(__file__) + "/../..")

    base_dir = os.path.abspath(os.path.dirname(__file__) + "/../..")
    return os.path.join(base_dir, *relative_paths)


# =====================================================
# RFC-ENABLED FILESYSTEM OPERATIONS
# =====================================================

def read_file_bin(relative_path: str, backup_dirs=None) -> bytes:
    """
    Read binary file content.

    Args:
        relative_path: Path to the file relative to base directory
        backup_dirs: List of backup directories to search in

    Returns:
        File content as bytes
    """
    if backup_dirs is None:
        backup_dirs = []

    # Find the file in directories
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # Use RFC routing for development mode
    b64_content = runtime.call_development_function_sync(
        _read_file_binary_impl, absolute_path
    )
    return base64.b64decode(b64_content)


def read_file_base64(relative_path: str, backup_dirs=None) -> str:
    """
    Read file content and return as base64 string.

    Args:
        relative_path: Path to the file relative to base directory
        backup_dirs: List of backup directories to search in

    Returns:
        File content as base64 encoded string
    """
    if backup_dirs is None:
        backup_dirs = []

    # Find the file in directories
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _read_file_as_base64_impl, absolute_path
    )


def write_file_binary(relative_path: str, content: bytes) -> bool:
    """
    Write binary content to a file.

    Args:
        relative_path: Path to the file relative to base directory
        content: Binary content to write

    Returns:
        True if successful
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    b64_content = base64.b64encode(content).decode('utf-8')
    return runtime.call_development_function_sync(
        _write_file_binary_impl, abs_path, b64_content
    )


def write_file_base64(relative_path: str, content: str) -> bool:
    """
    Write base64 content to a file.

    Args:
        relative_path: Path to the file relative to base directory
        content: Base64 encoded content to write

    Returns:
        True if successful
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _write_file_from_base64_impl, abs_path, content
    )


def delete_file(relative_path: str) -> bool:
    """
    Delete a file.

    Args:
        relative_path: Path to the file relative to base directory

    Returns:
        True if successful
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _delete_file_impl, abs_path
    )


def delete_directory(relative_path: str) -> bool:
    """
    Delete a directory recursively.

    Args:
        relative_path: Path to the directory relative to base directory

    Returns:
        True if successful
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _delete_folder_impl, abs_path
    )


def list_directory(relative_path: str, include_hidden: bool = False) -> list:
    """
    List directory contents.

    Args:
        relative_path: Path to the directory relative to base directory
        include_hidden: Whether to include hidden files/folders

    Returns:
        List of directory items with metadata
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _list_folder_impl, abs_path, include_hidden
    )


def make_directories(relative_path: str) -> bool:
    """
    Create directories recursively.

    Args:
        relative_path: Path to create relative to base directory

    Returns:
        True if successful
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _make_dirs_impl, abs_path
    )


def path_exists(relative_path: str) -> bool:
    """
    Check if a path exists.

    Args:
        relative_path: Path to check relative to base directory

    Returns:
        True if path exists
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _path_exists_impl, abs_path
    )


def file_exists(relative_path: str) -> bool:
    """
    Check if a file exists.

    Args:
        relative_path: Path to check relative to base directory

    Returns:
        True if file exists
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _file_exists_impl, abs_path
    )


def folder_exists(relative_path: str) -> bool:
    """
    Check if a folder exists.

    Args:
        relative_path: Path to check relative to base directory

    Returns:
        True if folder exists
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _folder_exists_impl, abs_path
    )


def get_subdirectories(relative_path: str, include: str | list[str] = "*", exclude: str | list[str] | None = None) -> list[str]:
    """
    Get subdirectories in a directory.

    Args:
        relative_path: Path to the directory relative to base directory
        include: Pattern(s) to include
        exclude: Pattern(s) to exclude

    Returns:
        List of subdirectory names
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _get_subdirectories_impl, abs_path, include, exclude
    )


def zip_directory(relative_path: str) -> str:
    """
    Create a zip archive of a directory.

    Args:
        relative_path: Path to the directory relative to base directory

    Returns:
        Path to the created zip file
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _zip_dir_impl, abs_path
    )


def move_file(source_path: str, destination_path: str) -> bool:
    """
    Move a file from source to destination.

    Args:
        source_path: Source path relative to base directory
        destination_path: Destination path relative to base directory

    Returns:
        True if successful
    """
    source_abs = get_abs_path(source_path)
    dest_abs = get_abs_path(destination_path)

    # Use RFC routing for development mode
    return runtime.call_development_function_sync(
        _move_file_impl, source_abs, dest_abs
    )


def read_directory_as_zip(relative_path: str) -> bytes:
    """
    Read entire directory contents as a zip file.

    Args:
        relative_path: Path to the directory relative to base directory

    Returns:
        Zip file content as bytes
    """
    abs_path = get_abs_path(relative_path)

    # Use RFC routing for development mode
    b64_zip = runtime.call_development_function_sync(
        _read_directory_impl, abs_path
    )
    return base64.b64decode(b64_zip)


def find_file_in_dirs(file_path: str, backup_dirs: list[str]) -> str:
    """
    Find a file in the main directory or backup directories.

    Args:
        file_path: Relative file path to search for
        backup_dirs: List of backup directories to search in

    Returns:
        Absolute path to the found file

    Raises:
        FileNotFoundError: If file is not found in any directory
    """
    # Try the main path first
    main_path = get_abs_path(file_path)
    if runtime.call_development_function_sync(_file_exists_impl, main_path):
        return main_path

    # Try backup directories
    for backup_dir in backup_dirs:
        backup_path = os.path.join(backup_dir, file_path)
        if runtime.call_development_function_sync(_file_exists_impl, backup_path):
            return backup_path

    # File not found anywhere
    raise FileNotFoundError(f"File not found: {file_path}")


# =====================================================
# IMPLEMENTATION FUNCTIONS (Container Operations)
# =====================================================

def _read_file_binary_impl(file_path: str) -> str:
    """
    Implementation function to read a file in binary mode.
    Returns base64 encoded content for RFC transport.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        raise Exception(f"Path is not a file: {file_path}")

    try:
        with open(file_path, 'rb') as file:
            content = file.read()
            return base64.b64encode(content).decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to read file {file_path}: {str(e)}")


def _write_file_binary_impl(file_path: str, b64_content: str) -> bool:
    """
    Implementation function to write binary content to a file.
    Expects base64 encoded content from RFC transport.
    """
    try:
        # Ensure b64_content is properly UTF-8 encoded before base64 decoding
        if isinstance(b64_content, str):
            b64_content_bytes = b64_content.encode('utf-8')
        else:
            b64_content_bytes = b64_content

        # Decode base64 content
        content = base64.b64decode(b64_content_bytes)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write file
        with open(file_path, 'wb') as file:
            file.write(content)

        return True
    except Exception as e:
        raise Exception(f"Failed to write file {file_path}: {str(e)}")


def _delete_file_impl(file_path: str) -> bool:
    """
    Implementation function to delete a file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        raise Exception(f"Path is not a file: {file_path}")

    try:
        os.remove(file_path)
        return True
    except Exception as e:
        raise Exception(f"Failed to delete file {file_path}: {str(e)}")


def _delete_folder_impl(folder_path: str) -> bool:
    """
    Implementation function to delete a folder recursively.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not os.path.isdir(folder_path):
        raise Exception(f"Path is not a directory: {folder_path}")

    try:
        shutil.rmtree(folder_path)
        return True
    except Exception as e:
        raise Exception(f"Failed to delete folder {folder_path}: {str(e)}")


def _list_folder_impl(folder_path: str, include_hidden: bool = False) -> list:
    """
    Implementation function to list folder contents.
    """
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    if not os.path.isdir(folder_path):
        raise Exception(f"Path is not a directory: {folder_path}")

    try:
        items = []
        for item_name in os.listdir(folder_path):
            # Skip hidden files if not requested
            if not include_hidden and item_name.startswith('.'):
                continue

            item_path = os.path.join(folder_path, item_name)
            stat_info = os.stat(item_path)

            item_info = {
                "name": item_name,
                "path": item_path,
                "is_file": os.path.isfile(item_path),
                "is_dir": os.path.isdir(item_path),
                "size": stat_info.st_size,
                "modified": stat_info.st_mtime
            }
            items.append(item_info)

        # Sort by name for consistent output
        items.sort(key=lambda x: str(x["name"]).lower())
        return items

    except Exception as e:
        raise Exception(f"Failed to list folder {folder_path}: {str(e)}")


def _make_dirs_impl(folder_path: str) -> bool:
    """
    Implementation function to create directories.
    """
    try:
        os.makedirs(folder_path, exist_ok=True)
        return True
    except Exception as e:
        raise Exception(f"Failed to create directories {folder_path}: {str(e)}")


def _path_exists_impl(file_path: str) -> bool:
    """Implementation function to check if path exists."""
    return os.path.exists(file_path)


def _file_exists_impl(file_path: str) -> bool:
    """Implementation function to check if file exists."""
    return os.path.exists(file_path) and os.path.isfile(file_path)


def _folder_exists_impl(folder_path: str) -> bool:
    """Implementation function to check if folder exists."""
    return os.path.exists(folder_path) and os.path.isdir(folder_path)


def _get_subdirectories_impl(folder_path: str, include: str | list[str], exclude: str | list[str] | None) -> list[str]:
    """
    Implementation function to get subdirectories.
    """
    if not os.path.exists(folder_path):
        return []

    if isinstance(include, str):
        include = [include]
    if isinstance(exclude, str):
        exclude = [exclude]

    return [
        subdir
        for subdir in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, subdir))
        and any(fnmatch.fnmatch(subdir, inc) for inc in include)
        and (exclude is None or not any(fnmatch.fnmatch(subdir, exc) for exc in exclude))
    ]


def _zip_dir_impl(folder_path: str) -> str:
    """
    Implementation function to create a zip archive of a directory.
    """
    zip_file_path = tempfile.NamedTemporaryFile(suffix=".zip", delete=False).name
    base_name = os.path.basename(folder_path)

    with zipfile.ZipFile(zip_file_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, folder_path)
                zip_file.write(file_path, os.path.join(base_name, rel_path))

    return zip_file_path


def _move_file_impl(source_path: str, destination_path: str) -> bool:
    """
    Implementation function to move a file.
    """
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        os.rename(source_path, destination_path)
        return True
    except Exception as e:
        raise Exception(f"Failed to move file {source_path} to {destination_path}: {str(e)}")


def _read_directory_impl(dir_path: str) -> str:
    """
    Implementation function to zip a directory and return base64 encoded zip.
    """
    if not os.path.exists(dir_path):
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    if not os.path.isdir(dir_path):
        raise Exception(f"Path is not a directory: {dir_path}")

    temp_zip_path = None
    try:
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
            temp_zip_path = temp_zip.name

        # Create zip archive
        with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, dir_path)
                    zipf.write(file_path, arcname)

        # Read zip file and encode as base64
        with open(temp_zip_path, 'rb') as zipf:
            zip_content = zipf.read()
            b64_zip = base64.b64encode(zip_content).decode('utf-8')

        # Clean up temporary file
        os.unlink(temp_zip_path)

        return b64_zip

    except Exception as e:
        # Clean up temporary file if it exists
        if temp_zip_path is not None and os.path.exists(temp_zip_path):
            os.unlink(temp_zip_path)
        raise Exception(f"Failed to zip directory {dir_path}: {str(e)}")


def _read_file_as_base64_impl(file_path: str) -> str:
    """
    Implementation function to read a file and return its content as base64.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.path.isfile(file_path):
        raise Exception(f"Path is not a file: {file_path}")

    try:
        with open(file_path, 'rb') as file:
            content = file.read()
            return base64.b64encode(content).decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to read file {file_path}: {str(e)}")


def _write_file_from_base64_impl(file_path: str, content: str) -> bool:
    """
    Implementation function to write base64 content to a file.
    """
    try:
        # Ensure content is properly UTF-8 encoded before base64 decoding
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Decode base64 content
        decoded_content = base64.b64decode(content_bytes)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Write file
        with open(file_path, 'wb') as file:
            file.write(decoded_content)

        return True
    except Exception as e:
        raise Exception(f"Failed to write file {file_path}: {str(e)}")
