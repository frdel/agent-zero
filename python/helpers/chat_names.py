import json
import os
import time
from typing import Dict, Any

from python.helpers import files


class ChatNames:
    _instance = None
    _names_file = "chat_names.json"
    _metadata_file = "chat_metadata.json"

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ChatNames()
            cls._instance._names_file = files.get_abs_path("tmp") + "/" + cls._names_file
            cls._instance._metadata_file = files.get_abs_path("tmp") + "/" + cls._metadata_file
        return cls._instance

    def _read_names(self) -> dict:
        """Read current names from file"""
        try:
            if os.path.exists(self._names_file):
                with open(self._names_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error reading chat names: {e}")
        return {}

    def _save_names(self, names: dict):
        """Save names to file"""
        try:
            with open(self._names_file, 'w') as f:
                json.dump(names, f, indent=2)
        except Exception as e:
            print(f"Error saving chat names: {e}")

    def _read_metadata(self) -> dict:
        """Read context metadata from file"""
        try:
            if os.path.exists(self._metadata_file):
                with open(self._metadata_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error reading context metadata: {e}")
        return {}

    def _save_metadata(self, metadata: dict):
        """Save metadata to file"""
        try:
            with open(self._metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving context metadata: {e}")

    def set_name(self, chat_id: str, name: str):
        """Set name for a chat/task"""
        names = self._read_names()
        names[chat_id] = name
        self._save_names(names)

        # Also update the name in metadata if it exists
        self.update_metadata(chat_id, {"name": name})

    def get_name(self, chat_id: str) -> str:
        """Get name for a chat/task"""
        names = self._read_names()
        return names.get(chat_id, f"Chat #{chat_id[:8]}")

    def set_metadata(self, chat_id: str, metadata_dict: Dict[str, Any]):
        """Set complete metadata for a chat/task"""
        all_metadata = self._read_metadata()

        # Ensure we have created_at timestamp if not provided
        if "created_at" not in metadata_dict:
            metadata_dict["created_at"] = int(time.time())

        all_metadata[chat_id] = metadata_dict
        self._save_metadata(all_metadata)

        # Also update the name in the names file for backward compatibility
        if "name" in metadata_dict:
            self.set_name(chat_id, metadata_dict["name"])

    def update_metadata(self, chat_id: str, metadata_update: Dict[str, Any]):
        """Update specific metadata fields for a chat/task"""
        all_metadata = self._read_metadata()

        if chat_id in all_metadata:
            all_metadata[chat_id].update(metadata_update)
        else:
            # Initialize with current timestamp if creating new metadata
            metadata_update["created_at"] = metadata_update.get("created_at", int(time.time()))
            all_metadata[chat_id] = metadata_update

        self._save_metadata(all_metadata)

    def get_metadata(self, chat_id: str) -> Dict[str, Any]:
        """Get metadata for a chat/task"""
        all_metadata = self._read_metadata()

        # Return metadata if it exists
        if chat_id in all_metadata:
            return all_metadata[chat_id]

        # Otherwise create default metadata with just the name
        name = self.get_name(chat_id)
        default_metadata = {
            "name": name,
            "created_at": int(time.time())  # Current time as fallback
        }
        return default_metadata

    def get_created_at(self, chat_id: str) -> int:
        """Get creation timestamp for a chat/task"""
        metadata = self.get_metadata(chat_id)
        return metadata.get("created_at", 0)

    def remove_chat(self, chat_id: str):
        """Remove chat/task and its metadata"""
        print("Removing chat name and metadata: ", chat_id)

        # Remove from names file
        names = self._read_names()
        if chat_id in names:
            del names[chat_id]
            print("Chat name removed: ", chat_id)
            self._save_names(names)

        # Remove from metadata file
        metadata = self._read_metadata()
        if chat_id in metadata:
            del metadata[chat_id]
            print("Chat metadata removed: ", chat_id)
            self._save_metadata(metadata)
