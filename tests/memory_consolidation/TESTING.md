# Memory Consolidation Testing Guide

## Overview

This guide explains how to run and interpret the memory consolidation test suite for Agent Zero.

## Test Runner

### Basic Usage

```bash
# Run all tests
python run_tests.py
```

### Exit Codes

The test runner uses standard exit codes for CI/CD integration:

- **0**: All tests passed successfully ✅
- **1**: One or more tests failed ❌
- **2**: Test environment setup failed ⚙️
- **3**: Unexpected error/crash 💥

### Example Usage in CI/CD

```bash
# Basic CI script
python run_tests.py
if [ $? -eq 0 ]; then
    echo "Tests passed, proceeding with deployment"
else
    echo "Tests failed, blocking deployment"
    exit 1
fi
```

```yaml
# GitHub Actions example
- name: Run Memory Tests
  run: python run_tests.py

- name: Deploy if tests pass
  if: success()
  run: ./deploy.sh
```

## Test Suite Structure

### Test Categories

The test suite includes 29 comprehensive test categories:

1. **Core Functionality** (21 tests)
   - Basic configuration and setup
   - Memory discovery and keyword extraction
   - LLM-powered consolidation analysis
   - All five consolidation actions
   - Integration with existing systems

2. **Critical Bug Prevention** (8 tests)
   - Duplicate memory bug prevention
   - Transaction safety
   - Cross-area isolation
   - Memory corruption prevention
   - Performance with many similarities
   - Circular consolidation prevention
   - Metadata preservation integrity
   - LLM failure graceful degradation

### Test Output Interpretation

#### Success Indicators ✅
```
✅ Basic consolidation configuration tests passed
✅ Memory discovery tests passed
...
🎉 ALL TESTS PASSED! Memory consolidation system is ready for use.
✅ Exit code will be 0 (success)
```

#### Failure Indicators ❌
```
❌ Duplicate memory bug prevention: Should consolidate to 1-2 memories, found 5
❌ Cross-area isolation: Area fragments should still have its memories
...
⚠️ 2 test(s) failed. Please review the implementation.
❌ Exit code will be 1 (test failures)
```

#### Setup Issues ⚙️
```
❌ Failed to setup test environment
💡 Common issues:
- Check if OpenAI API key is configured
- Verify all dependencies are installed
- Ensure memory directories are writable
```

## Running Specific Tests

### Individual Test Categories

```python
# Run specific test method
python -c "
import asyncio
from tests.memory_consolidation.test_memory_consolidation import MemoryConsolidationTester

async def main():
    tester = MemoryConsolidationTester()
    await tester.setup_test_environment()
    await tester.test_duplicate_memory_bug()

asyncio.run(main())
"
```

### Test Environment Requirements

1. **API Keys**: OpenAI API key configured in environment
2. **Dependencies**: All Python packages installed
3. **Permissions**: Write access to `memory/` directory
4. **Resources**: Sufficient disk space and memory

## Troubleshooting

### Common Issues

#### Exit Code 1 (Test Failures)
- **Symptom**: Tests run but some fail
- **Solution**: Review specific test failure messages
- **Common Causes**:
  - LLM API rate limits
  - Memory threshold configuration issues
  - Database state inconsistencies

#### Exit Code 2 (Setup Failure)
- **Symptom**: Tests fail to start
- **Solution**: Check environment configuration
- **Common Causes**:
  - Missing OpenAI API key
  - Import errors (missing dependencies)
  - File permission issues

#### Exit Code 3 (Unexpected Error)
- **Symptom**: Test runner crashes
- **Solution**: Check full traceback output
- **Common Causes**:
  - Python version incompatibility
  - Memory/disk space issues
  - Network connectivity problems

### Debug Mode

For detailed debugging, you can run tests with Python's verbose mode:

```bash
python -v run_tests.py
```

Or modify the test runner to add more debugging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Expectations

### Typical Runtime
- **Fast run**: 2-3 minutes (with all APIs responding quickly)
- **Normal run**: 5-10 minutes (typical API response times)
- **Slow run**: 10-15 minutes (with API throttling or timeouts)

### Performance Monitoring
The test runner tracks total execution time and reports it at the end:

```
⏱️ Total execution time: 247.52 seconds
```

### Timeout Protection
Individual tests have timeout protection (30-45 seconds) to prevent hanging.

## Integration with Development Workflow

### Pre-commit Testing
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
echo "Running memory consolidation tests..."
python run_tests.py
exit $?
```

### Continuous Integration
The exit codes make it easy to integrate with any CI/CD system:

- **Jenkins**: Use exit code for build status
- **GitHub Actions**: Automatic failure on non-zero exit
- **GitLab CI**: Pipeline fails on test failure
- **Travis CI**: Build marked as failed

### Development Loop
1. Make changes to memory consolidation system
2. Run `python run_tests.py`
3. If exit code 0: proceed with commit
4. If exit code 1: fix failing tests
5. If exit code 2/3: fix environment/setup issues

This testing framework ensures high confidence in the memory consolidation system before deployment.
