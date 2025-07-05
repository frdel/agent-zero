"""
Insight Generator Tool for Agent Zero
====================================

This tool provides Tree-of-Thought analysis capabilities including:
- Schema-aware insight generation
- Multi-expert perspective simulation
- Domain-aware analysis synthesis
- Business intelligence recommendations
"""

import os
import re
import json
import pandas as pd
from typing import Dict, Any, List, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage


class InsightGenerator(Tool):
    """
    Insight Generator Tool for advanced analytical reasoning.
    
    Provides:
    - Tree-of-Thought analytical methodology
    - Multi-expert perspective simulation  
    - Domain-aware insight synthesis
    - Business intelligence recommendations
    """
    
    def __init__(self, agent, name: str, method: str | None, args: dict, message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Define Tree-of-Thought prompt block
        self.tot_block = """
### Insight to Visualise and Interpret
{INSIGHT_TEXT}

### Three‑Expert Tree of Thought

**Step I – Extract Key Domain Findings**  
Experts identify the core domain insights that need visual representation:  
```
Expert 1: [Domain finding 1]
Expert 2: [Domain finding 2]
Expert 3: [Domain finding 3]
```

**Step II – Identify Relevant Data**  
Each expert independently lists dataframe columns they think support the insight.  
```
Expert 1: ['colA', 'colB', 'colC-B']
Expert 2: ['colB', 'colC']
Expert 3: ['colA', 'colC', 'colD+C', 'colE/A', 'colF-B']
```

**Step III – Evaluate Data Selection**  
Experts compare lists and agree on the minimal set.  
```
Agreed columns: ['colA', 'colB']
```

**Step IV – Visualise with Domain Context**  
Each expert proposes a chart type and explains how it highlights domain insights:
```
Expert 1: Bar chart - Shows investment preference patterns while highlighting the shift toward digital platforms
Expert 2: Trend line - Visualizes age-based patterns, supporting the prediction about retirement planning shifts
Expert 3: Stacked bar - Reveals demographic segments' behavior, illuminating the financial literacy variations
```

**Consolidation**  
Output final decisions:
```
Final chart: [chart type]
Reason: [visualization rationale]
Key insight narrative: [1-2 sentences explaining what domain insight this visualization helps reveal]
Recommended annotation: [Specific callout/annotation that should be added to highlight the domain insight]
```
"""
        
        # Define the main prompt template
        self.prompt_template = """
You are an elite data‑visualisation consultant.

Context:
  • **insight_library** (JSON):
{insight_json}
  • **CSV_SCHEMA** (column → dtype):
{schema_table}
  • **CSV_PATH** – a string pointing to the dataset on disk.

Below, you will see one or more *Tree‑of‑Thought* blocks.  Follow the
instructions inside each block to reason step‑by‑step and decide on a
single chart for every insight.

{TOT_BLOCKS}

Return **exactly two fenced blocks** in order and nothing else:

1️⃣ Thoughts block (label it ```thoughts) – include your full reasoning.

2️⃣ Python block (label it ```python) – write a script that:
   • imports pandas as pd, matplotlib.pyplot as plt, numpy as np, Path
   • reads dataset via CSV_PATH (already defined)
   • implements each **Final chart** decision
   • includes comments explaining the domain insights for each visualization
   • adds appropriate titles, labels, and annotations that highlight the key insights
   • wraps every plot in try/except (KeyError, ValueError, TypeError) and `print()` a warning
     if skipped
   • calls plt.tight_layout(); show() or save to figures/
   • uses **only** columns listed in CSV_SCHEMA.

   Visualization Best Practices:
   • For legends: Always use clear, descriptive legend titles and place them optimally (usually upper right or outside)
   • For color selection: Use colorblind-friendly palettes (viridis, plasma, cividis) or plt.cm.Paired
   • For multiple series: When plotting multiple data series, either:
     - Use plt.subplots to create separate plots, or
     - Use proper stacking techniques with stacked=True parameter
     - Avoid overwriting plots on the same axes unless showing direct comparisons
   • For pie charts: Use plt.axis('equal') to ensure proper circular appearance
   • For data preparation: Use pandas aggregation (crosstab, pivot_table) before plotting
   • For formatting: Set appropriate fontsize for title (14), labels (12), and tick labels (10)
"""

    async def execute(self, **kwargs) -> Response:
        """
        Execute insight generation using Tree-of-Thought methodology.
        
        Expected args:
        - csv_path: Path to the CSV file
        - profile_data: Data profile from data_profiler_tool (JSON string or dict)
        - domain_info: Domain detection results (optional)
        """
        try:
            # Get required parameters
            csv_path = self.args.get("csv_path")
            profile_data = self.args.get("profile_data")
            
            if not csv_path:
                return Response(
                    message="Error: csv_path parameter is required for insight generation.",
                    break_loop=False
                )
            
            if not profile_data:
                return Response(
                    message="Error: profile_data parameter is required. Please run data_profiler_tool first.",
                    break_loop=False
                )
            
            # Validate file exists
            if not os.path.exists(csv_path):
                return Response(
                    message=f"Error: CSV file not found at path: {csv_path}",
                    break_loop=False
                )
            
            # Parse profile data if it's a string
            if isinstance(profile_data, str):
                try:
                    profile_data = json.loads(profile_data)
                except json.JSONDecodeError:
                    return Response(
                        message="Error: Invalid profile_data format. Expected JSON string or dict.",
                        break_loop=False
                    )
            
            # Get optional parameters
            domain_info = self.args.get("domain_info", {})
            
            # Generate insights
            result = await self._generate_analysis(
                csv_path=csv_path,
                profile_data=profile_data,
                domain_info=domain_info
            )
            
            return Response(
                message=result,
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Error during insight generation: {str(e)}",
                break_loop=False
            )

    async def _generate_analysis(
        self,
        csv_path: str,
        profile_data: Dict[str, Any],
        domain_info: Dict[str, Any] = None
    ) -> str:
        """Generate Tree-of-Thought analysis and visualization code"""
        
        # Load CSV to get schema
        df = pd.read_csv(csv_path)
        schema_table = "\n".join(f"- {c}: {t}" for c, t in df.dtypes.items())
        
        # Build insight library from profile data
        semantic_profile = profile_data.get("semantic_profile", {})
        domain_info = domain_info or {}
        
        # Create insight library structure
        insight_library = {
            "descriptive": self._generate_descriptive_insight(profile_data, domain_info),
            "predictive": self._generate_predictive_insight(profile_data, domain_info),
            "domain_related": self._generate_domain_insight(profile_data, domain_info)
        }
        
        # Extract insight texts
        insight_texts = [
            insight_library.get("descriptive", ""),
            insight_library.get("predictive", ""),
            insight_library.get("domain_related", "")
        ]
        
        # Build Tree-of-Thought blocks
        tot_blocks = "\n\n".join(
            self.tot_block.replace("{INSIGHT_TEXT}", txt.strip() or "(missing)")
            for txt in insight_texts if txt.strip()
        )
        
        # Create final prompt
        prompt = self.prompt_template.format(
            insight_json=json.dumps(insight_library, indent=2),
            schema_table=schema_table,
            TOT_BLOCKS=tot_blocks
        )
        
        # Call agent's configured model
        thoughts, code_body = await self._chat_and_extract(
            prompt=prompt
        )
        
        # Format response
        response_parts = [
            "# Insight Generation Results",
            "",
            "## Generated Insights",
            "",
            "### Descriptive Analysis",
            insight_library.get("descriptive", "No descriptive insights generated."),
            "",
            "### Predictive Analysis", 
            insight_library.get("predictive", "No predictive insights generated."),
            "",
            "### Domain-Specific Analysis",
            insight_library.get("domain_related", "No domain-specific insights generated."),
            "",
            "## Tree-of-Thought Reasoning",
            "",
            "```",
            thoughts,
            "```",
            "",
            "## Generated Visualization Code",
            "",
            "The following Python code has been generated to create visualizations:",
            "",
            "```python",
            code_body,
            "```",
            "",
            "## Next Steps",
            "",
            "You can now:",
            "- Execute the generated code to create visualizations (will display inline in UI)",
            "- Use `chart_creator` tool to create UI-optimized charts that display directly",
            "- Refine the analysis based on the generated insights",
            "- Save the code for future use or modification"
        ]
        
        return "\n".join(response_parts)

    async def _chat_and_extract(self, prompt: str) -> Tuple[str, str]:
        """Call agent's configured model and extract thoughts and code blocks"""
        
        system_msg = """Answer with two fenced blocks: first ```thoughts, then ```python, nothing else.

When analyzing data, prioritize preserving domain expertise and insights in your visualizations:
1. Make visualizations that illuminate the domain context, not just show the data
2. Include annotations that highlight key domain insights
3. Use titles and comments that emphasize the domain-specific findings
4. Ensure the narrative in your thoughts connects the visualizations to the original domain insights

Visualization Best Practices:
- Legends should be clear, descriptive, and properly positioned
- Use appropriate color schemes (colorblind-friendly)
- When plotting multiple data series, use proper techniques to avoid overwriting
- Prepare data properly before visualization (aggregation, transformation)
- Include appropriate sizing and formatting for all visual elements"""

        # Use agent's configured chat model instead of OpenAI directly
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_msg),
            HumanMessage(content=prompt),
        ])
        
        # Call agent's configured model
        content = await self.agent.call_chat_model(prompt=chat_prompt)
        
        # Extract thoughts and code blocks
        thoughts_match = re.search(r"```thoughts(.*?)```", content, re.S)
        code_match = re.search(r"```python(.*?)```", content, re.S)
        
        if not (thoughts_match and code_match):
            raise ValueError("Model response missing required fenced blocks.")
        
        return thoughts_match.group(1).strip(), code_match.group(1).strip()

    def _generate_descriptive_insight(self, profile_data: Dict[str, Any], domain_info: Dict[str, Any]) -> str:
        """Generate descriptive analysis text"""
        raw_stats = profile_data.get("raw_stats", {})
        semantic = profile_data.get("semantic_profile", {})
        
        insights = []
        
        # Basic data characteristics
        n_rows = raw_stats.get("n_rows", 0)
        n_cols = raw_stats.get("n_cols", 0)
        insights.append(f"The dataset contains {n_rows:,} observations across {n_cols} variables.")
        
        # Data quality insights
        columns = raw_stats.get("columns", {})
        missing_data = [(col, info.get("null_percentage", 0)) for col, info in columns.items() if info.get("null_percentage", 0) > 0]
        if missing_data:
            high_missing = [col for col, pct in missing_data if pct > 10]
            if high_missing:
                insights.append(f"Data quality concerns identified in {len(high_missing)} columns with >10% missing values: {', '.join(high_missing[:3])}{'...' if len(high_missing) > 3 else ''}.")
        
        # Column diversity
        numeric_cols = [col for col, info in columns.items() if 'mean' in info]
        categorical_cols = [col for col, info in columns.items() if 'mean' not in info and info.get("unique_ratio", 0) < 0.5]
        
        if numeric_cols:
            insights.append(f"Contains {len(numeric_cols)} quantitative measures suitable for statistical analysis.")
        if categorical_cols:
            insights.append(f"Includes {len(categorical_cols)} categorical dimensions for segmentation analysis.")
        
        return " ".join(insights)

    def _generate_predictive_insight(self, profile_data: Dict[str, Any], domain_info: Dict[str, Any]) -> str:
        """Generate predictive analysis text"""
        semantic = profile_data.get("semantic_profile", {})
        raw_stats = profile_data.get("raw_stats", {})
        
        insights = []
        
        # Time series potential
        if semantic.get("time_series"):
            insights.append("Time series patterns detected, enabling trend forecasting and seasonal analysis.")
        
        # Predictive modeling potential
        columns = raw_stats.get("columns", {})
        numeric_cols = [col for col, info in columns.items() if 'mean' in info]
        
        if len(numeric_cols) >= 2:
            insights.append(f"Multiple quantitative variables ({len(numeric_cols)}) present, supporting predictive modeling and correlation analysis.")
        
        # Relationship detection
        if semantic.get("formulas"):
            insights.append("Mathematical relationships identified between variables, suggesting causal modeling opportunities.")
        
        # Key prediction opportunities
        high_variance_cols = []
        for col, info in columns.items():
            if 'std' in info and info.get('mean', 0) != 0:
                cv = info['std'] / abs(info['mean'])
                if cv > 0.5:  # High coefficient of variation
                    high_variance_cols.append(col)
        
        if high_variance_cols:
            insights.append(f"High variability in {len(high_variance_cols)} variables suggests prediction opportunities for optimization.")
        
        return " ".join(insights)

    def _generate_domain_insight(self, profile_data: Dict[str, Any], domain_info: Dict[str, Any]) -> str:
        """Generate domain-specific analysis text"""
        domain = domain_info.get("domain", "business")
        
        insights = []
        
        # Domain context
        if domain and domain != "Unknown":
            insights.append(f"Analysis within {domain} domain context reveals industry-specific patterns and benchmarking opportunities.")
        
        # Business value proposition
        semantic = profile_data.get("semantic_profile", {})
        if semantic.get("hierarchy"):
            insights.append("Hierarchical data structure identified, enabling drill-down analysis and performance attribution.")
        
        # Key performance indicators
        raw_stats = profile_data.get("raw_stats", {})
        columns = raw_stats.get("columns", {})
        
        # Look for potential KPIs based on column names
        kpi_keywords = ["revenue", "profit", "cost", "sales", "performance", "efficiency", "growth", "rate", "percentage"]
        potential_kpis = []
        for col in columns.keys():
            if any(keyword in col.lower() for keyword in kpi_keywords):
                potential_kpis.append(col)
        
        if potential_kpis:
            insights.append(f"Key performance indicators identified: {', '.join(potential_kpis[:3])}{'...' if len(potential_kpis) > 3 else ''}, enabling business performance monitoring.")
        
        # Strategic recommendations
        insights.append("Domain expertise suggests focusing on actionable metrics that drive business decision-making and competitive advantage.")
        
        return " ".join(insights)