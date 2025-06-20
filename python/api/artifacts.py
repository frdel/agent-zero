import os
import json
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from python.helpers.api import ApiHandler
from flask import Request, Response
from agent import AgentContext
from python.helpers import files
from python.helpers.print_style import PrintStyle


class ArtifactHandler(ApiHandler):
    """Handler for artifact-related operations and WebSocket streaming"""
    
    def __init__(self, app=None, thread_lock=None):
        super().__init__(app, thread_lock)
        self.observers = {}
        self.artifact_watchers = {}
        
    async def process(self, input: dict, request: Request):
        action = input.get("action", "list")
        chat_id = input.get("chat_id", "default")
        if action == "list":
            return self.list_artifacts(chat_id)
        elif action == "get":
            artifact_id = input.get("artifact_id")
            if not artifact_id:
                return {"error": "artifact_id is required"}
            return self.get_artifact(chat_id, artifact_id)
        elif action == "create":
            return self.create_artifact(input)
        elif action == "delete":
            artifact_id = input.get("artifact_id")
            if not artifact_id:
                return {"error": "artifact_id is required"}
            return self.delete_artifact(chat_id, artifact_id)
        else:
            return {"error": "Invalid action"}
    
    def list_artifacts(self, chat_id: str) -> dict:
        """List all artifacts for a given chat"""
        artifacts_dir = self.get_artifacts_dir(chat_id)
        artifacts = []
        
        if artifacts_dir.exists():
            metadata_file = artifacts_dir / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    artifacts = list(metadata.values())
                except Exception as e:
                    PrintStyle(font_color="red").print(f"Error reading artifacts metadata: {str(e)}")
        
        return {"artifacts": artifacts}
    
    def get_artifact(self, chat_id: str, artifact_id: str) -> dict:
        """Get a specific artifact"""
        artifacts_dir = self.get_artifacts_dir(chat_id)
        metadata_file = artifacts_dir / "metadata.json"
        
        if not metadata_file.exists():
            return {"error": "Artifact not found"}
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            if artifact_id not in metadata:
                return {"error": "Artifact not found"}
            
            artifact_info = metadata[artifact_id]
            artifact_file = artifacts_dir / artifact_info["filename"]
            
            if artifact_file.exists():
                with open(artifact_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                artifact_info["content"] = content
                return {"artifact": artifact_info}
            else:
                return {"error": "Artifact file not found"}
                
        except Exception as e:
            PrintStyle(font_color="red").print(f"Error reading artifact: {str(e)}")
            return {"error": str(e)}
    
    def create_artifact(self, input: dict) -> dict:
        """Create a new artifact"""
        chat_id = input.get("chat_id", "default")
        artifact_id = input.get("artifact_id")
        artifact_type = input.get("type", "text")
        content = input.get("content", "")
        metadata = input.get("metadata", {})
        
        if not artifact_id:
            return {"error": "artifact_id is required"}
        
        artifacts_dir = self.get_artifacts_dir(chat_id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine file extension based on type
        extensions = {
            "html": ".html",
            "css": ".css",
            "javascript": ".js",
            "python": ".py",
            "json": ".json",
            "markdown": ".md",
            "svg": ".svg",
            "text": ".txt"
        }
        
        extension = extensions.get(artifact_type, ".txt")
        filename = f"{artifact_id}{extension}"
        artifact_file = artifacts_dir / filename
        
        try:
            # Write content to file
            with open(artifact_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Update metadata
            metadata_file = artifacts_dir / "metadata.json"
            artifacts_metadata = {}
            
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    artifacts_metadata = json.load(f)
            
            artifacts_metadata[artifact_id] = {
                "id": artifact_id,
                "type": artifact_type,
                "filename": filename,
                "created_at": metadata.get("created_at", str(int(time.time()))),
                "size": len(content),
                "chat_id": chat_id,
                **metadata
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(artifacts_metadata, f, indent=2)
            
            PrintStyle(font_color="green").print(f"Artifact created: {artifact_id}")
            return {"success": True, "artifact_id": artifact_id}
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"Error creating artifact: {str(e)}")
            return {"error": str(e)}
    
    def delete_artifact(self, chat_id: str, artifact_id: str) -> dict:
        """Delete an artifact"""
        artifacts_dir = self.get_artifacts_dir(chat_id)
        metadata_file = artifacts_dir / "metadata.json"
        
        if not metadata_file.exists():
            return {"error": "Artifact not found"}
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            if artifact_id not in metadata:
                return {"error": "Artifact not found"}
            
            artifact_info = metadata[artifact_id]
            artifact_file = artifacts_dir / artifact_info["filename"]
            
            # Remove file
            if artifact_file.exists():
                artifact_file.unlink()
            
            # Remove from metadata
            del metadata[artifact_id]
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {"success": True}
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"Error deleting artifact: {str(e)}")
            return {"error": str(e)}
    
    def get_artifacts_dir(self, chat_id: str) -> Path:
        """Get the artifacts directory for a specific chat"""
        base_dir = files.get_abs_path("artifacts")
        return Path(base_dir) / chat_id
    
    def start_watching(self, chat_id: str, websocket_handler=None):
        """Start watching artifacts directory for changes"""
        artifacts_dir = self.get_artifacts_dir(chat_id)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        if chat_id in self.observers:
            return  # Already watching
        
        event_handler = ArtifactFileHandler(chat_id, websocket_handler)
        observer = Observer()
        observer.schedule(event_handler, str(artifacts_dir), recursive=False)
        observer.start()
        
        self.observers[chat_id] = observer
        self.artifact_watchers[chat_id] = event_handler
        
        PrintStyle(font_color="cyan").print(f"Started watching artifacts for chat: {chat_id}")
    
    def stop_watching(self, chat_id: str):
        """Stop watching artifacts directory"""
        if chat_id in self.observers:
            self.observers[chat_id].stop()
            self.observers[chat_id].join()
            del self.observers[chat_id]
            del self.artifact_watchers[chat_id]
            PrintStyle(font_color="cyan").print(f"Stopped watching artifacts for chat: {chat_id}")


class ArtifactFileHandler(FileSystemEventHandler):
    """File system event handler for artifact changes"""
    
    def __init__(self, chat_id: str, websocket_handler=None):
        super().__init__()
        self.chat_id = chat_id
        self.websocket_handler = websocket_handler
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else str(event.src_path)
        if src_path.endswith('.json'):
            return  # Skip metadata file changes
        
        self.handle_file_change(src_path, "modified")
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        src_path = event.src_path.decode() if isinstance(event.src_path, bytes) else str(event.src_path)
        if src_path.endswith('.json'):
            return  # Skip metadata file changes
        
        self.handle_file_change(src_path, "created")
    
    def handle_file_change(self, file_path: str, change_type: str):
        """Handle file change events"""
        try:
            filename = os.path.basename(file_path)
            artifact_id = os.path.splitext(filename)[0]
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get artifact metadata
            artifacts_dir = Path(file_path).parent
            metadata_file = artifacts_dir / "metadata.json"
            
            artifact_info = None
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    artifact_info = metadata.get(artifact_id, {})
            
            # Prepare update data
            update_data = {
                "type": "artifact_update",
                "payload": {
                    "id": artifact_id,
                    "type": artifact_info.get("type", "text") if artifact_info else "text",
                    "content": content,
                    "metadata": artifact_info or {},
                    "change_type": change_type,
                    "chat_id": self.chat_id
                }
            }
            
            # Send to WebSocket if handler exists
            if self.websocket_handler:
                self.websocket_handler(update_data)
            
            PrintStyle(font_color="yellow").print(f"Artifact {change_type}: {artifact_id}")
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"Error handling file change: {str(e)}")


# Global artifact handler instance
artifact_handler = ArtifactHandler()
