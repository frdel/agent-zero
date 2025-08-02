### clinical_trials_search:
search ClinicalTrials.gov database for clinical studies
comprehensive trial analysis with multiple filters
**Parameters:**
- condition: disease or condition (e.g., "diabetes", "cancer")
- intervention: treatment or intervention (e.g., "metformin", "placebo")
- sponsor: study sponsor organization
- phase: trial phase ("Phase 1", "Phase 2", "Phase 3", "Phase 4")
- status: trial status ("Recruiting", "Completed", "Active", "Terminated")
- country: country where trial is conducted
- max_results: maximum results (default 20, max 100)

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to find active clinical trials for Alzheimer's disease",
    ],
    "headline": "Searching for active Alzheimer's clinical trials",
    "tool_name": "clinical_trials_search",
    "tool_args": {
        "condition": "Alzheimer's disease",
        "status": "Recruiting",
        "phase": "Phase 3",
        "country": "United States",
        "max_results": 30
    }
}
~~~