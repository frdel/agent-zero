## Domain Detector Tool Usage Guidelines

### Purpose
The Domain Detector tool provides intelligent business domain identification and context-aware analysis, transforming raw data profiles into industry-specific insights with relevant business frameworks and analytical approaches.

### When to Use
- **After Data Profiling**: Run immediately after data profiler to add business context
- **Industry Identification**: When you need to understand the business domain of unknown datasets
- **Context Enhancement**: To apply domain-specific analytical frameworks and concepts
- **Business Translation**: To convert technical data insights into business-relevant analysis

### Required Parameters
- `profile_data`: Data profile from data_profiler_tool (JSON string or dictionary object)

### Optional Parameters
- `max_cycles`: Maximum improvement cycles for iterative refinement (default: 3)

### Tool Capabilities
The Domain Detector provides:

#### Intelligent Domain Recognition
- **Industry Classification**: Automatic identification of business domains using Wikipedia taxonomy
- **Context Analysis**: Deep understanding of data patterns within industry frameworks
- **Definition Provision**: Clear explanations of identified domains with authoritative references
- **Confidence Assessment**: Quality scores for domain identification accuracy

#### Concept Extraction
- **Business Concepts**: Identification of 4-6 core concepts relevant to the detected domain
- **Framework Application**: Integration of established business analysis frameworks (SWOT, Porter's 5 Forces, etc.)
- **Metric Identification**: Recognition of key performance indicators and business metrics
- **Relationship Mapping**: Understanding of concept interconnections and hierarchies

#### Advanced Analysis Generation
- **Descriptive Insights**: Current state analysis with statistical rigor
- **Predictive Modeling**: Forward-looking analysis with trend identification
- **Domain-Specific Commentary**: Industry-expert level insights and recommendations
- **Business Intelligence**: Strategic recommendations grounded in domain expertise

#### Iterative Refinement
- **Quality Evaluation**: Multi-dimensional scoring of analysis quality
- **Self-Reflection**: Automatic identification of weaknesses and improvement areas
- **Iterative Enhancement**: Continuous improvement through feedback loops
- **Convergence Detection**: Intelligent stopping when quality thresholds are met

### Usage Examples

#### Basic Domain Detection
```json
{
  "tool": "domain_detector",
  "profile_data": "{\"raw_stats\": {...}, \"semantic_profile\": {...}}"
}
```

#### Intensive Analysis with More Cycles
```json
{
  "tool": "domain_detector",
  "profile_data": "{\"raw_stats\": {...}, \"semantic_profile\": {...}}",
  "max_cycles": 5
}
```

### Expected Output
The tool returns comprehensive domain analysis including:
- **Domain Identification**: Precise industry/domain label with definition
- **Core Concepts**: 4-6 key business concepts relevant to the domain
- **Multi-Faceted Analysis**: Descriptive, predictive, and domain-specific insights
- **Quality Metrics**: Scoring across correctness, relevance, coverage, insight quality, novelty, and depth
- **Analysis History**: Iteration tracking showing improvement progression
- **Actionable Recommendations**: Next steps for deeper analysis

### Quality Scoring Framework
The tool evaluates analysis across six dimensions:
- **Correctness (1-4)**: Factual accuracy of domain identification
- **Relevance (1-4)**: Correspondence between concepts and actual data
- **Coverage (1-4)**: Completeness of concept coverage for the domain
- **Insightfulness (1-4)**: Practical value and actionability of insights
- **Novelty (1-4)**: Discovery of non-obvious patterns and relationships
- **Depth (1-4)**: Analysis of root causes and complex interactions

### Integration with Other Tools
Domain Detector output enhances:
- **Insight Generator**: Provides domain context for sophisticated analytical reasoning
- **Chart Creator**: Informs visualization choices with industry-appropriate chart types
- **Business Reporting**: Supplies executive-level insights and strategic recommendations

### Best Practices
1. **Sequential Workflow**: Always run after data profiler for optimal context
2. **Quality Monitoring**: Review quality scores to ensure analysis meets standards
3. **Iterative Approach**: Allow multiple cycles for complex or ambiguous domains
4. **Context Preservation**: Save domain analysis results for downstream tools
5. **Validation**: Cross-check domain identification with your business knowledge
6. **Concept Utilization**: Leverage identified concepts for targeted business questions

### Advanced Features
- **Memory System**: Maintains context across improvement cycles
- **Adaptive Refinement**: Focuses improvement efforts on lowest-scoring dimensions
- **Business Framework Integration**: Automatically applies relevant analytical frameworks
- **Executive Perspective**: Generates insights suitable for senior leadership consumption

### Performance Optimization
- **Early Termination**: Stops iteration when quality thresholds are achieved
- **Focused Improvement**: Targets specific weakness areas rather than global refinement
- **Context Efficiency**: Maintains minimal memory footprint while preserving essential insights
- **Convergence Detection**: Identifies when additional cycles provide diminishing returns

### Error Handling
- Graceful degradation when LLM responses are malformed
- Default domain assignment when detection fails
- Fallback analysis generation for edge cases
- Comprehensive error reporting with actionable recommendations