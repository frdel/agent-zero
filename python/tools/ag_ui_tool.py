import json
import os
import importlib.util
from typing import Dict, Any

from python.helpers.tool import Tool, Response
from python.helpers.ag_ui_parser import AGUIParser, AGUIComponent as ParsedComponent
from python.helpers.ag_ui_validator import AGUIValidator, AGUIValidationError
from python.helpers.ag_ui_state import AGUIStateManager, get_global_state_manager
from python.helpers.ag_ui_middleware import get_global_middleware_router, ProtocolType
from python.helpers.ag_ui_config import get_global_config_manager, create_default_agent_config, AgentCapability, AgentRole
from python.extensions.ag_ui_components.base import AGUIComponent

class AGUITool(Tool):
    """
    A tool for handling the AG-UI protocol with full event support and dynamic UI generation.
    """

    def __init__(self, agent, name: str, method: str | None, args: dict[str, str], message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        self.parser = AGUIParser()
        self.validator = AGUIValidator()
        self.custom_components = self._load_custom_components()
        
        # Initialize AG-UI systems
        self.state_manager = get_global_state_manager()
        self.middleware_router = get_global_middleware_router()
        self.config_manager = get_global_config_manager()
        
        # AG-UI debug mode configuration
        self.debug_mode = self.args.get("debug_mode", "false").lower() == "true"
        
        # Register this agent if not already registered
        self._register_agent_if_needed()

    def _load_custom_components(self):
        """
        Scans the `python/extensions/ag_ui_components` directory for custom components.
        """
        components = {}
        try:
            components_dir = os.path.join(os.path.dirname(__file__), "..", "extensions", "ag_ui_components")
            if not os.path.exists(components_dir):
                return components
                
            for filename in os.listdir(components_dir):
                if filename.endswith(".py") and filename != "base.py" and filename != "__init__.py":
                    module_name = filename[:-3]
                    module_path = os.path.join(components_dir, filename)
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, module_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for name in dir(module):
                            obj = getattr(module, name)
                            if isinstance(obj, type) and issubclass(obj, AGUIComponent) and obj is not AGUIComponent:
                                components[module_name] = obj()
                    except Exception as e:
                        # Skip components that fail to load
                        self.agent.context.log.log(type="warning", heading="AG-UI Component Loading", 
                                                  content=f"Failed to load component {module_name}: {e}")
        except Exception as e:
            self.agent.context.log.log(type="warning", heading="AG-UI Components", 
                                      content=f"Failed to scan components directory: {e}")
        return components

    async def execute(self, **kwargs) -> Response:
        """
        Executes the AG-UI tool with full protocol support.
        """
        ag_ui_spec = self.args.get("ag_ui_spec", "")
        
        if not ag_ui_spec:
            return Response(
                message="Error: AG-UI specification is required in 'ag_ui_spec' argument.",
                break_loop=False
            )

        # Emit RUN_STARTED lifecycle event
        self._emit_lifecycle_event("RUN_STARTED", {
            "tool_name": "ag_ui_tool",
            "timestamp": self._get_timestamp(),
            "agent_id": getattr(self.agent, 'id', 'unknown')
        })

        try:
            component_spec = json.loads(ag_ui_spec) if isinstance(ag_ui_spec, str) else ag_ui_spec

            # Validate the component specification
            validation_result = self._validate_component_spec(component_spec)

            # Log validation results if debug mode is enabled
            if self.debug_mode and (validation_result["warnings"] or validation_result["suggestions"]):
                self.agent.context.log.log(
                    type="warning",
                    heading="AG-UI Specification Validation",
                    content=json.dumps({
                        "warnings": validation_result["warnings"],
                        "suggestions": validation_result["suggestions"]
                    }, indent=2)
                )

            if not validation_result["is_valid"]:
                error_msg = f"Invalid AG-UI specification: {'; '.join(validation_result['errors'])}"
                self.agent.context.log.log(type="error", heading="AG-UI Validation Error", content=error_msg)
                return Response(message=error_msg, break_loop=False)

            # Check if this looks like a single component (has type and properties) or full spec
            is_single_component = 'type' in component_spec and 'properties' in component_spec
            
            if is_single_component:
                # Parse as single component
                parsed_component = self.parser.parse_component(component_spec)
                self.validator.validate_component(parsed_component)
                ui_components = self._generate_ui_component(parsed_component)
                message_type = "ag_ui"
            else:
                # Try to parse as full AG-UI specification
                parsed_spec = self.parser.parse_spec(component_spec)
                self.validator.validate_spec(parsed_spec)
                ui_components = self._process_full_spec(parsed_spec)
                message_type = "ag_ui"

            # Emit TEXT_MESSAGE_START event
            self._emit_lifecycle_event("TEXT_MESSAGE_START", {
                "component_type": parsed_component.type if 'parsed_component' in locals() else parsed_spec.get('type', 'unknown'),
                "timestamp": self._get_timestamp()
            })

            # Check if ui_components is empty and log error if so
            if not ui_components or ui_components.strip() == "":
                component_info = {
                    "type": parsed_component.type if 'parsed_component' in locals() else 'unknown',
                    "id": parsed_component.id if 'parsed_component' in locals() else None,
                    "properties": parsed_component.properties if 'parsed_component' in locals() else {},
                    "children_count": len(parsed_component.children) if 'parsed_component' in locals() else 0
                }
                self.agent.context.log.log(
                    type="error",
                    heading="AG-UI Component Generation Failed",
                    content=f"Generated UI components is empty. Component info: {json.dumps(component_info, indent=2)}"
                )
            
            # Stream the UI components content
            self._emit_streaming_content(ui_components)

            # Update component state management
            if 'parsed_component' in locals():
                component_id = parsed_component.id or f"ag-ui-{parsed_component.type}-{self._get_timestamp()}"
                self._update_component_state(component_id, {
                    "type": parsed_component.type,
                    "properties": parsed_component.properties
                })
                
                # Check for multi-agent delegation opportunities
                delegation_available = self._check_multi_agent_delegation(parsed_component.type)

            # Log the generated UI components to Agent Zero with initialization script
            initialization_script = """
            <script>
            // Ensure Alpine.js initializes the new AG-UI components
            if (window.Alpine) {
                window.Alpine.nextTick(() => {
                    const agUiElements = document.querySelectorAll('[x-data*="aguiButton"], [x-data*="aguiModal"], [x-data*="aguiTabs"]');
                    agUiElements.forEach(el => {
                        if (!el._x_dataStack) {
                            window.Alpine.initTree(el);
                        }
                    });
                });
            }

            // Debug: Log available functions
            console.log('Available AG-UI functions:', {
                setComponentState: typeof window.setComponentState,
                updateElement: typeof window.updateElement,
                changeElementClass: typeof window.changeElementClass,
                changeElementText: typeof window.changeElementText
            });
            </script>
            """

            # Only add Agent Zero interface controls if explicitly requested
            agent_zero_ui_controls = ""
            if component_spec.get("include_agent_zero_controls", False):
                agent_zero_ui_controls = """
                <div style="margin: 20px; padding: 20px; border: 2px solid #4CAF50; background: #f0f8f0; border-radius: 8px;">
                    <h3 style="color: #2E7D32; margin-top: 0;">🎨 Agent Zero Interface Controls</h3>
                    <p style="color: #555;">These buttons modify the actual Agent Zero interface:</p>
                    <div style="margin: 15px 0;">
                        <button onclick="document.getElementById('left-panel').style.backgroundColor='#d32f2f'">🔴 Red Sidebar</button>
                        <button onclick="document.getElementById('left-panel').style.backgroundColor='#388e3c'">🟢 Green Sidebar</button>
                        <button onclick="document.getElementById('left-panel').style.backgroundColor='#1976d2'">🔵 Blue Sidebar</button>
                        <button onclick="document.getElementById('left-panel').style.backgroundColor=''">↩️ Reset</button>
                    </div>
                </div>
                """

            self.agent.context.log.log(
                type=message_type,
                heading="AG-UI Component Generated",
                content=json.dumps({
                    "ui_components": ui_components + initialization_script + agent_zero_ui_controls,
                    "type": "ag_ui",
                    "protocol_version": "1.0",
                    "timestamp": self._get_timestamp(),
                    "agent_metadata": self._get_agent_metadata()
                })
            )

            # Emit TEXT_MESSAGE_END event
            self._emit_lifecycle_event("TEXT_MESSAGE_END", {
                "component_rendered": True,
                "timestamp": self._get_timestamp()
            })

            # Emit RUN_FINISHED success event
            self._emit_lifecycle_event("RUN_FINISHED", {
                "status": "success",
                "components_generated": True,
                "timestamp": self._get_timestamp()
            })

            return Response(
                message=f"✅ AG-UI Component Successfully Generated!\n\nThe interactive {parsed_component.type if 'parsed_component' in locals() else 'component'} has been rendered above with full functionality.",
                break_loop=False
            )

        except (ValueError, json.JSONDecodeError, AGUIValidationError) as e:
            error_details = {
                "error_message": str(e),
                "error_type": type(e).__name__,
                "input_spec_preview": str(ag_ui_spec)[:200] + "..." if len(str(ag_ui_spec)) > 200 else str(ag_ui_spec),
                "timestamp": self._get_timestamp()
            }
            error_msg = f"Failed to process AG-UI specification: {str(e)}"

            # Emit RUN_ERROR lifecycle event with detailed information
            self._emit_lifecycle_event("RUN_ERROR", error_details)

            # Log detailed error information
            self.agent.context.log.log(
                type="error",
                heading="AG-UI Processing Error",
                content=json.dumps(error_details, indent=2)
            )

            return Response(
                message=error_msg,
                break_loop=False
            )

    def _process_full_spec(self, parsed_spec: Dict[str, Any]) -> str:
        """
        Process a full AG-UI specification with events, messages, and components.
        """
        html_parts = []

        # Process components
        for component in parsed_spec.get('components', []):
            component_html = self._generate_ui_component(component)
            html_parts.append(component_html)

        # Process messages as components
        for message in parsed_spec.get('messages', []):
            message_html = self._render_message(message)
            html_parts.append(message_html)

        # Wrap everything in a container
        if html_parts:
            return f'<div class="ag-ui-container">{chr(10).join(html_parts)}</div>'
        else:
            return '<div class="ag-ui-container"><p>No components to render</p></div>'

    def _generate_ui_component(self, component: ParsedComponent) -> str:
        """
        Generate UI component HTML compatible with Alpine.js.
        """
        try:
            # Check for custom component
            if component.type in self.custom_components:
                return self.custom_components[component.type].render(component.properties)

            # Generate component based on type
            return self._render_default_component(component)

        except Exception as e:
            # Log detailed error information
            error_info = {
                "component_type": component.type,
                "component_id": component.id,
                "error": str(e),
                "properties_keys": list(component.properties.keys()) if component.properties else [],
                "children_count": len(component.children)
            }

            self.agent.context.log.log(
                type="error",
                heading="Component Generation Error",
                content=json.dumps(error_info, indent=2)
            )

            # Return error component instead of failing completely
            return f'''
            <div class="ag-ui-error" id="{component.id or 'error-component'}">
                <div class="ag-ui-error-header">
                    <strong>Component Error: {component.type}</strong>
                </div>
                <div class="ag-ui-error-message">
                    {str(e)}
                </div>
                <details class="ag-ui-error-details">
                    <summary>Debug Information</summary>
                    <pre>{json.dumps(error_info, indent=2)}</pre>
                </details>
            </div>
            '''

    def _render_default_component(self, component: ParsedComponent) -> str:
        """
        Render default component types.
        """
        component_id = component.id or f"ag-ui-{component.type}-{id(component)}"

        if component.type == "button":
            label = component.properties.get("label", "Click me")
            variant = component.properties.get("variant", "primary")
            disabled = "disabled" if component.properties.get("disabled") else ""
            variant_class = f"ag-ui-button-{variant}" if variant != "primary" else ""

            # Generate button with both Alpine.js and fallback event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback onclick handler
            fallback_onclick = ""
            if component.events and component.events.get("click"):
                click_code = component.events["click"]
                # Escape quotes for HTML attribute
                click_code_escaped = click_code.replace('"', '&quot;').replace("'", "&#39;")
                fallback_onclick = f'onclick="{click_code_escaped}"'

            return f'''<button id="{component_id}"
                       class="ag-ui-button {variant_class}"
                       x-data="aguiButton({{
                           id: '{component_id}',
                           properties: {properties_json},
                           events: {events_json}
                       }})"
                       @click="handleClick()"
                       {fallback_onclick}
                       {disabled}>{label}</button>'''

        elif component.type == "text":
            # Handle both "content" and "value" properties
            content = component.properties.get("content") or component.properties.get("value", "")
            content = self.validator.validate_and_sanitize(content)
            variant = component.properties.get("variant", "")
            custom_class = component.properties.get("class", "")
            variant_class = f"ag-ui-text-{variant}" if variant else ""
            all_classes = f"ag-ui-text {variant_class} {custom_class}".strip()
            return f'<div id="{component_id}" class="{all_classes}">{content}</div>'

        elif component.type == "input":
            input_type = component.properties.get("type", "text")
            placeholder = component.properties.get("placeholder", "")
            value = component.properties.get("value", "")
            required = "required" if component.properties.get("required") else ""

            # Generate input with Alpine.js data binding for proper event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback event handlers
            fallback_events = ""
            if component.events:
                if component.events.get("change"):
                    change_code = component.events["change"].replace('"', '&quot;').replace("'", "&#39;")
                    fallback_events += f' onchange="{change_code}"'
                if component.events.get("input"):
                    input_code = component.events["input"].replace('"', '&quot;').replace("'", "&#39;")
                    fallback_events += f' oninput="{input_code}"'

            return f'''<input id="{component_id}"
                       class="ag-ui-input"
                       type="{input_type}"
                       placeholder="{placeholder}"
                       value="{value}"
                       x-data="aguiInput({{
                           id: '{component_id}',
                           properties: {properties_json},
                           events: {events_json}
                       }})"
                       @input="handleInput($event)"
                       @change="handleChange($event)"
                       {fallback_events}
                       {required} />'''

        elif component.type == "container":
            layout = component.properties.get("layout", "")
            layout_class = f"ag-ui-layout-{layout}" if layout else ""
            custom_class = component.properties.get("class", "")
            all_classes = f"ag-ui-container {layout_class} {custom_class}".strip()

            children_html = ""

            # Handle children from component.children (parsed structure)
            # The parser now handles children from both 'children' and 'properties.children'
            for child in component.children:
                try:
                    children_html += self._generate_ui_component(child)
                except Exception as e:
                    # Log error and continue with other children
                    self.agent.context.log.log(
                        type="error",
                        heading="Child Component Rendering Error",
                        content=f"Failed to render child component: {e}"
                    )
                    # Add error placeholder
                    children_html += f'<div class="ag-ui-error">Error rendering child component: {e}</div>'

            return f'<div id="{component_id}" class="{all_classes}">{children_html}</div>'

        elif component.type == "form":
            action = component.properties.get("action", "#")
            method = component.properties.get("method", "POST")

            # Generate form with Alpine.js data binding for proper event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback event handlers
            fallback_events = ""
            if component.events and component.events.get("submit"):
                submit_code = component.events["submit"].replace('"', '&quot;').replace("'", "&#39;")
                fallback_events = f' onsubmit="{submit_code}"'

            children_html = ""
            for child in component.children:
                children_html += self._generate_ui_component(child)

            return f'''<form id="{component_id}"
                       class="ag-ui-form"
                       action="{action}"
                       method="{method}"
                       x-data="aguiForm({{
                           id: '{component_id}',
                           properties: {properties_json},
                           events: {events_json}
                       }})"
                       @submit="handleSubmit($event)"
                       {fallback_events}>
                       {children_html}
                   </form>'''

        elif component.type == "card":
            title = component.properties.get("title", "")
            content = self.validator.validate_and_sanitize(component.properties.get("content", ""))
            footer = component.properties.get("footer", "")
            
            title_html = f'<div class="ag-ui-card-header"><h3>{title}</h3></div>' if title else ""
            footer_html = f'<div class="ag-ui-card-footer">{footer}</div>' if footer else ""
            
            children_html = ""
            for child in component.children:
                children_html += self._generate_ui_component(child)
            
            return f'''
<div id="{component_id}" class="ag-ui-card">
    {title_html}
    <div class="ag-ui-card-body">
        {content}
        {children_html}
    </div>
    {footer_html}
</div>'''

        elif component.type == "modal":
            title = component.properties.get("title", "Modal")
            content = self.validator.validate_and_sanitize(component.properties.get("content", ""))
            size = component.properties.get("size", "medium")
            closable = component.properties.get("closable", True)
            show_footer = component.properties.get("show_footer", True)
            cancel_label = component.properties.get("cancel_label", "Cancel")
            confirm_label = component.properties.get("confirm_label", "OK")
            
            size_class = f"ag-ui-modal-{size}" if size != "medium" else ""
            close_button = '''
            <button @click="close()" class="ag-ui-modal-close" aria-label="Close modal">
                &times;
            </button>''' if closable else ""
            
            footer_html = f'''
            <div class="ag-ui-modal-footer">
                <button @click="close()" class="ag-ui-button ag-ui-button-secondary">
                    {cancel_label}
                </button>
                <button @click="triggerEvent('MODAL_CONFIRM')" class="ag-ui-button">
                    {confirm_label}
                </button>
            </div>''' if show_footer else ""
            
            properties_json = json.dumps(component.properties)
            return f'''
<div class="ag-ui-modal {size_class}" x-data="aguiModal({{
    id: '{component_id}',
    properties: {properties_json}
}})" x-show="isOpen" x-transition @click="handleBackdropClick($event)" style="display: none;">
    <div class="ag-ui-modal-content" @click.stop="">
        <div class="ag-ui-modal-header">
            <h3 class="ag-ui-modal-title">{title}</h3>
            {close_button}
        </div>
        <div class="ag-ui-modal-body">
            {content}
        </div>
        {footer_html}
    </div>
</div>'''

        elif component.type == "tabs":
            tabs = component.properties.get("tabs", [])
            active_tab = component.properties.get("active_tab", 0)
            
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
                tab_content = self.validator.validate_and_sanitize(tab.get("content", ""))
                content_html += f'''
                <div x-show="activeTab === {i}" 
                     x-transition:enter="transition ease-out duration-300"
                     x-transition:enter-start="opacity-0"
                     x-transition:enter-end="opacity-100"
                     class="ag-ui-tab-panel">
                    {tab_content}
                </div>'''
            
            properties_json = json.dumps(component.properties)
            return f'''
<div id="{component_id}" class="ag-ui-tabs" x-data="aguiTabs({{
    id: '{component_id}',
    properties: {properties_json}
}})">
    <div class="ag-ui-tab-nav">
        {nav_html}
    </div>
    <div class="ag-ui-tab-content">
        {content_html}
    </div>
</div>'''

        elif component.type == "progress":
            value = component.properties.get("value", 0)
            max_value = component.properties.get("max", 100)
            label = component.properties.get("label", "")
            show_percentage = component.properties.get("show_percentage", True)
            variant = component.properties.get("variant", "primary")
            size = component.properties.get("size", "medium")
            animated = component.properties.get("animated", False)
            
            percentage = min(100, max(0, (value / max_value) * 100)) if max_value > 0 else 0
            
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
<div id="{component_id}" class="{' '.join(classes)}">
    {label_html}
    <div class="ag-ui-progress-container">
        <div class="ag-ui-progress-bar" style="width: {percentage}%"></div>
    </div>
    {percentage_html}
</div>'''

        elif component.type == "table":
            headers = component.properties.get("headers", [])
            rows = component.properties.get("rows", [])
            sortable = component.properties.get("sortable", False)
            searchable = component.properties.get("searchable", False)
            pagination = component.properties.get("pagination", False)
            
            # Generate table headers
            header_html = ""
            for header in headers:
                sort_attrs = 'data-sortable="true"' if sortable else ""
                header_html += f'<th {sort_attrs}>{self.validator.validate_and_sanitize(str(header))}</th>'
            
            # Generate table rows
            rows_html = ""
            for row in rows:
                row_html = ""
                for cell in row:
                    row_html += f'<td>{self.validator.validate_and_sanitize(str(cell))}</td>'
                rows_html += f'<tr>{row_html}</tr>'
            
            search_html = '''
            <div class="ag-ui-table-search">
                <input type="text" placeholder="Search..." class="ag-ui-input" @input="filterTable($event)">
            </div>''' if searchable else ""
            
            if sortable or searchable:
                table_attrs = f'x-data="aguiTable({{id: \'{component_id}\', sortable: {str(sortable).lower()}, searchable: {str(searchable).lower()}}})"'
            else:
                table_attrs = ""
            
            return f'''
<div id="{component_id}" class="ag-ui-table-container" {table_attrs}>
    {search_html}
    <table class="ag-ui-table">
        <thead>
            <tr>{header_html}</tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</div>'''

        elif component.type == "list":
            items = component.properties.get("items", [])
            ordered = component.properties.get("ordered", False)
            variant = component.properties.get("variant", "")
            
            tag = "ol" if ordered else "ul"
            variant_class = f"ag-ui-list-{variant}" if variant else ""
            
            items_html = ""
            for item in items:
                if isinstance(item, dict):
                    item_content = self.validator.validate_and_sanitize(item.get("content", ""))
                    item_id = item.get("id", "")
                    item_attrs = f'data-item-id="{item_id}"' if item_id else ""
                else:
                    item_content = self.validator.validate_and_sanitize(str(item))
                    item_attrs = ""
                items_html += f'<li {item_attrs}>{item_content}</li>'
            
            return f'''
<{tag} id="{component_id}" class="ag-ui-list {variant_class}">
    {items_html}
</{tag}>'''

        elif component.type == "alert":
            message = self.validator.validate_and_sanitize(component.properties.get("message", ""))
            variant = component.properties.get("variant", "info")
            dismissible = component.properties.get("dismissible", False)
            title = component.properties.get("title", "")
            
            title_html = f'<div class="ag-ui-alert-title">{title}</div>' if title else ""
            dismiss_button = '''
            <button class="ag-ui-alert-dismiss" @click="dismiss()" aria-label="Close alert">
                &times;
            </button>''' if dismissible else ""
            
            if dismissible:
                alpine_attrs = f'x-data="aguiAlert({{id: \'{component_id}\'}})" x-show="isVisible"'
            else:
                alpine_attrs = ""
            
            return f'''
<div id="{component_id}" class="ag-ui-alert ag-ui-alert-{variant}" {alpine_attrs}>
    {title_html}
    <div class="ag-ui-alert-content">{message}</div>
    {dismiss_button}
</div>'''

        elif component.type == "dropdown":
            options = component.properties.get("options", [])
            placeholder = component.properties.get("placeholder", "Select an option")
            multiple = component.properties.get("multiple", False)
            searchable = component.properties.get("searchable", False)

            # Generate dropdown with Alpine.js data binding for proper event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback event handlers
            fallback_events = ""
            if component.events and component.events.get("change"):
                change_code = component.events["change"].replace('"', '&quot;').replace("'", "&#39;")
                fallback_events = f' onchange="{change_code}"'

            options_html = ""
            for option in options:
                if isinstance(option, dict):
                    value = option.get("value", "")
                    label = self.validator.validate_and_sanitize(option.get("label", value))
                    selected = "selected" if option.get("selected", False) else ""
                else:
                    value = label = self.validator.validate_and_sanitize(str(option))
                    selected = ""
                options_html += f'<option value="{value}" {selected}>{label}</option>'

            attrs = []
            if multiple:
                attrs.append("multiple")

            attrs_str = " " + " ".join(attrs) if attrs else ""

            return f'''
<select id="{component_id}"
        class="ag-ui-dropdown"
        x-data="aguiDropdown({{
            id: '{component_id}',
            properties: {properties_json},
            events: {events_json}
        }})"
        @change="handleChange($event)"
        {fallback_events}
        {attrs_str}>
    <option value="" disabled selected>{placeholder}</option>
    {options_html}
