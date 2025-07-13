# Advanced Shodan Reconnaissance and Vulnerability Scanning

## Overview
This document covers advanced Shodan techniques for reconnaissance, vulnerability discovery, and intelligence gathering using the Shodan search engine and API.

## Shodan API Configuration

### API Setup
**API Key**: 5lmLLu8KpMum2Py3yizKUus58w0pO6b3
**Account Level**: Academic membership

**API Configuration**:
```bash
# Shodan CLI setup
shodan init 5lmLLu8KpMum2Py3yizKUus58w0pO6b3

# Verify API key
shodan info

# Python API setup
import shodan
api = shodan.Shodan('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
```

## Basic Shodan Reconnaissance

### Target Discovery
**Objective**: Discover internet-facing assets for target organizations

**Basic Search Techniques**:
```bash
# Organization search
shodan search "org:target-company"

# Domain-based search
shodan search "hostname:target.com"

# IP range search
shodan search "net:192.168.1.0/24"

# ASN search
shodan search "asn:AS12345"

# SSL certificate search
shodan search "ssl:target.com"
```

**Advanced Search Filters**:
```bash
# Country-specific search
shodan search "country:US org:target-company"

# City-specific search
shodan search "city:"New York" org:target-company"

# Port-specific search
shodan search "port:22 org:target-company"

# Service-specific search
shodan search "product:Apache org:target-company"

# Operating system search
shodan search "os:Windows org:target-company"
```

## Vulnerability Discovery with Shodan

### CVE-based Searches
**Objective**: Find systems vulnerable to specific CVEs

**CVE Search Techniques**:
```bash
# EternalBlue (MS17-010)
shodan search "vuln:ms17-010"

# BlueKeep (CVE-2019-0708)
shodan search "vuln:cve-2019-0708"

# Log4Shell (CVE-2021-44228)
shodan search "vuln:cve-2021-44228"

# ProxyLogon (CVE-2021-26855)
shodan search "vuln:cve-2021-26855"

# Heartbleed (CVE-2014-0160)
shodan search "vuln:cve-2014-0160"

# Shellshock (CVE-2014-6271)
shodan search "vuln:cve-2014-6271"
```

**Vulnerability Scanning Scripts**:
```python
#!/usr/bin/env python3
import shodan
import json

class ShodanVulnScanner:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
        
    def search_vulnerabilities(self, target, cve_list):
        results = {}
        
        for cve in cve_list:
            try:
                query = f"vuln:{cve} {target}"
                search_results = self.api.search(query)
                
                results[cve] = {
                    'total': search_results['total'],
                    'hosts': []
                }
                
                for host in search_results['matches']:
                    host_info = {
                        'ip': host['ip_str'],
                        'port': host['port'],
                        'product': host.get('product', 'Unknown'),
                        'version': host.get('version', 'Unknown'),
                        'location': f"{host.get('location', {}).get('city', 'Unknown')}, {host.get('location', {}).get('country_name', 'Unknown')}"
                    }
                    results[cve]['hosts'].append(host_info)
                    
            except shodan.APIError as e:
                print(f"Error searching for {cve}: {e}")
                
        return results
    
    def generate_report(self, results, output_file):
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)

# Usage
scanner = ShodanVulnScanner('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
cves = ['cve-2021-44228', 'cve-2019-0708', 'ms17-010', 'cve-2021-26855']
results = scanner.search_vulnerabilities('org:target-company', cves)
scanner.generate_report(results, 'vuln_report.json')
```

### Service-Specific Vulnerability Searches
**Objective**: Target specific services for vulnerability assessment

**Web Server Vulnerabilities**:
```bash
# Apache vulnerabilities
shodan search "product:Apache vuln:cve-2021-41773"

# Nginx vulnerabilities
shodan search "product:nginx vuln:cve-2017-7529"

# IIS vulnerabilities
shodan search "product:IIS vuln:cve-2017-7269"

# Tomcat vulnerabilities
shodan search "product:Tomcat vuln:cve-2020-1938"
```

**Database Vulnerabilities**:
```bash
# MySQL vulnerabilities
shodan search "product:MySQL vuln:cve-2012-2122"

# PostgreSQL vulnerabilities
shodan search "product:PostgreSQL vuln:cve-2018-1058"

# MongoDB vulnerabilities
shodan search "product:MongoDB vuln:cve-2017-2665"

# Redis vulnerabilities
shodan search "product:Redis vuln:cve-2022-0543"
```

