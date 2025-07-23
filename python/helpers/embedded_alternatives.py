"""
Embedded alternatives for mem0 Graph Memory when Docker services are unavailable.
Provides in-memory and file-based alternatives for development and testing.
"""

import os
import sqlite3
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from python.helpers.print_style import PrintStyle

class EmbeddedNeo4jAlternative:
    """
    Lightweight graph database alternative using SQLite for development.
    Provides basic graph functionality for when Neo4j is unavailable.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize embedded graph database"""
        if db_path is None:
            # Use temp directory for development
            temp_dir = Path(tempfile.gettempdir()) / "agent_zero_graph"
            temp_dir.mkdir(exist_ok=True)
            db_path = temp_dir / "graph_memory.db"
        
        self.db_path = db_path
        self.conn = None
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with graph tables"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
        
        # Create tables for nodes and relationships
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                labels TEXT,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                source_id TEXT,
                target_id TEXT,
                type TEXT,
                properties TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_nodes_labels ON nodes(labels);
            CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(type);
            CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
            CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
        """)
        self.conn.commit()
    
    def add_node(self, node_id: str, labels: List[str], properties: Dict[str, Any]):
        """Add a node to the graph"""
        labels_json = json.dumps(labels)
        properties_json = json.dumps(properties)
        
        self.conn.execute(
            "INSERT OR REPLACE INTO nodes (id, labels, properties) VALUES (?, ?, ?)",
            (node_id, labels_json, properties_json)
        )
        self.conn.commit()
    
    def add_relationship(self, rel_id: str, source_id: str, target_id: str, 
                        rel_type: str, properties: Dict[str, Any] = None):
        """Add a relationship between nodes"""
        properties_json = json.dumps(properties or {})
        
        self.conn.execute(
            "INSERT OR REPLACE INTO relationships (id, source_id, target_id, type, properties) VALUES (?, ?, ?, ?, ?)",
            (rel_id, source_id, target_id, rel_type, properties_json)
        )
        self.conn.commit()
    
    def find_nodes(self, label: str = None, properties: Dict[str, Any] = None) -> List[Dict]:
        """Find nodes matching criteria"""
        query = "SELECT id, labels, properties FROM nodes WHERE 1=1"
        params = []
        
        if label:
            query += " AND labels LIKE ?"
            params.append(f'%"{label}"%')
        
        cursor = self.conn.execute(query, params)
        results = []
        
        for row in cursor:
            node_id, labels_json, properties_json = row
            labels = json.loads(labels_json)
            props = json.loads(properties_json)
            
            # Filter by properties if specified
            if properties:
                match = True
                for key, value in properties.items():
                    if key not in props or props[key] != value:
                        match = False
                        break
                if not match:
                    continue
            
            results.append({
                'id': node_id,
                'labels': labels,
                'properties': props
            })
        
        return results
    
    def find_relationships(self, source_id: str = None, target_id: str = None, 
                          rel_type: str = None) -> List[Dict]:
        """Find relationships matching criteria"""
        query = "SELECT id, source_id, target_id, type, properties FROM relationships WHERE 1=1"
        params = []
        
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        
        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)
        
        if rel_type:
            query += " AND type = ?"
            params.append(rel_type)
        
        cursor = self.conn.execute(query, params)
        results = []
        
        for row in cursor:
            rel_id, src_id, tgt_id, r_type, properties_json = row
            props = json.loads(properties_json)
            
            results.append({
                'id': rel_id,
                'source_id': src_id,
                'target_id': tgt_id,
                'type': r_type,
                'properties': props
            })
        
        return results
    
    def get_node_relationships(self, node_id: str, direction: str = "both") -> List[Dict]:
        """Get all relationships for a node"""
        if direction == "outgoing":
            return self.find_relationships(source_id=node_id)
        elif direction == "incoming":
            return self.find_relationships(target_id=node_id)
        else:  # both
            outgoing = self.find_relationships(source_id=node_id)
            incoming = self.find_relationships(target_id=node_id)
            return outgoing + incoming
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

class EmbeddedQdrantAlternative:
    """
    In-memory vector store alternative for when Qdrant is unavailable.
    Uses FAISS for similarity search with metadata storage.
    """
    
    def __init__(self):
        """Initialize embedded vector store"""
        self.vectors = {}  # collection_name -> {vectors, metadata, index}
        self.next_ids = {}  # collection_name -> next_id
        
        try:
            import faiss
            import numpy as np
            self.faiss = faiss
            self.np = np
            self.available = True
        except ImportError:
            PrintStyle.warning("FAISS not available - vector operations will be limited")
            self.available = False
    
    def create_collection(self, collection_name: str, vector_size: int = 1536):
        """Create a collection for vectors"""
        if not self.available:
            return False
        
        if collection_name not in self.vectors:
            # Create FAISS index
            index = self.faiss.IndexFlatIP(vector_size)  # Inner product (cosine similarity)
            
            self.vectors[collection_name] = {
                'index': index,
                'metadata': {},
                'vector_size': vector_size
            }
            self.next_ids[collection_name] = 0
        
        return True
    
    def add_vectors(self, collection_name: str, vectors: List[List[float]], 
                   metadata: List[Dict] = None, ids: List[str] = None):
        """Add vectors to collection"""
        if not self.available or collection_name not in self.vectors:
            return False
        
        collection = self.vectors[collection_name]
        
        # Convert to numpy array and normalize for cosine similarity
        vectors_np = self.np.array(vectors, dtype='float32')
        self.faiss.normalize_L2(vectors_np)
        
        # Add to FAISS index
        start_id = len(collection['metadata'])
        collection['index'].add(vectors_np)
        
        # Store metadata
        if metadata is None:
            metadata = [{}] * len(vectors)
        
        if ids is None:
            ids = [str(start_id + i) for i in range(len(vectors))]
        
        for i, (vector_id, meta) in enumerate(zip(ids, metadata)):
            collection['metadata'][start_id + i] = {
                'id': vector_id,
                'metadata': meta
            }
        
        return True
    
    def search(self, collection_name: str, query_vector: List[float], 
              limit: int = 10, score_threshold: float = 0.0) -> List[Dict]:
        """Search for similar vectors"""
        if not self.available or collection_name not in self.vectors:
            return []
        
        collection = self.vectors[collection_name]
        
        # Normalize query vector
        query_np = self.np.array([query_vector], dtype='float32')
        self.faiss.normalize_L2(query_np)
        
        # Search
        scores, indices = collection['index'].search(query_np, limit)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for invalid results
                continue
                
            if score < score_threshold:
                continue
            
            if idx in collection['metadata']:
                result = collection['metadata'][idx].copy()
                result['score'] = float(score)
                results.append(result)
        
        return results
    
    def get_collection_info(self, collection_name: str) -> Dict:
        """Get information about a collection"""
        if collection_name not in self.vectors:
            return {}
        
        collection = self.vectors[collection_name]
        return {
            'name': collection_name,
            'vector_count': collection['index'].ntotal if self.available else 0,
            'vector_size': collection['vector_size']
        }

class EmbeddedMemoryBackend:
    """
    Combines embedded alternatives to provide fallback memory functionality
    """
    
    def __init__(self, memory_subdir: str = "default"):
        """Initialize embedded memory backend"""
        self.memory_subdir = memory_subdir
        
        # Initialize embedded databases
        self.graph_db = EmbeddedNeo4jAlternative()
        self.vector_db = EmbeddedQdrantAlternative()
        
        # Create default collection
        self.collection_name = f"embedded_memory_{memory_subdir}"
        self.vector_db.create_collection(self.collection_name)
        
        PrintStyle.info(f"Initialized embedded memory backend for '{memory_subdir}'")
    
    def store_memory(self, content: str, metadata: Dict = None, embedding: List[float] = None):
        """Store a memory with both vector and graph components"""
        import uuid
        memory_id = str(uuid.uuid4())
        
        # Store vector if embedding provided
        if embedding and self.vector_db.available:
            meta = metadata or {}
            meta['content'] = content
            meta['memory_id'] = memory_id
            
            self.vector_db.add_vectors(
                self.collection_name,
                [embedding],
                [meta],
                [memory_id]
            )
        
        # Store graph components if metadata has entities/relationships
        if metadata:
            entities = metadata.get('entities', [])
            relationships = metadata.get('relationships', [])
            
            # Add nodes for entities
            for entity in entities:
                if isinstance(entity, dict):
                    entity_id = entity.get('id', entity.get('name', str(uuid.uuid4())))
                    labels = [entity.get('type', 'Entity')]
                    properties = entity.copy()
                    properties['memory_id'] = memory_id
                    properties['content'] = content
                    
                    self.graph_db.add_node(entity_id, labels, properties)
            
            # Add relationships
            for rel in relationships:
                if isinstance(rel, dict):
                    rel_id = rel.get('id', str(uuid.uuid4()))
                    source = rel.get('source', rel.get('from'))
                    target = rel.get('target', rel.get('to'))
                    rel_type = rel.get('type', rel.get('relationship', 'RELATED_TO'))
                    
                    if source and target:
                        rel_props = rel.copy()
                        rel_props['memory_id'] = memory_id
                        
                        self.graph_db.add_relationship(rel_id, source, target, rel_type, rel_props)
        
        return memory_id
    
    def search_similar(self, query_embedding: List[float], limit: int = 10, 
                      threshold: float = 0.0) -> List[Dict]:
        """Search for similar memories"""
        return self.vector_db.search(self.collection_name, query_embedding, limit, threshold)
    
    def find_graph_entities(self, entity_type: str = None) -> List[Dict]:
        """Find entities in the graph"""
        return self.graph_db.find_nodes(label=entity_type)
    
    def find_entity_relationships(self, entity_id: str) -> List[Dict]:
        """Find relationships for an entity"""
        return self.graph_db.get_node_relationships(entity_id)
    
    def get_stats(self) -> Dict:
        """Get statistics about stored memories"""
        vector_info = self.vector_db.get_collection_info(self.collection_name)
        
        return {
            'memory_subdir': self.memory_subdir,
            'backend_type': 'embedded',
            'vector_count': vector_info.get('vector_count', 0),
            'vector_db_available': self.vector_db.available,
            'graph_db_available': True  # SQLite is always available
        }
    
    def close(self):
        """Close database connections"""
        self.graph_db.close()

# Global registry of embedded backends
_embedded_backends = {}

def get_embedded_backend(memory_subdir: str = "default") -> EmbeddedMemoryBackend:
    """Get or create embedded backend for memory subdirectory"""
    if memory_subdir not in _embedded_backends:
        _embedded_backends[memory_subdir] = EmbeddedMemoryBackend(memory_subdir)
    
    return _embedded_backends[memory_subdir]