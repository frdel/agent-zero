@echo off
setlocal enabledelayedexpansion

:: Clone the repository
set REPO_URL=https://github.com/frdel/agent-zero.git
set REPO_DIR=agent-zero

if not exist %REPO_DIR% (
    echo Cloning the repository...
    git clone %REPO_URL%
    if %errorlevel% neq 0 (
        echo Failed to clone the repository.
        exit /b 1
    )
    echo Repository cloned successfully.
) else (
    echo Repository already exists. Pulling latest changes...
    cd %REPO_DIR%
    git pull
    if %errorlevel% neq 0 (
        echo Failed to pull the latest changes.
        exit /b 1
    )
    echo Repository updated successfully.
    cd ..
)

cd %REPO_DIR%

:: Set up environment variables
echo Setting up environment variables...
if not exist .env (
    echo .env file not found, copying from example.env...
    copy example.env .env
)
echo Environment variables set up.

:: Install Python dependencies
echo Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Please install Python and try again.
    exit /b 1
)

echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install Python dependencies.
    exit /b 1
)
echo Python dependencies installed.

:: Install Docker (optional)
echo Checking for Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not installed. You can download and install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo Skipping Docker setup.
) else (
    echo Docker is installed. Setting up Docker container...
    docker pull frdel/agent-zero-exe
    if %errorlevel% neq 0 (
        echo Failed to pull Docker image.
        exit /b 1
    )
    echo Docker container setup complete.
)

:: Run the main program
echo Running the Agent Zero framework...
python main.py

:: Keep the command prompt open after execution
echo Agent Zero setup and execution complete.
pause
