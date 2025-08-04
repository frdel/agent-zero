import asyncio
import json
import os
import platform
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from python.helpers.print_style import PrintStyle
from python.helpers import files


class JailbreakUtils:
    """Utility functions for iOS jailbreak operations"""

    def __init__(self):
        self.system = platform.system().lower()
        self.tools_dir = files.get_abs_path("tmp/jailbreak_tools")
        os.makedirs(self.tools_dir, exist_ok=True)

    async def check_required_tools(self):
        """Check if required tools are installed"""
        tools_status = {}

        # Check for libimobiledevice tools
        tools_to_check = [
            "ideviceinfo",
            "idevice_id",
            "ideviceactivation",
            "idevicerestore"
        ]

        for tool in tools_to_check:
            try:
                result = subprocess.run([tool, "--help"],
                                      capture_output=True,
                                      text=True,
                                      timeout=5)
                tools_status[tool] = "✅ Available"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                tools_status[tool] = "❌ Not found"

        # Check for platform-specific tools
        if self.system == "darwin":  # macOS
            try:
                result = subprocess.run(["brew", "--version"],
                                      capture_output=True,
                                      text=True,
                                      timeout=5)
                tools_status["homebrew"] = "✅ Available"
            except:
                tools_status["homebrew"] = "❌ Not found"

        status_text = "Tool Status:\n"
        for tool, status in tools_status.items():
            status_text += f"  {tool}: {status}\n"

        return status_text

    async def detect_ios_devices(self):
        """Detect connected iOS devices"""
        devices = []

        try:
            # Use idevice_id to get connected devices
            result = subprocess.run(["idevice_id", "-l"],
                                  capture_output=True,
                                  text=True,
                                  timeout=10)

            if result.returncode == 0 and result.stdout.strip():
                udids = result.stdout.strip().split('\n')

                for udid in udids:
                    if udid.strip():
                        device_info = await self._get_device_info(udid.strip())
                        if device_info:
                            devices.append(device_info)

        except Exception as e:
            PrintStyle().error(f"Error detecting devices: {str(e)}")

        return devices

    async def _get_device_info(self, udid):
        """Get detailed information about a specific device"""
        try:
            # Get device info using ideviceinfo
            result = subprocess.run(["ideviceinfo", "-u", udid],
                                  capture_output=True,
                                  text=True,
                                  timeout=15)

            if result.returncode != 0:
                return None

            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()

            # Extract relevant information
            device = {
                'udid': udid,
                'name': info.get('DeviceName', 'Unknown Device'),
                'model': info.get('ProductType', 'Unknown Model'),
                'version': info.get('ProductVersion', 'Unknown Version'),
                'build': info.get('BuildVersion', 'Unknown Build'),
                'status': self._determine_device_status(info),
                'jailbreak_status': await self._check_jailbreak_status(udid),
                'bypass_compatible': self._check_bypass_compatibility(info)
            }

            return device

        except Exception as e:
            PrintStyle().error(f"Error getting device info for {udid}: {str(e)}")
            return None

    def _determine_device_status(self, info):
        """Determine the current status of the device"""
        activation_state = info.get('ActivationState', '').lower()

        if activation_state == 'activated':
            return 'activated'
        elif activation_state == 'unactivated':
            return 'activation_locked'
        else:
            return 'unknown'

    async def _check_jailbreak_status(self, udid):
        """Check if device is jailbroken"""
        try:
            # Try to access Cydia or other jailbreak indicators
            # This is a simplified check - real implementation would be more thorough
            result = subprocess.run([
                "ideviceinstaller", "-u", udid, "-l"
            ], capture_output=True, text=True, timeout=10)

            if "cydia" in result.stdout.lower() or "sileo" in result.stdout.lower():
                return "jailbroken"
            else:
                return "not_jailbroken"

        except:
            return "unknown"

    def _check_bypass_compatibility(self, info):
        """Check if device is compatible with bypass tools"""
        model = info.get('ProductType', '').lower()
        version = info.get('ProductVersion', '')

        # Simplified compatibility check
        # Real implementation would have comprehensive compatibility matrix
        compatible_models = [
            'iphone6', 'iphone7', 'iphone8', 'iphonex',
            'ipad6', 'ipad7', 'ipadair2', 'ipadpro'
        ]

        for compatible_model in compatible_models:
            if compatible_model in model:
                return True

        return False

    async def check_jailbreak_compatibility(self, device, tool):
        """Check if device is compatible with specific jailbreak tool"""
        model = device['model'].lower()
        version = device['version']

        compatibility = {
            'compatible': False,
            'reason': 'Unknown compatibility issue'
        }

        if tool == "lockra1n":
            # Lockra1n compatibility (simplified)
            if any(x in model for x in ['iphone6', 'iphone7', 'iphone8', 'iphonex']):
                if version.startswith(('12.', '13.', '14.', '15.')):
                    compatibility['compatible'] = True
                else:
                    compatibility['reason'] = f"iOS {version} not supported by lockra1n"
            else:
                compatibility['reason'] = f"Device model {device['model']} not supported"

        elif tool == "checkra1n":
            # Checkra1n compatibility
            if any(x in model for x in ['iphone5', 'iphone6', 'iphone7', 'iphone8', 'iphonex']):
                compatibility['compatible'] = True
            else:
                compatibility['reason'] = "Device not compatible with checkra1n (A12+ devices not supported)"

        return compatibility

    async def execute_jailbreak(self, device, tool):
        """Execute jailbreak process"""
        PrintStyle().info(f"Executing {tool} jailbreak on {device['name']}...")

        if tool == "lockra1n":
            return await self._execute_lockra1n(device)
        elif tool == "checkra1n":
            return await self._execute_checkra1n(device)
        else:
            return f"Jailbreak tool {tool} not implemented yet"

    async def _execute_lockra1n(self, device):
        """Execute lockra1n jailbreak"""
        try:
            # Download lockra1n if not present
            lockra1n_path = await self._download_lockra1n()

            if not lockra1n_path:
                return "Failed to download lockra1n tool"

            # Execute lockra1n
            PrintStyle().info("Starting lockra1n jailbreak process...")

            # This would be the actual lockra1n execution
            # For safety, this is a simulation
            result = f"""
Lockra1n Jailbreak Process Started
Device: {device['name']} ({device['model']})
iOS Version: {device['version']}

⚠️  SIMULATION MODE - No actual jailbreak performed ⚠️

Steps that would be executed:
1. Put device in DFU mode
2. Exploit bootrom vulnerability
3. Install jailbreak payload
4. Reboot device
5. Install Cydia/Sileo

Status: Would complete successfully (simulated)
"""

            return result

        except Exception as e:
            return f"Lockra1n execution failed: {str(e)}"

    async def _execute_checkra1n(self, device):
        """Execute checkra1n jailbreak"""
        return "Checkra1n execution not implemented yet"

    async def _download_lockra1n(self):
        """Download lockra1n tool"""
        try:
            lockra1n_path = os.path.join(self.tools_dir, "lockra1n")

            if os.path.exists(lockra1n_path):
                return lockra1n_path

            PrintStyle().info("Downloading lockra1n...")

            # This would download the actual tool
            # For safety, we'll just create a placeholder
            with open(lockra1n_path, 'w') as f:
                f.write("# Lockra1n placeholder - actual tool would be downloaded here\n")

            os.chmod(lockra1n_path, 0o755)
            return lockra1n_path

        except Exception as e:
            PrintStyle().error(f"Failed to download lockra1n: {str(e)}")
            return None

    async def execute_icloud_bypass(self, device, tool):
        """Execute iCloud bypass"""
        PrintStyle().info(f"Executing iCloud bypass with {tool}...")

        result = f"""
iCloud Bypass Process (SIMULATION)
Device: {device['name']} ({device['model']})
Tool: {tool}

⚠️  EDUCATIONAL SIMULATION ONLY ⚠️

This would attempt to:
1. Check device activation status
2. Exploit activation vulnerabilities
3. Bypass iCloud activation lock
4. Enable device functionality

Note: Real bypass success depends on:
- iOS version vulnerabilities
- Device model compatibility
- Current patch level

Status: Simulation complete
"""

        return result

    async def install_jailbreak_tools(self):
        """Install required jailbreak tools"""
        PrintStyle().info("Installing jailbreak tools...")

        installation_steps = []

        if self.system == "darwin":  # macOS
            installation_steps.extend([
                "Installing libimobiledevice via Homebrew...",
                "brew install libimobiledevice",
                "brew install ideviceinstaller",
                "Installing additional tools..."
            ])
        elif self.system == "linux":
            installation_steps.extend([
                "Installing libimobiledevice via apt...",
                "sudo apt update",
                "sudo apt install libimobiledevice-utils",
                "sudo apt install ideviceinstaller"
            ])
        else:
            return "Windows support not implemented yet. Please use macOS or Linux."

        result = "Jailbreak Tools Installation:\n\n"
        result += "\n".join(f"• {step}" for step in installation_steps)
        result += "\n\nNote: This is a simulation. Run these commands manually to install actual tools."

        return result
    """Utility functions for iOS jailbreak operations"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.tools_dir = files.get_abs_path("tmp/jailbreak_tools")
        os.makedirs(self.tools_dir, exist_ok=True)
    
    async def check_required_tools(self):
        """Check if required tools are installed"""
        tools_status = {}
        
        # Check for libimobiledevice tools
        tools_to_check = [
            "ideviceinfo",
            "idevice_id", 
            "ideviceactivation",
            "idevicerestore"
        ]
        
        for tool in tools_to_check:
            try:
                result = subprocess.run([tool, "--help"], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                tools_status[tool] = "✅ Available"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                tools_status[tool] = "❌ Not found"
        
        # Check for platform-specific tools
        if self.system == "darwin":  # macOS
            try:
                result = subprocess.run(["brew", "--version"], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                tools_status["homebrew"] = "✅ Available"
            except:
                tools_status["homebrew"] = "❌ Not found"
        
        status_text = "Tool Status:\n"
        for tool, status in tools_status.items():
            status_text += f"  {tool}: {status}\n"
        
        return status_text
    
    async def detect_ios_devices(self):
        """Detect connected iOS devices"""
        devices = []
        
        try:
            # Use idevice_id to get connected devices
            result = subprocess.run(["idevice_id", "-l"], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                udids = result.stdout.strip().split('\n')
                
                for udid in udids:
                    if udid.strip():
                        device_info = await self._get_device_info(udid.strip())
                        if device_info:
                            devices.append(device_info)
            
        except Exception as e:
            PrintStyle().error(f"Error detecting devices: {str(e)}")
        
        return devices
    
    async def _get_device_info(self, udid):
        """Get detailed information about a specific device"""
        try:
            # Get device info using ideviceinfo
            result = subprocess.run(["ideviceinfo", "-u", udid], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=15)
            
            if result.returncode != 0:
                return None
            
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            # Extract relevant information
            device = {
                'udid': udid,
                'name': info.get('DeviceName', 'Unknown Device'),
                'model': info.get('ProductType', 'Unknown Model'),
                'version': info.get('ProductVersion', 'Unknown Version'),
                'build': info.get('BuildVersion', 'Unknown Build'),
                'status': self._determine_device_status(info),
                'jailbreak_status': await self._check_jailbreak_status(udid),
                'bypass_compatible': self._check_bypass_compatibility(info)
            }
            
            return device
            
        except Exception as e:
            PrintStyle().error(f"Error getting device info for {udid}: {str(e)}")
            return None
    
    def _determine_device_status(self, info):
        """Determine the current status of the device"""
        activation_state = info.get('ActivationState', '').lower()
        
        if activation_state == 'activated':
            return 'activated'
        elif activation_state == 'unactivated':
            return 'activation_locked'
        else:
            return 'unknown'
    
    async def _check_jailbreak_status(self, udid):
        """Check if device is jailbroken"""
        try:
            # Try to access Cydia or other jailbreak indicators
            # This is a simplified check - real implementation would be more thorough
            result = subprocess.run([
                "ideviceinstaller", "-u", udid, "-l"
            ], capture_output=True, text=True, timeout=10)
            
            if "cydia" in result.stdout.lower() or "sileo" in result.stdout.lower():
                return "jailbroken"
            else:
                return "not_jailbroken"
                
        except:
            return "unknown"
    
    def _check_bypass_compatibility(self, info):
        """Check if device is compatible with bypass tools"""
        model = info.get('ProductType', '').lower()
        version = info.get('ProductVersion', '')
        
        # Simplified compatibility check
        # Real implementation would have comprehensive compatibility matrix
        compatible_models = [
            'iphone6', 'iphone7', 'iphone8', 'iphonex',
            'ipad6', 'ipad7', 'ipadair2', 'ipadpro'
        ]
        
        for compatible_model in compatible_models:
            if compatible_model in model:
                return True
        
        return False
    
    async def check_jailbreak_compatibility(self, device, tool):
        """Check if device is compatible with specific jailbreak tool"""
        model = device['model'].lower()
        version = device['version']
        
        compatibility = {
            'compatible': False,
            'reason': 'Unknown compatibility issue'
        }
        
        if tool == "lockra1n":
            # Lockra1n compatibility (simplified)
            if any(x in model for x in ['iphone6', 'iphone7', 'iphone8', 'iphonex']):
                if version.startswith(('12.', '13.', '14.', '15.')):
                    compatibility['compatible'] = True
                else:
                    compatibility['reason'] = f"iOS {version} not supported by lockra1n"
            else:
                compatibility['reason'] = f"Device model {device['model']} not supported"
        
        elif tool == "checkra1n":
            # Checkra1n compatibility
            if any(x in model for x in ['iphone5', 'iphone6', 'iphone7', 'iphone8', 'iphonex']):
                compatibility['compatible'] = True
            else:
                compatibility['reason'] = "Device not compatible with checkra1n (A12+ devices not supported)"
        
        return compatibility
    
    async def execute_jailbreak(self, device, tool):
        """Execute jailbreak process"""
        PrintStyle().info(f"Executing {tool} jailbreak on {device['name']}...")
        
        if tool == "lockra1n":
            return await self._execute_lockra1n(device)
        elif tool == "checkra1n":
            return await self._execute_checkra1n(device)
        else:
            return f"Jailbreak tool {tool} not implemented yet"
    
    async def _execute_lockra1n(self, device):
        """Execute lockra1n jailbreak"""
        try:
            # Download lockra1n if not present
            lockra1n_path = await self._download_lockra1n()
            
            if not lockra1n_path:
                return "Failed to download lockra1n tool"
            
            # Execute lockra1n
            PrintStyle().info("Starting lockra1n jailbreak process...")
            
            # This would be the actual lockra1n execution
            # For safety, this is a simulation
            result = f"""
