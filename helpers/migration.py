import os
import json
from helpers import files
from helpers import subagents, extension
from helpers import yaml as yaml_helper
from helpers.print_style import PrintStyle


def startup_migration() -> None:
    migrate_user_data()
    convert_agents_json_yaml()

    extension.call_extensions_sync("startup_migration", None)



def migrate_user_data() -> None:
    """
    Migrate user data from /tmp and other locations to /usr.
    """

    # --- Migrate Directories -------------------------------------------------------
    # Move directories from tmp/ or other source locations to usr/
    
    _move_dir("tmp/chats", "usr/chats")
    _move_dir("tmp/scheduler", "usr/scheduler", overwrite=True)
    _move_dir("tmp/uploads", "usr/uploads")
    _move_dir("tmp/upload", "usr/upload")
    _move_dir("tmp/downloads", "usr/downloads")
    _move_dir("tmp/email", "usr/email")
    _move_dir("knowledge/custom", "usr/knowledge", overwrite=True)

    # --- Migrate Files -------------------------------------------------------------
    # Move specific configuration files to usr/
    
    _move_file("tmp/settings.json", "usr/settings.json")
    _move_file("tmp/secrets.env", "usr/secrets.env")
    migrate_dotenv()

    # --- Special Migration Cases ---------------------------------------------------
    
    # Migrate Memory
    _migrate_memory()

    # Flatten default directories (knowledge/default -> knowledge/, etc.)
    # We use _merge_dir_contents because we want to move the *contents* of default/ 
    # into the parent directory, not move the default directory itself.
    _merge_dir_contents("knowledge/default", "knowledge")

    # --- Cleanup -------------------------------------------------------------------
    
    # Remove obsolete directories after migration
    _cleanup_obsolete()


def migrate_dotenv() -> None:
    """Preserve active configuration while migrating a legacy file or symlink."""
    source = files.get_abs_path(".env")
    destination = files.get_abs_path("usr/.env")
    if not os.path.lexists(source):
        return
    if os.path.lexists(destination):
        if not os.path.isfile(destination):
            raise ValueError("Cannot migrate .env: usr/.env must resolve to a regular file.")
        if not os.path.isfile(source) or not os.path.samefile(source, destination):
            PrintStyle.warning("Keeping existing usr/.env; legacy .env was left unchanged.")
        return
    if not os.path.isfile(source):
        raise ValueError("Cannot migrate .env: the legacy file must resolve to a regular file.")
    if not os.path.islink(source):
        _move_file(".env", "usr/.env")
        return

    # Relative targets must be rebased from usr/'s actual directory.
    PrintStyle().print("Migrating .env to usr/.env...")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    target = os.path.join(
        os.path.relpath(os.path.dirname(source), os.path.realpath(os.path.dirname(destination))),
        os.readlink(source),
    )
    os.symlink(target, destination)


def convert_agents_json_yaml() -> None:
    for root in subagents.get_agents_roots():
        rel_root = files.deabsolute_path(root)
        for subdir in files.get_subdirectories(rel_root):
            agent_yaml = os.path.join(rel_root, subdir, "agent.yaml")
            if files.exists(agent_yaml):
                continue

            agent_json = os.path.join(rel_root, subdir, "agent.json")
            if not files.exists(agent_json):
                continue

            try:
                agent_obj = json.loads(files.read_file(agent_json))
                files.write_file(agent_yaml, yaml_helper.dumps(agent_obj))
            except Exception as e:
                PrintStyle.error(f"Failed to convert {agent_json} to YAML", e)
                continue

# --- Helper Functions ----------------------------------------------------------

def _move_dir(src: str, dst: str, overwrite: bool = False) -> None:
    """
    Move a directory from src to dst if src exists and dst does not.
    """
    if files.exists(src) and (not files.exists(dst) or overwrite):
        PrintStyle().print(f"Migrating {src} to {dst}...")
        if overwrite and files.exists(dst):
            files.delete_dir(dst)
        files.move_dir(src, dst)

def _move_file(src: str, dst: str, overwrite: bool = False) -> None:
    """
    Move a file from src to dst if src exists and dst does not.
    """
    if files.exists(src) and (not files.exists(dst) or overwrite):
        PrintStyle().print(f"Migrating {src} to {dst}...")
        files.move_file(src, dst)

def _migrate_memory(base_path: str = "memory") -> None:
    """
    Migrate memory subdirectories.
    """
    subdirs = files.get_subdirectories(base_path)
    for subdir in subdirs:
        if subdir == "embeddings":
            # Special case: Embeddings
            _move_dir("memory/embeddings", "tmp/memory/embeddings")
        else:
            # Move other memory items to usr/memory
            dst = f"usr/memory/{subdir}"
            _move_dir(f"memory/{subdir}", dst)

def _merge_dir_contents(src_parent: str, dst_parent: str) -> None:
    """
    Moves all items from src_parent to dst_parent.
    Useful for flattening structures like 'knowledge/default/*' -> 'knowledge/*'.
    """
    if not files.exists(src_parent):
        return

    entries = files.list_files(src_parent)
    for entry in entries:
        src = f"{src_parent}/{entry}"
        dst = f"{dst_parent}/{entry}"
        abs_src = files.get_abs_path(src)
        if os.path.isdir(abs_src):
            _move_dir(src, dst)
        elif os.path.isfile(abs_src):
            _move_file(src, dst)

def _cleanup_obsolete() -> None:
    """
    Remove directories that are no longer needed.
    """
    to_remove = [
        "knowledge/default",
        "memory",
        "logs",
    ]
    for path in to_remove:
        if files.exists(path):
            PrintStyle().print(f"Removing {path}...")
            files.delete_dir(path)
