## Data Profiler Tool Usage Guidelines

### Purpose
The Data Profiler tool provides comprehensive analysis of CSV datasets, combining statistical profiling with LLM-enhanced semantic understanding to create detailed data profiles suitable for advanced analytics.

### When to Use
- **Initial Data Exploration**: Always run this tool first when analyzing any new dataset
- **Data Quality Assessment**: Before proceeding with analysis to understand data completeness and quality
- **Schema Understanding**: To comprehend data structure, types, and relationships
- **Baseline Creation**: To establish a foundation for domain detection and insight generation

### Required Parameters
- `csv_path`: Full path to the CSV file to analyze

### Optional Parameters
- `max_rows`: Maximum number of rows to sample for analysis (default: 1000, use larger values for comprehensive profiling)

### Tool Capabilities
The Data Profiler provides:

#### Statistical Analysis
- **Data Type Detection**: Intelligent inference of column data types (numeric, categorical, datetime, text)
- **Distribution Analysis**: Statistical summaries including min, max, mean, median, quartiles
- **Quality Metrics**: Missing value counts, uniqueness ratios, and data completeness assessment
- **Sample Extraction**: Representative examples from each column for context

#### Semantic Understanding
- **Relationship Detection**: Identification of functional dependencies and mathematical relationships
- **Hierarchical Structure**: Recognition of parent-child relationships and data hierarchies
- **Time Series Identification**: Detection of temporal patterns and time-based structures
- **Key Detection**: Identification of potential primary and foreign key relationships

#### Business Context
- **Unit Detection**: Recognition of measurement units (currency, percentages, quantities)
- **Domain Hints**: Preliminary indicators of business domain and industry context
- **Aggregation Patterns**: Detection of subtotals, summaries, and calculated fields

### Usage Examples

#### Basic Data Profiling
```json
{
  "tool": "data_profiler",
  "csv_path": "/path/to/dataset.csv"
}
```

#### Comprehensive Profiling for Large Datasets
```json
{
  "tool": "data_profiler", 
  "csv_path": "/path/to/large_dataset.csv",
  "max_rows": 5000
}
```

### Expected Output
The tool returns a comprehensive profile including:
- **File metadata** (path, row counts, column counts)
- **Column analysis** with data types, statistics, and examples
- **Data quality assessment** with missing value analysis
- **Structural insights** including relationships and patterns
- **Semantic enrichment** with business context hints

### Integration with Other Tools
The Data Profiler output serves as input for:
- **Domain Detector**: Use `profile_data` from this tool's output
- **Insight Generator**: Profile data provides schema and context for analysis
- **Chart Creator**: Column information guides visualization recommendations

### Best Practices
1. **Always profile first**: Run data profiler before any other analysis tools
2. **Adjust sampling**: For very large datasets, increase `max_rows` for better accuracy
3. **Review quality**: Pay attention to missing values and data quality indicators
4. **Preserve output**: Save the profile data for use with subsequent tools
5. **Validate assumptions**: Use the semantic insights to verify your understanding of the data

### Error Handling
- Verify CSV file exists at the specified path
- Ensure file is properly formatted and readable
- Check for sufficient system memory for large datasets
- Validate column headers and data consistency

### Performance Considerations
- Large files are automatically sampled to maintain performance
- Complex datasets with many columns may require increased processing time
- Memory usage scales with dataset size and complexity
- Consider breaking very large datasets into chunks for analysis