# Advanced Acunetix API for Professional Web Application Security Testing

## Overview
This document provides comprehensive guidance for using Acunetix API to perform precise and automated security testing of HTTP applications, WebSocket services, ASMX web services, and various API endpoints.

## Acunetix API Configuration

### API Authentication
```python
import requests
import json
import time
from urllib.parse import urljoin

class AcunetixAPI:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Auth': api_key,
            'Content-Type': 'application/json'
        })
```

### API Endpoints Structure
```bash
# Base Acunetix API endpoints
GET    /api/v1/info                    # Get version info
GET    /api/v1/targets                 # List targets
POST   /api/v1/targets                 # Add target
GET    /api/v1/scans                   # List scans
POST   /api/v1/scans                   # Start scan
GET    /api/v1/vulnerabilities         # List vulnerabilities
```

## HTTP Application Scanning

### Basic HTTP Target Configuration
```python
class HTTPScanner:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def create_target(self, url, description=""):
        target_data = {
            "address": url,
            "description": description,
            "criticality": 30
        }
        
        response = self.api.session.post(
            f"{self.api.base_url}/api/v1/targets",
            json=target_data
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            raise Exception(f"Failed to create target: {response.text}")
```

## WebSocket (WSS) Testing

### WebSocket Target Configuration
```python
class WebSocketScanner:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def create_websocket_target(self, ws_url, http_url=None):
        if not http_url:
            http_url = ws_url.replace('ws://', 'http://').replace('wss://', 'https://')
        
        target_data = {
            "address": http_url,
            "description": f"WebSocket application: {ws_url}",
            "criticality": 30
        }
        
        response = self.api.session.post(
            f"{self.api.base_url}/api/v1/targets",
            json=target_data
        )
        
        target = response.json()
        target_id = target["target_id"]
        
        # Configure WebSocket specific settings
        ws_config = {
            "websocket_urls": [ws_url],
            "websocket_enabled": True,
            "websocket_message_patterns": [
                '{"action":"test","data":"FUZZ"}',
                '{"type":"message","content":"FUZZ"}',
                '{"command":"FUZZ","params":{}}'
            ]
        }
        
        self.api.session.patch(
            f"{self.api.base_url}/api/v1/targets/{target_id}/configuration",
            json=ws_config
        )
        
        return target_id
```

## ASMX Web Services Testing

### ASMX Service Configuration
```python
class ASMXScanner:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def create_asmx_target(self, asmx_url):
        target_data = {
            "address": asmx_url,
            "description": f"ASMX Web Service: {asmx_url}",
            "criticality": 30
        }
        
        response = self.api.session.post(
            f"{self.api.base_url}/api/v1/targets",
            json=target_data
        )
        
        target = response.json()
        target_id = target["target_id"]
        
        # Configure ASMX specific settings
        asmx_config = {
            "web_services": {
                "enabled": True,
                "wsdl_urls": [f"{asmx_url}?WSDL"],
                "soap_actions": "auto_discover"
            },
            "custom_headers": [
                {"name": "SOAPAction", "value": ""},
                {"name": "Content-Type", "value": "text/xml; charset=utf-8"}
            ]
        }
        
        self.api.session.patch(
            f"{self.api.base_url}/api/v1/targets/{target_id}/configuration",
            json=asmx_config
        )
        
        return target_id
```

## REST API Testing

### REST API Configuration
```python
class RESTAPIScanner:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def create_api_target(self, api_base_url, openapi_spec_url=None):
        target_data = {
            "address": api_base_url,
            "description": f"REST API: {api_base_url}",
            "criticality": 30
        }
        
        response = self.api.session.post(
            f"{self.api.base_url}/api/v1/targets",
            json=target_data
        )
        
        target = response.json()
        target_id = target["target_id"]
        
        # Configure API specific settings
        api_config = {
            "api_testing": {
                "enabled": True,
                "openapi_spec_url": openapi_spec_url,
                "api_definition_import": True
            },
            "custom_headers": [
                {"name": "Accept", "value": "application/json"},
                {"name": "Content-Type", "value": "application/json"}
            ]
        }
        
        if openapi_spec_url:
            api_config["import_openapi"] = True
        
        self.api.session.patch(
            f"{self.api.base_url}/api/v1/targets/{target_id}/configuration",
            json=api_config
        )
        
        return target_id
```

## Advanced Scanning Techniques

