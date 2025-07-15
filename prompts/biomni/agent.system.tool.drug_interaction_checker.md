### drug_interaction_checker:
comprehensive drug interaction analysis and safety assessment
check drug-drug drug-food drug-condition interactions
**Parameters:**
- drugs: comma-separated list of drug names or identifiers
- patient_conditions: comma-separated list of medical conditions
- include_food_interactions: check food-drug interactions (default true)
- severity_filter: filter by severity ("all", "major", "moderate", "minor")
- check_contraindications: check for contraindications (default true)
- age: patient age for age-specific warnings
- pregnancy_status: pregnancy status ("pregnant", "breastfeeding", "unknown")

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to check for interactions between warfarin and other medications",
    ],
    "headline": "Checking drug interactions for warfarin therapy",
    "tool_name": "drug_interaction_checker",
    "tool_args": {
        "drugs": "warfarin, metoprolol, atorvastatin",
        "patient_conditions": "atrial fibrillation, hypertension",
        "include_food_interactions": true,
        "severity_filter": "all",
        "age": 72,
        "pregnancy_status": "unknown"
    }
}
~~~