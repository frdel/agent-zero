from python.helpers.tool import Tool, Response
from agent import LoopData
import asyncio
import os
import json
import sqlite3
import shutil
from typing import Dict, List, Any, Optional
from pathlib import Path
import hashlib
import time
from datetime import datetime

class DataLakeManager(Tool):
    """
    Data Lake Management tool for biomedical research data.
    Manages large-scale biomedical datasets, metadata indexing, and data lifecycle using real file operations.
    """
    
    def __init__(self, agent, name: str, method: str | None, args: dict[str,str], message: str, loop_data: LoopData | None, **kwargs):
        super().__init__(agent, name, method, args, message, loop_data, **kwargs)
        self.data_lake_path = Path(os.getenv("BIOMNI_DATA_LAKE_PATH", "/tmp/biomni_data_lake"))
        self.metadata_db_path = self.data_lake_path / "metadata.db"
        self._ensure_data_lake_structure()
    
    def _ensure_data_lake_structure(self):
        """Ensure data lake directory structure exists."""
        try:
            # Create main directories
            self.data_lake_path.mkdir(parents=True, exist_ok=True)
            (self.data_lake_path / "genomics").mkdir(exist_ok=True)
            (self.data_lake_path / "proteomics").mkdir(exist_ok=True)
            (self.data_lake_path / "clinical").mkdir(exist_ok=True)
            (self.data_lake_path / "imaging").mkdir(exist_ok=True)
            (self.data_lake_path / "literature").mkdir(exist_ok=True)
            (self.data_lake_path / "backups").mkdir(exist_ok=True)
            
            # Initialize metadata database
            self._init_metadata_db()
            
        except Exception as e:
            print(f"Error setting up data lake structure: {str(e)}")
    
    def _init_metadata_db(self):
        """Initialize SQLite metadata database."""
        try:
            conn = sqlite3.connect(str(self.metadata_db_path))
            cursor = conn.cursor()
            
            # Create metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    name TEXT,
                    data_type TEXT,
                    source TEXT,
                    file_path TEXT,
                    size_bytes INTEGER,
                    created_at TEXT,
                    indexed_at TEXT,
                    checksum TEXT,
                    metadata TEXT,
                    access_level TEXT DEFAULT 'restricted'
                )
            """)
            
            # Create activity log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    action TEXT,
                    dataset_id TEXT,
                    details TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error initializing metadata database: {str(e)}")
    
    async def execute(self, action: str = "status", dataset_id: str = "", 
                     metadata: dict = None, query_params: dict = None, file_path: str = "", **kwargs) -> Response:
        """
        Execute data lake management operations.
        
        Args:
            action: Operation type (status, index, query, create, delete, backup, upload)
            dataset_id: Unique identifier for dataset
            metadata: Dataset metadata for indexing
            query_params: Parameters for data queries
            file_path: Path to file for upload operations
        """
        
        try:
            if action == "status":
                return await self._get_status()
            elif action == "index":
                return await self._index_dataset(dataset_id, metadata or {})
            elif action == "query":
                return await self._query_datasets(query_params or {})
            elif action == "create":
                return await self._create_dataset(dataset_id, metadata or {})
            elif action == "upload":
                return await self._upload_dataset(dataset_id, file_path, metadata or {})
            elif action == "delete":
                return await self._delete_dataset(dataset_id)
            elif action == "backup":
                return await self._backup_dataset(dataset_id)
            else:
                return Response(message=f"Unknown action: {action}", break_loop=False)

        except Exception as e:
            return Response(message=f"Data lake operation failed: {str(e)}", break_loop=False)
    
    async def _get_status(self) -> Response:
        """Get real data lake status and statistics."""
        
        try:
            # Get actual storage statistics
            storage_usage = {}
            total_size_bytes = 0
            total_datasets = 0
            
            for data_type in ["genomics", "proteomics", "clinical", "imaging", "literature"]:
                type_path = self.data_lake_path / data_type
                if type_path.exists():
                    size_bytes = sum(f.stat().st_size for f in type_path.rglob('*') if f.is_file())
                    dataset_count = len(list(type_path.rglob('*'))) if type_path.exists() else 0
                    
                    storage_usage[data_type] = {
                        "size_gb": round(size_bytes / (1024**3), 2),
                        "size_bytes": size_bytes,
                        "datasets": dataset_count
                    }
                    total_size_bytes += size_bytes
                    total_datasets += dataset_count
            
            # Get dataset count from database
            conn = sqlite3.connect(str(self.metadata_db_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM datasets")
            db_dataset_count = cursor.fetchone()[0]
            
            # Get recent activity
            cursor.execute("""
                SELECT timestamp, action, dataset_id, details 
                FROM activity_log 
                ORDER BY timestamp DESC 
                LIMIT 10
            """)
            recent_activity = []
            for row in cursor.fetchall():
                recent_activity.append({
                    "timestamp": row[0],
                    "action": row[1],
                    "dataset": row[2],
                    "details": row[3]
                })
            
            conn.close()
            
            # Check health status
            health_status = "healthy"
            if not self.data_lake_path.exists():
                health_status = "error"
            elif total_size_bytes > 50 * (1024**3):  # > 50GB warning
                health_status = "warning"
            
            status = {
                "data_lake_path": str(self.data_lake_path),
                "total_datasets": db_dataset_count,
                "total_size_gb": round(total_size_bytes / (1024**3), 2),
                "total_size_bytes": total_size_bytes,
                "health_status": health_status,
                "storage_usage": storage_usage,
                "recent_activity": recent_activity,
                "metadata_db_exists": self.metadata_db_path.exists(),
                "directories_exist": {
                    data_type: (self.data_lake_path / data_type).exists()
                    for data_type in ["genomics", "proteomics", "clinical", "imaging", "literature"]
                }
            }
            
            # Format status as a readable message
            status_msg = f"Data lake status retrieved successfully:\n"
            status_msg += f"- Path: {status['data_lake_path']}\n"
            status_msg += f"- Total datasets: {status['total_datasets']}\n"
            status_msg += f"- Total size: {status['total_size_gb']} GB\n"
            status_msg += f"- Health status: {status['health_status']}\n"
            status_msg += f"- Metadata DB exists: {status['metadata_db_exists']}\n"

            return Response(
                message=status_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(
                message=f"Failed to get data lake status: {str(e)}",
                break_loop=False
            )
    
    async def _upload_dataset(self, dataset_id: str, file_path: str, metadata: Dict[str, Any]) -> Response:
        """Upload and index a dataset file."""
        
        if not dataset_id:
            return Response(message="Dataset ID is required", break_loop=False)

        if not file_path or not os.path.exists(file_path):
            return Response(message="Valid file path is required", break_loop=False)
        
        try:
            source_path = Path(file_path)
            data_type = metadata.get("type", "unknown")
            
            # Determine destination directory
            dest_dir = self.data_lake_path / data_type
            dest_dir.mkdir(exist_ok=True)
            
            dest_path = dest_dir / f"{dataset_id}_{source_path.name}"
            
            # Copy file to data lake
            shutil.copy2(source_path, dest_path)
            
            # Calculate file checksum
            checksum = self._calculate_file_checksum(dest_path)
            
            # Get file size
            file_size = dest_path.stat().st_size
            
            # Index the dataset
            await self._index_dataset_in_db(
                dataset_id=dataset_id,
                name=metadata.get("name", dataset_id),
                data_type=data_type,
                source=metadata.get("source", "upload"),
                file_path=str(dest_path),
                size_bytes=file_size,
                checksum=checksum,
                metadata=metadata
            )
            
            # Log activity
            await self._log_activity("upload", dataset_id, f"Uploaded {source_path.name}")

            # Format upload info as readable message
            upload_msg = f"Dataset {dataset_id} uploaded and indexed successfully:\n"
            upload_msg += f"- Source: {source_path}\n"
            upload_msg += f"- Destination: {dest_path}\n"
            upload_msg += f"- Size: {round(file_size / (1024**2), 2)} MB\n"
            upload_msg += f"- Checksum: {checksum}\n"
            upload_msg += f"- Data type: {data_type}\n"

            return Response(
                message=upload_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(
                message=f"Upload failed: {str(e)}",
                break_loop=False
            )
    
    async def _index_dataset(self, dataset_id: str, metadata: Dict[str, Any]) -> Response:
        """Index an existing dataset in the data lake."""
        
        if not dataset_id:
            return Response(message="Dataset ID is required for indexing", break_loop=False)
        
        try:
            await self._index_dataset_in_db(
                dataset_id=dataset_id,
                name=metadata.get("name", dataset_id),
                data_type=metadata.get("type", "unknown"),
                source=metadata.get("source", "manual"),
                file_path=metadata.get("file_path", ""),
                size_bytes=metadata.get("size_bytes", 0),
                checksum=metadata.get("checksum", ""),
                metadata=metadata
            )
            
            await self._log_activity("index", dataset_id, "Dataset indexed manually")

            # Format index info as readable message
            index_msg = f"Dataset {dataset_id} indexed successfully:\n"
            index_msg += f"- Indexed at: {datetime.now().isoformat()}\n"
            index_msg += f"- Data type: {metadata.get('type', 'unknown')}\n"
            index_msg += f"- Source: {metadata.get('source', 'manual')}\n"
            index_msg += f"- Access level: {metadata.get('access_level', 'restricted')}\n"

            return Response(
                message=index_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(
                message=f"Indexing failed: {str(e)}",
                break_loop=False
            )
    
    async def _index_dataset_in_db(self, dataset_id: str, name: str, data_type: str, 
                                 source: str, file_path: str, size_bytes: int, 
                                 checksum: str, metadata: Dict[str, Any]):
        """Index dataset in SQLite database."""
        
        conn = sqlite3.connect(str(self.metadata_db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO datasets 
            (dataset_id, name, data_type, source, file_path, size_bytes, 
             created_at, indexed_at, checksum, metadata, access_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dataset_id, name, data_type, source, file_path, size_bytes,
            datetime.now().isoformat(), datetime.now().isoformat(),
            checksum, json.dumps(metadata), metadata.get("access_level", "restricted")
        ))
        
        conn.commit()
        conn.close()
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    async def _log_activity(self, action: str, dataset_id: str, details: str):
        """Log activity to database."""
        conn = sqlite3.connect(str(self.metadata_db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO activity_log (timestamp, action, dataset_id, details)
            VALUES (?, ?, ?, ?)
        """, (datetime.now().isoformat(), action, dataset_id, details))
        
        conn.commit()
        conn.close()
    
    async def _query_datasets(self, query_params: Dict[str, Any]) -> Response:
        """Query datasets based on parameters from the actual database."""

        try:
            conn = sqlite3.connect(str(self.metadata_db_path))
            cursor = conn.cursor()

            # Build query based on parameters
            query = "SELECT dataset_id, name, data_type, source, size_bytes, created_at, metadata FROM datasets WHERE 1=1"
            params = []

            if query_params.get("type"):
                query += " AND data_type = ?"
                params.append(query_params["type"])

            if query_params.get("source"):
                query += " AND source = ?"
                params.append(query_params["source"])

            if query_params.get("dataset_id"):
                query += " AND dataset_id LIKE ?"
                params.append(f"%{query_params['dataset_id']}%")

            cursor.execute(query, params)
            rows = cursor.fetchall()

            filtered_datasets = []
            for row in rows:
                dataset_id, name, data_type, source, size_bytes, created_at, metadata_json = row
                try:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                except:
                    metadata = {}

                filtered_datasets.append({
                    "dataset_id": dataset_id,
                    "name": name,
                    "type": data_type,
                    "source": source,
                    "size_gb": round(size_bytes / (1024**3), 2) if size_bytes else 0,
                    "created": created_at,
                    "description": metadata.get("description", "No description available")
                })

            conn.close()

        except Exception as e:
            return Response(message=f"Query failed: {str(e)}", break_loop=False)
        
        # Format query results as readable message
        query_msg = f"Found {len(filtered_datasets)} datasets matching query:\n"
        for dataset in filtered_datasets:
            query_msg += f"- {dataset['dataset_id']} ({dataset['type']}, {dataset['size_gb']} GB)\n"
            query_msg += f"  Source: {dataset['source']}, Created: {dataset['created']}\n"
            query_msg += f"  Description: {dataset['description']}\n\n"

        return Response(
            message=query_msg,
            break_loop=False
        )
    
    async def _create_dataset(self, dataset_id: str, metadata: Dict[str, Any]) -> Response:
        """Create a new dataset entry in the data lake."""

        if not dataset_id:
            return Response(message="Dataset ID is required", break_loop=False)

        try:
            # Create dataset directory structure
            data_type = metadata.get('type', 'general')
            dataset_dir = self.data_lake_path / data_type / dataset_id
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Create dataset entry in database
            await self._index_dataset_in_db(
                dataset_id=dataset_id,
                name=metadata.get("name", dataset_id),
                data_type=data_type,
                source=metadata.get("source", "manual_creation"),
                file_path=str(dataset_dir),
                size_bytes=0,  # Empty dataset initially
                checksum="",
                metadata=metadata
            )

            # Log the creation activity
            await self._log_activity("create", dataset_id, f"Dataset created with type {data_type}")

            create_msg = f"Dataset {dataset_id} created successfully:\n"
            create_msg += f"- Created at: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            create_msg += f"- Data type: {data_type}\n"
            create_msg += f"- Storage path: {dataset_dir}\n"
            create_msg += f"- Access level: {metadata.get('access_level', 'restricted')}\n"
            create_msg += f"- Status: created and indexed\n"

            return Response(
                message=create_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(message=f"Dataset creation failed: {str(e)}", break_loop=False)
    
    async def _delete_dataset(self, dataset_id: str) -> Response:
        """Delete a dataset from the data lake."""
        
        if not dataset_id:
            return Response(message="Dataset ID is required", break_loop=False)

        try:
            # First create a backup before deletion
            backup_response = await self._backup_dataset(dataset_id)
            if "failed" in backup_response.message.lower():
                return Response(message=f"Cannot delete dataset: backup failed - {backup_response.message}", break_loop=False)

            # Get dataset info from database
            conn = sqlite3.connect(str(self.metadata_db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT file_path FROM datasets WHERE dataset_id = ?", (dataset_id,))
            result = cursor.fetchone()

            if not result:
                conn.close()
                return Response(message=f"Dataset {dataset_id} not found", break_loop=False)

            file_path = result[0]

            # Delete from database
            cursor.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
            conn.commit()
            conn.close()

            # Delete physical file if it exists
            file_deleted = False
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                file_deleted = True

            # Log the deletion activity
            await self._log_activity("delete", dataset_id, f"Dataset deleted (backup created)")

            delete_msg = f"Dataset {dataset_id} deleted successfully:\n"
            delete_msg += f"- Deleted at: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            delete_msg += f"- Backup created: Yes\n"
            delete_msg += f"- Physical file removed: {'Yes' if file_deleted else 'N/A'}\n"
            delete_msg += f"- Database record removed: Yes\n"

            return Response(
                message=delete_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(message=f"Deletion failed: {str(e)}", break_loop=False)
    
    async def _backup_dataset(self, dataset_id: str) -> Response:
        """Create a real backup of a dataset."""

        if not dataset_id:
            return Response(message="Dataset ID is required", break_loop=False)

        try:
            # Get dataset info from database
            conn = sqlite3.connect(str(self.metadata_db_path))
            cursor = conn.cursor()

            cursor.execute("SELECT file_path, size_bytes FROM datasets WHERE dataset_id = ?", (dataset_id,))
            result = cursor.fetchone()
            conn.close()

            if not result:
                return Response(message=f"Dataset {dataset_id} not found", break_loop=False)

            file_path, size_bytes = result

            if not file_path or not os.path.exists(file_path):
                return Response(message=f"Dataset file not found: {file_path}", break_loop=False)

            # Create backup directory
            backup_dir = self.data_lake_path / "backups"
            backup_dir.mkdir(exist_ok=True)

            # Create backup with timestamp
            timestamp = int(time.time())
            backup_id = f"{dataset_id}_backup_{timestamp}"
            source_path = Path(file_path)
            backup_path = backup_dir / f"{backup_id}{source_path.suffix}"

            # Copy file to backup location
            shutil.copy2(source_path, backup_path)

            # Log the backup activity
            await self._log_activity("backup", dataset_id, f"Backup created: {backup_path}")

            backup_msg = f"Backup created for dataset {dataset_id}:\n"
            backup_msg += f"- Backup ID: {backup_id}\n"
            backup_msg += f"- Created at: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            backup_msg += f"- Backup location: {backup_path}\n"
            backup_msg += f"- Original size: {round(size_bytes / (1024**2), 2)} MB\n"
            backup_msg += f"- Status: completed\n"

            return Response(
                message=backup_msg,
                break_loop=False
            )

        except Exception as e:
            return Response(message=f"Backup failed: {str(e)}", break_loop=False)