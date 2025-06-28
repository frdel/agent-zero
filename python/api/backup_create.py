from python.helpers.api import ApiHandler
from flask import Request, Response, send_file
from python.helpers.backup import BackupService
from python.helpers.persist_chat import save_tmp_chats


class BackupCreate(ApiHandler):
    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_loopback(cls) -> bool:
        return False

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Get input parameters
            include_patterns = input.get("include_patterns", [])
            exclude_patterns = input.get("exclude_patterns", [])
            include_hidden = input.get("include_hidden", False)
            backup_name = input.get("backup_name", "agent-zero-backup")

            # Support legacy string patterns format for backward compatibility
            patterns_string = input.get("patterns", "")
            if patterns_string and not include_patterns and not exclude_patterns:
                # Parse legacy format
                lines = [line.strip() for line in patterns_string.split('\n') if line.strip() and not line.strip().startswith('#')]
                for line in lines:
                    if line.startswith('!'):
                        exclude_patterns.append(line[1:])
                    else:
                        include_patterns.append(line)

            # Save all chats to the chats folder
            save_tmp_chats()

            # Create backup service and generate backup
            backup_service = BackupService()
            zip_path = await backup_service.create_backup(
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                include_hidden=include_hidden,
                backup_name=backup_name
            )

            # Return file for download
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=f"{backup_name}.zip",
                mimetype='application/zip'
            )

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
