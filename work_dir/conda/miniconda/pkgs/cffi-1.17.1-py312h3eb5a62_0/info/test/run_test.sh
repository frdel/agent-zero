

set -ex



pip check
python -X faulthandler -c "from cffi import FFI; print(FFI().dlopen(None))"
exit 0
