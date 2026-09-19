# Memory

Provide persistent vector-based memory and knowledge retrieval for Agent Zero.

## What It Does

This plugin stores memories and knowledge embeddings in a FAISS-backed vector database, exposes tools for saving and recalling memories, and provides APIs and UI support for browsing, importing, updating, and deleting memory entries.

## Main Behavior

- **Persistent vector store**
  - Creates and loads FAISS indexes per memory subdirectory.
  - Stores embedding metadata so the index can be rebuilt if the embedding model changes.
- **Knowledge preloading**
  - Loads configured knowledge directories into memory when a database is initialized.
- **Memory tools**
  - Includes tools for saving, loading, deleting, forgetting, and behavior adjustment workflows.
- **Automatic conversation memory**
  - Stores durable preferences, project facts, and recurring constraints while filtering transient action-history fragments before insertion.
- **Dashboard APIs**
  - Exposes search, delete, bulk delete, update, and subdirectory listing endpoints for the memory dashboard.
- **Scoped storage**
  - Supports different memory subdirectories so memory can be separated by context or agent scope.

## Key Files

- **Core memory engine**
  - `helpers/memory.py` implements FAISS storage, index loading, embedding configuration, and knowledge preload.
- **Knowledge import**
  - `helpers/knowledge_import.py` imports external knowledge into memory storage.
- **Consolidation**
  - `helpers/memory_consolidation.py` contains memory consolidation logic.
- **Tools**
  - `tools/memory_save.py`
  - `tools/memory_load.py`
  - `tools/memory_delete.py`
  - `tools/memory_forget.py`
- **API**
  - `api/memory_dashboard.py` powers the memory management dashboard.
  - `api/import_knowledge.py` and `api/knowledge_reindex.py` handle knowledge import and reindexing.

## Configuration Scope

- **Settings section**: `agent`
- **Per-project config**: `true`
- **Per-agent config**: `true`

## Plugin Metadata

- **Name**: `_memory`
- **Title**: `Memory`
- **Description**: Provides persistent memory capabilities to Agent Zero agents.