**Network Device Vulnerabilities**:
```bash
# Cisco vulnerabilities
shodan search "cisco vuln:cve-2020-3452"

# Fortinet vulnerabilities
shodan search "fortinet vuln:cve-2018-13379"

# Palo Alto vulnerabilities
shodan search "palo alto vuln:cve-2020-2021"

# SonicWall vulnerabilities
shodan search "sonicwall vuln:cve-2021-20016"
```

## Advanced Shodan Techniques

### Custom Search Queries
**Objective**: Create sophisticated search queries for targeted reconnaissance

**Complex Query Examples**:
```bash
# Exposed databases
shodan search "port:27017 -authentication"
shodan search "port:3306 mysql"
shodan search "port:5432 postgresql"
shodan search "port:6379 redis"

# Exposed admin panels
shodan search "title:"Admin Panel" country:US"
shodan search "http.title:"phpMyAdmin" country:US"
shodan search "title:"Grafana" country:US"

# Industrial control systems
shodan search "port:502 modbus"
shodan search "port:102 s7comm"
shodan search "port:44818 opcua"

# IoT devices
shodan search "product:"Hikvision IP Camera""
shodan search "product:"Dahua IP Camera""
shodan search "title:"DVR Web Client""

# VPN and remote access
shodan search "product:"Fortinet FortiGate""
shodan search "product:"Pulse Secure""
shodan search "title:"Citrix Gateway""
```

**Automated Reconnaissance Script**:
```python
#!/usr/bin/env python3
import shodan
import csv
import time

class ShodanRecon:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
        
    def comprehensive_scan(self, target):
        queries = [
            f"org:{target}",
            f"hostname:{target}",
            f"ssl:{target}",
            f"http.title:{target}",
            f"html:{target}"
        ]
        
        all_results = []
        
        for query in queries:
            try:
                print(f"Searching: {query}")
                results = self.api.search(query)
                
                for host in results['matches']:
                    host_data = {
                        'ip': host['ip_str'],
                        'port': host['port'],
                        'protocol': host.get('transport', 'unknown'),
                        'product': host.get('product', 'Unknown'),
                        'version': host.get('version', 'Unknown'),
                        'os': host.get('os', 'Unknown'),
                        'country': host.get('location', {}).get('country_name', 'Unknown'),
                        'city': host.get('location', {}).get('city', 'Unknown'),
                        'org': host.get('org', 'Unknown'),
                        'isp': host.get('isp', 'Unknown'),
                        'vulns': list(host.get('vulns', [])),
                        'tags': host.get('tags', []),
                        'timestamp': host.get('timestamp', 'Unknown')
                    }
                    all_results.append(host_data)
                
                time.sleep(1)  # Rate limiting
                
            except shodan.APIError as e:
                print(f"Error with query {query}: {e}")
                
        return all_results
    
    def export_to_csv(self, results, filename):
        if not results:
            return
            
        fieldnames = results[0].keys()
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                # Convert lists to strings for CSV
                for key, value in row.items():
                    if isinstance(value, list):
                        row[key] = ', '.join(map(str, value))
                writer.writerow(row)

# Usage
recon = ShodanRecon('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
results = recon.comprehensive_scan('target-company')
recon.export_to_csv(results, 'shodan_recon.csv')
```

### Shodan Dorks and Advanced Searches
**Objective**: Use specialized search queries for specific reconnaissance goals

**Network Infrastructure Dorks**:
```bash
# Exposed routers
shodan search "title:"Router" country:US"
shodan search "Server: lighttpd/1.4.35"

# Exposed switches
shodan search "product:"Cisco IOS""
shodan search "title:"Switch Configuration""

# Exposed firewalls
shodan search "product:"pfSense""
shodan search "title:"SonicWall""

# VPN concentrators
shodan search "product:"Cisco ASA""
shodan search "ssl:"anyconnect""
```

**Web Application Dorks**:
```bash
# Exposed Jenkins
shodan search "title:"Dashboard [Jenkins]""
shodan search "X-Jenkins:"

# Exposed GitLab
shodan search "title:"GitLab""
shodan search "Server: nginx gitlab"

# Exposed Docker registries
shodan search "product:"Docker Registry""
shodan search "title:"Docker Registry""

# Exposed Elasticsearch
shodan search "product:"Elasticsearch""
shodan search "port:9200 elasticsearch"
```

**Database and Storage Dorks**:
```bash
# Exposed MongoDB
shodan search "product:"MongoDB" port:27017"
shodan search ""MongoDB server information" port:27017"

# Exposed MySQL
shodan search "product:"MySQL" port:3306"
shodan search ""mysql_native_password""

# Exposed FTP servers
shodan search "port:21 "220" "FTP""
shodan search ""Anonymous FTP login allowed""

# Exposed SMB shares
shodan search "port:445 "SMB""
shodan search ""Authentication: disabled" port:445"
```

