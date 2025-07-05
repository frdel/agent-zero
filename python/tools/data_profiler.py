"""
Data Profiler Tool for Agent Zero
=================================

This tool provides comprehensive data profiling capabilities including:
- CSV data loading and validation
- Statistical analysis and data type detection
- LLM-assisted semantic profiling
- Data quality assessment
- Structural pattern recognition
"""

import json
import pandas as pd
import numpy as np
import os
from typing import Dict, Any, Optional
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from langchain_core.prompts import PromptTemplate
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)


class DataProfiler(Tool):
    """
    Data Profiler Tool for comprehensive CSV analysis.
    
    Provides:
    - Basic statistical profiling
    - LLM-enhanced semantic analysis
    - Data type inference and validation
    - Relationship detection
    - Quality assessment
    """
    
    def __init__(self, agent, name: str, method: str | None, args: dict, message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Define the profiling prompt template
        self.profile_prompt_template = (
            "You are a data profiling assistant. Carefully inspect the raw preview of a CSV table and think step‑by‑step to extract *structural facts* that an LLM can later use.\n"
            "--- RAW PREVIEW START ---\n"
            "{raw_preview}\n"
            "--- RAW PREVIEW END ---\n\n"
            "**TREE OF THOUGHT ANALYSIS PROCESS**:\n"
            "For each step below, think about multiple possible interpretations before selecting the most likely conclusion.\n\n"
            "**STAGE 1: BASIC STRUCTURE**\n"
            "- Count total rows and columns in the dataset\n"
            "- For each column, determine the most likely data type:\n"
            "  * Consider multiple possibilities (numeric? categorical? datetime? text?)\n"
            "  * Choose the most appropriate type based on pattern analysis\n"
            "  * IMPORTANT: If a column name contains 'id', 'ID', 'Id', 'identifier', or similar terms, classify it as categorical, NOT numeric, even if it contains only numbers\n"
            "  * Assign final type: numeric, categorical, datetime, or text\n\n"
            
            "**STAGE 2: TYPE-SPECIFIC ANALYSIS**\n"
            "- For numeric columns:\n"
            "  * Calculate distribution statistics (min, 25%, median, 75%, max)\n"
            "  * Identify possible units by examining patterns and contexts (currency, %, kWh, etc.)\n"
            "  * Note any outliers or irregular distributions\n"
            "- For categorical columns:\n" 
            "  * Extract 3-5 representative categories\n"
            "  * Evaluate if these categories appear exhaustive or partial\n"
            "  * Consider hierarchical relationships between categories\n"
            "- For datetime columns:\n"
            "  * Determine range (earliest to latest)\n"
            "  * Identify granularity (day/month/quarter/year)\n"
            "  * Check for time-series patterns or irregularities\n"
            "- For text columns:\n"
            "  * Analyze content patterns and typical length\n"
            "  * Summarize what information each text column likely represents\n\n"
            
            "**STAGE 3: RELATIONSHIP DISCOVERY**\n"
            "- Functional dependencies:\n"
            "  * Test multiple hypotheses about column relationships (e.g., Revenue - Cost ≈ Profit)\n"
            "  * Verify the most promising relationships\n"
            "- Structural patterns:\n"
            "  * Identify hierarchical relationships (category → subcategory)\n"
            "  * Detect time-series structure (year/quarter/month patterns)\n"
            "  * Find related column groups\n"
            "- Key identification:\n"
            "  * Evaluate columns that could serve as primary keys (unique values)\n"
            "  * Identify potential foreign-key relationships between columns\n"
            "- Aggregation detection:\n"
            "  * Examine rows/columns that may represent totals or subtotals\n"
            "  * Check for summary statistics within the data itself\n\n"
            
            "After completing all three stages of reasoning, output a JSON object with keys:\n"
            "  rows, cols, columns (list with {{\"name\": \"<column_name>\",\"type\": \"<numeric|categorical|datetime|text>\", \"examples\": [\"<ex1>\", \"<ex2>\", ...],\"unit\": \"<currency|%|kWh|none>\", \"min\": \"<number or earliest-date or n/a>\", \"max\": \"<number or latest-date or n/a>\"}},\n"
            "  formulas (list of strings),\n"
            "  hierarchy (free text),\n"
            "  time_series (true/false),\n"
            "  candidate_pk (list of column names),\n"
            "  possible_fk (list of tuple strings),\n"
            "  subtotal_cols (list), subtotal_rows (true/false)\n"
            "Use double quotes for all JSON keys. Do **not** wrap the JSON in markdown."
        )

    async def execute(self, **kwargs) -> Response:
        """
        Execute data profiling on the specified CSV file.
        
        Expected args:
        - csv_path: Path to the CSV file to analyze
        - max_rows: Maximum rows to sample for analysis (optional, default: 1000)
        """
        try:
            # Get CSV path from arguments
            csv_path = self.args.get("csv_path")
            if not csv_path:
                return Response(
                    message="Error: csv_path parameter is required for data profiling.",
                    break_loop=False
                )
            
            # Validate file exists
            if not os.path.exists(csv_path):
                return Response(
                    message=f"Error: CSV file not found at path: {csv_path}",
                    break_loop=False
                )
            
            # Get optional parameters
            max_rows = int(self.args.get("max_rows", 1000))
            
            # Perform data profiling
            profile_result = await self._build_profile(csv_path, max_rows)
            
            # Format the response
            response_message = self._format_profile_response(profile_result)
            
            return Response(
                message=response_message,
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Error during data profiling: {str(e)}",
                break_loop=False
            )

    async def _build_profile(self, csv_path: str, max_rows: int = 1000) -> Dict[str, Any]:
        """Build comprehensive data profile using statistical and LLM analysis"""
        
        # Load CSV data
        df = pd.read_csv(csv_path)
        
        # Sample data if too large
        if len(df) > max_rows:
            df = df.sample(n=max_rows, random_state=42)
        
        # Generate raw statistical profile
        raw_stats = self._generate_raw_stats(df)
        
        # Get LLM-enhanced semantic profile using agent's configured model
        prompt_text = self.profile_prompt_template.format(raw_preview=json.dumps(raw_stats, cls=NumpyEncoder))
        
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a data profiling assistant. Respond with valid JSON only, no markdown formatting."),
            HumanMessage(content=prompt_text),
        ])
        
        llm_response = await self.agent.call_chat_model(prompt=chat_prompt)
        
        # Extract content from response
        llm_enriched = str(llm_response)
        
        # Parse LLM response
        try:
            semantic_profile = json.loads(llm_enriched)
        except json.JSONDecodeError:
            semantic_profile = {"error": "Failed to parse LLM response"}
        
        return {
            "file_path": csv_path,
            "raw_stats": raw_stats,
            "semantic_profile": semantic_profile,
            "total_rows": len(pd.read_csv(csv_path)),  # Get actual row count
            "sample_rows": len(df),
            "profiling_complete": True
        }

    def _generate_raw_stats(self, df: pd.DataFrame, n: int = 5) -> Dict[str, Any]:
        """Generate basic statistical profile of the dataframe"""
        
        meta = {
            "n_rows": len(df), 
            "n_cols": df.shape[1], 
            "columns": {}
        }
        
        for col in df.columns:
            series = df[col]
            col_meta = {
                "dtype": str(series.dtype),
                "unique_ratio": round(series.nunique() / len(series), 4),
                "sample": series.head(n).astype(str).tolist(),
                "null_count": series.isnull().sum(),
                "null_percentage": round((series.isnull().sum() / len(series)) * 100, 2)
            }
            
            # Add numeric statistics if applicable
            if pd.api.types.is_numeric_dtype(series):
                col_meta.update({
                    "min": series.min(),
                    "max": series.max(),
                    "mean": round(series.mean(), 4),
                    "std": round(series.std(), 4),
                    "median": series.median(),
                    "q25": series.quantile(0.25),
                    "q75": series.quantile(0.75)
                })
            
            meta["columns"][col] = col_meta
        
        return meta

    def _format_profile_response(self, profile_result: Dict[str, Any]) -> str:
        """Format the profiling results into a readable response"""
        
        if not profile_result.get("profiling_complete"):
            return "Data profiling failed to complete successfully."
        
        raw_stats = profile_result.get("raw_stats", {})
        semantic = profile_result.get("semantic_profile", {})
        
        response_parts = [
            "# Data Profiling Results",
            "",
            f"**File:** {profile_result.get('file_path')}",
            f"**Total Rows:** {profile_result.get('total_rows'):,}",
            f"**Columns:** {raw_stats.get('n_cols', 0)}",
            f"**Sample Size:** {profile_result.get('sample_rows'):,}",
            "",
            "## Data Structure Overview"
        ]
        
        # Add semantic insights if available
        if semantic and "error" not in semantic:
            if semantic.get("time_series"):
                response_parts.append("📈 **Time Series Data Detected**")
            
            if semantic.get("hierarchy"):
                response_parts.extend([
                    "",
                    "### Hierarchical Structure",
                    semantic.get("hierarchy", "")
                ])
            
            if semantic.get("formulas"):
                response_parts.extend([
                    "",
                    "### Detected Relationships",
                    *[f"- {formula}" for formula in semantic.get("formulas", [])]
                ])
        
        # Add column details
        response_parts.extend([
            "",
            "## Column Analysis",
            ""
        ])
        
        for col_name, col_info in raw_stats.get("columns", {}).items():
            response_parts.extend([
                f"### {col_name}",
                f"- **Type:** {col_info.get('dtype')}",
                f"- **Unique Values:** {col_info.get('unique_ratio', 0):.1%}",
                f"- **Missing Values:** {col_info.get('null_count', 0)} ({col_info.get('null_percentage', 0):.1f}%)",
                f"- **Sample:** {', '.join(map(str, col_info.get('sample', [])))}"
            ])
            
            # Add numeric statistics if available
            if 'mean' in col_info:
                response_parts.extend([
                    f"- **Range:** {col_info.get('min')} to {col_info.get('max')}",
                    f"- **Mean:** {col_info.get('mean')}",
                    f"- **Median:** {col_info.get('median')}"
                ])
            
            response_parts.append("")
        
        # Add recommendations
        response_parts.extend([
            "## Next Steps",
            "",
            "The data has been successfully profiled. You can now:",
            "- Use `domain_detector` to identify the business domain",
            "- Run `insight_generator` to create analytical insights",
            "- Apply `chart_creator` to visualize the data",
            ""
        ])
        
        return "\n".join(response_parts)