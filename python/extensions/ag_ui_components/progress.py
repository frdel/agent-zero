from python.extensions.ag_ui_components.base import AGUIComponent

class Progress(AGUIComponent):
    """
    A progress bar component.
    """

    def render(self, properties: dict) -> str:
        """
        Renders a progress bar with customizable appearance.
        """
        progress_id = properties.get("id", "ag-ui-progress")
        value = properties.get("value", 0)
        max_value = properties.get("max", 100)
        label = properties.get("label", "")
        show_percentage = properties.get("show_percentage", True)
        variant = properties.get("variant", "primary")  # primary, success, warning, danger
        size = properties.get("size", "medium")  # small, medium, large
        animated = properties.get("animated", False)
        
        # Calculate percentage
        percentage = min(100, max(0, (value / max_value) * 100)) if max_value > 0 else 0
        
        # Build classes
        classes = [
            "ag-ui-progress",
            f"ag-ui-progress-{variant}",
            f"ag-ui-progress-{size}"
        ]
        
        if animated:
            classes.append("ag-ui-progress-animated")
        
        label_html = f'<div class="ag-ui-progress-label">{label}</div>' if label else ""
        
        percentage_html = f'''
        <div class="ag-ui-progress-percentage">
            {percentage:.0f}%
        </div>''' if show_percentage else ""
        
        return f'''
<div id="{progress_id}" class="{' '.join(classes)}">
    {label_html}
    <div class="ag-ui-progress-container">
        <div class="ag-ui-progress-bar" style="width: {percentage}%"></div>
    </div>
    {percentage_html}
</div>'''