@echo off
REM Clear the screen for a fresh start
cls

REM Display welcome message
echo =============================================
echo        Agent Zero Setup and Execution
echo =============================================

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Downloading Python...
    curl -o python-installer.exe https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1
    if %errorlevel% neq 0 (
        echo Python installation failed. Exiting.
        exit /b 1
    )
)

:: Docker Installation
:check_docker_installed
where docker >nul 2>&1
if %errorlevel%==0 (
    echo Docker is already installed.
    goto end
) else (
    where choco >nul 2>&1
    if %errorlevel%==0 (
        echo Installing Docker using Chocolatey...
        choco install docker-desktop -y
    ) else (
        echo Installing Chocolatey...
        @"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "[System.Net.ServicePointManager]::SecurityProtocol = 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))" && SET "PATH=%PATH%;%ALLUSERSPROFILE%\chocolatey\bin"
        echo Installing Docker using Chocolatey...
        choco install docker-desktop -y
    )
    echo Docker installed
)

:end
echo Done!

REM Set up Python virtual environment
echo Creating Python virtual environment...
python -m venv .venv
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to create virtual environment. Exiting...
    exit /b
)

REM Activate Python virtual environment
echo Activating Python virtual environment...
call .venv\Scripts\activate
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to activate virtual environment. Exiting...
    exit /b
)

REM Install required Python packages
echo Installing required Python packages...
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install Python packages. Please check your setup.
    exit /b
)

REM Navigate to bundle directory
echo Setting up bundle environment...
cd bundle
REM Check for platform and run respective bundle script
IF "%OS%"=="Windows_NT" (
    echo Running Windows bundle script...
    call windows_bundle.bat
) ELSE (
    echo Running MacOS bundle script...
    sh macos_bundle.sh
)

REM Return to main directory
cd..

REM Display success message for setup
echo Setup complete.
REM Provide user options to run either CLI or UI mode
echo.
echo =============================================
echo        Choose an option to run Agent Zero:
echo        1. Run CLI
echo        2. Run UI
echo =============================================
set /p option="Enter 1 or 2: "
IF "%option%"=="1" (
    echo Running Agent Zero in CLI mode...
    echo Configure API Keys by: Duplicating example.env, renaming it to .env, and adding your API keys. Then run again by executing setup.bat or by using the command: python run_cli.py.
    python run_cli.py
    exit /b
) ELSE IF "%option%"=="2" (
    echo Running Agent Zero in UI mode...
    python run_ui.py
    exit /b
) ELSE (
    echo Invalid option selected. Exiting...
    exit /b
)
