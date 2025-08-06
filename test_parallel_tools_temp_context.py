#!/usr/bin/env python3
"""
Test script for parallel tool execution with temporary contexts.

This script demonstrates the new parallel tool execution system where:
1. Tools run in isolated temporary contexts
2. Results are stored persistently
3. Contexts are automatically cleaned up
4. Only results survive context cleanup

Usage: python test_parallel_tools_temp_context.py
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent import Agent, AgentConfig, AgentContext, UserMessage
import models


async def test_parallel_tools_temp_context():
    """Test parallel tool execution with temporary context isolation."""

    print("🚀 Testing Parallel Tool Execution with Temporary Contexts")
    print("=" * 60)

    # Create test configuration
    config = AgentConfig(
        chat_model=models.get_model("gpt-4"),
        utility_model=models.get_model("gpt-3.5-turbo"),
        embeddings_model=models.get_model("text-embedding-ada-002"),
        browser_model=models.get_model("gpt-4")
    )

    # Create main context and agent
    main_context = AgentContext(config=config)
    agent = Agent(0, config, main_context)

    print(f"📊 Main Agent Context ID: {main_context.id}")
    print(f"📊 Agent Number: {agent.number}")
    print()

    # Test 1: Simulate parallel tool execution
    print("🔧 Test 1: Simulating parallel tool calls")
    print("-" * 40)

    # Simulate multiple tool calls (they would return task IDs in real usage)
    task_responses = []

    # Mock tool call 1
    response1 = await agent.process_tools('{"tool_name": "response", "tool_args": {"message": "Test result 1"}}')
    task_responses.append(response1)
    print(f"Tool 1: {response1}")

    # Mock tool call 2
    response2 = await agent.process_tools('{"tool_name": "response", "tool_args": {"message": "Test result 2"}}')
    task_responses.append(response2)
    print(f"Tool 2: {response2}")

    print()

    # Test 2: Check active and completed tasks
    print("📊 Test 2: Checking task storage")
    print("-" * 40)

    active_tasks = agent.get_data("active_tool_tasks") or {}
    completed_tasks = agent.get_data("completed_tool_tasks") or {}

    print(f"Active tasks: {len(active_tasks)}")
    print(f"Completed tasks: {len(completed_tasks)}")

    for task_id, task_info in active_tasks.items():
        print(f"  Active: {task_id[:8]}... - {task_info['tool_name']}")

    for task_id, result_info in completed_tasks.items():
        print(f"  Completed: {task_id[:8]}... - {result_info['tool_name']} - Success: {result_info['success']}")

    print()

    # Test 3: Check context isolation
    print("🔒 Test 3: Verifying context isolation")
    print("-" * 40)

    all_contexts = AgentContext.all()
    print(f"Total contexts after tool execution: {len(all_contexts)}")

    for ctx in all_contexts:
        print(f"  Context {ctx.id[:8]}... - Type: {ctx.type.value} - No: {ctx.no}")

    # Should only have the main context, temp contexts should be cleaned up
    if len(all_contexts) == 1:
        print("✅ Context isolation working - temporary contexts cleaned up")
    else:
        print("❌ Context isolation issue - temporary contexts may not be cleaned")

    print()

    # Test 4: Test subordinate agent isolation
    print("👥 Test 4: Testing subordinate agent isolation")
    print("-" * 40)

    subordinate_response = await agent.process_tools('{"tool_name": "call_subordinate", "tool_args": {"message": "Hello from subordinate"}}')
    print(f"Subordinate response: {subordinate_response}")

    # Check context count again
    all_contexts_after_subordinate = AgentContext.all()
    print(f"Contexts after subordinate call: {len(all_contexts_after_subordinate)}")

    if len(all_contexts_after_subordinate) == 1:
        print("✅ Subordinate isolation working - temporary contexts cleaned up")
    else:
        print("❌ Subordinate isolation issue - temporary contexts may not be cleaned")

    print()

    # Test 5: Simulate wait_for_tasks call
    print("⏳ Test 5: Simulating wait_for_tasks call")
    print("-" * 40)

    # Extract task IDs from responses (in real usage, these would be parsed from task responses)
    active_tasks = agent.get_data("active_tool_tasks") or {}
    if active_tasks:
        task_ids = list(active_tasks.keys())
        task_ids_str = ",".join(task_ids[:2])  # Test with first 2 tasks

        wait_response = await agent.process_tools(f'{{"tool_name": "wait_for_tasks", "tool_args": {{"tool_call_ids": "{task_ids_str}"}}}}')
        print(f"Wait for tasks response: {wait_response}")
    else:
        print("No active tasks to wait for")

    print()
    print("🎉 Test completed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(test_parallel_tools_temp_context())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
