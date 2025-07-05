"""
Chart Creator Tool for Agent Zero
=================================

This tool provides professional visualization capabilities including:
- Standardized chart styling and formatting
- Colorblind-friendly palette selection
- Legend optimization and enhancement
- Multi-series chart handling
- Publication-ready output
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from pathlib import Path
import json
import os
import base64
import io
from typing import Dict, Any, List, Optional, Union
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers import images, files


class ChartCreator(Tool):
    """
    Chart Creator Tool for professional data visualization.
    
    Provides:
    - Standardized chart styling
    - Colorblind-friendly palettes
    - Legend optimization
    - Multi-series handling
    - Professional formatting
    """
    
    def __init__(self, agent, name: str, method: str | None, args: dict, message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Set default matplotlib parameters for UI-optimized appearance
        plt.style.use('default')
        plt.rcParams.update({
            'figure.figsize': (12, 8),  # Optimized for UI display
            'figure.dpi': 150,          # Higher DPI for crisp UI rendering
            'font.size': 12,            # Readable in UI
            'axes.labelsize': 13,
            'axes.titlesize': 16,
            'xtick.labelsize': 11,
            'ytick.labelsize': 11,
            'legend.fontsize': 11,
            'axes.grid': True,
            'grid.alpha': 0.3,
            'grid.linestyle': '--',
            'figure.facecolor': 'white',  # Ensure clean background for UI
            'axes.facecolor': 'white'
        })

    async def execute(self, **kwargs) -> Response:
        """
        Execute chart creation with professional styling.
        
        Expected args:
        - csv_path: Path to the CSV file
        - chart_type: Type of chart (bar, line, scatter, pie, heatmap, histogram)
        - x_column: Column for x-axis (optional for some chart types)
        - y_column: Column for y-axis (optional for some chart types)
        - category_column: Column for categorization (optional)
        - title: Chart title (optional)
        - output_dir: Directory to save charts (default: figures/)
        - color_palette: Color palette name (default: viridis)
        - ui_optimized: Whether to optimize for UI display (default: true)
        - inline_display: Whether to include base64 image data for inline display (default: true)
        """
        try:
            # Get required parameters
            csv_path = self.args.get("csv_path")
            chart_type = self.args.get("chart_type", "bar").lower()
            
            if not csv_path:
                return Response(
                    message="Error: csv_path parameter is required for chart creation.",
                    break_loop=False
                )
            
            # Validate file exists
            if not os.path.exists(csv_path):
                return Response(
                    message=f"Error: CSV file not found at path: {csv_path}",
                    break_loop=False
                )
            
            # Load data
            df = pd.read_csv(csv_path)
            
            # Get chart parameters
            ui_optimized = self.args.get("ui_optimized", "true").lower() == "true"
            inline_display = self.args.get("inline_display", "true").lower() == "true"
            
            chart_params = {
                'x_column': self.args.get("x_column"),
                'y_column': self.args.get("y_column"),
                'category_column': self.args.get("category_column"),
                'title': self.args.get("title"),
                'color_palette': self.args.get("color_palette", "viridis"),
                'output_dir': self.args.get("output_dir", "figures"),
                'figsize': eval(self.args.get("figsize", "(12, 8)" if ui_optimized else "(10, 6)")),
                'stacked': self.args.get("stacked", "false").lower() == "true",
                'ui_optimized': ui_optimized,
                'inline_display': inline_display
            }
            
            # Create output directory
            Path(chart_params['output_dir']).mkdir(parents=True, exist_ok=True)
            
            # Create chart based on type
            result = await self._create_chart(df, chart_type, chart_params)
            
            return Response(
                message=result,
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Error during chart creation: {str(e)}",
                break_loop=False
            )

    async def _create_chart(self, df: pd.DataFrame, chart_type: str, params: Dict[str, Any]) -> str:
        """Create chart based on specified type and parameters"""
        
        chart_functions = {
            'bar': self._create_bar_chart,
            'line': self._create_line_chart,
            'scatter': self._create_scatter_plot,
            'pie': self._create_pie_chart,
            'heatmap': self._create_heatmap,
            'histogram': self._create_histogram,
            'box': self._create_box_plot,
            'violin': self._create_violin_plot
        }
        
        if chart_type not in chart_functions:
            return f"Error: Unsupported chart type '{chart_type}'. Supported types: {', '.join(chart_functions.keys())}"
        
        try:
            # Create the chart
            fig, ax, chart_info = chart_functions[chart_type](df, params)
            
            # Apply standard enhancements
            self._enhance_plot(fig, ax, params)
            
            # Save the chart and get image data for UI
            output_path, image_data = self._save_chart_with_ui_data(fig, chart_type, params)
            
            # Close the figure to free memory
            plt.close(fig)
            
            return self._format_chart_response(chart_type, chart_info, output_path, image_data, params)
            
        except Exception as e:
            return f"Error creating {chart_type} chart: {str(e)}"

    def _create_bar_chart(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional bar chart"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        x_col = params['x_column']
        y_col = params['y_column']
        category_col = params.get('category_column')
        
        if not x_col or not y_col:
            # Auto-select columns if not specified
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            if not x_col and categorical_cols:
                x_col = categorical_cols[0]
            if not y_col and numeric_cols:
                y_col = numeric_cols[0]
        
        # Create color palette
        colors = self._create_color_palette(
            len(df[x_col].unique()) if x_col else 1, 
            params['color_palette']
        )
        
        if category_col and category_col in df.columns:
            # Multi-series bar chart
            pivot_data = df.pivot_table(values=y_col, index=x_col, columns=category_col, aggfunc='mean')
            pivot_data.plot(kind='bar', ax=ax, colormap=params['color_palette'], 
                          stacked=params['stacked'], width=0.8)
        else:
            # Simple bar chart
            data_agg = df.groupby(x_col)[y_col].mean() if x_col in df.columns else df[y_col]
            ax.bar(range(len(data_agg)), data_agg.values, color=colors[:len(data_agg)], width=0.7)
            if x_col in df.columns:
                ax.set_xticks(range(len(data_agg)))
                ax.set_xticklabels(data_agg.index, rotation=45, ha='right')
        
        chart_info = f"Bar chart showing {y_col} by {x_col}"
        if category_col:
            chart_info += f" (grouped by {category_col})"
            
        return fig, ax, chart_info

    def _create_line_chart(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional line chart"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        x_col = params['x_column']
        y_col = params['y_column']
        category_col = params.get('category_column')
        
        # Auto-select columns if not specified
        if not x_col:
            # Look for date/time columns or use index
            date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
            x_col = date_cols[0] if date_cols else df.index.name or 'index'
        
        if not y_col:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            y_col = numeric_cols[0] if numeric_cols else df.columns[0]
        
        # Sort by x column for proper line progression
        if x_col in df.columns:
            df_sorted = df.sort_values(x_col)
        else:
            df_sorted = df.sort_index()
        
        if category_col and category_col in df.columns:
            # Multi-series line chart
            categories = df_sorted[category_col].unique()
            colors = self._create_color_palette(len(categories), params['color_palette'])
            
            for i, category in enumerate(categories):
                data_subset = df_sorted[df_sorted[category_col] == category]
                x_values = data_subset[x_col] if x_col in df.columns else data_subset.index
                ax.plot(x_values, data_subset[y_col], label=category, 
                       color=colors[i], linewidth=2.5, marker='o', markersize=4)
        else:
            # Simple line chart
            colors = self._create_color_palette(1, params['color_palette'])
            x_values = df_sorted[x_col] if x_col in df.columns else df_sorted.index
            ax.plot(x_values, df_sorted[y_col], color=colors[0], linewidth=2.5, 
                   marker='o', markersize=4)
        
        chart_info = f"Line chart showing {y_col} over {x_col}"
        if category_col:
            chart_info += f" (series: {category_col})"
            
        return fig, ax, chart_info

    def _create_scatter_plot(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional scatter plot"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        x_col = params['x_column']
        y_col = params['y_column']
        category_col = params.get('category_column')
        
        # Auto-select numeric columns if not specified
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not x_col and len(numeric_cols) > 0:
            x_col = numeric_cols[0]
        if not y_col and len(numeric_cols) > 1:
            y_col = numeric_cols[1]
        elif not y_col and len(numeric_cols) > 0:
            y_col = numeric_cols[0]
        
        if category_col and category_col in df.columns:
            # Colored by category
            categories = df[category_col].unique()
            colors = self._create_color_palette(len(categories), params['color_palette'])
            
            for i, category in enumerate(categories):
                data_subset = df[df[category_col] == category]
                ax.scatter(data_subset[x_col], data_subset[y_col], 
                          c=[colors[i]], label=category, s=60, alpha=0.7)
        else:
            # Simple scatter plot
            colors = self._create_color_palette(1, params['color_palette'])
            ax.scatter(df[x_col], df[y_col], c=colors[0], s=60, alpha=0.7)
        
        chart_info = f"Scatter plot of {y_col} vs {x_col}"
        if category_col:
            chart_info += f" (colored by {category_col})"
            
        return fig, ax, chart_info

    def _create_pie_chart(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional pie chart"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        category_col = params.get('category_column') or params.get('x_column')
        value_col = params.get('y_column')
        
        if not category_col:
            # Use first categorical column
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            category_col = categorical_cols[0] if categorical_cols else df.columns[0]
        
        if value_col:
            # Sum values by category
            pie_data = df.groupby(category_col)[value_col].sum()
        else:
            # Count occurrences
            pie_data = df[category_col].value_counts()
        
        # Limit to top 10 categories for readability
        if len(pie_data) > 10:
            pie_data = pie_data.head(10)
        
        colors = self._create_color_palette(len(pie_data), params['color_palette'])
        
        wedges, texts, autotexts = ax.pie(
            pie_data.values, 
            labels=pie_data.index,
            colors=colors,
            autopct='%1.1f%%',
            startangle=90,
            textprops={'fontsize': 10}
        )
        
        # Ensure circular pie
        ax.set_aspect('equal')
        
        chart_info = f"Pie chart of {category_col}"
        if value_col:
            chart_info += f" (values: {value_col})"
            
        return fig, ax, chart_info

    def _create_heatmap(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional heatmap"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        # Use correlation matrix of numeric columns
        numeric_df = df.select_dtypes(include=[np.number])
        
        if numeric_df.empty:
            raise ValueError("No numeric columns found for heatmap")
        
        # Calculate correlation matrix
        corr_matrix = numeric_df.corr()
        
        # Create heatmap
        sns.heatmap(
            corr_matrix,
            annot=True,
            cmap=params['color_palette'],
            center=0,
            square=True,
            fmt='.2f',
            cbar_kws={'shrink': 0.8},
            ax=ax
        )
        
        chart_info = f"Correlation heatmap of {len(numeric_df.columns)} numeric variables"
        
        return fig, ax, chart_info

    def _create_histogram(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional histogram"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        x_col = params['x_column']
        
        if not x_col:
            # Use first numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            x_col = numeric_cols[0] if numeric_cols else df.columns[0]
        
        colors = self._create_color_palette(1, params['color_palette'])
        
        ax.hist(
            df[x_col].dropna(),
            bins=30,
            color=colors[0],
            alpha=0.7,
            edgecolor='white',
            linewidth=0.5
        )
        
        chart_info = f"Histogram of {x_col}"
        
        return fig, ax, chart_info

    def _create_box_plot(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional box plot"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        y_col = params['y_column']
        category_col = params.get('category_column') or params.get('x_column')
        
        if not y_col:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            y_col = numeric_cols[0] if numeric_cols else df.columns[0]
        
        if category_col and category_col in df.columns:
            # Grouped box plot
            df.boxplot(column=y_col, by=category_col, ax=ax)
            ax.set_title('')  # Remove automatic title
        else:
            # Single box plot
            ax.boxplot(df[y_col].dropna())
            ax.set_xticklabels([y_col])
        
        chart_info = f"Box plot of {y_col}"
        if category_col:
            chart_info += f" by {category_col}"
            
        return fig, ax, chart_info

    def _create_violin_plot(self, df: pd.DataFrame, params: Dict[str, Any]) -> tuple:
        """Create a professional violin plot"""
        
        fig, ax = plt.subplots(figsize=params['figsize'])
        
        y_col = params['y_column']
        category_col = params.get('category_column') or params.get('x_column')
        
        if not y_col:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            y_col = numeric_cols[0] if numeric_cols else df.columns[0]
        
        if category_col and category_col in df.columns:
            # Grouped violin plot
            sns.violinplot(data=df, x=category_col, y=y_col, ax=ax, palette=params['color_palette'])
        else:
            # Single violin plot
            sns.violinplot(y=df[y_col], ax=ax, color=self._create_color_palette(1, params['color_palette'])[0])
        
        chart_info = f"Violin plot of {y_col}"
        if category_col:
            chart_info += f" by {category_col}"
            
        return fig, ax, chart_info

    def _create_color_palette(self, n_colors: int, palette_name: str = 'viridis') -> List:
        """Create a colorblind-friendly color palette"""
        
        if palette_name.lower() == 'paired':
            cmap = plt.cm.Paired
        else:
            cmap = getattr(plt.cm, palette_name, plt.cm.viridis)
        
        return [cmap(i) for i in np.linspace(0, 0.9, n_colors)]

    def _enhance_plot(self, fig, ax, params: Dict[str, Any]):
        """Apply consistent styling and enhancements to the plot"""
        
        # Set title
        title = params.get('title')
        if title:
            ax.set_title(title, fontsize=14, pad=15, fontweight='bold')
        
        # Improve tick labels
        ax.tick_params(axis='both', labelsize=10)
        
        # Add grid if not already present
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Fix legend if present
        legend = ax.get_legend()
        if legend:
            self._fix_legend(ax, legend)
        
        # Tight layout
        fig.tight_layout()

    def _fix_legend(self, ax, legend, title=None, loc='best', fontsize=10):
        """Improve legend appearance and placement"""
        
        # Get handles and labels
        handles, labels = ax.get_legend_handles_labels()
        
        # If we have handles but no labels, generate meaningful labels
        if len(handles) > 0 and (len(labels) == 0 or all(not label for label in labels)):
            labels = [f"Series {i+1}" for i in range(len(handles))]
        
        # Recreate legend with improved settings
        if handles:
            ax.legend(
                handles=handles,
                labels=labels,
                title=title or (legend.get_title().get_text() if legend else None),
                loc=loc,
                fontsize=fontsize,
                framealpha=0.9,
                edgecolor='lightgray'
            )

    def _save_chart_with_ui_data(self, fig, chart_type: str, params: Dict[str, Any]) -> tuple:
        """Save the chart and prepare UI image data"""
        
        output_dir = Path(params['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = f"{chart_type}_chart_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        output_path = output_dir / filename
        
        # Determine DPI based on UI optimization
        dpi = 200 if params.get('ui_optimized', True) else 300
        
        # Save file to disk
        fig.savefig(
            output_path,
            dpi=dpi,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
            format='png'
        )
        
        # Generate base64 image data for UI display if requested
        image_data = None
        if params.get('inline_display', True):
            try:
                # Save to memory buffer
                img_buffer = io.BytesIO()
                fig.savefig(
                    img_buffer,
                    format='png',
                    dpi=150,  # Optimized for UI display
                    bbox_inches='tight',
                    facecolor='white',
                    edgecolor='none'
                )
                img_buffer.seek(0)
                
                # Compress image for UI
                img_bytes = img_buffer.getvalue()
                compressed_img = images.compress_image(
                    img_bytes, 
                    max_pixels=512_000,  # UI-optimized size
                    quality=85  # High quality for crisp display
                )
                
                # Encode as base64
                image_data = base64.b64encode(compressed_img).decode('utf-8')
                
                img_buffer.close()
                
            except Exception as e:
                print(f"Warning: Could not generate UI image data: {e}")
                image_data = None
        
        return str(output_path), image_data

    def _save_chart(self, fig, chart_type: str, params: Dict[str, Any]) -> str:
        """Save the chart to the specified output directory (legacy method)"""
        output_path, _ = self._save_chart_with_ui_data(fig, chart_type, params)
        return output_path

    def _format_chart_response(self, chart_type: str, chart_info: str, output_path: str, image_data: str = None, params: Dict[str, Any] = None) -> str:
        """Format the response message for chart creation with UI integration"""
        
        params = params or {}
        ui_optimized = params.get('ui_optimized', True)
        
        response_parts = [
            f"# Chart Creation Complete",
            "",
            f"**Chart Type:** {chart_type.title()}",
            f"**Description:** {chart_info}",
            f"**Output File:** {output_path}",
        ]
        
        # Add image display for UI integration
        if image_data and ui_optimized:
            response_parts.extend([
                "",
                "## Generated Visualization",
                "",
                f"![{chart_type.title()} Chart](data:image/png;base64,{image_data})",
                ""
            ])
        
        response_parts.extend([
            "",
            "## Chart Features",
            "- Professional styling with colorblind-friendly palette",
            "- Optimized legend placement and formatting",
            f"- {'UI-optimized' if ui_optimized else 'High-resolution'} output",
            "- Consistent grid and typography",
            "- Accessible color schemes for inclusive design"
        ])
        
        if ui_optimized:
            response_parts.extend([
                "- Optimized for Agent Zero UI display",
                "- Crisp rendering with proper sizing"
            ])
        
        response_parts.extend([
            "",
            "## Next Steps",
            "You can now:",
            "- View the chart directly in the UI above" if image_data else "- View the generated chart at the output location",
            "- Create additional charts with different parameters",
            "- Use the chart in reports or presentations",
            "- Apply further customizations if needed",
            "- Download the high-resolution file for external use"
        ])
        
        return "\n".join(response_parts)