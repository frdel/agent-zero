### environment_manager:
manage biomedical research computing environments
create, activate, update virtual environments with biomedical packages and tools
resource allocation and compliance configuration
usage:
~~~json
{
    "thoughts": [
        "User needs a new environment for proteomics analysis...",
        "I should create an environment with appropriate biomedical tools...",
    ],
    "headline": "Creating specialized biomedical research environment",
    "tool_name": "environment_manager",
    "tool_args": {
        "action": "create",
        "environment_name": "proteomics_analysis",
        "config": {
            "type": "python_venv",
            "python_version": "3.11",
            "base_packages": ["biopython", "pandas", "rdkit", "pymol"],
            "biomedical_tools": ["blast+", "muscle", "hmmer"],
            "resource_limits": {
                "max_memory_gb": 16,
                "max_cpu_cores": 8
            },
            "hipaa_compliant": true
        }
    }
}
~~~