from python.helpers.api import ApiHandler
from flask import Request, Response
from python.helpers.backup import BackupService
from typing import Dict, Any


class BackupPreviewGrouped(ApiHandler):
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
            max_depth = input.get("max_depth", 3)
            search_filter = input.get("search_filter", "")

            # Support legacy string patterns format for backward compatibility
            patterns_string = input.get("patterns", "")
            if patterns_string and not include_patterns:
                lines = [line.strip() for line in patterns_string.split('\n')
                         if line.strip() and not line.strip().startswith('#')]
                for line in lines:
                    if line.startswith('!'):
                        exclude_patterns.append(line[1:])
                    else:
                        include_patterns.append(line)

            if not include_patterns:
                return {
                    "success": True,
                    "groups": [],
                    "stats": {"total_groups": 0, "total_files": 0, "total_size": 0},
                    "total_files": 0,
                    "total_size": 0
                }

            # Create metadata object for testing
            metadata = {
                "include_patterns": include_patterns,
                "exclude_patterns": exclude_patterns,
                "include_hidden": include_hidden
            }

            backup_service = BackupService()
            all_files = await backup_service.test_patterns(metadata, max_files=10000)

            # Apply search filter if provided
            if search_filter.strip():
                search_lower = search_filter.lower()
                all_files = [f for f in all_files if search_lower in f["path"].lower()]

            # Group files by directory structure
            groups: Dict[str, Dict[str, Any]] = {}
            total_size = 0

            for file_info in all_files:
                path = file_info["path"]
                total_size += file_info["size"]

                # Split path and limit depth
                path_parts = path.strip('/').split('/')

                # Limit to max_depth for grouping
                if len(path_parts) > max_depth:
                    group_path = '/' + '/'.join(path_parts[:max_depth])
                    is_truncated = True
                else:
                    group_path = '/' + '/'.join(path_parts[:-1]) if len(path_parts) > 1 else '/'
                    is_truncated = False

                if group_path not in groups:
                    groups[group_path] = {
                        "path": group_path,
                        "files": [],
                        "file_count": 0,
                        "total_size": 0,
                        "is_truncated": False,
                        "subdirectories": set()
                    }

                groups[group_path]["files"].append(file_info)
                groups[group_path]["file_count"] += 1
                groups[group_path]["total_size"] += file_info["size"]
                groups[group_path]["is_truncated"] = groups[group_path]["is_truncated"] or is_truncated

                # Track subdirectories for truncated groups
                if is_truncated and len(path_parts) > max_depth:
                    next_dir = path_parts[max_depth]
                    groups[group_path]["subdirectories"].add(next_dir)

            # Convert groups to sorted list and add display info
            sorted_groups = []
            for group_path, group_info in sorted(groups.items()):
                group_info["subdirectories"] = sorted(list(group_info["subdirectories"]))

                # Limit displayed files for UI performance
                if len(group_info["files"]) > 50:
                    group_info["displayed_files"] = group_info["files"][:50]
                    group_info["additional_files"] = len(group_info["files"]) - 50
                else:
                    group_info["displayed_files"] = group_info["files"]
                    group_info["additional_files"] = 0

                sorted_groups.append(group_info)

            return {
                "success": True,
                "groups": sorted_groups,
                "stats": {
                    "total_groups": len(sorted_groups),
                    "total_files": len(all_files),
                    "total_size": total_size,
                    "search_applied": bool(search_filter.strip()),
                    "max_depth": max_depth
                },
                "total_files": len(all_files),
                "total_size": total_size
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