### Custom Vulnerability Checks
```python
class CustomVulnerabilityScanner:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def configure_advanced_sql_injection(self, target_id):
        sqli_config = {
            "sql_injection": {
                "enabled": True,
                "test_types": [
                    "union_based",
                    "boolean_based", 
                    "time_based",
                    "error_based",
                    "second_order"
                ],
                "database_types": ["mysql", "postgresql", "mssql", "oracle"],
                "advanced_payloads": True
            }
        }
        
        return self.api.session.patch(
            f"{self.api.base_url}/api/v1/targets/{target_id}/configuration",
            json=sqli_config
        )
```

## Scan Management and Monitoring

### Scan Lifecycle Management
```python
class ScanManager:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def get_scan_status(self, scan_id):
        response = self.api.session.get(
            f"{self.api.base_url}/api/v1/scans/{scan_id}"
        )
        return response.json()
    
    def wait_for_scan_completion(self, scan_id, timeout=3600):
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_scan_status(scan_id)
            current_status = status.get("current_session", {}).get("status")
            
            if current_status in ["completed", "failed", "aborted"]:
                return status
            
            print(f"Scan {scan_id} status: {current_status}")
            time.sleep(30)
        
        raise TimeoutError(f"Scan {scan_id} did not complete within {timeout} seconds")
```

## Vulnerability Analysis and Reporting

### Vulnerability Extraction
```python
class VulnerabilityAnalyzer:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
    
    def get_vulnerabilities(self, target_id=None, severity=None):
        params = {}
        if target_id:
            params["q"] = f"target_id:{target_id}"
        if severity:
            params["q"] = f"{params.get('q', '')} severity:{severity}".strip()
        
        response = self.api.session.get(
            f"{self.api.base_url}/api/v1/vulnerabilities",
            params=params
        )
        return response.json()
    
    def generate_vulnerability_report(self, target_id, report_format="pdf"):
        report_data = {
            "template_id": "11111111-1111-1111-1111-111111111111",
            "source": {
                "list_type": "targets",
                "id_list": [target_id]
            },
            "format": report_format
        }
        
        response = self.api.session.post(
            f"{self.api.base_url}/api/v1/reports",
            json=report_data
        )
        return response.json()
```

## Automated Scanning Workflows

### Complete Scanning Pipeline
```python
class AutomatedScanningPipeline:
    def __init__(self, acunetix_api):
        self.api = acunetix_api
        self.http_scanner = HTTPScanner(acunetix_api)
        self.ws_scanner = WebSocketScanner(acunetix_api)
        self.asmx_scanner = ASMXScanner(acunetix_api)
        self.api_scanner = RESTAPIScanner(acunetix_api)
        self.scan_manager = ScanManager(acunetix_api)
        self.vuln_analyzer = VulnerabilityAnalyzer(acunetix_api)
    
    def comprehensive_application_scan(self, app_config):
        results = {}
        
        # HTTP Application Scan
        if app_config.get("http_url"):
            print("Starting HTTP application scan...")
            http_target_id = self.http_scanner.create_target(
                app_config["http_url"], 
                "HTTP Application Scan"
            )
            
            http_scan = self.api.session.post(
                f"{self.api.base_url}/api/v1/scans",
                json={"target_id": http_target_id, "profile_id": "11111111-1111-1111-1111-111111111111"}
            ).json()
            
            results["http_scan"] = {
                "target_id": http_target_id,
                "scan_id": http_scan["scan_id"]
            }
        
        return results
```

## Best Practices

### Performance Optimization
```python
optimization_config = {
    "crawling_settings": {
        "max_crawl_depth": 10,
        "max_crawl_pages": 1000,
        "crawl_speed": "fast"
    },
    "scanning_settings": {
        "max_scan_time": 7200,
        "concurrent_connections": 20,
        "request_delay": 0
    }
}
```

### Security Best Practices
```python
security_config = {
    "api_rate_limiting": True,
    "secure_communication": True,
    "audit_logging": True,
    "access_control": {
        "ip_whitelist": ["192.168.1.0/24"],
        "api_key_rotation": True
    }
}
```

## Conclusion

This comprehensive guide provides professional-level expertise for using Acunetix API to perform precise security testing across various application types:

- HTTP Applications: Complete web application security testing
- WebSocket Services: Real-time communication security assessment  
- ASMX Web Services: SOAP-based service vulnerability testing
- REST APIs: Modern API security assessment
- Custom vulnerability detection and automated workflows

These techniques enable comprehensive automated security testing with professional-grade precision and coverage.
