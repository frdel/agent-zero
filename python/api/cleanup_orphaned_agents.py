from python.helpers.api import ApiHandler, Request, Response
import subprocess
import sys
import os


class CleanupOrphanedAgents(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        """Clean up orphaned subordinate agent processes"""
        
        try:
            # Get the project root directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cleanup_script = os.path.join(project_root, "cleanup_orphaned_agents.py")
            
            if not os.path.exists(cleanup_script):
                return Response(
                    response="Cleanup script not found",
                    status=404,
                    mimetype="text/plain"
                )
            
            # Run the cleanup script
            result = subprocess.run([
                sys.executable, cleanup_script, "--cleanup", "--force"
            ], cwd=project_root, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "message": "Orphaned agents cleanup completed successfully",
                    "output": result.stdout,
                    "cleaned_count": self._extract_cleaned_count(result.stdout)
                }
            else:
                return Response(
                    response=f"Cleanup failed: {result.stderr}",
                    status=500,
                    mimetype="text/plain"
                )
                
        except subprocess.TimeoutExpired:
            return Response(
                response="Cleanup operation timed out",
                status=408,
                mimetype="text/plain"
            )
        except Exception as e:
            return Response(
                response=f"Error during cleanup: {str(e)}",
                status=500,
                mimetype="text/plain"
            )
    
    def _extract_cleaned_count(self, output: str) -> int:
        """Extract the number of cleaned processes from output"""
        try:
            for line in output.split('\n'):
                if 'Terminated' in line and 'orphaned processes' in line:
                    # Extract number from "Terminated X orphaned processes"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'Terminated' and i + 1 < len(parts):
                            return int(parts[i + 1])
            return 0
        except Exception:
            return 0