</select>'''

        elif component.type == "textarea":
            placeholder = component.properties.get("placeholder", "")
            value = self.validator.validate_and_sanitize(component.properties.get("value", ""))
            rows = component.properties.get("rows", 4)
            required = "required" if component.properties.get("required", False) else ""
            readonly = "readonly" if component.properties.get("readonly", False) else ""

            # Generate textarea with Alpine.js data binding for proper event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback event handlers
            fallback_events = ""
            if component.events:
                if component.events.get("change"):
                    change_code = component.events["change"].replace('"', '&quot;').replace("'", "&#39;")
                    fallback_events += f' onchange="{change_code}"'
                if component.events.get("input"):
                    input_code = component.events["input"].replace('"', '&quot;').replace("'", "&#39;")
                    fallback_events += f' oninput="{input_code}"'

            return f'''
<textarea id="{component_id}"
          class="ag-ui-textarea"
          placeholder="{placeholder}"
          rows="{rows}"
          x-data="aguiTextarea({{
              id: '{component_id}',
              properties: {properties_json},
              events: {events_json}
          }})"
          @input="handleInput($event)"
          @change="handleChange($event)"
          {fallback_events}
          {required} {readonly}>{value}</textarea>'''

        elif component.type == "checkbox":
            label = self.validator.validate_and_sanitize(component.properties.get("label", ""))
            checked = "checked" if component.properties.get("checked", False) else ""
            value = component.properties.get("value", "")
            required = "required" if component.properties.get("required", False) else ""

            # Generate checkbox with Alpine.js data binding for proper event handling
            events_json = json.dumps(component.events) if component.events else "{}"
            properties_json = json.dumps(component.properties)

            # Create fallback event handlers
            fallback_events = ""
            if component.events and component.events.get("change"):
                change_code = component.events["change"].replace('"', '&quot;').replace("'", "&#39;")
                fallback_events = f' onchange="{change_code}"'

            return f'''
