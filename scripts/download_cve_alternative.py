#!/usr/bin/env python3
"""
Alternative CVE Data Downloader for DeepGaza
Uses multiple sources to download CVE data for 2024 and 2025
"""

import requests
import json
import time
import os
import csv
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

# Output directory
KNOWLEDGE_DIR = Path("../knowledge/cybersecurity/main")

class AlternativeCVEDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'DeepGaza-CVE-Downloader/1.0'
        })
    
    def download_from_cve_mitre(self, year):
        """Download CVE data from MITRE's CVE database"""
        print(f"Downloading CVEs from MITRE for {year}...")
        
        # MITRE CVE downloads (these are usually available)
        urls = {
            2024: "https://cve.mitre.org/data/downloads/allitems-cvrf-year-2024.xml",
            2025: "https://cve.mitre.org/data/downloads/allitems-cvrf-year-2025.xml"
        }
        
        if year not in urls:
            print(f"No MITRE data available for year {year}")
            return []
        
        try:
            response = self.session.get(urls[year], timeout=60)
            if response.status_code == 404:
                print(f"MITRE data not yet available for {year}")
                return []
            
            response.raise_for_status()
            return self.parse_mitre_xml(response.content, year)
            
        except Exception as e:
            print(f"Error downloading from MITRE: {e}")
            return []
    
    def parse_mitre_xml(self, xml_content, year):
        """Parse MITRE XML format"""
        try:
            root = ET.fromstring(xml_content)
            cves = []
            
            # Parse XML structure (simplified)
            for item in root.findall('.//item'):
                cve_id = item.get('name', 'Unknown')
                description = ""
                
                desc_elem = item.find('.//description')
                if desc_elem is not None:
                    description = desc_elem.text or ""
                
                cves.append({
                    'cve_id': cve_id,
                    'description': description,
                    'year': year,
                    'source': 'MITRE'
                })
            
            return cves
            
        except Exception as e:
            print(f"Error parsing MITRE XML: {e}")
            return []
    
    def download_from_github_advisories(self, year):
        """Download CVE data from GitHub Security Advisories"""
        print(f"Downloading GitHub Security Advisories for {year}...")
        
        # GitHub GraphQL API for security advisories
        query = """
        query($first: Int!, $after: String) {
          securityAdvisories(first: $first, after: $after, orderBy: {field: PUBLISHED_AT, direction: DESC}) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              ghsaId
              summary
              description
              severity
              publishedAt
              updatedAt
              identifiers {
                type
                value
              }
              references {
                url
              }
              vulnerabilities(first: 10) {
                nodes {
                  package {
                    name
                    ecosystem
                  }
                  vulnerableVersionRange
                  firstPatchedVersion {
                    identifier
                  }
                }
              }
            }
          }
        }
        """
        
        advisories = []
        has_next_page = True
        after = None
        
        while has_next_page:
            variables = {"first": 100}
            if after:
                variables["after"] = after
            
            try:
                response = self.session.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN', '')}"},
                    timeout=30
                )
                
                if response.status_code != 200:
                    print(f"GitHub API error: {response.status_code}")
                    break
                
                data = response.json()
                if 'errors' in data:
                    print(f"GraphQL errors: {data['errors']}")
                    break
                
                security_advisories = data['data']['securityAdvisories']
                nodes = security_advisories['nodes']
                
                # Filter by year
                for advisory in nodes:
                    published_at = advisory.get('publishedAt', '')
                    if str(year) in published_at:
                        advisories.append(advisory)
                
                page_info = security_advisories['pageInfo']
                has_next_page = page_info['hasNextPage']
                after = page_info['endCursor']
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error fetching GitHub advisories: {e}")
                break
        
        return advisories
    
    def create_sample_cve_data(self, year):
        """Create sample CVE data for demonstration"""
        print(f"Creating sample CVE data for {year}...")
        
        sample_cves = [
            {
                'cve_id': f'CVE-{year}-0001',
                'description': 'Remote code execution vulnerability in web application framework',
                'severity': 'CRITICAL',
                'base_score': '9.8',
                'affected_products': ['Web Framework 1.0', 'Application Server 2.1'],
                'year': year,
                'source': 'Sample Data'
            },
            {
                'cve_id': f'CVE-{year}-0002',
                'description': 'SQL injection vulnerability in database connector',
                'severity': 'HIGH',
                'base_score': '8.1',
                'affected_products': ['Database Connector 3.2', 'ORM Library 1.5'],
                'year': year,
                'source': 'Sample Data'
            },
            {
                'cve_id': f'CVE-{year}-0003',
                'description': 'Cross-site scripting (XSS) vulnerability in web interface',
                'severity': 'MEDIUM',
                'base_score': '6.1',
                'affected_products': ['Web Interface 2.0', 'Admin Panel 1.3'],
                'year': year,
                'source': 'Sample Data'
            },
            {
                'cve_id': f'CVE-{year}-0004',
                'description': 'Information disclosure vulnerability in logging component',
                'severity': 'LOW',
                'base_score': '3.3',
                'affected_products': ['Logging Library 1.1', 'Debug Tools 2.0'],
                'year': year,
                'source': 'Sample Data'
            }
        ]
        
        return sample_cves
    
    def format_cve_for_rag(self, cve_data):
        """Format CVE data for RAG system"""
        cve_id = cve_data.get('cve_id', 'Unknown')
        description = cve_data.get('description', 'No description available')
        severity = cve_data.get('severity', 'Unknown')
        base_score = cve_data.get('base_score', 'N/A')
        affected_products = cve_data.get('affected_products', [])
        source = cve_data.get('source', 'Unknown')
        year = cve_data.get('year', 'Unknown')
        
        # Format for RAG
        formatted_text = f"""
CVE ID: {cve_id}
Year: {year}
Severity: {severity}
CVSS Base Score: {base_score}
Source: {source}

Description:
{description}

Affected Products:
{chr(10).join(affected_products) if affected_products else 'Not specified'}

Security Impact:
This vulnerability affects the confidentiality, integrity, and/or availability of the affected systems.

Mitigation Recommendations:
- Update affected software to the latest version
- Apply security patches as soon as they become available
- Implement additional security controls if patches are not available
- Monitor systems for signs of exploitation

---
"""
        
        return {
            "cve_id": cve_id,
            "severity": severity,
            "base_score": base_score,
            "year": year,
            "text": formatted_text
        }
    
    def save_cves_to_knowledge_base(self, cves, year):
        """Save CVEs to knowledge base files"""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        
        if not cves:
            print(f"No CVEs to save for {year}")
            return
        
        # Group CVEs by severity
        severity_groups = {
            "CRITICAL": [],
            "HIGH": [],
            "MEDIUM": [],
            "LOW": [],
            "UNKNOWN": []
        }
        
        for cve_data in cves:
            formatted = self.format_cve_for_rag(cve_data)
            severity = formatted["severity"].upper()
            if severity not in severity_groups:
                severity = "UNKNOWN"
            severity_groups[severity].append(formatted)
        
        # Save each severity group to separate files
        for severity, cve_list in severity_groups.items():
            if not cve_list:
                continue
                
            filename = f"cve_{year}_{severity.lower()}.md"
            filepath = KNOWLEDGE_DIR / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# CVE Database {year} - {severity} Severity\n\n")
                f.write(f"Total CVEs: {len(cve_list)}\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n\n")
                f.write(f"## Security Vulnerabilities - {severity} Risk Level\n\n")
                f.write(f"This document contains {severity.lower()} severity vulnerabilities discovered in {year}.\n")
                f.write(f"These vulnerabilities require immediate attention and remediation.\n\n")
                
                for cve in cve_list:
                    f.write(cve["text"])
                    f.write("\n")
            
            print(f"Saved {len(cve_list)} {severity} CVEs to {filename}")
    
    def create_cve_summary(self, year):
        """Create a summary file for CVE data"""
        summary_file = KNOWLEDGE_DIR / f"cve_{year}_summary.md"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# CVE Summary for {year}\n\n")
            f.write(f"## Overview\n\n")
            f.write(f"This knowledge base contains Common Vulnerabilities and Exposures (CVE) data for {year}.\n")
            f.write(f"The data is organized by severity levels to help prioritize security responses.\n\n")
            
            f.write(f"## Severity Levels\n\n")
            f.write(f"- **CRITICAL**: Vulnerabilities with CVSS scores 9.0-10.0\n")
            f.write(f"- **HIGH**: Vulnerabilities with CVSS scores 7.0-8.9\n")
            f.write(f"- **MEDIUM**: Vulnerabilities with CVSS scores 4.0-6.9\n")
            f.write(f"- **LOW**: Vulnerabilities with CVSS scores 0.1-3.9\n\n")
            
            f.write(f"## Usage in DeepGaza\n\n")
            f.write(f"This CVE data is automatically loaded into DeepGaza's RAG system.\n")
            f.write(f"You can query for specific vulnerabilities, affected products, or security recommendations.\n\n")
            
            f.write(f"## Example Queries\n\n")
            f.write(f"- \"Show me critical vulnerabilities from {year}\"\n")
            f.write(f"- \"What are the latest SQL injection vulnerabilities?\"\n")
            f.write(f"- \"Find vulnerabilities affecting web applications\"\n")
            f.write(f"- \"Show mitigation strategies for high severity CVEs\"\n\n")

