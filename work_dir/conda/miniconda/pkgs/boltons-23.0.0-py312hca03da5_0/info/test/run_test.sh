

set -ex



pytest -vv --doctest-modules boltons tests
pip check
exit 0