## Shodan API Advanced Usage

### Bulk IP Analysis
**Objective**: Analyze multiple IP addresses efficiently

**Bulk Analysis Script**:
```python
#!/usr/bin/env python3
import shodan
import json
import time

class ShodanBulkAnalyzer:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
        
    def analyze_ip_list(self, ip_list):
        results = {}
        
        for ip in ip_list:
            try:
                print(f"Analyzing {ip}...")
                host_info = self.api.host(ip)
                
                results[ip] = {
                    'org': host_info.get('org', 'Unknown'),
                    'isp': host_info.get('isp', 'Unknown'),
                    'country': host_info.get('country_name', 'Unknown'),
                    'city': host_info.get('city', 'Unknown'),
                    'ports': host_info.get('ports', []),
                    'vulns': list(host_info.get('vulns', [])),
                    'tags': host_info.get('tags', []),
                    'last_update': host_info.get('last_update', 'Unknown'),
                    'services': []
                }
                
                # Extract service information
                for service in host_info.get('data', []):
                    service_info = {
                        'port': service.get('port'),
                        'protocol': service.get('transport'),
                        'product': service.get('product'),
                        'version': service.get('version'),
                        'banner': service.get('data', '')[:200]  # First 200 chars
                    }
                    results[ip]['services'].append(service_info)
                
                time.sleep(1)  # Rate limiting
                
            except shodan.APIError as e:
                print(f"Error analyzing {ip}: {e}")
                results[ip] = {'error': str(e)}
                
        return results
    
    def generate_vulnerability_report(self, results):
        vuln_summary = {}
        
        for ip, data in results.items():
            if 'vulns' in data and data['vulns']:
                for vuln in data['vulns']:
                    if vuln not in vuln_summary:
                        vuln_summary[vuln] = []
                    vuln_summary[vuln].append(ip)
        
        return vuln_summary

# Usage
analyzer = ShodanBulkAnalyzer('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
ip_list = ['192.168.1.1', '10.0.0.1', '172.16.0.1']
results = analyzer.analyze_ip_list(ip_list)
vuln_report = analyzer.generate_vulnerability_report(results)
```

### Continuous Monitoring
**Objective**: Set up continuous monitoring for new vulnerabilities

**Monitoring Script**:
```python
#!/usr/bin/env python3
import shodan
import json
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

class ShodanMonitor:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
        
    def monitor_organization(self, org_name, alert_email=None):
        previous_results = self.load_previous_results(org_name)
        current_results = self.scan_organization(org_name)
        
        # Compare results
        new_hosts = self.find_new_hosts(previous_results, current_results)
        new_vulns = self.find_new_vulnerabilities(previous_results, current_results)
        
        if new_hosts or new_vulns:
            report = self.generate_alert_report(new_hosts, new_vulns)
            print(report)
            
            if alert_email:
                self.send_alert_email(alert_email, report)
        
        # Save current results
        self.save_results(org_name, current_results)
    
    def scan_organization(self, org_name):
        try:
            results = self.api.search(f"org:{org_name}")
            return results['matches']
        except shodan.APIError as e:
            print(f"Error scanning organization: {e}")
            return []
    
    def find_new_hosts(self, previous, current):
        previous_ips = {host['ip_str'] for host in previous}
        current_ips = {host['ip_str'] for host in current}
        new_ips = current_ips - previous_ips
        
        return [host for host in current if host['ip_str'] in new_ips]
    
    def find_new_vulnerabilities(self, previous, current):
        previous_vulns = {}
        for host in previous:
            ip = host['ip_str']
            vulns = host.get('vulns', [])
            previous_vulns[ip] = set(vulns)
        
        new_vulns = []
        for host in current:
            ip = host['ip_str']
            current_host_vulns = set(host.get('vulns', []))
            previous_host_vulns = previous_vulns.get(ip, set())
            
            new_host_vulns = current_host_vulns - previous_host_vulns
            if new_host_vulns:
                new_vulns.append({
                    'ip': ip,
                    'new_vulns': list(new_host_vulns)
                })
        
        return new_vulns
    
    def generate_alert_report(self, new_hosts, new_vulns):
        report = f"Shodan Monitoring Alert - {datetime.now()}\n\n"
        
        if new_hosts:
            report += f"New Hosts Discovered ({len(new_hosts)}):\n"
            for host in new_hosts:
                report += f"  - {host['ip_str']}:{host['port']} ({host.get('product', 'Unknown')})\n"
            report += "\n"
        
        if new_vulns:
            report += f"New Vulnerabilities Detected:\n"
            for vuln_info in new_vulns:
                report += f"  - {vuln_info['ip']}: {', '.join(vuln_info['new_vulns'])}\n"
        
        return report
    
    def load_previous_results(self, org_name):
        try:
            with open(f"{org_name}_previous.json", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def save_results(self, org_name, results):
        with open(f"{org_name}_previous.json", 'w') as f:
            json.dump(results, f)

# Usage
monitor = ShodanMonitor('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
monitor.monitor_organization('target-company', 'admin@company.com')
```