<label class="ag-ui-checkbox-container"
       x-data="aguiCheckbox({{
           id: '{component_id}',
           properties: {properties_json},
           events: {events_json}
       }})">
    <input type="checkbox"
           id="{component_id}"
           class="ag-ui-checkbox"
           value="{value}"
           @change="handleChange($event)"
           {fallback_events}
           {checked} {required}>
    <span class="ag-ui-checkbox-label">{label}</span>
</label>'''

        elif component.type == "radio":
            name = component.properties.get("name", component_id)
            options = component.properties.get("options", [])
            
            options_html = ""
            for i, option in enumerate(options):
                if isinstance(option, dict):
                    value = option.get("value", "")
                    label = self.validator.validate_and_sanitize(option.get("label", value))
                    checked = "checked" if option.get("checked", False) else ""
                else:
                    value = label = self.validator.validate_and_sanitize(str(option))
                    checked = ""
                
                option_id = f"{component_id}-{i}"
                options_html += f'''
                <label class="ag-ui-radio-container">
                    <input type="radio" id="{option_id}" name="{name}" 
                           class="ag-ui-radio" value="{value}" {checked}>
                    <span class="ag-ui-radio-label">{label}</span>
                </label>'''
            
            return f'''
<div id="{component_id}" class="ag-ui-radio-group">
    {options_html}
