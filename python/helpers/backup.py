import zipfile
import json
import os
import tempfile
import datetime
import platform
from typing import List, Dict, Any, Optional

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from python.helpers import files, runtime, git
from python.helpers.print_style import PrintStyle


class BackupService:
    """
    Core backup and restore service for Agent Zero.

    Features:
    - JSON-based metadata with user-editable path specifications
    - Comprehensive system information collection
    - Checksum validation for integrity
    - RFC compatibility through existing file helpers
    - Git version integration consistent with main application
    """

    def __init__(self):
        self.agent_zero_version = self._get_agent_zero_version()
        self.agent_zero_root = files.get_abs_path("")  # Resolved Agent Zero root

        # Build base paths map for pattern resolution
        self.base_paths = {
            self.agent_zero_root: self.agent_zero_root,
        }

    def get_default_backup_metadata(self) -> Dict[str, Any]:
        """Get default backup patterns and metadata"""
        timestamp = datetime.datetime.now().isoformat()

        default_patterns = self._get_default_patterns()
        include_patterns, exclude_patterns = self._parse_patterns(default_patterns)

        return {
            "backup_name": f"agent-zero-backup-{timestamp[:10]}",
            "include_hidden": False,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "backup_config": {
                "compression_level": 6,
                "integrity_check": True
            }
        }

    def _get_default_patterns(self) -> str:
        """Get default backup patterns with resolved absolute paths.

        Only includes Agent Zero project directory patterns.
        """
        # Ensure paths don't have double slashes
        agent_root = self.agent_zero_root.rstrip('/')

        return f"""# Agent Zero Knowledge (excluding defaults)
{agent_root}/knowledge/**
!{agent_root}/knowledge/default/**

# Agent Zero Instruments (excluding defaults)
{agent_root}/instruments/**
!{agent_root}/instruments/default/**

# Memory (excluding embeddings cache)
{agent_root}/memory/**
!{agent_root}/memory/**/embeddings/**

# Configuration and Settings (CRITICAL)
{agent_root}/.env
{agent_root}/tmp/settings.json
{agent_root}/tmp/chats/**
{agent_root}/tmp/scheduler/**
{agent_root}/tmp/uploads/**"""

    def _get_agent_zero_version(self) -> str:
        """Get current Agent Zero version"""
        try:
            # Get version from git info (same as run_ui.py)
            gitinfo = git.get_git_info()
            return gitinfo.get("version", "development")
        except Exception:
            return "unknown"

    def _resolve_path(self, pattern_path: str) -> str:
        """Resolve pattern path to absolute system path (now patterns are already absolute)"""
        return pattern_path

    def _unresolve_path(self, abs_path: str) -> str:
        """Convert absolute path back to pattern path (now patterns are already absolute)"""
        return abs_path

    def _parse_patterns(self, patterns: str) -> tuple[list[str], list[str]]:
        """Parse patterns string into include and exclude pattern arrays"""
        include_patterns = []
        exclude_patterns = []

        for line in patterns.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('!'):
                # Exclude pattern
                exclude_patterns.append(line[1:])  # Remove the '!' prefix
            else:
                # Include pattern
                include_patterns.append(line)

        return include_patterns, exclude_patterns

    def _patterns_to_string(self, include_patterns: list[str], exclude_patterns: list[str]) -> str:
        """Convert pattern arrays back to patterns string for pathspec processing"""
        patterns = []

        # Add include patterns
        for pattern in include_patterns:
            patterns.append(pattern)

        # Add exclude patterns with '!' prefix
        for pattern in exclude_patterns:
            patterns.append(f"!{pattern}")

        return '\n'.join(patterns)

    async def _get_system_info(self) -> Dict[str, Any]:
        """Collect system information for metadata"""
        import psutil

        try:
            return {
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "architecture": platform.architecture()[0],
                "hostname": platform.node(),
                "python_version": platform.python_version(),
                "cpu_count": str(psutil.cpu_count()),
                "memory_total": str(psutil.virtual_memory().total),
                "disk_usage": str(psutil.disk_usage('/').total if os.path.exists('/') else 0)
            }
        except Exception as e:
            return {"error": f"Failed to collect system info: {str(e)}"}

    async def _get_environment_info(self) -> Dict[str, Any]:
        """Collect environment information for metadata"""
        try:
            return {
                "user": os.environ.get("USER", "unknown"),
                "home": os.environ.get("HOME", "unknown"),
                "shell": os.environ.get("SHELL", "unknown"),
                "path": os.environ.get("PATH", "")[:200] + "..." if len(os.environ.get("PATH", "")) > 200 else os.environ.get("PATH", ""),
                "timezone": str(datetime.datetime.now().astimezone().tzinfo),
                "working_directory": os.getcwd(),
                "agent_zero_root": files.get_abs_path(""),
                "runtime_mode": "development" if runtime.is_development() else "production"
            }
        except Exception as e:
            return {"error": f"Failed to collect environment info: {str(e)}"}

    async def _get_backup_author(self) -> str:
        """Get backup author/system identifier"""
        try:
            import getpass
            username = getpass.getuser()
            hostname = platform.node()
            return f"{username}@{hostname}"
        except Exception:
            return "unknown"

    def _count_directories(self, matched_files: List[Dict[str, Any]]) -> int:
        """Count unique directories in file list"""
        directories = set()
        for file_info in matched_files:
            dir_path = os.path.dirname(file_info["path"])
            if dir_path:
                directories.add(dir_path)
        return len(directories)

    def _get_explicit_patterns(self, include_patterns: List[str]) -> set[str]:
        """Extract explicit (non-wildcard) patterns that should always be included"""
        explicit_patterns = set()

        for pattern in include_patterns:
            # If pattern doesn't contain wildcards, it's explicit
            if '*' not in pattern and '?' not in pattern:
                # Remove leading slash for comparison
                explicit_patterns.add(pattern.lstrip('/'))

                # Also add parent directories as explicit (so hidden dirs can be traversed)
                path_parts = pattern.lstrip('/').split('/')
                for i in range(1, len(path_parts)):
                    parent_path = '/'.join(path_parts[:i])
                    explicit_patterns.add(parent_path)

        return explicit_patterns

    def _is_explicitly_included(self, file_path: str, explicit_patterns: set[str]) -> bool:
        """Check if a file/directory is explicitly included in patterns"""
        relative_path = file_path.lstrip('/')
        return relative_path in explicit_patterns

    def _translate_patterns(self, patterns: List[str], backup_metadata: Dict[str, Any]) -> List[str]:
        """Translate patterns from backed up system to current system.

        Replaces the backed up Agent Zero root path with the current Agent Zero root path
        in all patterns if there's an exact match at the beginning of the pattern.

        Args:
            patterns: List of patterns from the backed up system
            backup_metadata: Backup metadata containing the original agent_zero_root

        Returns:
            List of translated patterns for the current system
        """
        # Get the backed up agent zero root path from metadata
        environment_info = backup_metadata.get("environment_info", {})
        backed_up_agent_root = environment_info.get("agent_zero_root", "")

        # Get current agent zero root path
        current_agent_root = self.agent_zero_root

        # If we don't have the backed up root path, return patterns as-is
        if not backed_up_agent_root:
            return patterns

        # Ensure paths have consistent trailing slash handling
        backed_up_agent_root = backed_up_agent_root.rstrip('/')
        current_agent_root = current_agent_root.rstrip('/')

        translated_patterns = []
        for pattern in patterns:
            # Check if the pattern starts with the backed up agent zero root
            if pattern.startswith(backed_up_agent_root + '/') or pattern == backed_up_agent_root:
                # Replace the backed up root with the current root
                relative_pattern = pattern[len(backed_up_agent_root):].lstrip('/')
                if relative_pattern:
                    translated_pattern = current_agent_root + '/' + relative_pattern
                else:
                    translated_pattern = current_agent_root
                translated_patterns.append(translated_pattern)
            else:
                # Pattern doesn't start with backed up agent root, keep as-is
                translated_patterns.append(pattern)

        return translated_patterns

    async def test_patterns(self, metadata: Dict[str, Any], max_files: int = 1000) -> List[Dict[str, Any]]:
        """Test backup patterns and return list of matched files"""
        include_patterns = metadata.get("include_patterns", [])
        exclude_patterns = metadata.get("exclude_patterns", [])
        include_hidden = metadata.get("include_hidden", False)

        # Convert to patterns string for pathspec
        patterns_string = self._patterns_to_string(include_patterns, exclude_patterns)

        # Parse patterns using pathspec
        pattern_lines = [line.strip() for line in patterns_string.split('\n') if line.strip() and not line.strip().startswith('#')]

        if not pattern_lines:
            return []

        # Get explicit patterns for hidden file handling
        explicit_patterns = self._get_explicit_patterns(include_patterns)

        matched_files = []
        processed_count = 0

        try:
            spec = PathSpec.from_lines(GitWildMatchPattern, pattern_lines)

            # Walk through base directories
            for base_pattern_path, base_real_path in self.base_paths.items():
                if not os.path.exists(base_real_path):
                    continue

                for root, dirs, files_list in os.walk(base_real_path):
                    # Filter hidden directories if not included, BUT allow explicit ones
                    if not include_hidden:
                        dirs_to_keep = []
                        for d in dirs:
                            if not d.startswith('.'):
                                dirs_to_keep.append(d)
                            else:
                                # Check if this hidden directory is explicitly included
                                dir_path = os.path.join(root, d)
                                pattern_path = self._unresolve_path(dir_path)
                                if self._is_explicitly_included(pattern_path, explicit_patterns):
                                    dirs_to_keep.append(d)
                        dirs[:] = dirs_to_keep

                    for file in files_list:
                        if processed_count >= max_files:
                            break

                        file_path = os.path.join(root, file)
                        pattern_path = self._unresolve_path(file_path)

                        # Skip hidden files if not included, BUT allow explicit ones
                        if not include_hidden and file.startswith('.'):
                            if not self._is_explicitly_included(pattern_path, explicit_patterns):
                                continue

                        # Remove leading slash for pathspec matching
                        relative_path = pattern_path.lstrip('/')

                        if spec.match_file(relative_path):
                            try:
                                stat = os.stat(file_path)
                                matched_files.append({
                                    "path": pattern_path,
                                    "real_path": file_path,
                                    "size": stat.st_size,
                                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                    "type": "file"
                                })
                                processed_count += 1
                            except (OSError, IOError):
                                # Skip files we can't access
                                continue

                    if processed_count >= max_files:
                        break

                if processed_count >= max_files:
                    break

        except Exception as e:
            raise Exception(f"Error processing patterns: {str(e)}")

        return matched_files

    async def create_backup(
        self,
        include_patterns: List[str],
        exclude_patterns: List[str],
        include_hidden: bool = False,
        backup_name: str = "agent-zero-backup"
    ) -> str:
        """Create backup archive and return path to created file"""

        # Create metadata for test_patterns
        metadata = {
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "include_hidden": include_hidden
        }

        # Get matched files
        matched_files = await self.test_patterns(metadata, max_files=50000)

        if not matched_files:
            raise Exception("No files matched the backup patterns")

        # Create temporary zip file
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f"{backup_name}.zip")

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add comprehensive metadata
                metadata = {
                    # Basic backup information
                    "agent_zero_version": self.agent_zero_version,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "backup_name": backup_name,
                    "include_hidden": include_hidden,

                    # Pattern arrays for granular control during restore
                    "include_patterns": include_patterns,
                    "exclude_patterns": exclude_patterns,

                    # System and environment information
                    "system_info": await self._get_system_info(),
                    "environment_info": await self._get_environment_info(),
                    "backup_author": await self._get_backup_author(),

                    # Backup configuration
                    "backup_config": {
                        "include_patterns": include_patterns,
                        "exclude_patterns": exclude_patterns,
                        "include_hidden": include_hidden,
                        "compression_level": 6,
                        "integrity_check": True
                    },

                    # File information
                    "files": [
                        {
                            "path": f["path"],
                            "size": f["size"],
                            "modified": f["modified"],
                            "type": "file"
                        }
                        for f in matched_files
                    ],

                    # Statistics
                    "total_files": len(matched_files),
                    "backup_size": sum(f["size"] for f in matched_files),
                    "directory_count": self._count_directories(matched_files),
                }

                zipf.writestr("metadata.json", json.dumps(metadata, indent=2))

                # Add files
                for file_info in matched_files:
                    real_path = file_info["real_path"]
                    archive_path = file_info["path"].lstrip('/')

                    try:
                        if os.path.exists(real_path) and os.path.isfile(real_path):
                            zipf.write(real_path, archive_path)
                    except (OSError, IOError) as e:
                        # Log error but continue with other files
                        PrintStyle().warning(f"Warning: Could not backup file {real_path}: {e}")
                        continue

            return zip_path

        except Exception as e:
            # Cleanup on error
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise Exception(f"Error creating backup: {str(e)}")

    async def inspect_backup(self, backup_file) -> Dict[str, Any]:
        """Inspect backup archive and return metadata"""

        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "backup.zip")

        try:
            backup_file.save(temp_file)

            with zipfile.ZipFile(temp_file, 'r') as zipf:
                # Read metadata
                if "metadata.json" not in zipf.namelist():
                    raise Exception("Invalid backup file: missing metadata.json")

                metadata_content = zipf.read("metadata.json").decode('utf-8')
                metadata = json.loads(metadata_content)

                # Add file list from archive
                files_in_archive = [name for name in zipf.namelist() if name != "metadata.json"]
                metadata["files_in_archive"] = files_in_archive

                return metadata

        except zipfile.BadZipFile:
            raise Exception("Invalid backup file: not a valid zip archive")
        except json.JSONDecodeError:
            raise Exception("Invalid backup file: corrupted metadata")
        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    async def preview_restore(
        self,
        backup_file,
        restore_include_patterns: Optional[List[str]] = None,
        restore_exclude_patterns: Optional[List[str]] = None,
        overwrite_policy: str = "overwrite",
        clean_before_restore: bool = False,
        user_edited_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Preview which files would be restored based on patterns"""

        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "backup.zip")

        files_to_restore = []
        skipped_files = []

        try:
            backup_file.save(temp_file)

            with zipfile.ZipFile(temp_file, 'r') as zipf:
                # Read backup metadata from archive
                original_backup_metadata = {}
                if "metadata.json" in zipf.namelist():
                    metadata_content = zipf.read("metadata.json").decode('utf-8')
                    original_backup_metadata = json.loads(metadata_content)

                # Use user-edited metadata if provided, otherwise fall back to original
                backup_metadata = user_edited_metadata if user_edited_metadata else original_backup_metadata

                # Get files from archive (excluding metadata files)
                archive_files = [name for name in zipf.namelist()
                                 if name not in ["metadata.json", "checksums.json"]]

                # Create pathspec for restore patterns if provided
                restore_spec = None
                if restore_include_patterns or restore_exclude_patterns:
                    pattern_lines = []
                    if restore_include_patterns:
                        # Translate patterns from backed up system to current system
                        translated_include_patterns = self._translate_patterns(restore_include_patterns, original_backup_metadata)
                        for pattern in translated_include_patterns:
                            # Remove leading slash for pathspec matching
                            pattern_lines.append(pattern.lstrip('/'))
                    if restore_exclude_patterns:
                        # Translate patterns from backed up system to current system
                        translated_exclude_patterns = self._translate_patterns(restore_exclude_patterns, original_backup_metadata)
                        for pattern in translated_exclude_patterns:
                            # Remove leading slash for pathspec matching
                            pattern_lines.append(f"!{pattern.lstrip('/')}")

                    if pattern_lines:
                        from pathspec import PathSpec
                        from pathspec.patterns.gitwildmatch import GitWildMatchPattern
                        restore_spec = PathSpec.from_lines(GitWildMatchPattern, pattern_lines)

                # Process each file in archive
                for archive_path in archive_files:
                    # Archive path is already the correct relative path (e.g., "a0/tmp/settings.json")
                    original_path = archive_path

                    # Translate path from backed up system to current system
                    # Use original metadata for path translation (environment_info needed for this)
                    target_path = self._translate_restore_path(archive_path, original_backup_metadata)

                    # For pattern matching, we need to use the translated path (current system)
                    # so that patterns like "/home/rafael/a0/data/**" can match files correctly
                    translated_path_for_matching = target_path.lstrip('/')

                    # Check if file matches restore patterns
                    if restore_spec and not restore_spec.match_file(translated_path_for_matching):
                        skipped_files.append({
                            "archive_path": archive_path,
                            "original_path": original_path,
                            "reason": "not_matched_by_pattern"
                        })
                        continue

                    # Check file conflict policy for existing files
                    if os.path.exists(target_path):
                        if overwrite_policy == "skip":
                            skipped_files.append({
                                "archive_path": archive_path,
                                "original_path": original_path,
                                "reason": "file_exists_skip_policy"
                            })
                            continue

                    # File will be restored
                    files_to_restore.append({
                        "archive_path": archive_path,
                        "original_path": original_path,
                        "target_path": target_path,
                        "action": "restore"
                    })

                # Handle clean before restore if requested
                files_to_delete = []
                if clean_before_restore:
                    # Use user-edited metadata for clean operations so patterns from ACE editor are used
                    files_to_delete = await self._find_files_to_clean_with_user_metadata(backup_metadata, original_backup_metadata)

                # Combine delete and restore operations for preview
                all_operations = files_to_delete + files_to_restore

                return {
                    "files": all_operations,
                    "files_to_delete": files_to_delete,
                    "files_to_restore": files_to_restore,
                    "skipped_files": skipped_files,
                    "total_count": len(all_operations),
                    "delete_count": len(files_to_delete),
                    "restore_count": len(files_to_restore),
                    "skipped_count": len(skipped_files),
                    "backup_metadata": backup_metadata,  # Return user-edited metadata
                    "overwrite_policy": overwrite_policy,
                    "clean_before_restore": clean_before_restore
                }

        except zipfile.BadZipFile:
            raise Exception("Invalid backup file: not a valid zip archive")
        except json.JSONDecodeError:
            raise Exception("Invalid backup file: corrupted metadata")
        except Exception as e:
            raise Exception(f"Error previewing restore: {str(e)}")
        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    async def restore_backup(
        self,
        backup_file,
        restore_include_patterns: Optional[List[str]] = None,
        restore_exclude_patterns: Optional[List[str]] = None,
        overwrite_policy: str = "overwrite",
        clean_before_restore: bool = False,
        user_edited_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Restore files from backup archive"""

        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "backup.zip")

        restored_files = []
        skipped_files = []
        errors = []
        deleted_files = []

        try:
            backup_file.save(temp_file)

            with zipfile.ZipFile(temp_file, 'r') as zipf:
                # Read backup metadata from archive
                original_backup_metadata = {}
                if "metadata.json" in zipf.namelist():
                    metadata_content = zipf.read("metadata.json").decode('utf-8')
                    original_backup_metadata = json.loads(metadata_content)

                # Use user-edited metadata if provided, otherwise fall back to original
                backup_metadata = user_edited_metadata if user_edited_metadata else original_backup_metadata

                # Perform clean before restore if requested
                if clean_before_restore:
                    # Use user-edited metadata for clean operations so patterns from ACE editor are used
                    files_to_delete = await self._find_files_to_clean_with_user_metadata(backup_metadata, original_backup_metadata)
                    for delete_info in files_to_delete:
                        try:
                            real_path = delete_info["real_path"]
                            if os.path.exists(real_path) and os.path.isfile(real_path):
                                os.remove(real_path)
                                deleted_files.append({
                                    "path": delete_info["path"],
                                    "real_path": real_path,
                                    "action": "deleted",
                                    "reason": "clean_before_restore"
                                })
                        except Exception as e:
                            errors.append({
                                "path": delete_info["path"],
                                "real_path": delete_info.get("real_path", "unknown"),
                                "error": f"Failed to delete: {str(e)}"
                            })

                # Get files from archive (excluding metadata files)
                archive_files = [name for name in zipf.namelist()
                                 if name not in ["metadata.json", "checksums.json"]]

                # Create pathspec for restore patterns if provided
                restore_spec = None
                if restore_include_patterns or restore_exclude_patterns:
                    pattern_lines = []
                    if restore_include_patterns:
                        # Translate patterns from backed up system to current system
                        translated_include_patterns = self._translate_patterns(restore_include_patterns, original_backup_metadata)
                        for pattern in translated_include_patterns:
                            # Remove leading slash for pathspec matching
                            pattern_lines.append(pattern.lstrip('/'))
                    if restore_exclude_patterns:
                        # Translate patterns from backed up system to current system
                        translated_exclude_patterns = self._translate_patterns(restore_exclude_patterns, original_backup_metadata)
                        for pattern in translated_exclude_patterns:
                            # Remove leading slash for pathspec matching
                            pattern_lines.append(f"!{pattern.lstrip('/')}")

                    if pattern_lines:
                        from pathspec import PathSpec
                        from pathspec.patterns.gitwildmatch import GitWildMatchPattern
                        restore_spec = PathSpec.from_lines(GitWildMatchPattern, pattern_lines)

                # Process each file in archive
                for archive_path in archive_files:
                    # Archive path is already the correct relative path (e.g., "a0/tmp/settings.json")
                    original_path = archive_path

                    # Translate path from backed up system to current system
                    # Use original metadata for path translation (environment_info needed for this)
                    target_path = self._translate_restore_path(archive_path, original_backup_metadata)

                    # For pattern matching, we need to use the translated path (current system)
                    # so that patterns like "/home/rafael/a0/data/**" can match files correctly
                    translated_path_for_matching = target_path.lstrip('/')

                    # Check if file matches restore patterns
                    if restore_spec and not restore_spec.match_file(translated_path_for_matching):
                        skipped_files.append({
                            "archive_path": archive_path,
                            "original_path": original_path,
                            "reason": "not_matched_by_pattern"
                        })
                        continue

                    try:
                        # Handle overwrite policy
                        if os.path.exists(target_path):
                            if overwrite_policy == "skip":
                                skipped_files.append({
                                    "archive_path": archive_path,
                                    "original_path": original_path,
                                    "reason": "file_exists_skip_policy"
                                })
                                continue
                            elif overwrite_policy == "backup":
                                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                                backup_path = f"{target_path}.backup.{timestamp}"
                                import shutil
                                shutil.move(target_path, backup_path)

                        # Create target directory if needed
                        target_dir = os.path.dirname(target_path)
                        if target_dir:
                            os.makedirs(target_dir, exist_ok=True)

                        # Extract file
                        import shutil
                        with zipf.open(archive_path) as source, open(target_path, 'wb') as target:
                            shutil.copyfileobj(source, target)

                        restored_files.append({
                            "archive_path": archive_path,
                            "original_path": original_path,
                            "target_path": target_path,
                            "status": "restored"
                        })

                    except Exception as e:
                        errors.append({
                            "path": archive_path,
                            "original_path": original_path,
                            "error": str(e)
                        })

                return {
                    "restored_files": restored_files,
                    "deleted_files": deleted_files,
                    "skipped_files": skipped_files,
                    "errors": errors,
                    "backup_metadata": backup_metadata,  # Return user-edited metadata
                    "clean_before_restore": clean_before_restore
                }

        except zipfile.BadZipFile:
            raise Exception("Invalid backup file: not a valid zip archive")
        except json.JSONDecodeError:
            raise Exception("Invalid backup file: corrupted metadata")
        except Exception as e:
            raise Exception(f"Error restoring backup: {str(e)}")
        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def _translate_restore_path(self, archive_path: str, backup_metadata: Dict[str, Any]) -> str:
        """Translate file path from backed up system to current system.

        Replaces the backed up Agent Zero root path with the current Agent Zero root path
        if there's an exact match at the beginning of the path.

        Args:
            archive_path: Original file path from the archive
            backup_metadata: Backup metadata containing the original agent_zero_root

        Returns:
            Translated path for the current system
        """
        # Get the backed up agent zero root path from metadata
        environment_info = backup_metadata.get("environment_info", {})
        backed_up_agent_root = environment_info.get("agent_zero_root", "")

        # Get current agent zero root path
        current_agent_root = self.agent_zero_root

        # If we don't have the backed up root path, use original path with leading slash
        if not backed_up_agent_root:
            return "/" + archive_path.lstrip('/')

        # Ensure paths have consistent trailing slash handling
        backed_up_agent_root = backed_up_agent_root.rstrip('/')
        current_agent_root = current_agent_root.rstrip('/')

        # Convert archive path to absolute path (add leading slash if missing)
        if not archive_path.startswith('/'):
            absolute_archive_path = "/" + archive_path
        else:
            absolute_archive_path = archive_path

        # Check if the archive path starts with the backed up agent zero root
        if absolute_archive_path.startswith(backed_up_agent_root + '/') or absolute_archive_path == backed_up_agent_root:
            # Replace the backed up root with the current root
            relative_path = absolute_archive_path[len(backed_up_agent_root):].lstrip('/')
            if relative_path:
                translated_path = current_agent_root + '/' + relative_path
            else:
                translated_path = current_agent_root
            return translated_path
        else:
            # Path doesn't start with backed up agent root, return as-is
            return absolute_archive_path

    async def _find_files_to_clean_with_user_metadata(self, user_metadata: Dict[str, Any], original_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find existing files that match patterns from user-edited metadata for clean operations"""
        # Use user-edited patterns for what to clean
        user_include_patterns = user_metadata.get("include_patterns", [])
        user_exclude_patterns = user_metadata.get("exclude_patterns", [])
        include_hidden = user_metadata.get("include_hidden", False)

        if not user_include_patterns:
            return []

        # Translate user-edited patterns from backed up system to current system
        # Use original metadata for path translation (environment_info)
        translated_include_patterns = self._translate_patterns(user_include_patterns, original_metadata)
        translated_exclude_patterns = self._translate_patterns(user_exclude_patterns, original_metadata)

        # Create metadata object for testing translated patterns
        metadata = {
            "include_patterns": translated_include_patterns,
            "exclude_patterns": translated_exclude_patterns,
            "include_hidden": include_hidden
        }

        # Find existing files that match the translated user-edited patterns
        try:
            existing_files = await self.test_patterns(metadata, max_files=10000)

            # Convert to delete operations format
            files_to_delete = []
            for file_info in existing_files:
                if os.path.exists(file_info["real_path"]):
                    files_to_delete.append({
                        "path": file_info["path"],
                        "real_path": file_info["real_path"],
                        "action": "delete",
                        "reason": "clean_before_restore"
                    })

            return files_to_delete
        except Exception:
            # If pattern testing fails, return empty list to avoid breaking restore
            return []
