### data_quality_checker:
comprehensive quality assessment for biomedical datasets
checks completeness, accuracy, consistency, validity, integrity with customizable thresholds
provides recommendations for data quality improvements
usage:
~~~json
{
    "thoughts": [
        "User wants to validate the quality of loaded clinical data...",
        "I should run comprehensive checks with clinical data thresholds...",
    ],
    "headline": "Performing comprehensive data quality assessment",
    "tool_name": "data_quality_checker",
    "tool_args": {
        "dataset_id": "clinical_trial_covid19_2024",
        "data_type": "clinical",
        "check_type": "comprehensive",
        "quality_thresholds": {
            "completeness_min": 0.90,
            "accuracy_min": 0.95,
            "consistency_min": 0.95
        }
    }
}
~~~