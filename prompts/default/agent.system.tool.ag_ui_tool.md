### ag_ui_tool:
Generate dynamic, interactive user interface components using the AG-UI protocol. Creates buttons, forms, cards, modals, progress bars, and other UI elements that render directly in the web interface with full interactivity and state management.

**Supported component types:**
- **button**: Interactive buttons with click handlers, variants (primary/secondary/danger/success), disabled states
- **text**: Text display with variants (small/large/center/right), safe HTML rendering
- **input**: Form inputs (text/email/password/number/tel/url), validation, placeholders, required fields
- **textarea**: Multi-line text inputs with rows, placeholders, readonly/required states
- **container**: Layout containers with children, layout modes (horizontal/grid/flex)
- **form**: Complete forms with validation, submission handling, field management
- **card**: Content cards with headers, bodies, footers, and nested components
- **modal**: Modal dialogs with headers, content, footers, size variants (small/medium/large)
- **tabs**: Tabbed interfaces with multiple content panels, active tab control
- **progress**: Progress bars with percentages, variants, animations, custom labels
- **table**: Data tables with headers, rows, sorting, searching, row selection
- **list**: Ordered/unordered lists with bullet variants, interactive items
- **alert**: Notification alerts with variants (info/success/warning/error), dismissible
- **dropdown**: Select dropdowns with options, placeholders, multiple selection, searchable
- **checkbox**: Checkboxes with labels, checked states, validation
- **radio**: Radio button groups with multiple options, single selection
- **slider**: Range sliders with min/max values, step controls, value display
- **canvas**: Interactive workflow canvases with nodes, edges, drag and drop

**Features:**
- Real-time state persistence in localStorage
- Cross-tab state synchronization
- Event handling and form submissions
- Responsive design with mobile support
- Accessibility features and keyboard navigation
- Security validation and XSS protection
- Alpine.js reactive components with data binding

**Example usage - Simple button:**
~~~json
{
    "thoughts": [
        "User wants a button to trigger an action",
        "I'll create an interactive button with success styling"
    ],
    "headline": "Creating interactive AG-UI button",
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"button\",\"properties\":{\"label\":\"Click Me!\",\"variant\":\"success\"},\"events\":{\"click\":\"alert('Button clicked!')\"},\"id\":\"demo-btn\"}"
    }
}
~~~

**Example usage - Contact form:**
~~~json
{
    "thoughts": [
        "User needs a contact form with validation",
        "I'll create a form with name, email, and message fields"
    ],
    "headline": "Creating AG-UI contact form with validation",
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"form\",\"properties\":{\"title\":\"Contact Us\",\"action\":\"/contact\",\"fields\":[{\"type\":\"text\",\"id\":\"name\",\"label\":\"Full Name\",\"required\":true},{\"type\":\"email\",\"id\":\"email\",\"label\":\"Email Address\",\"required\":true},{\"type\":\"textarea\",\"id\":\"message\",\"label\":\"Message\",\"placeholder\":\"Your message here...\"}],\"submit_label\":\"Send Message\"},\"id\":\"contact-form\"}"
    }
}
~~~

**Example usage - Dashboard with multiple components:**
~~~json
{
    "thoughts": [
        "User wants a dashboard layout with cards and progress",
        "I'll create a container with multiple child components"
    ],
    "headline": "Creating AG-UI dashboard layout",
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"container\",\"properties\":{\"layout\":\"grid\"},\"children\":[{\"type\":\"card\",\"properties\":{\"title\":\"Welcome\",\"content\":\"Dashboard overview\"},\"id\":\"welcome-card\"},{\"type\":\"progress\",\"properties\":{\"label\":\"Project Progress\",\"value\":75,\"variant\":\"primary\",\"show_percentage\":true},\"id\":\"project-progress\"},{\"type\":\"button\",\"properties\":{\"label\":\"View Details\",\"variant\":\"primary\"},\"id\":\"details-btn\"}],\"id\":\"dashboard\"}"
    }
}
~~~

