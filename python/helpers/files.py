from abc import ABC, abstractmethod
from fnmatch import fnmatch
import json
import os
import sys
import re
import base64
import shutil
import tempfile
from typing import Any, Dict, List
import zipfile
import importlib
import importlib.util
import inspect
import glob


class VariablesPlugin(ABC):
    @abstractmethod
    def get_variables(self, file: str, backup_dirs: List[str] = None) -> Dict[str, Any]:  # type: ignore
        pass


def load_plugin_variables(file: str, backup_dirs: List[str] = None) -> Dict[str, Any]:
    if not file.endswith(".md"):
        return {}

    if backup_dirs is None:
        backup_dirs = []

    try:
        plugin_file = find_file_in_dirs(
            get_abs_path(dirname(file), basename(file, ".md") + ".py"),
            backup_dirs
        )
    except FileNotFoundError:
        plugin_file = None

    if plugin_file and exists(plugin_file):

        from python.helpers import extract_tools
        classes = extract_tools.load_classes_from_file(plugin_file, VariablesPlugin, one_per_file=False)
        for cls in classes:
            return cls().get_variables(file, backup_dirs) # type: ignore < abstract class here is ok, it is always a subclass

        # load python code and extract variables variables from it
        # module = None
        # module_name = dirname(plugin_file).replace("/", ".") + "." + basename(plugin_file, '.py')

        # try:
        #     spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        #     if not spec:
        #         return {}
        #     module = importlib.util.module_from_spec(spec)
        #     sys.modules[spec.name] = module
        #     spec.loader.exec_module(module)  # type: ignore
        # except ImportError:
        #     return {}

        # if module is None:
        #     return {}

        # # Get all classes in the module
        # class_list = inspect.getmembers(module, inspect.isclass)
        # # Filter for classes that are subclasses of VariablesPlugin
        # # iterate backwards to skip imported superclasses
        # for cls in reversed(class_list):
        #     if cls[1] is not VariablesPlugin and issubclass(cls[1], VariablesPlugin):
        #         return cls[1]().get_variables()  # type: ignore
    return {}

from python.helpers.strings import sanitize_string


def parse_file(_relative_path, _backup_dirs=None, _encoding="utf-8", **kwargs):
    if _backup_dirs is None:
        _backup_dirs = []

    # Try to get the absolute path for the file from the original directory or backup directories
    absolute_path = find_file_in_dirs(_relative_path, _backup_dirs)

    # Read the file content
    with open(absolute_path, "r", encoding=_encoding) as f:
        # content = remove_code_fences(f.read())
        content = f.read()

    is_json = is_full_json_template(content)
    content = remove_code_fences(content)
    variables = load_plugin_variables(_relative_path, _backup_dirs) or {}  # type: ignore
    variables.update(kwargs)
    if is_json:
        content = replace_placeholders_json(content, **variables)
        obj = json.loads(content)
        # obj = replace_placeholders_dict(obj, **variables)
        return obj
    else:
        content = replace_placeholders_text(content, **variables)
        # Process include statements
        content = process_includes(
            # here we use kwargs, the plugin variables are not inherited
            content, os.path.dirname(_relative_path), _backup_dirs, **kwargs
        )
        return content


def read_prompt_file(_relative_path, _backup_dirs=None, _encoding="utf-8", **kwargs):
    if _backup_dirs is None:
        _backup_dirs = []

    # Try to get the absolute path for the file from the original directory or backup directories
    absolute_path = find_file_in_dirs(_relative_path, _backup_dirs)

    # Read the file content
    with open(absolute_path, "r", encoding=_encoding) as f:
        # content = remove_code_fences(f.read())
        content = f.read()

    variables = load_plugin_variables(_relative_path, _backup_dirs) or {}  # type: ignore
    variables.update(kwargs)

    # Replace placeholders with values from kwargs
    content = replace_placeholders_text(content, **variables)

    # Process include statements
    content = process_includes(
        # here we use kwargs, the plugin variables are not inherited
        content, os.path.dirname(_relative_path), _backup_dirs, **kwargs
    )

    return content


