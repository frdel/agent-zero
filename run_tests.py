#!/usr/bin/env python3
"""
Agent Zero Memory Consolidation Test Runner

Test runner with proper exit codes for CI/CD integration.
Exit codes:
- 0: All tests passed
- 1: One or more tests failed
- 2: Test environment setup failed
- 3: Unexpected error/crash
"""

import asyncio
import sys
import time
from pathlib import Path

# Add the project root to the path for imports
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))


def print_banner():
    """Print test runner banner."""
    print("🧪 Agent Zero Test Runner")
    print("=" * 60)
    print("Testing Agent Zero...")
    print(f"Project root: {project_root}")
    print(f"Python version: {sys.version}")
    print("=" * 60)


async def run_memory_consolidation_tests():
    """Run all memory consolidation tests with proper error handling."""

    try:
        # Import the test module
        from tests.memory_consolidation.test_memory_consolidation import MemoryConsolidationTester

        print("🔧 Initializing test environment...")

        # Create test instance
        tester = MemoryConsolidationTester()

        # Setup test environment
        setup_success = await tester.setup_test_environment()
        if not setup_success:
            print("❌ Failed to setup test environment")
            print("\n💡 Common issues:")
            print("- Check if OpenAI API key is configured")
            print("- Verify all dependencies are installed")
            print("- Ensure memory directories are writable")
            return 2  # Setup failure

        print("✅ Test environment ready")
        print("\n🚀 Running comprehensive test suite...")

        # Record start time for performance tracking
        start_time = time.time()

        # Run all tests
        all_passed = await tester.run_all_tests()

        # Calculate total time
        total_time = time.time() - start_time

        # Print final results
        print(f"\n⏱️ Total execution time: {total_time:.2f} seconds")

        if all_passed:
            print("\n🎉 SUCCESS: All tests passed!")
            print("✅ Memory consolidation system is ready for production")
            return 0  # Success
        else:
            print("\n❌ FAILURE: One or more tests failed")
            print("⚠️ Please review the test output and fix issues before deployment")
            return 1  # Test failures

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n💡 Make sure you're running this from the Agent Zero root directory")
        print("💡 Check that all required dependencies are installed")
        return 2  # Setup failure

    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user (Ctrl+C)")
        return 3  # Unexpected termination

    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print(f"💥 Error type: {type(e).__name__}")

        # Print traceback for debugging
        import traceback
        print("\n🔍 Traceback:")
        traceback.print_exc()

        return 3  # Unexpected error


def main():
    """Main entry point with comprehensive error handling."""

    # Print banner
    print_banner()

    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"❌ Current version: {sys.version}")
        sys.exit(2)

    # Check if we're in the right directory
    if not (project_root / "python" / "helpers" / "memory_consolidation.py").exists():
        print("❌ memory_consolidation.py not found")
        print("💡 Make sure you're running this from the Agent Zero root directory")
        sys.exit(2)

    # Run memory consolidation tests
    try:
        exit_code = asyncio.run(run_memory_consolidation_tests())

        # Print final exit code info
        if exit_code == 0:
            print("\n🚀 Exit code: 0 (Success)")
        elif exit_code == 1:
            print("\n💔 Exit code: 1 (Test failures)")
        elif exit_code == 2:
            print("\n⚙️ Exit code: 2 (Setup failure)")
        elif exit_code == 3:
            print("\n💥 Exit code: 3 (Unexpected error)")

        sys.exit(exit_code)

    except Exception as e:
        print(f"\n💥 Critical error in test runner: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
