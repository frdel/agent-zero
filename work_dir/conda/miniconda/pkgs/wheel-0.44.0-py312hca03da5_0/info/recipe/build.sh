#!/bin/bash

set -ex

$PYTHON -c "import flit_core.buildapi; flit_core.buildapi.build_wheel('.')"
$PYTHON -m installer --no-compile-bytecode wheel-*.whl