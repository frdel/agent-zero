from python.helpers.api import ApiHandler, Request, Response
from python.helpers.backup import BackupService
from werkzeug.datastructures import FileStorage


class BackupInspect(ApiHandler):
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

        try:
            backup_service = BackupService()
            metadata = await backup_service.inspect_backup(backup_file)

            return {
                "success": True,
                "metadata": metadata,
                "files": metadata.get("files", []),
                "include_patterns": metadata.get("include_patterns", []),
                "exclude_patterns": metadata.get("exclude_patterns", []),
                "default_patterns": metadata.get("backup_config", {}).get("default_patterns", ""),
                "agent_zero_version": metadata.get("agent_zero_version", "unknown"),
                "timestamp": metadata.get("timestamp", ""),
                "backup_name": metadata.get("backup_name", ""),
                "total_files": metadata.get("total_files", len(metadata.get("files", []))),
                "backup_size": metadata.get("backup_size", 0),
                "include_hidden": metadata.get("include_hidden", False),
                "files_in_archive": metadata.get("files_in_archive", []),
                "checksums": {}  # Will be added if needed
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