## Shodan Integration with Other Tools

### Nmap Integration
**Objective**: Combine Shodan reconnaissance with Nmap scanning

**Integration Script**:
```python
#!/usr/bin/env python3
import shodan
import subprocess
import json

class ShodanNmapIntegration:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
    
    def shodan_to_nmap(self, query, output_file):
        try:
            results = self.api.search(query)
            ip_list = []
            
            for host in results['matches']:
                ip = host['ip_str']
                port = host['port']
                ip_list.append(f"{ip}:{port}")
            
            # Create Nmap target list
            unique_ips = list(set([ip.split(':')[0] for ip in ip_list]))
            
            # Run Nmap scan
            nmap_command = [
                'nmap', '-sV', '-sC', '--script', 'vuln',
                '-oA', output_file
            ] + unique_ips
            
            subprocess.run(nmap_command)
            
            return unique_ips
            
        except shodan.APIError as e:
            print(f"Shodan API error: {e}")
            return []

# Usage
integration = ShodanNmapIntegration('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
targets = integration.shodan_to_nmap('org:target-company', 'nmap_results')
```

### Metasploit Integration
**Objective**: Use Shodan results to feed Metasploit modules

**Integration Script**:
```python
#!/usr/bin/env python3
import shodan
import json

class ShodanMetasploitIntegration:
    def __init__(self, api_key):
        self.api = shodan.Shodan(api_key)
    
    def generate_msf_resource(self, query, output_file):
        try:
            results = self.api.search(query)
            
            with open(output_file, 'w') as f:
                f.write("# Metasploit resource script generated from Shodan\n")
                f.write("# Usage: msfconsole -r this_file.rc\n\n")
                
                for host in results['matches']:
                    ip = host['ip_str']
                    port = host['port']
                    product = host.get('product', '').lower()
                    
                    # Map products to Metasploit modules
                    if 'ssh' in product:
                        f.write(f"use auxiliary/scanner/ssh/ssh_version\n")
                        f.write(f"set RHOSTS {ip}\n")
                        f.write(f"set RPORT {port}\n")
                        f.write(f"run\n\n")
                    
                    elif 'ftp' in product:
                        f.write(f"use auxiliary/scanner/ftp/ftp_version\n")
                        f.write(f"set RHOSTS {ip}\n")
                        f.write(f"set RPORT {port}\n")
                        f.write(f"run\n\n")
                    
                    elif 'http' in product or 'apache' in product:
                        f.write(f"use auxiliary/scanner/http/http_version\n")
                        f.write(f"set RHOSTS {ip}\n")
                        f.write(f"set RPORT {port}\n")
                        f.write(f"run\n\n")
            
            print(f"Metasploit resource script saved to {output_file}")
            
        except shodan.APIError as e:
            print(f"Shodan API error: {e}")

# Usage
msf_integration = ShodanMetasploitIntegration('5lmLLu8KpMum2Py3yizKUus58w0pO6b3')
msf_integration.generate_msf_resource('org:target-company', 'shodan_targets.rc')
```

## Conclusion

This comprehensive Shodan guide covers advanced reconnaissance and vulnerability scanning techniques including:

- **API configuration and setup**
- **Target discovery and enumeration**
- **CVE-based vulnerability searches**
- **Service-specific vulnerability assessment**
- **Advanced search queries and dorks**
- **Bulk IP analysis and monitoring**
- **Integration with other security tools**
- **Continuous monitoring and alerting**

These techniques provide powerful capabilities for:
- **Asset discovery and inventory**
- **Vulnerability assessment at scale**
- **Threat intelligence gathering**
- **Continuous security monitoring**
- **Integration with existing security workflows**

Remember: Use Shodan responsibly and only for authorized reconnaissance and security assessment activities.

**API Key**: 5lmLLu8KpMum2Py3yizKUus58w0pO6b3 (Academic membership)
