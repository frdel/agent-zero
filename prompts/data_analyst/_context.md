# Data Analyst Profile Documentation

## Overview

The `data_analyst` profile transforms Agent Zero into a specialized data analysis expert with advanced statistical capabilities, business intelligence expertise, and professional visualization skills. This profile integrates sophisticated D2D_Data2Dashboard analytical capabilities into Agent Zero's framework.

## Profile Capabilities

### Core Competencies
- **Advanced Data Profiling**: Comprehensive analysis of CSV datasets with statistical and semantic insights
- **Domain Detection**: Intelligent identification of business contexts and industry-specific patterns
- **Insight Generation**: Tree-of-Thought analytical reasoning for sophisticated business intelligence
- **Professional Visualization**: Publication-ready charts with consistent styling and accessibility compliance

### Specialized Tools

#### 1. Data Profiler Tool (`data_profiler`)
- **Purpose**: Comprehensive CSV dataset analysis and profiling
- **Key Features**:
  - Statistical summarization with distribution analysis
  - Data type inference and validation
  - Quality assessment including missing values and outliers
  - Relationship detection and pattern recognition
  - LLM-enhanced semantic understanding

#### 2. Domain Detector Tool (`domain_detector`)
- **Purpose**: Business domain identification and context-aware analysis
- **Key Features**:
  - Automatic industry classification using Wikipedia taxonomy
  - Core business concept extraction (4-6 key concepts per domain)
  - Multi-dimensional analysis (descriptive, predictive, domain-specific)
  - Iterative refinement with quality scoring
  - Business framework integration (SWOT, Porter's 5 Forces, etc.)

#### 3. Insight Generator Tool (`insight_generator`)
- **Purpose**: Advanced analytical reasoning with automated visualization code generation
- **Key Features**:
  - Tree-of-Thought methodology with multi-expert simulation
  - Schema-aware analysis that respects actual data structure
  - Automated Python code generation for visualizations
  - Domain-specific insight synthesis
  - Professional code with error handling and best practices

#### 4. Chart Creator Tool (`chart_creator`)
- **Purpose**: Professional-grade data visualization creation
- **Key Features**:
  - Eight chart types (bar, line, scatter, pie, heatmap, histogram, box, violin)
  - Colorblind-friendly palette selection
  - Publication-ready output (300 DPI)
  - Consistent professional styling
  - Accessibility compliance and clear legends

## Usage Workflow

### Standard Analysis Process
1. **Data Profiling**: Start with `data_profiler` to understand structure and quality
2. **Domain Detection**: Use `domain_detector` to identify business context
3. **Insight Generation**: Apply `insight_generator` for sophisticated analysis
4. **Visualization**: Create charts with `chart_creator` for presentation

## Configuration and Setup

### Activating the Profile
To use the data analyst profile, set the Agent Zero configuration:
```json
{
  "agent_prompts_subdir": "data_analyst"
}
```

### Required Dependencies
The profile requires additional Python packages (automatically added to requirements.txt):
- `pandas>=1.5.0` - Data manipulation and analysis
- `matplotlib>=3.6.0` - Basic plotting and visualization
- `seaborn>=0.12.0` - Statistical data visualization
- `numpy>=1.24.0` - Numerical computing
- `scikit-learn>=1.2.0` - Machine learning and statistical analysis
- `openai>=1.0.0` - OpenAI API integration

### Environment Variables
Ensure the following environment variables are configured:
- `OPENAI_API_KEY` - Required for LLM-enhanced analysis and insight generation

## Advanced Features

### Tree-of-Thought Analysis
The insight generator employs a sophisticated multi-expert simulation:
- **Expert Collaboration**: Simulates multiple data science experts with different perspectives
- **Systematic Reasoning**: Four-step process from domain findings to visualization decisions
- **Consensus Building**: Expert debate and consolidation for optimal analysis choices
- **Domain Integration**: Business context influences all analytical decisions

### Quality Assurance Framework
All tools implement comprehensive quality scoring:
- **Correctness**: Factual accuracy of domain and technical analysis
- **Relevance**: Alignment between insights and actual data characteristics
- **Coverage**: Completeness of analysis across all important data dimensions
- **Insightfulness**: Practical value and actionability of generated insights
- **Novelty**: Discovery of non-obvious patterns and relationships
- **Depth**: Analysis of root causes and complex variable interactions

## Integration with Agent Zero

### Tool Registration
All data analysis tools are automatically registered with Agent Zero's tool system and available through the standard tool invocation interface.

### Professional Output Standards
- **Publication Ready**: All visualizations meet business presentation standards
- **Accessibility Compliant**: Colorblind-friendly palettes and clear formatting
- **Executive Appropriate**: Insights suitable for C-level consumption
- **Reproducible**: Complete documentation and code for replication

This profile represents the integration of advanced D2D_Data2Dashboard capabilities into Agent Zero, providing enterprise-grade data analysis functionality within the familiar Agent Zero interface.