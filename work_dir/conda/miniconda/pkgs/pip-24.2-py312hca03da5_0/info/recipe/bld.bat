set PYTHONPATH=%SRC_DIR%\src
%PYTHON% -m pip install --no-deps --no-build-isolation . -vv
if errorlevel 1 exit 1

cd %SCRIPTS%
del *.exe
del *.exe.manifest
del pip2*
del pip3*
:: del %SP_DIR%\__pycache__\pkg_res*