</div>'''

        elif component.type == "slider":
            min_val = component.properties.get("min", 0)
            max_val = component.properties.get("max", 100)
            value = component.properties.get("value", 50)
            step = component.properties.get("step", 1)
            label = component.properties.get("label", "")
            show_value = component.properties.get("show_value", True)
            
            label_html = f'<label class="ag-ui-slider-label">{label}</label>' if label else ""
            value_display = f'<span class="ag-ui-slider-value" x-text="sliderValue">{value}</span>' if show_value else ""
            
            slider_data = f'aguiSlider({{value: {value}, min: {min_val}, max: {max_val}}})'
            return f'''
<div id="{component_id}" class="ag-ui-slider-container" 
     x-data="{slider_data}">
    {label_html}
    <input type="range" class="ag-ui-slider" 
           min="{min_val}" max="{max_val}" step="{step}" 
           x-model="sliderValue">
    {value_display}
</div>'''

        elif component.type == "canvas":
            nodes = component.properties.get("nodes", [])
            edges = component.properties.get("edges", [])
            width = component.properties.get("width", "100%")
            
            # Calculate dynamic height based on node positions
            max_y = 0
            max_x = 0
            for node in nodes:
                position = node.get("position", {"x": 0, "y": 0})
                x, y = position.get("x", 0), position.get("y", 0)
                max_y = max(max_y, y)
                max_x = max(max_x, x)
            
            # Add padding and set minimum height
            calculated_height = max_y + 120  # Add 120px padding for node height + margin
            min_height = 400
            final_height = max(calculated_height, min_height)
            height = component.properties.get("height", f"{final_height}px")
            
            # Generate nodes HTML
            nodes_html = ""
            for node in nodes:
                node_id = node.get("id", "")
                label = self.validator.validate_and_sanitize(node.get("label", ""))
                position = node.get("position", {"x": 0, "y": 0})
                x, y = position.get("x", 0), position.get("y", 0)
                nodes_html += f'''
                <div class="ag-ui-canvas-node" data-node-id="{node_id}" style="left: {x}px; top: {y}px;">
                    <div class="ag-ui-node-content">{label}</div>
                </div>'''
            
            # Generate edges HTML (simple lines)
            edges_html = ""
            for edge in edges:
                edge_id = edge.get("id", "")
                source = edge.get("source", "")
                target = edge.get("target", "")
                edges_html += f'''
                <div class="ag-ui-canvas-edge" data-edge-id="{edge_id}" data-source="{source}" data-target="{target}"></div>'''
            
            # Generate Alpine.js data for canvas
            canvas_data = {
                "id": component_id,
                "properties": {
                    "nodes": nodes,
                    "edges": edges,
                    "width": width,
                    "height": height
                }
            }
            canvas_data_json = json.dumps(canvas_data)

            return f'''
