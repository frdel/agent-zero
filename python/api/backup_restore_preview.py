from python.helpers.api import ApiHandler, Request, Response
from werkzeug.datastructures import FileStorage
from python.helpers.backup import BackupService
import json


class BackupRestorePreview(ApiHandler):
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

        # Get restore patterns and options from form data
        metadata_json = request.form.get('metadata', '{}')
        overwrite_policy = request.form.get('overwrite_policy', 'overwrite')
        clean_before_restore = request.form.get('clean_before_restore', 'false').lower() == 'true'

        try:
            metadata = json.loads(metadata_json)
            restore_include_patterns = metadata.get("include_patterns", [])
            restore_exclude_patterns = metadata.get("exclude_patterns", [])
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid metadata JSON"}

        try:
            backup_service = BackupService()
            result = await backup_service.preview_restore(
                backup_file=backup_file,
                restore_include_patterns=restore_include_patterns,
                restore_exclude_patterns=restore_exclude_patterns,
                overwrite_policy=overwrite_policy,
                clean_before_restore=clean_before_restore,
                user_edited_metadata=metadata
            )

            return {
                "success": True,
                "files": result["files"],
                "files_to_delete": result.get("files_to_delete", []),
                "files_to_restore": result.get("files_to_restore", []),
                "skipped_files": result["skipped_files"],
                "total_count": result["total_count"],
                "delete_count": result.get("delete_count", 0),
                "restore_count": result.get("restore_count", 0),
                "skipped_count": result["skipped_count"],
                "backup_metadata": result["backup_metadata"],
                "overwrite_policy": result.get("overwrite_policy", "overwrite"),
                "clean_before_restore": result.get("clean_before_restore", False)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
