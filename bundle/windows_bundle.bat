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
if exist agent-zero-git (
    echo Deleting agent-zero-git folder...
    rmdir /s /q agent-zero-git
    if exist agent-zero-git (
        echo Error: Unable to delete agent-zero-git folder, retrying...
        timeout /t 3 /nobreak >nul
        rmdir /s /q agent-zero-git
    )
    if exist agent-zero-git (
        echo Error: Failed to purge agent-zero-git folder after retry.
        pause
    )
)

:: 4. Clone the repository (testing branch)
echo Cloning the repository (testing branch)...
git clone --branch testing https://github.com/frdel/agent-zero agent-zero-git
if %ERRORLEVEL% neq 0 (
    echo Error cloning the repository
    pause
)

@REM :: 5. Change directory to agent-zero
@REM cd agent-zero
@REM if %errorlevel% neq 0 (
@REM     echo Error changing directory
@REM     pause
@REM )

:: 6. Install requirements
pip install -r ./agent-zero-git/requirements.txt
if %errorlevel% neq 0 (
    echo Error installing project requirements
    pause
)

pip install -r ./agent-zero-git/bundle/requirements.txt
if %errorlevel% neq 0 (
    echo Error installing bundle requirements
    pause
)

:: 7. Install specific version of pefile
pip install pefile==2023.2.7
if %errorlevel% neq 0 (
    echo Error installing pefile
    pause
)

:: 8. Run bundle.py
python ./agent-zero-git/bundle/bundle.py
if %errorlevel% neq 0 (
    echo Error running bundle.py
    pause
)

:: 9. Create Windows self-extracting archive with 7-Zip
echo Creating Windows self-extracting archive...
"C:\Program Files\7-Zip\7z.exe" a -sfx"C:\Program Files\7-Zip\7z.sfx" agent-zero-preinstalled-win-x86.exe ".\agent-zero-git\bundle\dist\agent-zero" -mx=7
if %errorlevel% neq 0 (
    echo Error creating Windows self-extracting archive.
    pause
)

echo Script completed
pause
