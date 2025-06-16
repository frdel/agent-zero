#!/bin/bash

# This script generates sudoers rules for a comprehensive list of pentesting tools.
# It finds the full path of each tool and formats it for the sudoers file.

echo "# ================================================================================"
echo "# Custom sudoers rules for User natefoxtrot, generated on $(date)"
echo "# Allows Agent-Zero to run common pentesting tools without a password."
echo "# ================================================================================"
echo ""

# Define the user for the sudoers rule
SUDO_USER="natefoxtrot"

# --- List of tools to grant passwordless sudo access to ---
# This list includes the tools you specified and many others common to Kali.
TOOLS=(
    # --- Custom Scripts & Agent-Zero ---
    "/home/natefoxtrot/miniconda3/envs/a0_hacking/bin/python"

    # --- Frameworks & Exploitation ---
    msfconsole msfvenom msfdb
    beef-xss
    fatrat
    veil
    ghidra ghidraRun
    backdoor-factory
    shellter

    # --- Wireless Tools ---
    airmon-ng aireplay-ng airodump-ng
    wifite
    bettercap
    macchanger
    sparrow-wifi
    hcxdumptool hcxpcapngtool hcxhashtool hcxpsktool hcxpmktool hcxeiutool

    # --- Scanners, Discovery & Sniffing Tools ---
    nmap
    netdiscover
    netsniff-ng
    fragrouter
    wireshark tshark tcpdump

    # --- DNS & SQL Tools ---
    dnsrecon dnsenum dnschef dnswalk sqlmap sqlninja

    # --- Password Cracking & Wordlist Tools ---
    john hashcat hydra crunch cewl

    # --- OSINT & Recon Tools ---
    recon-ng theharvester metagoofil sublist3r sherlock

    # --- Lateral Movement & Post-Exploitation ---
    netexec evil-winrm
    # Add common impacket examples if they are in PATH
    psexec.py smbclient.py secretsdump.py

    # --- Web & Evasion Tools ---
    weevely
    # Add paths to webshell directories if needed

    # --- Forensic, Priv-Esc & Steganography Tools ---
    scrounge-ntfs
    unix-privesc-check
    autopsy volatility fls icat
    stegosuite steghide
    # Add paths to PEAS scripts if they exist
    # /path/to/linpeas.sh /path/to/winpeas.bat
)

# --- Generate the sudoers lines ---
for tool in "${TOOLS[@]}"; do
    # Check if the tool path is absolute or needs 'which'
    if [[ "$tool" == /* ]]; then
        # If it's already an absolute path, check if it exists
        if [ -x "$tool" ]; then
            echo "$SUDO_USER ALL=(ALL) NOPASSWD: $tool"
        else
            echo "# WARNING: Specified tool path not found or not executable: $tool"
        fi
    else
        # If it's just a name, find the full path
        TOOL_PATH=$(which "$tool" 2>/dev/null)
        if [ -n "$TOOL_PATH" ]; then
            echo "$SUDO_USER ALL=(ALL) NOPASSWD: $TOOL_PATH"
        else
            echo "# WARNING: Tool not found in PATH: $tool"
        fi
    fi
done

echo "# ================================================================================"
