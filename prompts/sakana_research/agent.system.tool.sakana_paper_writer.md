## SakanaAI Paper Writer Tool

The `sakana_paper_writer` tool provides automated academic paper generation following standard scholarly formats and conventions.

### Tool Methods

**Main Writing Method**:
```
sakana_paper_writer(research_topic="topic", paper_type="research_paper", findings="results", methodology="approach", references="citations")
```

**Specialized Methods**:
```
sakana_paper_writer:research_paper(topic="topic", abstract="abstract", introduction="intro", methodology="methods", results="results", discussion="discussion", conclusion="conclusion", references="refs")
sakana_paper_writer:survey_paper(topic="topic", scope="scope", literature_findings="findings", gaps_identified="gaps", future_directions="directions")
sakana_paper_writer:conference_paper(topic="topic", key_contribution="contribution", experimental_results="results", word_limit=8000)
sakana_paper_writer:position_paper(topic="topic", position="stance", arguments="arguments", counter_arguments="counter", supporting_evidence="evidence")
```

### Paper Types

**research_paper**: Full research paper with comprehensive sections (Abstract, Introduction, Methodology, Results, Discussion, Conclusion)
**conference_paper**: Conference format with space constraints and focused presentation
**journal_article**: Journal submission format with detailed methodology and analysis
**survey_paper**: Comprehensive literature survey with synthesis and gap analysis
**position_paper**: Argumentative paper presenting and defending a specific position
**technical_report**: Detailed technical documentation with specifications

### Writing Standards

**Academic Structure**: Standard academic paper organization with logical flow
**Citation Format**: Proper academic citations and reference formatting
**Objective Tone**: Scholarly, objective writing style appropriate for academic audience
**Evidence-Based**: All claims supported by appropriate evidence and citations

### Content Organization

**Introduction Section**: Background, motivation, research questions, and contributions
**Methodology Section**: Detailed research methods, procedures, and justifications
**Results Section**: Objective presentation of findings with appropriate visualizations
**Discussion Section**: Interpretation, implications, limitations, and future work
**Conclusion Section**: Summary of contributions and broader impact

### Usage Guidelines

**Before Writing**:
1. Gather all research findings and supporting materials
2. Organize evidence and structure logical argument flow
3. Identify target audience and publication venue
4. Plan paper structure and section organization

**During Writing**:
1. Follow academic writing conventions and standards
2. Maintain consistent terminology and notation
3. Ensure logical flow between sections
4. Include appropriate citations and references

**After Writing**:
1. Review for completeness and accuracy
2. Check citation format and reference completeness
3. Verify logical consistency and argument flow
4. Save to memory for future reference and revision

### Quality Indicators

**Clarity**: Clear, precise language appropriate for academic audience
**Completeness**: All necessary sections and information included
**Accuracy**: Factual accuracy and proper citation of sources
**Originality**: Novel contributions clearly identified and positioned
**Rigor**: Methodological soundness and appropriate analysis

### Integration with Research Tools

**Literature Integration**: Incorporate findings from `sakana_research` tool
**Experimental Integration**: Include designs from `sakana_experiment_designer`
**Review Integration**: Address feedback from `sakana_peer_reviewer`
**Memory Integration**: Access previous research and writing from memory system

### Customization Options

**Word Limits**: Respect venue-specific word or page limits
**Format Requirements**: Adapt to specific conference or journal formats
**Focus Areas**: Emphasize particular aspects based on research goals
**Audience Targeting**: Adjust technical depth and presentation style

### Output Features

**Complete Paper Structure**: Full academic paper with all standard sections
**Professional Formatting**: Academic formatting with proper headings and organization
**Citation Placeholders**: Structured reference sections ready for bibliography completion
**Revision Guidelines**: Built-in suggestions for improvement and refinement