#!/usr/bin/env python3
"""Comprehensive test script for GraphRAG tools integration.

Tests both graphrag_ingest and graphrag_query tools with realistic scenarios
to verify end-to-end functionality, error handling, and data consistency.
"""

import asyncio
import logging
import sys
import traceback
from typing import Dict, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def test_graphrag_tools() -> bool:
    """Comprehensive test of GraphRAG tools functionality.

    Returns:
        bool: True if all tests pass, False otherwise
    """
    logger.info("=" * 70)
    logger.info("Starting Comprehensive GraphRAG Tools Test")
    logger.info("=" * 70)

    try:
        # Import tools after ensuring we're in the right environment
        from python.tools.graphrag_ingest import GraphRAGIngest
        from python.tools.graphrag_query import GraphRAGQuery
        from python.helpers.graphrag_helper import GraphRAGHelper
        from agent import Agent, AgentConfig, AgentContext
        from models import ModelConfig, ModelType

        # Create a minimal agent context for testing
        logger.info("Setting up test environment...")

        # Create mock agent config (minimal for testing)
        config = AgentConfig(
            chat_model=ModelConfig(
                type=ModelType.CHAT,
                provider="openrouter",
                name="openai/gpt-4.1"
            ),
            utility_model=ModelConfig(
                type=ModelType.CHAT,
                provider="openrouter",
                name="openai/gpt-4.1"
            ),
            embeddings_model=ModelConfig(
                type=ModelType.EMBEDDING,
                provider="openai",
                name="text-embedding-ada-002"
            ),
            browser_model=ModelConfig(
                type=ModelType.CHAT,
                provider="openrouter",
                name="openai/gpt-4.1"
            ),
            mcp_servers=""
        )

        # Create agent context
        context = AgentContext(config=config, id="test_context")
        agent = Agent(number=0, config=config, context=context)

        # Test scenarios with different types of content
        test_scenarios = [
            {
                "name": "Scientific Biography",
                "ingest_data": {
                    "text": """
                    Marie Curie was a Polish-French physicist and chemist who conducted pioneering research on radioactivity.
                    She was the first woman to win a Nobel Prize, the first person to win Nobel Prizes in two different scientific fields (Physics in 1903 and Chemistry in 1911),
                    and the first female professor at the University of Paris. She discovered the elements polonium and radium.
                    Her work laid the foundation for modern atomic physics and led to the development of X-ray technology.
                    She died in 1934 from aplastic anemia, likely caused by radiation exposure from her scientific work.
                    """,
                    "instruction": "Focus on scientific achievements, awards, and biographical details"
                },
                "queries": [
                    "What Nobel Prizes did Marie Curie win?",
                    "What elements did Marie Curie discover?",
                    "How did Marie Curie contribute to X-ray technology?",
                    "What was the cause of Marie Curie's death?"
                ]
            },
            {
                "name": "Software Architecture",
                "ingest_data": {
                    "text": """
                    The microservices architecture pattern decomposes applications into loosely coupled services.
                    Each service is responsible for a specific business capability and can be developed, deployed, and scaled independently.
                    Services communicate through well-defined APIs, typically REST or gRPC.
                    Key benefits include improved scalability, technology diversity, and fault isolation.
                    Challenges include increased complexity in service coordination, distributed system debugging, and data consistency.
                    Common patterns include API Gateway for request routing, Service Discovery for dynamic service location,
                    and Circuit Breaker for handling service failures gracefully.
                    """,
                    "instruction": "Extract architectural patterns, benefits, challenges, and communication methods"
                },
                "queries": [
                    "What are the main benefits of microservices architecture?",
                    "How do microservices communicate with each other?",
                    "What challenges are associated with microservices?",
                    "What are common microservices patterns?"
                ]
            },
            {
                "name": "Project Management",
                "ingest_data": {
                    "text": """
                    Project Phoenix Sprint Planning Meeting - March 20, 2024
                    Attendees: Sarah Johnson (Product Manager), Mike Chen (Lead Developer), Lisa Rodriguez (QA Lead), Tom Wilson (DevOps)

                    Key Decisions:
                    - Migrating user authentication system to OAuth 2.0 by end of Q2
                    - Sarah will coordinate with security team for compliance review by April 15
                    - Mike will lead the technical implementation with 3 developers
                    - Lisa will create comprehensive test scenarios for the new auth flow
                    - Tom will set up staging environment with new OAuth provider by April 1

                    Budget approved: $50,000 for external OAuth provider licensing
                    Next review meeting: April 10, 2024
                    """,
                    "instruction": "Focus on decisions, assignments, deadlines, budget, and meeting details"
                },
                "queries": [
                    "Who is responsible for the security compliance review?",
                    "When is the OAuth migration deadline?",
                    "What is the approved budget for OAuth licensing?",
                    "When is the next review meeting scheduled?"
                ]
            }
        ]

        # Test error handling scenarios
        error_scenarios = [
            {
                "name": "Empty Text Ingestion",
                "ingest_data": {"text": "", "instruction": ""},
                "expected_error": "No text provided"
            },
            {
                "name": "Empty Query",
                "query": "",
                "expected_error": "No query provided"
            }
        ]

        # Run tests
        passed_tests = 0
        total_tests = 0

        # Test 1: Error handling
        logger.info("\n" + "="*50)
        logger.info("TEST 1: Error Handling")
        logger.info("="*50)

        for scenario in error_scenarios:
            total_tests += 1
            logger.info(f"\nTesting: {scenario['name']}")

            try:
                if 'ingest_data' in scenario:
                    # Test ingest error
                    ingest_tool = GraphRAGIngest(
                        agent=agent, name="graphrag_ingest", method=None,
                        args=scenario['ingest_data'], message="", loop_data=None
                    )
                    response = await ingest_tool.execute(**scenario['ingest_data'])

                    if scenario['expected_error'] in response.message:
                        logger.info(f"✅ PASS: Correctly handled error - {response.message}")
                        passed_tests += 1
                    else:
                        logger.error(f"❌ FAIL: Expected error not found. Got: {response.message}")

                elif 'query' in scenario:
                    # Test query error
                    query_tool = GraphRAGQuery(
                        agent=agent, name="graphrag_query", method=None,
                        args={"message": scenario['query']}, message="", loop_data=None
                    )
                    response = await query_tool.execute(message=scenario['query'])

                    if scenario['expected_error'] in response.message:
                        logger.info(f"✅ PASS: Correctly handled error - {response.message}")
                        passed_tests += 1
                    else:
                        logger.error(f"❌ FAIL: Expected error not found. Got: {response.message}")

            except Exception as e:
                logger.error(f"❌ FAIL: Unexpected exception - {e}")

        # Test 2: Data ingestion and querying
        logger.info("\n" + "="*50)
        logger.info("TEST 2: Data Ingestion and Querying")
        logger.info("="*50)

        for scenario in test_scenarios:
            logger.info(f"\n--- Testing Scenario: {scenario['name']} ---")

            # Test ingestion
            total_tests += 1
            logger.info("Testing data ingestion...")

            try:
                ingest_tool = GraphRAGIngest(
                    agent=agent, name="graphrag_ingest", method=None,
                    args=scenario['ingest_data'], message="", loop_data=None
                )

                ingest_response = await ingest_tool.execute(**scenario['ingest_data'])

                if "successfully ingested" in ingest_response.message.lower():
                    logger.info(f"✅ PASS: Ingestion successful - {ingest_response.message}")
                    passed_tests += 1

                    # Test queries for this scenario
                    for query in scenario['queries']:
                        total_tests += 1
                        logger.info(f"Testing query: '{query}'")

                        try:
                            query_tool = GraphRAGQuery(
                                agent=agent, name="graphrag_query", method=None,
                                args={"message": query}, message="", loop_data=None
                            )

                            query_response = await query_tool.execute(message=query)

                            # Check if we got a meaningful response (not an error message)
                            if (
                                "no data yet" not in query_response.message.lower() and
                                "failed" not in query_response.message.lower() and
                                len(query_response.message.strip()) > 20  # Reasonable answer length
                            ):
                                logger.info(f"✅ PASS: Query successful")
                                logger.info(f"Response: {query_response.message[:200]}...")
                                passed_tests += 1
                            else:
                                logger.error(f"❌ FAIL: Query failed or returned insufficient data")
                                logger.error(f"Response: {query_response.message}")

                        except Exception as e:
                            logger.error(f"❌ FAIL: Query exception - {e}")
                            logger.error(traceback.format_exc())

                else:
                    logger.error(f"❌ FAIL: Ingestion failed - {ingest_response.message}")
                    # Skip queries for failed ingestion
                    total_tests += len(scenario['queries'])

            except Exception as e:
                logger.error(f"❌ FAIL: Ingestion exception - {e}")
                logger.error(traceback.format_exc())
                # Skip queries for failed ingestion
                total_tests += len(scenario['queries'])

        # Test 3: Complex cross-scenario queries
        logger.info("\n" + "="*50)
        logger.info("TEST 3: Cross-Scenario Queries")
        logger.info("="*50)

        cross_queries = [
            "Compare the achievements of Marie Curie with microservices benefits",
            "What are the common patterns between scientific research and software architecture?",
            "How do project management deadlines compare to scientific timelines?"
        ]

        for query in cross_queries:
            total_tests += 1
            logger.info(f"Testing cross-scenario query: '{query}'")

            try:
                query_tool = GraphRAGQuery(
                    agent=agent, name="graphrag_query", method=None,
                    args={"message": query}, message="", loop_data=None
                )

                response = await query_tool.execute(message=query)

                if (
                    "no data yet" not in response.message.lower() and
                    "failed" not in response.message.lower() and
                    len(response.message.strip()) > 50
                ):
                    logger.info(f"✅ PASS: Cross-scenario query successful")
                    logger.info(f"Response: {response.message[:200]}...")
                    passed_tests += 1
                else:
                    logger.error(f"❌ FAIL: Cross-scenario query failed")
                    logger.error(f"Response: {response.message}")

            except Exception as e:
                logger.error(f"❌ FAIL: Cross-scenario query exception - {e}")

        # Test 4: Knowledge graph state
        logger.info("\n" + "="*50)
        logger.info("TEST 4: Knowledge Graph State Verification")
        logger.info("="*50)

        total_tests += 1
        try:
            helper = GraphRAGHelper.get_default()

            # Test that we can access the knowledge graph
            test_query = "What information is stored in the knowledge graph?"
            response = helper.query(test_query)

            if response and len(str(response)) > 20:
                logger.info(f"✅ PASS: Knowledge graph contains data")
                logger.info(f"Sample response: {str(response)[:200]}...")
                passed_tests += 1
            else:
                logger.error(f"❌ FAIL: Knowledge graph appears empty or inaccessible")

        except Exception as e:
            logger.error(f"❌ FAIL: Knowledge graph state check failed - {e}")

        # Final results
        logger.info("\n" + "="*70)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("="*70)
        logger.info(f"Passed: {passed_tests}/{total_tests} tests")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if passed_tests == total_tests:
            logger.info("🎉 ALL TESTS PASSED! GraphRAG tools are working correctly.")
            return True
        else:
            logger.warning(f"⚠️  {total_tests - passed_tests} tests failed. Please review the issues above.")
            return False

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR during testing: {e}")
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = asyncio.run(test_graphrag_tools())
    sys.exit(0 if success else 1)
