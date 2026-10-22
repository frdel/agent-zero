from helpers.api import ApiHandler, Request, Response
from werkzeug.datastructures import FileStorage
from helpers.backup import BackupService
from helpers.persist_chat import load_tmp_chats
import json


class BackupRestore(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_loopback(cls) -> bool:
        return False


    @staticmethod
    def _reload_runtime_state() -> None:
        """Reload env vars, provider configs, and plugin caches after restore."""
        try:
            from helpers import dotenv

            dotenv.load_dotenv()  # re-read restored .env into os.environ
        except Exception:
            pass
        try:
            from helpers.providers import reload_providers

            reload_providers()  # rebuild ProviderManager from base + plugin confs
        except Exception:
            pass
        try:
            from helpers import cache

            cache.clear("*(plugins)*")
            cache.clear("*(api)*")
        except Exception:
            pass
        try:
            from helpers import settings as _settings_mod

            # get_settings() caches usr/settings.json in a module global; drop
            # it so a restored settings file is re-read on the next access.
            _settings_mod._settings = None
        except Exception:
            pass

    async def process(self, input: dict, request: Request) -> dict | Response:
        # Handle file upload
        if 'backup_file' not in request.files:
            return {"success": False, "error": "No backup file provided"}

        backup_file: FileStorage = request.files['backup_file']
        if backup_file.filename == '':
            return {"success": False, "error": "No file selected"}

        # Get restore configuration from form data
        metadata_json = request.form.get('metadata', '{}')
        overwrite_policy = request.form.get('overwrite_policy', 'overwrite')  # overwrite, skip, backup
        clean_before_restore = request.form.get('clean_before_restore', 'false').lower() == 'true'

        try:
            metadata = json.loads(metadata_json)
            restore_include_patterns = metadata.get("include_patterns", [])
            restore_exclude_patterns = metadata.get("exclude_patterns", [])
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid metadata JSON"}

        try:
            backup_service = BackupService()
            result = await backup_service.restore_backup(
                backup_file=backup_file,
                restore_include_patterns=restore_include_patterns,
                restore_exclude_patterns=restore_exclude_patterns,
                overwrite_policy=overwrite_policy,
                clean_before_restore=clean_before_restore,
                user_edited_metadata=metadata
            )

            # Load all chats from the chats folder
            load_tmp_chats()

            # Reload runtime state that the restored files affect. Restored
            # .env values (e.g. provider API keys) and restored plugin conf
            # files (custom model providers) must become visible to the running
            # instance without requiring a manual restart; otherwise restored
            # model presets reference providers/keys that the runtime cannot
            # resolve.
            self._reload_runtime_state()

            return {
                "success": True,
                "restored_files": result["restored_files"],
                "deleted_files": result.get("deleted_files", []),
                "skipped_files": result["skipped_files"],
                "errors": result["errors"],
                "backup_metadata": result["backup_metadata"],
                "clean_before_restore": result.get("clean_before_restore", False)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
