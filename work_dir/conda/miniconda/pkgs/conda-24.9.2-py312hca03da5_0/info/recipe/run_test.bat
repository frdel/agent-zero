:: clear conda stuff from parent process
SET CONDA_SHLVL=
SET _CE_CONDA=
SET _CE_M=
SET _CONDA_EXE=

:: load shell interface
:: CALL is necessary because conda is a bat script,
:: running bat files within other bat files requires CALL or else
:: the outer script (our test script) exits when the inner completes
CALL %PREFIX%\condabin\conda_hook.bat

:: display conda details
CALL conda info --all

:: create, activate, and deactivate a conda environment
CALL conda create --yes --prefix ".\built-conda-test-env" "m2-patch"
IF NOT %ERRORLEVEL% == 0 EXIT /B 1

CALL conda activate ".\built-conda-test-env"
ECHO "CONDA_PREFIX=%CONDA_PREFIX%"

IF NOT "%CONDA_PREFIX%" == "%CD%\built-conda-test-env" EXIT /B 1
%CONDA_PREFIX%\Library\usr\bin\patch.exe --version
IF NOT %ERRORLEVEL% == 0 EXIT /B 1

CALL conda deactivate