Lockra1n Jailbreak Process Started
Device: {device['name']} ({device['model']})
iOS Version: {device['version']}

⚠️  SIMULATION MODE - No actual jailbreak performed ⚠️

Steps that would be executed:
1. Put device in DFU mode
2. Exploit bootrom vulnerability
3. Install jailbreak payload
4. Reboot device
5. Install Cydia/Sileo

Status: Would complete successfully (simulated)
"""
            
            return result
            
        except Exception as e:
            return f"Lockra1n execution failed: {str(e)}"
    
    async def _execute_checkra1n(self, device):
        """Execute checkra1n jailbreak"""
        return "Checkra1n execution not implemented yet"
    
    async def _download_lockra1n(self):
        """Download lockra1n tool"""
        try:
            lockra1n_path = os.path.join(self.tools_dir, "lockra1n")
            
            if os.path.exists(lockra1n_path):
                return lockra1n_path
            
            PrintStyle().info("Downloading lockra1n...")
            
            # This would download the actual tool
            # For safety, we'll just create a placeholder
            with open(lockra1n_path, 'w') as f:
                f.write("# Lockra1n placeholder - actual tool would be downloaded here\n")
            
            os.chmod(lockra1n_path, 0o755)
            return lockra1n_path
            
        except Exception as e:
            PrintStyle().error(f"Failed to download lockra1n: {str(e)}")
            return None
    
    async def execute_icloud_bypass(self, device, tool):
        """Execute iCloud bypass"""
        PrintStyle().info(f"Executing iCloud bypass with {tool}...")
        
        result = f"""
