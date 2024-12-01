

set -ex



pip check
SP_DIR="$(python -c 'import site; print(site.getsitepackages()[0])')"
test -f "${SP_DIR}/menuinst/data/appkit_launcher_arm64"
test -f "${SP_DIR}/menuinst/data/appkit_launcher_x86_64"
test -f "${SP_DIR}/menuinst/data/osx_launcher_arm64"
test -f "${SP_DIR}/menuinst/data/osx_launcher_x86_64"
pytest tests/ -vvv --ignore=tests/test_schema.py --ignore=tests/test_elevation.py
exit 0
