

set -ex



pip check
pytest -v -s -rs --no-flaky-report --max-runs=3 tests/
exit 0