<div id="{component_id}"
     class="ag-ui-canvas"
     style="width: {width}; height: {height}; position: relative; overflow: hidden;"
     x-data="aguiCanvas({canvas_data_json})">
    <div class="ag-ui-canvas-nodes">{nodes_html}</div>
    <div class="ag-ui-canvas-edges">{edges_html}</div>
    <svg class="ag-ui-canvas-svg" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1;">
        {self._generate_canvas_edges_svg(edges, nodes)}
    </svg>
</div>'''

        else:
            # Generic component rendering
            title = component.properties.get("title", "AG-UI Component")
            content = self.validator.validate_and_sanitize(component.properties.get("content", "No content provided."))

            children_html = ""
            for child in component.children:
                children_html += self._generate_ui_component(child)

            return f'''
<div id="{component_id}" class="ag-ui-component ag-ui-{component.type}">
    <h3 class="ag-ui-title">{title}</h3>
    <div class="ag-ui-content">{content}</div>
    {children_html}
</div>
'''

    def _generate_canvas_edges_svg(self, edges, nodes):
        """
        Generate SVG lines for canvas edges connecting nodes.
        """
        svg_lines = ""
        
        # Create a lookup for node positions
        node_positions = {}
        for node in nodes:
            node_id = node.get("id", "")
            position = node.get("position", {"x": 0, "y": 0})
            # Add node center offset (assuming nodes are 80x40px)
            node_positions[node_id] = {
                "x": position.get("x", 0) + 40,
                "y": position.get("y", 0) + 20
            }
        
        for edge in edges:
            source_id = edge.get("source", "")
            target_id = edge.get("target", "")
            
            if source_id in node_positions and target_id in node_positions:
                source_pos = node_positions[source_id]
                target_pos = node_positions[target_id]
                
                svg_lines += f'''
                <line x1="{source_pos['x']}" y1="{source_pos['y']}" 
                      x2="{target_pos['x']}" y2="{target_pos['y']}" 
                      stroke="#666" stroke-width="2" marker-end="url(#arrowhead)" />'''
        
        # Add arrowhead marker definition
        arrowhead = '''
        <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" 
                    refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#666" />
            </marker>
        </defs>'''
        
        return arrowhead + svg_lines

    def _render_message(self, message) -> str:
        """
        Render an AG-UI message as a component.
        """
        message_id = f"ag-ui-message-{message.id}"
        content = self.validator.validate_and_sanitize(message.content)
        message_type = message.type.value if hasattr(message.type, 'value') else str(message.type)

        return f'''
