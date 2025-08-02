### data_lake_manager:
manage biomedical research data lake - status, indexing, querying, dataset lifecycle
supports large-scale genomics, proteomics, clinical data with metadata management
usage:
~~~json
{
    "thoughts": [
        "User wants to check data lake status and available datasets...",
        "I need to query for proteomics datasets from recent studies...",
    ],
    "headline": "Managing biomedical data lake operations",
    "tool_name": "data_lake_manager",
    "tool_args": {
        "action": "query",
        "query_params": {
            "type": "proteomics",
            "source": "UniProt",
            "date_range": "2024-01-01,2024-01-15"
        }
    }
}
~~~