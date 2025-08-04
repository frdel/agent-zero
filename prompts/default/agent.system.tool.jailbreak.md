## jailbreak_tool

**Purpose**: iOS device jailbreak and iCloud bypass operations for security research and device recovery.

**Usage**:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "status|detect|jailbreak|bypass|install_tools",
    "device_udid": "optional_device_identifier",
    "tool": "lockra1n|checkra1n|unc0ver"
  }
}
```

**Parameters**:
- `action` (required): Operation to perform
  - `status`: Check connected device status and jailbreak compatibility
  - `detect`: List all connected iOS devices
  - `jailbreak`: Perform jailbreak operation on device
  - `bypass`: Attempt iCloud activation lock bypass
  - `install_tools`: Install required jailbreak tools and dependencies
- `device_udid` (optional): Target specific device by UDID. If not provided, will use single connected device
- `tool` (optional): Jailbreak tool to use (default: lockra1n)

**Examples**:

Check device status:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "status"
  }
}
```

Detect connected devices:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "detect"
  }
}
```

Jailbreak device with lockra1n:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "jailbreak",
    "tool": "lockra1n"
  }
}
```

Bypass iCloud activation lock:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "bypass",
    "device_udid": "00008030-001234567890123A",
    "tool": "lockra1n"
  }
}
```

Install jailbreak tools:
```json
{
  "tool_name": "jailbreak_tool",
  "parameters": {
    "action": "install_tools"
  }
}
```

**Important Notes**:
- Only use on devices you own or have explicit permission to modify
- Always backup devices before jailbreaking
- Jailbreaking may void warranty and can brick devices if done incorrectly
- iCloud bypass should only be used for legitimate device recovery
- Some operations require the device to be in specific modes (DFU, recovery)
- Tool availability depends on your operating system (macOS/Linux recommended)

**Prerequisites**:
- libimobiledevice tools installed
- Device connected via USB
- Device trusted on this computer
- Compatible iOS version for chosen jailbreak tool

**Security Warning**: This tool is for educational and legitimate security research purposes only. Ensure you comply with all applicable laws and regulations.