<div id="{message_id}" class="ag-ui-message ag-ui-message-{message_type}">
    <div class="ag-ui-message-content">{content}</div>
</div>
'''

    def create_simple_component(self, component_type: str, properties: Dict[str, Any], component_id: str = None) -> str:
        """
        Create a simple AG-UI component (convenience method).
        """
        component_spec = {
            "type": component_type,
            "properties": properties
        }

        if component_id:
            component_spec["id"] = component_id

        try:
            parsed_component = self.parser.parse_component(component_spec)
            self.validator.validate_component(parsed_component)
            return self._generate_ui_component(parsed_component)
        except (ValueError, AGUIValidationError) as e:
            return f'<div class="ag-ui-error">Error creating component: {e}</div>'

    def _emit_lifecycle_event(self, event_type: str, data: dict):
        """
        Emit AG-UI protocol lifecycle events.
        """
        event_data = {
            "type": event_type,
            "data": data,
            "protocol": "ag_ui",
            "version": "1.0"
        }
        
        # Log to Agent Zero system only if debug mode is enabled
        if self.debug_mode:
            self.agent.context.log.log(
                type="ag_ui_event",
                heading=f"AG-UI Event: {event_type}",
                content=json.dumps(event_data)
            )
        
        # Store in agent context for potential multi-agent coordination
        if not hasattr(self.agent.context, 'ag_ui_events'):
            self.agent.context.ag_ui_events = []
        self.agent.context.ag_ui_events.append(event_data)

    def _emit_streaming_content(self, content: str):
        """
        Emit streaming content as TEXT_MESSAGE_CONTENT events.
        """
        # Split content into chunks for streaming simulation
        chunk_size = 100
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        
        # Only log streaming chunks if debug mode is enabled
        if self.debug_mode:
            for i, chunk in enumerate(chunks):
                self.agent.context.log.log(
                    type="ag_ui_stream",
                    heading="AG-UI Stream Chunk",
                    content=json.dumps({
                        "type": "TEXT_MESSAGE_CONTENT",
                        "chunk": chunk,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "timestamp": self._get_timestamp()
                    })
                )

    def _get_timestamp(self) -> int:
        """
        Get current timestamp in milliseconds.
        """
        import time
        return int(time.time() * 1000)

    def _get_agent_metadata(self) -> dict:
        """
        Get agent metadata for AG-UI protocol compliance.
        """
        return {
            "agent_id": getattr(self.agent, 'id', 'agent_zero'),
            "agent_type": "agent_zero",
            "capabilities": [
                "ui_generation",
                "event_handling", 
                "state_management",
                "multi_component_support"
            ],
            "protocol_version": "1.0",
            "framework": "agent_zero"
        }

    def _register_agent_if_needed(self):
        """Register this agent with the AG-UI system if not already registered"""
        agent_id = getattr(self.agent, 'id', 'agent_zero')
        
        if not self.config_manager.get_agent_config(agent_id):
            # Create default configuration
            config = create_default_agent_config(
                agent_id=agent_id,
                name=f"Agent Zero - {agent_id}",
                description="Agent Zero instance with AG-UI capabilities"
            )
            
            # Add additional capabilities based on available components
            config.capabilities.update({
                AgentCapability.UI_GENERATION,
                AgentCapability.EVENT_HANDLING,
                AgentCapability.STATE_MANAGEMENT,
                AgentCapability.MULTI_COMPONENT_SUPPORT,
                AgentCapability.STREAMING_RESPONSES,
                AgentCapability.FORM_PROCESSING,
                AgentCapability.CANVAS_INTERACTION,
                AgentCapability.TABLE_OPERATIONS
            })
            
            # Register with configuration manager
            self.config_manager.register_agent(config)
            
            # Register with state manager
            self.state_manager.register_agent(agent_id, {
                "name": config.name,
                "capabilities": [cap.value for cap in config.capabilities],
                "role": config.role.value
            })

    def _update_component_state(self, component_id: str, component_data: dict):
        """Update component state in the state management system"""
        self.state_manager.set_component_state(component_id, {
            "component_type": component_data.get("type"),
            "properties": component_data.get("properties", {}),
            "rendered_at": self._get_timestamp(),
            "agent_id": getattr(self.agent, 'id', 'agent_zero')
        })

    def _check_multi_agent_delegation(self, component_type: str) -> bool:
        """Check if this component should be delegated to a specialist agent"""
        agent_id = getattr(self.agent, 'id', 'agent_zero')
        config = self.config_manager.get_agent_config(agent_id)

        if not config or not config.can_delegate:
            return False

        # Complex component types that might benefit from delegation
        complex_components = ["canvas", "table", "form"]

        if component_type in complex_components:
            # Find specialist agents for this component type
            capability_map = {
                "canvas": AgentCapability.CANVAS_INTERACTION,
                "table": AgentCapability.TABLE_OPERATIONS,
                "form": AgentCapability.FORM_PROCESSING
            }

            required_capability = capability_map.get(component_type)
            if required_capability:
                specialists = self.config_manager.suggest_delegation_targets(
                    required_capability, exclude_agents=[agent_id]
                )

                if specialists:
                    # Log delegation opportunity if debug mode is enabled
                    if self.debug_mode:
                        self.agent.context.log.log(
                            type="info",
                            heading="Delegation Opportunity Available",
                            content=json.dumps({
                                "component_type": component_type,
                                "available_specialists": len(specialists),
                                "recommended_agent": specialists[0]["agent_id"] if specialists else None
                            })
                        )
                    return True

        return False

    def _validate_component_spec(self, spec_data: dict) -> dict:
        """Validate and provide detailed feedback on component specification"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }

        # Check basic structure
        if not isinstance(spec_data, dict):
            validation_result["is_valid"] = False
            validation_result["errors"].append("Specification must be a dictionary/object")
            return validation_result

        # Check for required fields
        if "type" not in spec_data:
            validation_result["is_valid"] = False
            validation_result["errors"].append("Component type is required")

        # Check for common issues
        if "properties" not in spec_data:
            validation_result["warnings"].append("No properties defined for component")

        # Check for children in properties (should be moved to children array)
        if isinstance(spec_data.get("properties"), dict) and "children" in spec_data["properties"]:
            validation_result["suggestions"].append(
                "Consider moving 'children' from properties to root level for better structure"
            )

        # Check for nested structure depth
        def check_nesting_depth(obj, current_depth=0, max_depth=10):
            if current_depth > max_depth:
                validation_result["warnings"].append(
                    f"Deep nesting detected (depth > {max_depth}). This may impact performance."
                )
                return

            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in ["children", "properties"] and isinstance(value, (dict, list)):
                        check_nesting_depth(value, current_depth + 1, max_depth)
            elif isinstance(obj, list):
                for item in obj:
                    check_nesting_depth(item, current_depth + 1, max_depth)

        check_nesting_depth(spec_data)

        return validation_result