iCloud Bypass Process (SIMULATION)
Device: {device['name']} ({device['model']})
Tool: {tool}

⚠️  EDUCATIONAL SIMULATION ONLY ⚠️

This would attempt to:
1. Check device activation status
2. Exploit activation vulnerabilities
3. Bypass iCloud activation lock
4. Enable device functionality

Note: Real bypass success depends on:
- iOS version vulnerabilities
- Device model compatibility
- Current patch level

Status: Simulation complete
"""
        
        return result
    
    async def install_jailbreak_tools(self):
        """Install required jailbreak tools"""
        PrintStyle().info("Installing jailbreak tools...")
        
        installation_steps = []
        
        if self.system == "darwin":  # macOS
            installation_steps.extend([
                "Installing libimobiledevice via Homebrew...",
                "brew install libimobiledevice",
                "brew install ideviceinstaller",
                "Installing additional tools..."
            ])
        elif self.system == "linux":
            installation_steps.extend([
                "Installing libimobiledevice via apt...",
                "sudo apt update",
                "sudo apt install libimobiledevice-utils",
                "sudo apt install ideviceinstaller"
            ])
        else:
            return "Windows support not implemented yet. Please use macOS or Linux."
        
        result = "Jailbreak Tools Installation:\n\n"
        result += "\n".join(f"• {step}" for step in installation_steps)
        result += "\n\nNote: This is a simulation. Run these commands manually to install actual tools."
        
        return result
