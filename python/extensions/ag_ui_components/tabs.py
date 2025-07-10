from python.extensions.ag_ui_components.base import AGUIComponent

class Tabs(AGUIComponent):
    """
    A tabs component for organizing content.
    """

    def render(self, properties: dict) -> str:
        """
        Renders a tabs component with navigation and content panels.
        """
        tabs_id = properties.get("id", "ag-ui-tabs")
        tabs = properties.get("tabs", [])
        active_tab = properties.get("active_tab", 0)
        
        if not tabs:
            return '<div class="ag-ui-error">No tabs provided</div>'
        
        # Generate tab navigation
        nav_html = ""
        for i, tab in enumerate(tabs):
            tab_title = tab.get("title", f"Tab {i + 1}")
            active_class = "active" if i == active_tab else ""
            nav_html += f'''
            <button @click="setActiveTab({i})" 
                    class="ag-ui-tab-button {active_class}"
                    :class="{{ active: activeTab === {i} }}"
                    type="button">
                {tab_title}
            </button>'''
        
        # Generate tab content
        content_html = ""
        for i, tab in enumerate(tabs):
            tab_content = tab.get("content", "")
            display_style = "" if i == active_tab else "display: none;"
            content_html += f'''
            <div x-show="activeTab === {i}" 
                 x-transition:enter="transition ease-out duration-300"
                 x-transition:enter-start="opacity-0"
                 x-transition:enter-end="opacity-100"
                 class="ag-ui-tab-panel">
                {tab_content}
            </div>'''
        
        return f'''
<div id="{tabs_id}" class="ag-ui-tabs" x-data="aguiTabs({{
    id: '{tabs_id}',
    properties: {properties}
}})">
    <div class="ag-ui-tab-nav">
        {nav_html}
    </div>
    <div class="ag-ui-tab-content">
        {content_html}
    </div>
</div>'''