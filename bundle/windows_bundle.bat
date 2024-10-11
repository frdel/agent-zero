@echo off
setlocal enabledelayedexpansion

:: Check if conda is recognized
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo Conda not found in PATH. Checking known location...

    set "CONDA_PATH=C:\Users\%USERNAME%\miniconda3"
    if exist "!CONDA_PATH!\Scripts\conda.exe" (
        echo Found Conda at !CONDA_PATH!
        set "PATH=!CONDA_PATH!;!CONDA_PATH!\Scripts;!CONDA_PATH!\Library\bin;%PATH%"
        echo Added Conda to PATH
    ) else (
        echo Conda installation not found at !CONDA_PATH!
        echo Please install Conda or add it to PATH manually.
        pause
        exit /b 1
    )
)

:: Verify conda is now accessible
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo Failed to add Conda to PATH. Please add it manually.
    pause
    exit /b 1
)

:: Initialize conda shell (if not done before)
call conda init bash >nul 2>nul
if %errorlevel% neq 0 (
    echo Error running 'conda init'. Please check your conda installation.
    pause
    exit /b 1
)

:: 1. Remove conda environment if it exists
conda env remove -n az-bundle -y 2>nul
if %errorlevel% neq 0 (
    echo Error removing conda environment
    pause
)

:: 2. Create new environment with Python 3.12 and activate it
conda create -n az-bundle python=3.12 -y
if %errorlevel% neq 0 (
    echo Error creating conda environment
    pause
) else (
    call conda.bat activate az-bundle
    if %errorlevel% neq 0 (
        echo Error activating conda environment
        pause
    )
)

:: 3. Purge folder ./agent-zero (retry mechanism in case of failure)
if exist agent-zero (
    echo Deleting agent-zero folder...
    rmdir /s /q agent-zero
    if exist agent-zero (
        echo Error: Unable to delete agent-zero folder, retrying...
        timeout /t 3 /nobreak >nul
        rmdir /s /q agent-zero
    )
    if exist agent-zero (
        echo Error: Failed to purge agent-zero folder after retry.
        pause
    )
)

:: 4. Clone the repository (development branch)
git clone --branch development https://github.com/frdel/agent-zero agent-zero
if %ERRORLEVEL% neq 0 (
    echo Error cloning the repository
    pause
)

:: 5. Change directory to agent-zero
cd agent-zero
if %errorlevel% neq 0 (
    echo Error changing directory
    pause
)

:: 6. Install requirements
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing requirements
    pause
)

:: 7. Install specific version of pefile
pip install pefile==2023.2.7
if %errorlevel% neq 0 (
    echo Error installing pefile
    pause
)

:: 8. Run bundle.py
python bundle.py
if %errorlevel% neq 0 (
    echo Error running bundle.py
    pause
)

echo Script completed
pause
