import os
import platform
import requests
import subprocess
import threading
from python.helpers import files
from python.helpers.print_style import PrintStyle

class CloudflareTunnel:
    def __init__(self, port: int):
        self.port = port
        self.bin_dir = "tmp"  # Relative path
        self.cloudflared_path = None
        self.tunnel_process = None
        self.tunnel_url = None
        self._stop_event = threading.Event()
        
    def download_cloudflared(self):
        """Downloads the appropriate cloudflared binary for the current system"""
        # Create bin directory if it doesn't exist using files helper
        os.makedirs(files.get_abs_path(self.bin_dir), exist_ok=True)
        
        # Determine OS and architecture
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        # Define executable name
        executable_name = "cloudflared.exe" if system == "windows" else "cloudflared"
        install_path = files.get_abs_path(self.bin_dir, executable_name)
        
        # Return if already exists
        if files.exists(self.bin_dir, executable_name):
            self.cloudflared_path = install_path
            return install_path
            
        # Map platform/arch to download URLs
        base_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/"
        
        if system == "darwin":  # macOS
            # Download and extract .tgz for macOS
            download_file = "cloudflared-darwin-amd64.tgz" if arch == "x86_64" else "cloudflared-darwin-arm64.tgz"
            download_url = f"{base_url}{download_file}"
            download_path = files.get_abs_path(self.bin_dir, download_file)
            
            PrintStyle().print(f"\nDownloading cloudflared from: {download_url}")
            response = requests.get(download_url, stream=True)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to download cloudflared: {response.status_code}")
                
            # Save the .tgz file
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Extract cloudflared binary from .tgz
            import tarfile
            with tarfile.open(download_path, "r:gz") as tar:
                tar.extract("cloudflared", files.get_abs_path(self.bin_dir))
                
            # Cleanup .tgz file
            os.remove(download_path)
            
        else:  # Linux and Windows
            if system == "linux":
                if arch in ["x86_64", "amd64"]:
                    download_file = "cloudflared-linux-amd64"
                elif arch == "arm64" or arch == "aarch64":
                    download_file = "cloudflared-linux-arm64"
                elif arch == "arm":
                    download_file = "cloudflared-linux-arm"
                else:
                    download_file = "cloudflared-linux-386"
            elif system == "windows":
                download_file = "cloudflared-windows-amd64.exe"
            else:
                raise RuntimeError(f"Unsupported platform: {system} {arch}")
                
            download_url = f"{base_url}{download_file}"
            download_path = files.get_abs_path(self.bin_dir, download_file)
            
            PrintStyle().print(f"\nDownloading cloudflared from: {download_url}")
            response = requests.get(download_url, stream=True)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to download cloudflared: {response.status_code}")
                
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            
            # Rename and set permissions
            if os.path.exists(install_path):
                os.remove(install_path)
            os.rename(download_path, install_path)
        
        # Set executable permissions
        if system != "windows":
            os.chmod(install_path, 0o755)
            
        self.cloudflared_path = install_path
        return install_path

    def _extract_tunnel_url(self, process):
        """Extracts the tunnel URL from cloudflared output"""
        while not self._stop_event.is_set():
            line = process.stdout.readline()
            if not line:
                break
                
            if isinstance(line, bytes):
                line = line.decode('utf-8')
                
            if "trycloudflare.com" in line and "https://" in line:
                start = line.find("https://")
                end = line.find("trycloudflare.com") + len("trycloudflare.com")
                self.tunnel_url = line[start:end].strip()
                PrintStyle().print("\n=== Cloudflare Tunnel URL ===")
                PrintStyle().print(f"URL: {self.tunnel_url}")
                PrintStyle().print("============================\n")
                return

    def start(self):
        """Starts the cloudflare tunnel"""
        if not self.cloudflared_path:
            self.download_cloudflared()
            
        PrintStyle().print("\nStarting Cloudflare tunnel...")
        # Start tunnel process
        self.tunnel_process = subprocess.Popen(
            [
                str(self.cloudflared_path),
                "tunnel", 
                "--url",
                f"http://localhost:{self.port}"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
        
        # Extract tunnel URL in separate thread
        threading.Thread(
            target=self._extract_tunnel_url,
            args=(self.tunnel_process,),
            daemon=True
        ).start()

    def stop(self):
        """Stops the cloudflare tunnel"""
        self._stop_event.set()
        if self.tunnel_process:
            PrintStyle().print("\nStopping Cloudflare tunnel...")
            self.tunnel_process.terminate()
            self.tunnel_process.wait()
            self.tunnel_process = None
            self.tunnel_url = None