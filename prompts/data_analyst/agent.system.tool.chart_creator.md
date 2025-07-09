## Chart Creator Tool Usage Guidelines

### Purpose
The Chart Creator tool provides professional-grade data visualization capabilities with consistent styling, colorblind-friendly palettes, and publication-ready output suitable for business presentations and executive reporting.

### When to Use
- **Professional Visualizations**: When you need high-quality charts for business presentations
- **Standardized Styling**: To ensure consistent visual formatting across multiple charts
- **Accessibility Compliance**: For colorblind-friendly and accessible visualizations
- **Publication Output**: When creating charts for reports, dashboards, or external communication

### Required Parameters
- `csv_path`: Full path to the CSV file containing the data to visualize
- `chart_type`: Type of chart to create (see supported types below)

### Optional Parameters
- `x_column`: Column for x-axis (auto-selected if not specified)
- `y_column`: Column for y-axis (auto-selected if not specified)  
- `category_column`: Column for grouping/categorization
- `title`: Custom chart title
- `output_dir`: Directory to save charts (default: "figures/")
- `color_palette`: Color scheme (default: "viridis")
- `figsize`: Figure dimensions as tuple (default: auto-optimized for UI)
- `stacked`: Whether to stack series in applicable charts (default: false)
- `ui_optimized`: Whether to optimize for UI display (default: true)
- `inline_display`: Whether to include base64 image data for inline display (default: true)

### Supported Chart Types
The tool supports eight professional visualization types:

#### Statistical Charts
- **`bar`**: Bar charts for categorical comparisons
- **`line`**: Line charts for trends and time series
- **`histogram`**: Distribution analysis of single variables
- **`box`**: Box plots for statistical summaries and outlier detection
- **`violin`**: Violin plots for distribution shape analysis

#### Relationship Charts  
- **`scatter`**: Scatter plots for correlation analysis
- **`heatmap`**: Correlation matrices and pattern visualization

#### Composition Charts
- **`pie`**: Pie charts for proportion analysis (limited to top 10 categories)

### Usage Examples

#### Basic Bar Chart
```json
{
  "tool": "chart_creator",
  "csv_path": "/path/to/data.csv",
  "chart_type": "bar",
  "x_column": "Category",
  "y_column": "Revenue"
}
```

#### Multi-Series Line Chart with Custom Styling
```json
{
  "tool": "chart_creator",
  "csv_path": "/path/to/timeseries.csv", 
  "chart_type": "line",
  "x_column": "Date",
  "y_column": "Sales",
  "category_column": "Region",
  "title": "Regional Sales Trends",
  "color_palette": "plasma",
  "figsize": "(12, 8)"
}
```

#### Correlation Heatmap
```json
{
  "tool": "chart_creator",
  "csv_path": "/path/to/numeric_data.csv",
  "chart_type": "heatmap",
  "title": "Variable Correlation Analysis"
}
```

#### Professional Pie Chart
```json
{
  "tool": "chart_creator",
  "csv_path": "/path/to/categories.csv",
  "chart_type": "pie",
  "category_column": "Product_Type",
  "y_column": "Sales_Volume",
  "title": "Market Share by Product Type"
}
```

### Professional Features

#### Visual Excellence
- **Consistent Styling**: Standardized fonts, spacing, and layout across all chart types
- **UI-Optimized Display**: Charts appear directly in Agent Zero interface with perfect sizing
- **Dual Output**: High-resolution files (200-300 DPI) plus compressed UI display versions
- **Clean Aesthetics**: Professional grid lines, typography, and spacing
- **Intelligent Sizing**: Auto-optimized dimensions for UI display and print use

#### Accessibility Standards
- **Colorblind-Friendly Palettes**: Viridis, plasma, cividis, and Paired color schemes
- **Clear Legends**: Descriptive titles and optimal placement
- **Readable Text**: Appropriate font sizes for all chart elements
- **High Contrast**: Ensuring visibility across different viewing conditions

#### Advanced Formatting
- **Smart Auto-Selection**: Intelligent column selection when parameters not specified
- **Multi-Series Handling**: Proper grouping and visualization of complex data relationships
- **Legend Optimization**: Automatic improvement of legend appearance and positioning
- **Error Handling**: Graceful management of data quality issues

### Color Palette Options
- **`viridis`** (default): Professional blue-to-yellow gradient, excellent for data
- **`plasma`**: Purple-to-pink-to-yellow, high contrast and engaging
- **`cividis`**: Colorblind-optimized version of viridis
- **`paired`**: Qualitative palette with distinct colors for categories

### Output Specifications
- **File Format**: High-quality PNG images with UI-optimized compression
- **Resolution**: 200 DPI for UI display, 300 DPI for print (when ui_optimized=false)
- **Inline Display**: Base64-encoded images appear directly in Agent Zero UI
- **Naming**: Automatic timestamp-based naming for organization
- **Directory Structure**: Organized output in specified directories
- **Dual Format**: Both file storage and immediate UI display capabilities

### Best Practices

#### Data Preparation
1. **Clean Data**: Ensure data quality before visualization
2. **Appropriate Types**: Match chart types to data characteristics
3. **Reasonable Scale**: Consider data range and distribution
4. **Missing Values**: Handle null values appropriately

#### Visual Design
1. **Title Clarity**: Use descriptive, business-focused titles
2. **Axis Labels**: Ensure clear and informative axis labeling
3. **Color Consistency**: Maintain consistent color schemes across related charts
4. **Legend Placement**: Position legends for optimal readability

#### Business Communication
1. **Audience Awareness**: Choose chart types appropriate for your audience
2. **Key Message**: Ensure visualizations support your analytical narrative
3. **Context Provision**: Include necessary context for proper interpretation
4. **Action Orientation**: Focus on insights that drive business decisions

### Integration with Other Tools
Chart Creator works seamlessly with:
- **Data Profiler**: Uses column information for intelligent auto-selection
- **Domain Detector**: Applies domain-appropriate visualization conventions
- **Insight Generator**: Executes visualization code generated by analytical reasoning

### Advanced Capabilities

#### Automatic Intelligence
- **Column Type Detection**: Automatically identifies numeric vs. categorical columns
- **Relationship Recognition**: Understands data relationships for optimal visualization
- **Quality Assessment**: Handles missing data and outliers appropriately
- **Scale Optimization**: Adjusts scales and ranges for best visual impact

#### Performance Optimization
- **Memory Management**: Efficient handling of large datasets
- **Processing Speed**: Optimized rendering for quick chart generation
- **Resource Cleanup**: Proper memory management and figure closing
- **Batch Processing**: Support for multiple chart creation workflows

### Error Prevention and Handling
- File existence validation before processing
- Data type compatibility checking
- Memory usage monitoring for large datasets
- Graceful degradation when visualization requirements cannot be met
- Comprehensive error reporting with actionable solutions

### Professional Output Standards
All charts meet business presentation standards:
- Publication-ready quality and resolution
- Consistent branding and styling possibilities
- Executive-appropriate visual design
- Professional color schemes and typography
- Accessibility compliance for inclusive communication