@echo on

%PYTHON% -c "import flit_core.buildapi; flit_core.buildapi.build_wheel('.')"
if errorlevel 1 exit 1
FOR %%w in (*.whl) DO %PYTHON% -m installer --no-compile-bytecode %%w
if errorlevel 1 exit 1