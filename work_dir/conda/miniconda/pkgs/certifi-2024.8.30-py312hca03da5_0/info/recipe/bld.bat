REM use bootstrapped pip to install certifi without depending on installed pip
set PYTHONPATH=%cd%\pip_wheel;%cd%\setuptools_wheel
%PYTHON% -m pip install .\certifi --ignore-installed --no-deps --no-build-isolation -vv
