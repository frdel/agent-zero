from python.helpers.api import ApiHandler, Request, Response
from werkzeug.datastructures import FileStorage
from python.helpers.backup import BackupService
from python.helpers.persist_chat import load_tmp_chats
import json


class BackupRestore(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_loopback(cls) -> bool:
        return False

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
