"""Unit-tests for the safe comparator helpers.

The project currently has no testing dependencies; therefore the tests use
the standard library ``unittest`` framework and build *stub* versions of the
external libraries that ``python.helpers.memory`` and ``python.helpers.vector_db``
import at module import-time.  This allows us to import those modules without
installing their heavy dependencies (langchain, faiss, numpy, etc.).

Only the parts of the external libraries that are accessed during import of
the comparator helpers are stubbed.
"""

from __future__ import annotations

import sys
import types
import math
import importlib
import unittest


def _setup_stub_modules() -> None:
    """Inject minimal stub versions of heavy optional dependencies."""

    module_names = [
        # langchain family
        "langchain",
        "langchain.storage",
        "langchain.embeddings",
        "langchain_community",
        "langchain_community.vectorstores",
        "langchain_community.vectorstores.utils",
        "langchain_community.docstore",
        "langchain_community.docstore.in_memory",
        # langchain-core family
        "langchain_core",
        "langchain_core.embeddings",
        "langchain_core.vectorstores",
        "langchain_core.vectorstores.base",
        "langchain_core.documents",
        # other heavy deps
        "faiss",
        "numpy",
        # internal modules referenced at import-time
        "models",
        "python.helpers.faiss_monkey_patch",
        "python.helpers.print_style",
        "python.helpers.files",
        "python.helpers.knowledge_import",
        "python.helpers.log",
        "agent",
    ]

    # Create empty module placeholders first to satisfy circular imports
    for name in module_names:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    # Populate attributes that the imported code touches -------------------

    # langchain.storage
    sys.modules["langchain.storage"].InMemoryByteStore = object
    sys.modules["langchain.storage"].LocalFileStore = object

    # langchain.embeddings
    sys.modules["langchain.embeddings"].CacheBackedEmbeddings = object

    # Fake FAISS class
    FAISS = type("FAISS", (), {})
    vec_mod = sys.modules["langchain_community.vectorstores"]
    vec_mod.FAISS = FAISS  # export attribute so "from ... import FAISS" works

    # DistanceStrategy enum replacement
    util_mod = sys.modules["langchain_community.vectorstores.utils"]
    util_mod.DistanceStrategy = type("DistanceStrategy", (), {"COSINE": "cosine"})

    # InMemoryDocstore stub
    sys.modules["langchain_community.docstore.in_memory"].InMemoryDocstore = object

    # langchain_core stubs
    sys.modules["langchain_core.embeddings"].Embeddings = object
    sys.modules["langchain_core.vectorstores.base"].VectorStore = object
    sys.modules["langchain_core.documents"].Document = type("Document", (), {})

    # numpy – only exp() is referenced
    np_stub = types.ModuleType("numpy")
    np_stub.exp = math.exp
    sys.modules["numpy"] = np_stub

    # print_style.PrintStyle stub
    sys.modules["python.helpers.print_style"].PrintStyle = type("PrintStyle", (), {})

    # knowledge_import stubs
    kn_mod = sys.modules["python.helpers.knowledge_import"]
    if not hasattr(kn_mod, "KnowledgeImport"):
        kn_mod.KnowledgeImport = type("KnowledgeImport", (), {})
    if not hasattr(kn_mod, "load_knowledge"):
        kn_mod.load_knowledge = lambda *args, **kwargs: {}

    # log stubs
    sys.modules["python.helpers.log"].Log = type("Log", (), {})
    sys.modules["python.helpers.log"].LogItem = type("LogItem", (), {})

    # agent stubs
    sys.modules["agent"].Agent = type("Agent", (), {})
    sys.modules["agent"].ModelConfig = type("ModelConfig", (), {})


class ComparatorTestCase(unittest.TestCase):
    """Tests for the secure comparator helpers."""

    @classmethod
    def setUpClass(cls):
        _setup_stub_modules()

    # ------------------------------------------------------------------
    # Memory comparator
    # ------------------------------------------------------------------
    def test_memory_comparator_allows_simple_filters(self):
        Memory = importlib.import_module("python.helpers.memory").Memory
        cmp_fn = Memory._get_comparator("area == 'MAIN' or area == 'FRAGMENTS'")

        self.assertTrue(cmp_fn({"area": "MAIN"}))
        self.assertTrue(cmp_fn({"area": "FRAGMENTS"}))
        self.assertFalse(cmp_fn({"area": "SOLUTIONS"}))

    def test_memory_comparator_rejects_malicious_code(self):
        Memory = importlib.import_module("python.helpers.memory").Memory

        with self.assertRaises(ValueError):
            Memory._get_comparator("__import__('os').system('echo hacked')")

    # ------------------------------------------------------------------
    # Vector DB comparator (module-level function)
    # ------------------------------------------------------------------
    def test_vector_comparator(self):
        vector_db = importlib.import_module("python.helpers.vector_db")

        cmp_fn = vector_db.get_comparator("score > 0.5 and area == 'MAIN'")

        self.assertTrue(cmp_fn({"score": 0.7, "area": "MAIN"}))
        self.assertFalse(cmp_fn({"score": 0.3, "area": "MAIN"}))

        with self.assertRaises(ValueError):
            vector_db.get_comparator("(__import__('os').system('bad'))")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
