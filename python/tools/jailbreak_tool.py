import asyncio
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers import files
from python.helpers.jailbreak_utils import JailbreakUtils


class JailbreakTool(Tool):
    """
    iOS Jailbreak Tool - Provides functionality for jailbreaking iOS devices
    Supports checkra1n, lockra1n, and other popular jailbreak tools
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.utils = JailbreakUtils()
        
    async def execute(self, action="status", device_udid="", tool="lockra1n", **kwargs):
        """
        Execute jailbreak operations
        
        Args:
            action: Operation to perform (status, detect, jailbreak, bypass, install_tools)
            device_udid: Specific device UDID to target
            tool: Jailbreak tool to use (lockra1n, checkra1n, unc0ver)
        """
        
        try:
            if action == "status":
                return await self._check_device_status(device_udid)
            elif action == "detect":
                return await self._detect_devices()
            elif action == "jailbreak":
                return await self._perform_jailbreak(device_udid, tool)
            elif action == "bypass":
                return await self._icloud_bypass(device_udid, tool)
            elif action == "install_tools":
                return await self._install_jailbreak_tools()
            else:
                return Response(
                    message=f"Unknown action: {action}. Available actions: status, detect, jailbreak, bypass, install_tools",
                    break_loop=False
                )
                
        except Exception as e:
            PrintStyle().error(f"Jailbreak tool error: {str(e)}")
            return Response(
                message=f"Error executing jailbreak operation: {str(e)}",
                break_loop=False
            )
    
    async def _check_device_status(self, device_udid=""):
        """Check the status of connected iOS devices"""
        PrintStyle().info("Checking iOS device status...")
        
        # Check if required tools are available
        tools_status = await self.utils.check_required_tools()
        
        # Detect connected devices
        devices = await self.utils.detect_ios_devices()
        
        if not devices:
            return Response(
                message="No iOS devices detected. Please connect your device and ensure it's trusted.",
                break_loop=False
            )
        
        status_report = "=== iOS Device Status Report ===\n\n"
        status_report += f"Required Tools Status:\n{tools_status}\n\n"
        status_report += "Connected Devices:\n"
        
        for device in devices:
            status_report += f"- Device: {device['name']}\n"
            status_report += f"  UDID: {device['udid']}\n"
            status_report += f"  iOS Version: {device['version']}\n"
            status_report += f"  Model: {device['model']}\n"
            status_report += f"  Jailbreak Status: {device['jailbreak_status']}\n"
            status_report += f"  Bypass Compatible: {device['bypass_compatible']}\n\n"
        
        return Response(message=status_report, break_loop=False)
    
    async def _detect_devices(self):
        """Detect and list all connected iOS devices"""
        PrintStyle().info("Detecting iOS devices...")
        
        devices = await self.utils.detect_ios_devices()
        
        if not devices:
            return Response(
                message="No iOS devices found. Please:\n1. Connect your iOS device\n2. Trust this computer\n3. Ensure iTunes/3uTools is installed",
                break_loop=False
            )
        
        device_list = "=== Detected iOS Devices ===\n\n"
        for i, device in enumerate(devices, 1):
            device_list += f"{i}. {device['name']} ({device['model']})\n"
            device_list += f"   UDID: {device['udid']}\n"
            device_list += f"   iOS: {device['version']}\n"
            device_list += f"   Status: {device['status']}\n\n"
        
        return Response(message=device_list, break_loop=False)
    
    async def _perform_jailbreak(self, device_udid, tool):
        """Perform jailbreak operation on specified device"""
        PrintStyle().info(f"Starting jailbreak process with {tool}...")
        
        # Validate device
        devices = await self.utils.detect_ios_devices()
        target_device = None
        
        if device_udid:
            target_device = next((d for d in devices if d['udid'] == device_udid), None)
        elif len(devices) == 1:
            target_device = devices[0]
        
        if not target_device:
            return Response(
                message="Please specify a valid device UDID or connect only one device.",
                break_loop=False
            )
        
        # Check compatibility
        compatibility = await self.utils.check_jailbreak_compatibility(target_device, tool)
        if not compatibility['compatible']:
            return Response(
                message=f"Device not compatible with {tool}: {compatibility['reason']}",
                break_loop=False
            )
        
        # Perform jailbreak
        result = await self.utils.execute_jailbreak(target_device, tool)
        
        return Response(message=result, break_loop=False)
    
    async def _icloud_bypass(self, device_udid, tool):
        """Perform iCloud activation lock bypass"""
        PrintStyle().info(f"Starting iCloud bypass with {tool}...")
        
        # Warning message
        warning = """
⚠️  WARNING: iCloud Bypass Operations ⚠️

This operation will attempt to bypass iCloud activation lock.
- Only use on devices you own or have explicit permission to modify
- This may void your warranty
- Success is not guaranteed and depends on iOS version and device model
- Always backup your device before proceeding

Do you want to continue? (This is for educational/research purposes only)
"""
        
        # In a real implementation, you'd want user confirmation here
        PrintStyle().warning(warning)
        
        devices = await self.utils.detect_ios_devices()
        target_device = None
        
        if device_udid:
            target_device = next((d for d in devices if d['udid'] == device_udid), None)
        elif len(devices) == 1:
            target_device = devices[0]
        
        if not target_device:
            return Response(
                message="Please specify a valid device UDID or connect only one device.",
                break_loop=False
            )
        
        # Check if device is in activation lock
        if target_device['status'] != 'activation_locked':
            return Response(
                message="Device is not in activation lock state. Bypass not needed.",
                break_loop=False
            )
        
        # Perform bypass
        result = await self.utils.execute_icloud_bypass(target_device, tool)
        
        return Response(message=result, break_loop=False)
    
    async def _install_jailbreak_tools(self):
        """Install and setup jailbreak tools"""
        PrintStyle().info("Installing jailbreak tools...")
        
        result = await self.utils.install_jailbreak_tools()
        
        return Response(message=result, break_loop=False)
