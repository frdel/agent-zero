#!/usr/bin/env python3
"""
CVE Data Downloader for DeepGaza
Downloads CVE data from NIST NVD API for 2024 and 2025
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

# NIST NVD API endpoint
NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Output directory
KNOWLEDGE_DIR = Path("../knowledge/cybersecurity/main")

class CVEDownloader:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"apiKey": api_key})
        
        # Rate limiting: 5 requests per 30 seconds without API key
        # 50 requests per 30 seconds with API key
        self.rate_limit = 50 if api_key else 5
        self.rate_window = 30
        self.last_requests = []
    
    def rate_limit_check(self):
        """Implement rate limiting"""
        now = time.time()
        # Remove requests older than rate_window
        self.last_requests = [req_time for req_time in self.last_requests 
                             if now - req_time < self.rate_window]
        
        if len(self.last_requests) >= self.rate_limit:
            sleep_time = self.rate_window - (now - self.last_requests[0]) + 1
            print(f"Rate limit reached. Sleeping for {sleep_time:.1f} seconds...")
            time.sleep(sleep_time)
        
        self.last_requests.append(now)
    
    def download_cves_by_year(self, year):
        """Download all CVEs for a specific year"""
        print(f"Downloading CVEs for year {year}...")
        
        start_date = f"{year}-01-01T00:00:00.000"
        end_date = f"{year}-12-31T23:59:59.999"
        
        all_cves = []
        start_index = 0
        results_per_page = 2000  # Maximum allowed by API
        
        while True:
            self.rate_limit_check()
            
            params = {
                "pubStartDate": start_date,
                "pubEndDate": end_date,
                "startIndex": start_index,
                "resultsPerPage": results_per_page
            }
            
            try:
                print(f"Fetching CVEs {start_index} to {start_index + results_per_page}...")
                response = self.session.get(NVD_API_BASE, params=params, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                vulnerabilities = data.get("vulnerabilities", [])
                
                if not vulnerabilities:
                    break
                
                all_cves.extend(vulnerabilities)
                
                # Check if we got all results
                total_results = data.get("totalResults", 0)
                if start_index + len(vulnerabilities) >= total_results:
                    break
                
                start_index += len(vulnerabilities)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data: {e}")
                time.sleep(5)  # Wait before retry
                continue
        
        print(f"Downloaded {len(all_cves)} CVEs for {year}")
        return all_cves
    
    def format_cve_for_rag(self, cve_data):
        """Format CVE data for RAG system"""
        cve = cve_data.get("cve", {})
        cve_id = cve.get("id", "Unknown")
        
        # Extract basic info
        published = cve.get("published", "")
        modified = cve.get("lastModified", "")
        
        # Extract descriptions
        descriptions = cve.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        
        # Extract CVSS scores
        metrics = cve.get("metrics", {})
        cvss_v3 = metrics.get("cvssMetricV31", [])
        cvss_v2 = metrics.get("cvssMetricV2", [])
        
        severity = "Unknown"
        base_score = "N/A"
        
        if cvss_v3:
            cvss_data = cvss_v3[0].get("cvssData", {})
            severity = cvss_data.get("baseSeverity", "Unknown")
            base_score = cvss_data.get("baseScore", "N/A")
        elif cvss_v2:
            cvss_data = cvss_v2[0].get("cvssData", {})
            severity = cvss_data.get("baseSeverity", "Unknown")
            base_score = cvss_data.get("baseScore", "N/A")
        
        # Extract CPE configurations
        configurations = cve.get("configurations", [])
        affected_products = []
        
        for config in configurations:
            nodes = config.get("nodes", [])
            for node in nodes:
                cpe_matches = node.get("cpeMatch", [])
                for cpe_match in cpe_matches:
                    if cpe_match.get("vulnerable", False):
                        cpe_name = cpe_match.get("criteria", "")
                        affected_products.append(cpe_name)
        
        # Extract references
        references = cve.get("references", [])
        ref_urls = [ref.get("url", "") for ref in references]
        
        # Format for RAG
        formatted_text = f"""
CVE ID: {cve_id}
Published: {published}
Last Modified: {modified}
Severity: {severity}
CVSS Base Score: {base_score}

Description:
{description}

Affected Products:
{chr(10).join(affected_products[:10])}  # Limit to first 10 products

References:
{chr(10).join(ref_urls[:5])}  # Limit to first 5 references

---
"""
        
        return {
            "cve_id": cve_id,
            "severity": severity,
            "base_score": base_score,
            "published": published,
            "text": formatted_text
        }
    
    def save_cves_to_knowledge_base(self, cves, year):
        """Save CVEs to knowledge base files"""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        
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
                
                for cve in cve_list:
                    f.write(cve["text"])
                    f.write("\n")
            
            print(f"Saved {len(cve_list)} {severity} CVEs to {filename}")
    
    def download_and_save_year(self, year):
        """Download and save CVEs for a specific year"""
        cves = self.download_cves_by_year(year)
        if cves:
            self.save_cves_to_knowledge_base(cves, year)
        return len(cves)

def main():
    print("DeepGaza CVE Data Downloader")
    print("============================")
    
    # You can get a free API key from: https://nvd.nist.gov/developers/request-an-api-key
    api_key = os.getenv("NVD_API_KEY")  # Optional but recommended
    
    if api_key:
        print("Using API key for faster downloads")
    else:
        print("No API key found. Using rate-limited access.")
        print("Consider getting an API key from: https://nvd.nist.gov/developers/request-an-api-key")
    
    downloader = CVEDownloader(api_key)
    
    years = [2024, 2025]
    total_cves = 0
    
    for year in years:
        try:
            count = downloader.download_and_save_year(year)
            total_cves += count
            print(f"Completed {year}: {count} CVEs")
        except Exception as e:
            print(f"Error processing year {year}: {e}")
    
    print(f"\nTotal CVEs downloaded: {total_cves}")
    print("CVE data has been saved to the knowledge base!")

if __name__ == "__main__":
    main()