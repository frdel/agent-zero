### regulatory_compliance:
comprehensive regulatory compliance checker for biomedical research
FDA EMA ICH regulatory guidance submission requirements
**Parameters:**
- regulation_type: regulatory authority ("fda", "ema", "ich", "pmda", "hc")
- product_type: product type ("drug", "biologic", "device", "diagnostic", "vaccine")
- development_phase: phase ("preclinical", "phase1", "phase2", "phase3", "nda")
- indication: therapeutic indication or disease area
- jurisdiction: regulatory jurisdiction ("usa", "eu", "japan", "canada", "global")
- compliance_check: check type ("comprehensive", "submission", "gmp", "clinical")
- submission_type: submission type ("ind", "nda", "bla", "cta", "ma")

**Example usage:**
~~~json
{
    "thoughts": [
        "I need to check FDA requirements for Phase 2 drug development",
    ],
    "headline": "Checking FDA Phase 2 regulatory requirements",
    "tool_name": "regulatory_compliance",
    "tool_args": {
        "regulation_type": "fda",
        "product_type": "drug",
        "development_phase": "phase2",
        "indication": "type 2 diabetes",
        "jurisdiction": "usa",
        "compliance_check": "comprehensive"
    }
}
~~~