def main():
    print("DeepGaza Alternative CVE Data Downloader")
    print("=======================================")
    
    downloader = AlternativeCVEDownloader()
    
    years = [2024, 2025]
    total_cves = 0
    
    for year in years:
        print(f"\nProcessing year {year}...")
        
        # Try multiple sources
        all_cves = []
        
        # Try MITRE first
        mitre_cves = downloader.download_from_cve_mitre(year)
        all_cves.extend(mitre_cves)
        
        # Try GitHub advisories (requires GITHUB_TOKEN)
        if os.getenv('GITHUB_TOKEN'):
            github_cves = downloader.download_from_github_advisories(year)
            all_cves.extend(github_cves)
        
        # If no data found, create sample data for demonstration
        if not all_cves:
            print(f"No real CVE data found for {year}, creating sample data...")
            sample_cves = downloader.create_sample_cve_data(year)
            all_cves.extend(sample_cves)
        
        # Save to knowledge base
        downloader.save_cves_to_knowledge_base(all_cves, year)
        downloader.create_cve_summary(year)
        
        total_cves += len(all_cves)
        print(f"Completed {year}: {len(all_cves)} CVEs")
    
    print(f"\nTotal CVEs processed: {total_cves}")
    print("CVE data has been saved to the knowledge base!")
    print(f"Files saved to: {KNOWLEDGE_DIR}")

if __name__ == "__main__":
    main()