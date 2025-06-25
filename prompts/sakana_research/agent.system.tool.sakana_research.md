## SakanaAI Research Tool

The `sakana_research` tool provides comprehensive research capabilities implementing AI-Scientist methodology for automated scientific research.

### Tool Methods

**Main Research Method**:
```
sakana_research(research_query="your research topic", research_type="comprehensive", depth="medium", focus_areas="area1,area2", max_papers=20)
```

**Specialized Methods**:
```
sakana_research:literature_review(topic="research area", max_papers=15)
sakana_research:paper_analysis(paper_url="https://...", analysis_focus="methodology,results,limitations")  
sakana_research:research_gap_analysis(domain="field of study", current_knowledge="what is known")
```

### Research Types

**comprehensive**: Full literature review with synthesis and gap analysis
- Best for: Initial research phases, broad topic exploration
- Outputs: Detailed literature synthesis, methodology comparison, future directions

**targeted**: Focused search on specific aspects or questions
- Best for: Specific technical questions, narrow scope investigations
- Outputs: Focused analysis, targeted recommendations

**citation_analysis**: Follow citation chains for deep investigation
- Best for: Understanding research lineage, finding foundational work
- Outputs: Citation network analysis, influence mapping

**trend_analysis**: Identify emerging patterns and developments
- Best for: Understanding field evolution, identifying hot topics
- Outputs: Trend identification, future predictions

**gap_analysis**: Systematic identification of research opportunities
- Best for: Finding novel research directions, thesis topic selection
- Outputs: Gap identification, opportunity assessment

### Depth Levels

**shallow**: Quick overview with top 3-5 sources
**medium**: Balanced analysis with 5-8 key sources (default)
**deep**: Comprehensive investigation with 8+ sources

### Usage Guidelines

**Research Query Formulation**:
- Be specific about research objectives
- Include key terms and concepts
- Specify scope and boundaries
- Consider alternative phrasings

**Focus Areas**:
- Comma-separated list of specific aspects to emphasize
- Examples: "methodology,applications,limitations", "recent work,challenges"
- Leave blank for general coverage

**Paper Analysis**:
- Provide direct URLs to academic papers
- Specify analysis focus areas for targeted insights
- Use for detailed examination of key sources

**Integration with Other Tools**:
- Combine with `memory_save` to store research findings
- Use `call_subordinate` for complex multi-phase research
- Leverage `document_query` for detailed paper examination

### Best Practices

**Before Using**:
1. Define clear research objectives
2. Consider scope and resource constraints  
3. Plan how results will be used
4. Identify key success criteria

**During Research**:
1. Monitor for quality and relevance
2. Adjust parameters based on initial results
3. Save important findings to memory
4. Note areas requiring deeper investigation

**After Research**:
1. Synthesize findings across multiple searches
2. Identify gaps requiring additional investigation
3. Plan follow-up research activities
4. Document lessons learned for future use

### Output Interpretation

**Comprehensive Reports**: Include executive summary, key findings, methodologies, gaps, and future directions

**Source Quality Assessment**: Academic sources prioritized, recency considered, multiple perspectives included

**Research Synthesis**: Findings integrated across sources with critical analysis and evaluation

**Actionable Insights**: Specific recommendations for future research directions and practical applications