**Example usage - Full specification with events:**
~~~json
{
    "thoughts": [
        "User needs complex UI with multiple components and events",
        "I'll use the full AG-UI specification format"
    ],
    "headline": "Creating comprehensive AG-UI interface",
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"components\":[{\"type\":\"card\",\"properties\":{\"title\":\"User Profile\",\"content\":\"Manage your account settings\"},\"id\":\"profile-card\"},{\"type\":\"form\",\"properties\":{\"fields\":[{\"type\":\"text\",\"id\":\"username\",\"label\":\"Username\"},{\"type\":\"email\",\"id\":\"email\",\"label\":\"Email\"}]},\"id\":\"profile-form\"}],\"events\":[{\"type\":\"RUN_STARTED\",\"timestamp\":1234567890}]}"
    }
}
~~~

**Supported Events:**
- **BUTTON_CLICK**: Button click interactions
- **FORM_SUBMIT**: Form submission with validation
- **INPUT_CHANGE/FOCUS/BLUR**: Input field interactions
- **MODAL_OPEN/CLOSE/CONFIRM/CANCEL**: Modal dialog events
- **TAB_CHANGE/CLICK**: Tab navigation events
- **TABLE_SORT/SEARCH/ROW_SELECT**: Table interaction events
- **LIST_ITEM_CLICK/SELECT**: List item interactions
- **ALERT_DISMISS/ACTION**: Alert notification events
- **DROPDOWN_CHANGE/OPEN/CLOSE**: Dropdown selection events
- **CHECKBOX_CHANGE/RADIO_CHANGE**: Form control events
- **SLIDER_CHANGE/START/END**: Slider value events
- **CANVAS_NODE_CLICK/DRAG/EDGE_CLICK**: Canvas interaction events
- **PROGRESS_UPDATE/COMPLETE**: Progress tracking events

**Example usage - Data Table:**
~~~json
{
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"table\",\"properties\":{\"headers\":[\"Name\",\"Email\",\"Status\"],\"rows\":[[\"John Doe\",\"john@example.com\",\"Active\"],[\"Jane Smith\",\"jane@example.com\",\"Inactive\"]],\"sortable\":true,\"searchable\":true},\"id\":\"users-table\"}"
    }
}
~~~

**Example usage - Interactive Canvas:**
~~~json
{
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"canvas\",\"properties\":{\"nodes\":[{\"id\":\"start\",\"label\":\"Start\",\"position\":{\"x\":50,\"y\":100}},{\"id\":\"process\",\"label\":\"Process\",\"position\":{\"x\":200,\"y\":150}},{\"id\":\"end\",\"label\":\"End\",\"position\":{\"x\":350,\"y\":100}}],\"edges\":[{\"id\":\"e1\",\"source\":\"start\",\"target\":\"process\"},{\"id\":\"e2\",\"source\":\"process\",\"target\":\"end\"}]},\"id\":\"workflow-canvas\"}"
    }
}
~~~

**Example usage - Alert with Actions:**
~~~json
{
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"alert\",\"properties\":{\"message\":\"Operation completed successfully!\",\"title\":\"Success\",\"variant\":\"success\",\"dismissible\":true},\"id\":\"success-alert\"}"
    }
}
~~~

**Example usage - Slider Control:**
~~~json
{
    "tool_name": "ag_ui_tool",
    "tool_args": {
        "ag_ui_spec": "{\"type\":\"slider\",\"properties\":{\"min\":0,\"max\":100,\"value\":50,\"step\":5,\"label\":\"Volume Level\",\"show_value\":true},\"id\":\"volume-slider\"}"
    }
}
~~~

**Guidelines:**
- Always provide meaningful IDs for components to enable state management
- Use appropriate component types for the intended functionality
- Include proper labels and placeholders for form fields
- Set required fields for form validation
- Choose appropriate variants for visual consistency
- Nest components logically using containers
- Ensure JSON is properly escaped in the ag_ui_spec argument
- Test complex specifications with simpler components first
- Listen for component events to create interactive experiences
- Use state persistence for user preferences and form data

**Security considerations:**
- All content is automatically sanitized for XSS protection
- HTML tags are validated against an allowed list
- Component properties are validated for type and length
- Event handlers are sandboxed and validated
- State data is encrypted and secured in localStorage

The AG-UI tool creates rich, interactive components that seamlessly integrate with Agent Zero's interface, providing users with dynamic, responsive UI elements that persist state, handle user interactions, and support complex workflows through comprehensive event handling.