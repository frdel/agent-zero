## SakanaAI Citation Manager Tool

The `sakana_citation_manager` tool provides comprehensive citation management capabilities for academic research and paper writing.

### Tool Methods

**Main Management Method**:
```
sakana_citation_manager(action="extract", text="", url="", citation_style="apa")
```

**Specialized Methods**:
```
sakana_citation_manager:extract_citations(text="document text", url="https://paper.url")
sakana_citation_manager:format_citations(text="citations", citation_style="apa")
sakana_citation_manager:generate_bibliography(text="citations", citation_style="apa")
sakana_citation_manager:verify_citations(text="citations", url="source_url")
```

### Available Actions

**extract**: Extract citations from text or URL sources
**format**: Format existing citations in specified academic style
**verify**: Verify citation accuracy through web search
**search**: Search for citation information by query
**generate**: Generate formatted bibliography from citations
**validate**: Validate citation completeness and format

### Citation Styles

**APA**: American Psychological Association style (default)
**MLA**: Modern Language Association style
**IEEE**: Institute of Electrical and Electronics Engineers style
**Generic**: Basic structured format for any style

### Extraction Capabilities

**DOI Detection**: Automatically extract DOI-based citations
**URL Recognition**: Identify and process academic URLs (ArXiv, PubMed, IEEE, ACM)
**In-text Citations**: Parse author-year format citations from text
**Metadata Extraction**: Extract title, author, year, and publication information

### Formatting Features

**Style Compliance**: Format citations according to established academic standards
**Complete References**: Generate full bibliographic entries
**Consistent Structure**: Maintain consistent formatting across all citations
**Field Validation**: Ensure required fields are present and properly formatted

### Verification System

**Web Search Verification**: Cross-reference citations with online sources
**Academic Database Priority**: Focus on scholarly and academic sources
**Accuracy Assessment**: Provide confidence levels for citation accuracy
**Source Validation**: Verify publication details and accessibility

### Bibliography Generation

**Alphabetical Sorting**: Automatically sort citations by author/title
**Style-Specific Formatting**: Apply appropriate citation style rules
**Complete Listings**: Generate comprehensive bibliography sections
**Metadata Preservation**: Maintain all citation information

### Usage Guidelines

**Citation Extraction**:
1. Provide text with embedded citations or URLs to academic papers
2. Tool automatically identifies and extracts citation information
3. Review extracted citations for completeness and accuracy
4. Use verification to confirm citation details

**Bibliography Creation**:
1. Extract or input citations from research sources
2. Choose appropriate citation style for target publication
3. Generate formatted bibliography with consistent styling
4. Validate completeness before final use

**Citation Management Workflow**:
1. Extract citations during literature review process
2. Verify accuracy of important citations
3. Format citations according to publication requirements
4. Generate final bibliography for paper submission

### Integration with Research Tools

**Research Tool Integration**: Automatically process citations from `sakana_research` outputs
**Paper Writer Integration**: Provide formatted citations for `sakana_paper_writer`
**Memory Integration**: Store citations in research memory for future reference
**Session Tracking**: Track citation work as part of research sessions

### Quality Assurance

**Completeness Validation**: Check for required citation fields
**Format Verification**: Ensure proper citation structure and style
**Duplicate Detection**: Identify and handle duplicate citations
**Error Reporting**: Provide detailed feedback on citation issues

### Best Practices

**Systematic Collection**: Extract citations systematically during research
**Regular Verification**: Verify important citations for accuracy
**Style Consistency**: Use consistent citation style throughout work
**Backup Management**: Save citation libraries to research memory

### Academic Standards

**Professional Formatting**: Adhere to established academic citation standards
**Complete Attribution**: Ensure proper credit to original authors
**Accessibility**: Include DOIs and URLs where appropriate
**Currency**: Verify publication dates and current availability