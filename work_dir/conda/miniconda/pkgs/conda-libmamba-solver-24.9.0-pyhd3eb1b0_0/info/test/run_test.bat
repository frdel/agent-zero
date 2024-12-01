



CONDA_SOLVER=libmamba conda create -n test --dry-run scipy
IF %ERRORLEVEL% NEQ 0 exit /B 1
conda create --solver libmamba -n test --dry-run scipy
IF %ERRORLEVEL% NEQ 0 exit /B 1
exit /B 0