def read_file(relative_path:str, backup_dirs:list[str]|None=None, encoding="utf-8"):
    if backup_dirs is None:
        backup_dirs = []

    # Try to get the absolute path for the file from the original directory or backup directories
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # Read the file content
    with open(absolute_path, "r", encoding=encoding) as f:
        return f.read()


def read_file_bin(relative_path:str, backup_dirs:list[str]|None=None):
    if backup_dirs is None:
        backup_dirs = []

    # Try to get the absolute path for the file from the original directory or backup directories
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # read binary content
    with open(absolute_path, "rb") as f:
        return f.read()


def read_file_base64(relative_path, backup_dirs:list[str]|None=None):
    # init backup dirs
    if backup_dirs is None:
        backup_dirs = []

    # get absolute path
    absolute_path = find_file_in_dirs(relative_path, backup_dirs)

    # read binary content and encode to base64
    with open(absolute_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def replace_placeholders_text(_content: str, **kwargs):
    # Replace placeholders with values from kwargs
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        strval = str(value)
        _content = _content.replace(placeholder, strval)
    return _content


def replace_placeholders_json(_content: str, **kwargs):
    # Replace placeholders with values from kwargs
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        strval = json.dumps(value)
        _content = _content.replace(placeholder, strval)
    return _content


def replace_placeholders_dict(_content: dict, **kwargs):
    def replace_value(value):
        if isinstance(value, str):
            placeholders = re.findall(r"{{(\w+)}}", value)
            if placeholders:
                for placeholder in placeholders:
                    if placeholder in kwargs:
                        replacement = kwargs[placeholder]
                        if value == f"{{{{{placeholder}}}}}":
                            return replacement
                        elif isinstance(replacement, (dict, list)):
                            value = value.replace(
                                f"{{{{{placeholder}}}}}", json.dumps(replacement)
                            )
                        else:
                            value = value.replace(
                                f"{{{{{placeholder}}}}}", str(replacement)
                            )
            return value
        elif isinstance(value, dict):
            return {k: replace_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [replace_value(item) for item in value]
        else:
            return value

    return replace_value(_content)


def process_includes(_content, _base_path, _backup_dirs, **kwargs):
    # Regex to find {{ include 'path' }} or {{include'path'}}
    include_pattern = re.compile(r"{{\s*include\s*['\"](.*?)['\"]\s*}}")

    def replace_include(match):
        include_path = match.group(1)
        # if the path is absolute, do not process it
        if os.path.isabs(include_path):
            return match.group(0)
        # First attempt to resolve the include relative to the base path
        full_include_path = find_file_in_dirs(
            os.path.join(_base_path, include_path), _backup_dirs
        )

        # Recursively read the included file content, keeping the original base path
        included_content = read_prompt_file(full_include_path, _backup_dirs, **kwargs)
        return included_content

    # Replace all includes with the file content
    return re.sub(include_pattern, replace_include, _content)


def find_file_in_dirs(file_path, backup_dirs):
    """
    This function tries to find the file first in the given file_path,
    and then in the backup_dirs if not found in the original location.
    Returns the absolute path of the found file.
    """
    # Try the original path first
    if os.path.isfile(get_abs_path(file_path)):
        return get_abs_path(file_path)

    # Loop through the backup directories
    for backup_dir in backup_dirs:
        # backup path should be os.path.join(backup_dir, file_path) but that can lead to problems
        # with absolute paths in file_path. So we use basename.
        # This means that we don't support include paths like "subdir/something.md" from backups
        backup_path = os.path.join(backup_dir, os.path.basename(file_path))
        if os.path.isfile(get_abs_path(backup_path)):
            return get_abs_path(backup_path)

    # If the file is not found, let it raise the FileNotFoundError
    raise FileNotFoundError(
        f"File '{file_path}' not found in the original path or backup directories."
    )

def get_unique_filenames_in_dirs(dir_paths: list[str], pattern: str = "*"):
    # returns absolute paths for unique filenames, priority by order in dir_paths
    seen = set()
    result = []
    for dir_path in dir_paths:
        full_dir = get_abs_path(dir_path)
        for file_path in glob.glob(os.path.join(full_dir, pattern)):
            fname = os.path.basename(file_path)
            if fname not in seen and os.path.isfile(file_path):
                seen.add(fname)
                result.append(get_abs_path(file_path))
    # sort by filename (basename), not the full path
    result.sort(key=lambda path: os.path.basename(path))
    return result

def remove_code_fences(text):
    # Pattern to match code fences with optional language specifier
    pattern = r"(```|~~~)(.*?\n)(.*?)(\1)"

    # Function to replace the code fences
    def replacer(match):
        return match.group(3)  # Return the code without fences

    # Use re.DOTALL to make '.' match newlines
    result = re.sub(pattern, replacer, text, flags=re.DOTALL)

    return result


def is_full_json_template(text):
    # Pattern to match the entire text enclosed in ```json or ~~~json fences
    pattern = r"^\s*(```|~~~)\s*json\s*\n(.*?)\n\1\s*$"
    # Use re.DOTALL to make '.' match newlines
    match = re.fullmatch(pattern, text.strip(), flags=re.DOTALL)
    return bool(match)


def write_file(relative_path: str, content: str, encoding: str = "utf-8"):
    abs_path = get_abs_path(relative_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    content = sanitize_string(content, encoding)
    with open(abs_path, "w", encoding=encoding) as f:
        f.write(content)


def write_file_bin(relative_path: str, content: bytes):
    abs_path = get_abs_path(relative_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(content)


def write_file_base64(relative_path: str, content: str):
    # decode base64 string to bytes
    data = base64.b64decode(content)
    abs_path = get_abs_path(relative_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(data)


def delete_dir(relative_path: str):
    # ensure deletion of directory without propagating errors
    abs_path = get_abs_path(relative_path)
    if os.path.exists(abs_path):
        # first try with ignore_errors=True which is the safest option
        shutil.rmtree(abs_path, ignore_errors=True)

        # if directory still exists, try more aggressive methods
        if os.path.exists(abs_path):
            try:
                # try to change permissions and delete again
                for root, dirs, files in os.walk(abs_path, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        os.chmod(file_path, 0o777)
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        os.chmod(dir_path, 0o777)

                # try again after changing permissions
                shutil.rmtree(abs_path, ignore_errors=True)
            except:
                # suppress all errors - we're ensuring no errors propagate
                pass


def list_files(relative_path: str, filter: str = "*"):
    abs_path = get_abs_path(relative_path)
    if not os.path.exists(abs_path):
        return []
    return [file for file in os.listdir(abs_path) if fnmatch(file, filter)]


def make_dirs(relative_path: str):
    abs_path = get_abs_path(relative_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)


def get_abs_path(*relative_paths):
    "Convert relative paths to absolute paths based on the base directory."
    # Normalize first path segment to support inputs like "tmp/settings.json"
    if relative_paths:
        first = relative_paths[0]
        # If first is a composite path, split it and check the first component
        if isinstance(first, str) and ("/" in first or os.sep in first):
            parts = first.split(os.sep)
            if parts and _is_user_data_directory(parts[0]):
                combined = tuple([parts[0]] + parts[1:] + list(relative_paths[1:]))
                return _get_user_specific_path(*combined)
        # Regular check for user-specific directories
        if _is_user_data_directory(first):
            return _get_user_specific_path(*relative_paths)
    return os.path.join(get_base_dir(), *relative_paths)


def _is_user_data_directory(path: str) -> bool:
    """Check if the path is a user-specific data directory"""
    user_data_dirs = {'memory', 'knowledge', 'logs', 'tmp'}
    return path in user_data_dirs


def _get_user_specific_path(*relative_paths) -> str:
    """Get user-specific path for data directories"""
    try:
        from python.helpers.user_management import get_user_manager
        user_manager = get_user_manager()
        username = user_manager.get_current_username_safe()

        # If the username is already present as the second path segment, don't insert it again
        if len(relative_paths) >= 2 and relative_paths[1] == username:
            user_path = os.path.join(get_base_dir(), *relative_paths)
        else:
            # Insert username after the first directory component
            if len(relative_paths) == 1:
                user_path = os.path.join(get_base_dir(), relative_paths[0], username)
            else:
                user_path = os.path.join(get_base_dir(), relative_paths[0], username, *relative_paths[1:])

        # Ensure the user data directory exists
        os.makedirs(os.path.dirname(user_path), exist_ok=True)
        if len(relative_paths) == 1:
            # If requesting just the base directory (e.g., "tmp"), create it too
            os.makedirs(user_path, exist_ok=True)

        return user_path
    except (ImportError, RuntimeError):
        # If no user context or user management not available, fall back to original behavior
        return os.path.join(get_base_dir(), *relative_paths)

def deabsolute_path(path:str):
    "Convert absolute paths to relative paths based on the base directory."
    return os.path.relpath(path, get_base_dir())

def fix_dev_path(path:str):
    "On dev environment, convert /a0/... paths to local absolute paths"
    from python.helpers.runtime import is_development
    if is_development():
        if path.startswith("/a0/"):
            path = path.replace("/a0/", "")
    return get_abs_path(path)

def exists(*relative_paths):
    path = get_abs_path(*relative_paths)
    return os.path.exists(path)


def get_base_dir():
    # Get the base directory from the current file path
    base_dir = os.path.dirname(os.path.abspath(os.path.join(__file__, "../../")))
    return base_dir


def basename(path: str, suffix: str | None = None):
    if suffix:
        return os.path.basename(path).removesuffix(suffix)
    return os.path.basename(path)


def dirname(path: str):
    return os.path.dirname(path)


def is_in_base_dir(path: str):
    # check if the given path is within the base directory
    base_dir = get_base_dir()
    # normalize paths to handle relative paths and symlinks
    abs_path = os.path.abspath(path)
    # check if the absolute path starts with the base directory
    return os.path.commonpath([abs_path, base_dir]) == base_dir


def get_subdirectories(
    relative_path: str,
    include: str | list[str] = "*",
    exclude: str | list[str] | None = None,
):
    abs_path = get_abs_path(relative_path)
    if not os.path.exists(abs_path):
        return []
    if isinstance(include, str):
        include = [include]
    if isinstance(exclude, str):
        exclude = [exclude]
    return [
        subdir
        for subdir in os.listdir(abs_path)
        if os.path.isdir(os.path.join(abs_path, subdir))
        and any(fnmatch(subdir, inc) for inc in include)
        and (exclude is None or not any(fnmatch(subdir, exc) for exc in exclude))
    ]


def zip_dir(dir_path: str):
    full_path = get_abs_path(dir_path)
    zip_file_path = tempfile.NamedTemporaryFile(suffix=".zip", delete=False).name
    base_name = os.path.basename(full_path)
    with zipfile.ZipFile(zip_file_path, "w", compression=zipfile.ZIP_DEFLATED) as zip:
        for root, _, files in os.walk(full_path):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, full_path)
                zip.write(file_path, os.path.join(base_name, rel_path))
    return zip_file_path


def move_file(relative_path: str, new_path: str):
    abs_path = get_abs_path(relative_path)
    new_abs_path = get_abs_path(new_path)
    os.makedirs(os.path.dirname(new_abs_path), exist_ok=True)
    os.rename(abs_path, new_abs_path)


def safe_file_name(filename: str) -> str:
    # Replace any character that's not alphanumeric, dash, underscore, or dot with underscore
    return re.sub(r'[^a-zA-Z0-9-._]', '_', filename)
