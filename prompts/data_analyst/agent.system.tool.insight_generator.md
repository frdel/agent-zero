## Insight Generator Tool Usage Guidelines

### Purpose
The Insight Generator tool employs advanced Tree-of-Thought methodology to create sophisticated analytical insights and automated visualization code, bridging the gap between domain expertise and actionable data science outputs.

### When to Use
- **Advanced Analysis**: After domain detection when you need sophisticated business insights
- **Visualization Planning**: When you need both analytical reasoning and visualization code
- **Multi-Perspective Analysis**: To simulate expert collaboration and debate on data interpretation
- **Automated Code Generation**: For creating publication-ready visualizations with domain context

### Required Parameters
- `csv_path`: Full path to the CSV file being analyzed
- `profile_data`: Data profile from data_profiler_tool (JSON string or dictionary)

### Optional Parameters
- `domain_info`: Domain detection results from domain_detector_tool (enhances analysis quality)
- `model`: OpenAI model to use (default: "gpt-4o")
- `temperature`: Sampling temperature for creativity control (default: 0.2)

### Tool Capabilities
The Insight Generator provides:

#### Tree-of-Thought Analysis
- **Multi-Expert Simulation**: Simulates collaboration between data science experts with different perspectives
- **Systematic Reasoning**: Structured analytical process moving from domain findings to data selection to visualization
- **Expert Debate**: Multiple viewpoints on chart selection and insight interpretation
- **Consensus Building**: Consolidation of expert opinions into final analytical decisions

#### Comprehensive Insight Generation
- **Descriptive Analysis**: Current state understanding with statistical depth
- **Predictive Insights**: Forward-looking analysis with trend identification and forecasting potential
- **Domain-Specific Commentary**: Industry-expert level insights grounded in business context
- **Cross-Dimensional Analysis**: Integration of multiple analytical perspectives

#### Automated Visualization Code
- **Schema-Aware Generation**: Code that respects actual column names and data types
- **Professional Styling**: Implementation of best practices for publication-ready charts
- **Error Handling**: Robust try/catch blocks preventing execution failures
- **Multiple Chart Types**: Support for various visualization approaches based on data characteristics

#### Advanced Code Features
- **Colorblind-Friendly Palettes**: Automatic selection of accessible color schemes
- **Legend Optimization**: Intelligent legend placement and formatting
- **Multi-Series Handling**: Proper techniques for complex data relationships
- **Annotation Integration**: Domain-specific callouts and highlighting

### Usage Examples

#### Basic Insight Generation
```json
{
  "tool": "insight_generator",
  "csv_path": "/path/to/dataset.csv",
  "profile_data": "{\"raw_stats\": {...}, \"semantic_profile\": {...}}"
}
```

#### Enhanced Analysis with Domain Context
```json
{
  "tool": "insight_generator",
  "csv_path": "/path/to/dataset.csv",
  "profile_data": "{\"raw_stats\": {...}, \"semantic_profile\": {...}}",
  "domain_info": "{\"domain\": \"Financial Services\", \"concepts\": [...]}"
}
```

#### Custom Model Configuration
```json
{
  "tool": "insight_generator",
  "csv_path": "/path/to/dataset.csv",
  "profile_data": "{\"raw_stats\": {...}, \"semantic_profile\": {...}}",
  "model": "gpt-4",
  "temperature": 0.3
}
```

### Expected Output
The tool returns comprehensive analytical results including:
- **Generated Insights**: Three-tier analysis (descriptive, predictive, domain-specific)
- **Tree-of-Thought Reasoning**: Complete expert collaboration simulation
- **Visualization Code**: Production-ready Python code for chart creation
- **Implementation Guidance**: Best practices and execution recommendations
- **Integration Instructions**: Steps for using with other analysis tools

### Tree-of-Thought Methodology
The tool implements a sophisticated four-step expert collaboration:

#### Step I: Domain Finding Extraction
- Multiple experts identify core domain insights requiring visualization
- Focus on business-relevant patterns and relationships
- Emphasis on actionable discoveries

#### Step II: Data Relevance Assessment
- Independent column selection by each simulated expert
- Coverage of different analytical perspectives
- Validation against actual schema

#### Step III: Consensus Building
- Expert comparison and debate on data selection
- Convergence on minimal viable dataset
- Quality validation of selected variables

#### Step IV: Visualization Strategy
- Multiple chart type proposals with domain-specific rationale
- Business impact assessment for each visualization approach
- Final selection with comprehensive justification

### Generated Code Features
The tool produces high-quality Python code with:
- **Professional Libraries**: pandas, matplotlib, numpy integration
- **Error Resilience**: Comprehensive exception handling
- **Schema Compliance**: Strict adherence to actual column names
- **Visual Excellence**: Professional styling and formatting
- **Accessibility**: Colorblind-friendly palettes and clear legends
- **Flexibility**: Support for various chart types and data structures

### Best Practices
1. **Sequential Execution**: Run after both data profiler and domain detector for optimal results
2. **Domain Context**: Always provide domain information when available
3. **Code Validation**: Review generated code before execution
4. **Iterative Refinement**: Use insights to guide further analysis questions
5. **Context Preservation**: Maintain analytical context for subsequent tools
6. **Business Focus**: Leverage domain insights for strategic recommendations

### Integration with Other Tools
Insight Generator coordinates with:
- **Data Profiler**: Uses schema and statistical insights as foundation
- **Domain Detector**: Incorporates business context and industry frameworks
- **Chart Creator**: Generated code can be enhanced with additional styling tools

### Advanced Features
- **Adaptive Reasoning**: Adjusts analytical approach based on data characteristics
- **Business Framework Integration**: Incorporates established analytical methodologies
- **Multi-Modal Analysis**: Combines quantitative and qualitative insights
- **Executive Communication**: Generates insights suitable for leadership consumption

### Performance Considerations
- Processing time varies with dataset complexity and model selection
- Higher temperature values increase creativity but may reduce consistency
- Complex schemas require additional reasoning time
- Domain context significantly enhances output quality

### Quality Assurance
- Generated code includes error handling for common data issues
- Schema validation prevents runtime errors
- Business logic validation ensures meaningful insights
- Statistical rigor in all quantitative claims