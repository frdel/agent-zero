# use bootstrapped pip to install certifi without depending on installed pip
export PYTHONPATH=$PWD/pip_wheel:$PWD/setuptools_wheel
$PYTHON -m pip install ./certifi/ --ignore-installed --no-deps --no-build-isolation -vv
