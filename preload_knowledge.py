#!/usr/bin/env python3
"""
Standalone script to preload knowledge documents into mem0 memory backend.
Run this before starting Agent Zero to ensure all knowledge is ready.

Usage:
    python preload_knowledge.py [--memory-subdir default] [--max-docs 500] [--batch-size 20]
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from python.helpers.print_style import PrintStyle
from python.helpers.settings import get_settings
from python.helpers.memory_mem0 import Mem0Memory
from python.helpers.memory import Memory
from python.helpers import files
import models


class KnowledgePreloader:
    """Preload knowledge documents into mem0 memory backend"""
    
    def __init__(self, memory_subdir="default", max_docs=500, batch_size=20):
        self.memory_subdir = memory_subdir
        self.max_docs = max_docs
        self.batch_size = batch_size
        self.start_time = datetime.now()
        
    async def preload(self):
        """Main preloading process"""
        PrintStyle.standard("🚀 Agent Zero Knowledge Preloader")
        PrintStyle.standard("=" * 50)
        
        # Check if mem0 is configured
        settings = get_settings()
        if settings.get("memory_backend") != "mem0" or not settings.get("mem0_enabled"):
            PrintStyle.error("❌ mem0 is not configured as the memory backend")
            PrintStyle.standard("Please set memory_backend='mem0' and mem0_enabled=true in settings")
            return False
            
        PrintStyle.standard(f"✓ Memory backend: {settings.get('memory_backend')}")
        PrintStyle.standard(f"✓ Memory subdir: {self.memory_subdir}")
        PrintStyle.standard(f"✓ Max documents: {self.max_docs}")
        PrintStyle.standard(f"✓ Batch size: {self.batch_size}")
        
        # Create mock agent for mem0 initialization
        agent = self._create_mock_agent()
        
        try:
            # Initialize mem0 memory
            PrintStyle.standard("\n📚 Initializing mem0 memory backend...")
            memory_instance = await self._get_memory_instance(agent)
            
            # Preload knowledge
            PrintStyle.standard("📖 Starting knowledge preloading...")
            await self._preload_knowledge(memory_instance, agent)
            
            # Test the loaded knowledge
            PrintStyle.standard("🔍 Testing loaded knowledge...")
            await self._test_knowledge(memory_instance)
            
            duration = (datetime.now() - self.start_time).total_seconds()
            PrintStyle.standard(f"\n✅ Knowledge preloading completed successfully in {duration:.1f} seconds!")
            PrintStyle.standard("🎉 Agent Zero is ready to use with preloaded knowledge!")
            
            return True
            
        except Exception as e:
            PrintStyle.error(f"❌ Knowledge preloading failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _create_mock_agent(self):
        """Create a mock agent for mem0 initialization"""
        
        class MockAgent:
            def __init__(self, memory_subdir, max_docs, batch_size):
                self.config = MockConfig(memory_subdir)
                self.context = MockContext()
                self.max_docs = max_docs
                self.batch_size = batch_size
                
            async def rate_limiter(self, **kwargs):
                # No rate limiting during preloading
                pass
                
        class MockConfig:
            def __init__(self, memory_subdir):
                self.memory_subdir = memory_subdir
                self.embeddings_model = MockEmbeddingModel()
                self.utility_model = MockUtilityModel()
                self.knowledge_subdirs = ["default", "custom"]
                
        class MockEmbeddingModel:
            def __init__(self):
                settings = get_settings()
                self.name = settings.get("embed_model_name", "text-embedding-3-small")
                provider_name = settings.get("embed_model_provider", "OPENAI")
                self.provider = getattr(models.ModelProvider, provider_name, models.ModelProvider.OPENAI)
                
        class MockUtilityModel:
            def __init__(self):
                settings = get_settings()
                self.name = settings.get("util_model_name", "gpt-4o-mini")
                provider_name = settings.get("util_model_provider", "OPENAI")
                self.provider = getattr(models.ModelProvider, provider_name, models.ModelProvider.OPENAI)
                
        class MockContext:
            def __init__(self):
                self.id = f"preloader_{int(datetime.now().timestamp())}"
                self.log = MockLog()
                
        class MockLog:
            def log(self, **kwargs):
                heading = kwargs.get('heading', '')
                if heading:
                    PrintStyle.standard(f"  {heading}")
                return MockLogItem()
                
        class MockLogItem:
            def stream(self, **kwargs):
                if 'progress' in kwargs:
                    progress = kwargs['progress'].strip()
                    if progress:
                        PrintStyle.standard(f"    {progress}")
                        
            def update(self, **kwargs):
                if 'heading' in kwargs:
                    heading = kwargs['heading']
                    PrintStyle.standard(f"  {heading}")
        
        return MockAgent(self.memory_subdir, self.max_docs, self.batch_size)
    
    async def _get_memory_instance(self, agent):
        """Get mem0 memory instance"""
        # Force mem0 backend by temporarily updating the static cache key
        memory_subdir = agent.config.memory_subdir or "default"
        
        # Clear any existing instance to force recreation
        if memory_subdir in Mem0Memory.index:
            del Mem0Memory.index[memory_subdir]
            
        # Create new instance
        return await Mem0Memory.get(agent)
    
    async def _preload_knowledge(self, memory_instance, agent):
        """Preload knowledge with custom limits"""
        from python.helpers import knowledge_import
        
        # Override the max_docs setting temporarily
        original_preload_knowledge = memory_instance.preload_knowledge
        
        async def custom_preload_knowledge(log_item, kn_dirs, memory_subdir):
            """Custom preload with our settings"""
            if log_item:
                log_item.update(heading="Preloading knowledge into mem0...")
                
            # Load knowledge using existing system
            index = {}
            
            for kn_dir in kn_dirs:
                for area in Memory.Area:
                    index = knowledge_import.load_knowledge(
                        log_item,
                        files.get_abs_path("knowledge", kn_dir, area.value),
                        index,
                        {"area": area.value},
                    )
                    
            # Load instrument descriptions
            index = knowledge_import.load_knowledge(
                log_item,
                files.get_abs_path("instruments"),
                index,
                {"area": Memory.Area.INSTRUMENTS.value},
                filename_pattern="**/*.md",
            )
            
            # Insert knowledge documents with our custom limits
            all_docs = []
            for file_path, knowledge_data in index.items():
                if knowledge_data.get("documents"):
                    all_docs.extend(knowledge_data["documents"])
            
            total_found = len(all_docs)
            if len(all_docs) > self.max_docs:
                PrintStyle.info(f"Limiting knowledge preload to {self.max_docs} documents (found {total_found})")
                all_docs = all_docs[:self.max_docs]
                
            if all_docs:
                try:
                    if log_item:
                        log_item.update(heading=f"Inserting {len(all_docs)} knowledge documents into mem0...")
                    
                    # Insert in batches
                    for i in range(0, len(all_docs), self.batch_size):
                        batch = all_docs[i:i + self.batch_size]
                        await memory_instance.insert_documents(batch)
                        
                        if log_item:
                            progress = f"Inserted {min(i + self.batch_size, len(all_docs))}/{len(all_docs)} documents"
                            log_item.stream(progress=f"\n{progress}")
                            
                    if log_item:
                        log_item.update(heading=f"Knowledge preloading completed: {len(all_docs)} documents inserted")
                        
                except Exception as e:
                    PrintStyle.error(f"Error inserting knowledge documents: {str(e)}")
                    if log_item:
                        log_item.update(heading=f"Knowledge insertion partially failed: {str(e)}")
            else:
                if log_item:
                    log_item.update(heading="No knowledge documents found to preload")
        
        # Use our custom preload function
        mock_log = agent.context.log.log(heading="Starting knowledge preloading...")
        await custom_preload_knowledge(mock_log, agent.config.knowledge_subdirs, self.memory_subdir)
    
    async def _test_knowledge(self, memory_instance):
        """Test that knowledge was loaded correctly"""
        try:
            # Test search for common terms
            test_queries = ["agent", "tool", "memory", "python"]
            
            for query in test_queries:
                results = await memory_instance.search_similarity_threshold(
                    query, limit=3, threshold=0.1
                )
                PrintStyle.standard(f"  Query '{query}': {len(results)} results found")
                
            # Overall test
            all_results = await memory_instance.search_similarity_threshold(
                "agent zero", limit=10, threshold=0.0
            )
            PrintStyle.standard(f"  Total searchable memories: {len(all_results)} found")
            
        except Exception as e:
            PrintStyle.error(f"Knowledge testing failed: {str(e)}")


async def main():
    parser = argparse.ArgumentParser(description="Preload knowledge documents into mem0")
    parser.add_argument("--memory-subdir", default="default", help="Memory subdirectory to use")
    parser.add_argument("--max-docs", type=int, default=500, help="Maximum documents to preload")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size for insertions")
    
    args = parser.parse_args()
    
    preloader = KnowledgePreloader(
        memory_subdir=args.memory_subdir,
        max_docs=args.max_docs,
        batch_size=args.batch_size
    )
    
    success = await preloader.preload()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())