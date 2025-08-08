#!/usr/bin/env python3
"""Integration test for GraphRAG functionality.

This script tests the real GraphRAG integration with actual models and FalkorDB.
It performs end-to-end testing of ingestion and querying capabilities.

Run with: python test_graphrag_integration.py
"""

import logging
import sys
import traceback
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def test_graphrag_helper() -> bool:
    """Test GraphRAG helper functionality with real models and database.

    Returns:
        bool: True if all tests pass, False otherwise
    """
    logger.info("=" * 60)
    logger.info("Starting GraphRAG Integration Test")
    logger.info("=" * 60)

    try:
        # Import GraphRAG helper
        logger.info("Importing GraphRAG helper...")
        from python.helpers.graphrag_helper import GraphRAGHelper
        logger.info("✓ GraphRAG helper imported successfully")

        # Get singleton instance
        logger.info("Creating GraphRAG helper instance...")
        helper = GraphRAGHelper.get_default()
        logger.info("✓ GraphRAG helper instance created")

        # Test ingestion
        logger.info("Testing text ingestion...")
        test_text = """
        Albert Einstein was a German-born theoretical physicist who is widely held
        to be one of the greatest and most influential scientists of all time.
        He was born on March 14, 1879, in Ulm, in the Kingdom of Württemberg in
        the German Empire. Einstein developed the theory of relativity, one of the
        two pillars of modern physics. He received the Nobel Prize in Physics in 1921
        for his services to theoretical physics, and especially for his discovery
        of the law of the photoelectric effect.
        """

        helper.ingest_text(test_text, "Focus on biographical information and scientific achievements")
        logger.info("✓ Text ingested successfully")

        # Test queries
        test_queries = [
            "Who was Albert Einstein?",
            "When was Einstein born?",
            "What did Einstein win the Nobel Prize for?",
            "What theory did Einstein develop?"
        ]

        logger.info("Testing knowledge graph queries...")
        for i, query in enumerate(test_queries, 1):
            logger.info(f"Query {i}: {query}")
            try:
                answer = helper.query(query)
                logger.info(f"Answer {i}: {answer}")
                logger.info("✓ Query executed successfully")
            except Exception as e:
                logger.error(f"✗ Query {i} failed: {e}")
                return False

        # Test ingestion of additional related information
        logger.info("Testing ingestion of additional related information...")
        additional_text = """
        Einstein's famous equation E=mc² expresses the mass-energy equivalence.
        He also contributed to the development of quantum theory and statistical mechanics.
        Einstein emigrated to the United States in 1933 and became a U.S. citizen in 1940.
        He spent his later years at Princeton University working on a unified field theory.
        """

        helper.ingest_text(additional_text, "Focus on scientific contributions and later life")
        logger.info("✓ Additional text ingested successfully")

        # Test queries on combined knowledge
        logger.info("Testing queries on combined knowledge...")
        combined_queries = [
            "What is Einstein's famous equation?",
            "When did Einstein become a U.S. citizen?",
            "Where did Einstein work in his later years?"
        ]

        for i, query in enumerate(combined_queries, 1):
            logger.info(f"Combined Query {i}: {query}")
            try:
                answer = helper.query(query)
                logger.info(f"Combined Answer {i}: {answer}")
                logger.info("✓ Combined query executed successfully")
            except Exception as e:
                logger.error(f"✗ Combined query {i} failed: {e}")
                return False

        logger.info("=" * 60)
        logger.info("✓ All GraphRAG integration tests passed successfully!")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"✗ GraphRAG integration test failed: {e}")
        logger.error("Stack trace:")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        return False


def test_graphrag_tools() -> bool:
    """Test GraphRAG tools functionality.

    Returns:
        bool: True if all tests pass, False otherwise
    """
    logger.info("Testing GraphRAG tools...")

    try:
        # Import tools
        from python.tools.graphrag_ingest import GraphRAGIngest
        from python.tools.graphrag_query import GraphRAGQuery
        logger.info("✓ GraphRAG tools imported successfully")

        # Create minimal agent stub for tool initialization
        class MockAgent:
            def log_to_all(self, *args, **kwargs):
                pass

        mock_agent = MockAgent()

        # Test ingest tool
        logger.info("Testing GraphRAGIngest tool...")
        ingest_tool = GraphRAGIngest(mock_agent, "graphrag_ingest", None, {}, "", None)

        import asyncio
        result = asyncio.run(ingest_tool.execute(
            text="The Eiffel Tower is located in Paris, France. It was built in 1889.",
            instruction="Focus on landmarks and locations"
        ))

        if "successfully" in result.message.lower():
            logger.info("✓ GraphRAGIngest tool executed successfully")
        else:
            logger.error(f"✗ GraphRAGIngest tool failed: {result.message}")
            return False

        # Test query tool
        logger.info("Testing GraphRAGQuery tool...")
        query_tool = GraphRAGQuery(mock_agent, "graphrag_query", None, {}, "", None)

        result = asyncio.run(query_tool.execute(message="Where is the Eiffel Tower located?"))

        if result.message and "no data" not in result.message.lower():
            logger.info(f"✓ GraphRAGQuery tool executed successfully: {result.message}")
        else:
            logger.error(f"✗ GraphRAGQuery tool failed: {result.message}")
            return False

        logger.info("✓ All GraphRAG tool tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ GraphRAG tool test failed: {e}")
        logger.error("Stack trace:")
        logger.error(traceback.format_exc())
        return False


def main():
    """Main test runner."""
    logger.info("Starting comprehensive GraphRAG integration testing...")

    # Test GraphRAG helper
    helper_success = test_graphrag_helper()

    # Test GraphRAG tools
    tools_success = test_graphrag_tools()

    # Final results
    if helper_success and tools_success:
        logger.info("🎉 All GraphRAG integration tests completed successfully!")
        sys.exit(0)
    else:
        logger.error("❌ Some GraphRAG integration tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
