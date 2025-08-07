### biomarker_analyzer:
comprehensive biomarker discovery and validation analysis
clinical biomarker assessment feature selection statistical analysis
**Parameters:**
- analysis_type: analysis type ("discovery", "validation", "clinical_utility")
- biomarker_data: path to biomarker dataset or description
- outcome_variable: clinical outcome or phenotype of interest
- biomarker_type: type of biomarkers ("protein", "genomic", "metabolomic", "imaging")
- study_design: study design ("case_control", "cohort", "cross_sectional")
- validation_cohort: include validation cohort analysis (default false)
- statistical_method: method ("auto", "univariate", "multivariate", "machine_learning")
- multiple_testing_correction: correction ("fdr", "bonferroni", "none")
- effect_size_threshold: minimum effect size (default 0.5)

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to discover protein biomarkers for cardiovascular disease",
    ],
    "headline": "Discovering protein biomarkers for cardiovascular disease",
    "tool_name": "biomarker_analyzer",
    "tool_args": {
        "analysis_type": "discovery",
        "biomarker_data": "protein_expression_data.csv",
        "outcome_variable": "cardiovascular_event",
        "biomarker_type": "protein",
        "study_design": "case_control",
        "statistical_method": "machine_learning",
        "multiple_testing_correction": "fdr"
    }
}
~~~