### clinical_data_analyzer:
comprehensive clinical data analysis and biostatistics
patient cohort analysis statistical modeling outcome prediction
**Parameters:**
- analysis_type: type of analysis ("descriptive", "comparative", "predictive", "survival")
- data_source: path to clinical dataset or description
- outcome_variable: primary outcome variable for analysis
- covariates: comma-separated list of covariate variables
- stratify_by: variable to stratify analysis (e.g., treatment group)
- statistical_test: test to perform ("auto", "ttest", "chi2", "anova", "logrank")
- confidence_level: confidence level (0.90-0.99, default 0.95)
- generate_plots: whether to generate visualization plots

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to analyze patient outcomes by treatment group",
    ],
    "headline": "Performing comparative analysis of treatment outcomes",
    "tool_name": "clinical_data_analyzer",
    "tool_args": {
        "analysis_type": "comparative",
        "data_source": "clinical_trial_data.csv",
        "outcome_variable": "cv_event",
        "stratify_by": "treatment_group",
        "statistical_test": "auto",
        "confidence_level": 0.95,
        "generate_plots": true
    }
}
~~~