from python.extensions.ag_ui_components.base import AGUIComponent

class Form(AGUIComponent):
    """
    A form component with validation and submission handling.
    """

    def render(self, properties: dict) -> str:
        """
        Renders a form with fields and validation.
        """
        form_id = properties.get("id", "ag-ui-form")
        action = properties.get("action", "#")
        method = properties.get("method", "POST")
        title = properties.get("title", "")
        fields = properties.get("fields", [])
        submit_label = properties.get("submit_label", "Submit")
        
        fields_html = ""
        for field in fields:
            field_type = field.get("type", "text")
            field_id = field.get("id", "")
            field_name = field.get("name", field_id)
            field_label = field.get("label", "")
            field_placeholder = field.get("placeholder", "")
            field_required = field.get("required", False)
            field_value = field.get("value", "")
            
            required_attr = "required" if field_required else ""
            required_mark = "*" if field_required else ""
            
            if field_type == "textarea":
                field_html = f'''
                <div class="ag-ui-form-field">
                    <label for="{field_id}" class="ag-ui-form-label">{field_label}{required_mark}</label>
                    <textarea id="{field_id}" name="{field_name}" class="ag-ui-input" 
                             placeholder="{field_placeholder}" {required_attr} rows="4">{field_value}</textarea>
                </div>'''
            elif field_type == "select":
                options = field.get("options", [])
                options_html = ""
                for option in options:
                    option_value = option.get("value", "")
                    option_label = option.get("label", option_value)
                    selected = "selected" if option_value == field_value else ""
                    options_html += f'<option value="{option_value}" {selected}>{option_label}</option>'
                
                field_html = f'''
                <div class="ag-ui-form-field">
                    <label for="{field_id}" class="ag-ui-form-label">{field_label}{required_mark}</label>
                    <select id="{field_id}" name="{field_name}" class="ag-ui-input" {required_attr}>
                        {options_html}
                    </select>
                </div>'''
            else:
                field_html = f'''
                <div class="ag-ui-form-field">
                    <label for="{field_id}" class="ag-ui-form-label">{field_label}{required_mark}</label>
                    <input type="{field_type}" id="{field_id}" name="{field_name}" 
                           class="ag-ui-input" placeholder="{field_placeholder}" 
                           value="{field_value}" {required_attr} />
                </div>'''
            
            fields_html += field_html
        
        title_html = f'<h3 class="ag-ui-title">{title}</h3>' if title else ""
        
        return f'''
<div class="ag-ui-component ag-ui-form-wrapper" x-data="aguiForm({{
    id: '{form_id}',
    action: '{action}',
    method: '{method}',
    children: {fields}
}})">
    {title_html}
    <form id="{form_id}" class="ag-ui-form" @submit.prevent="submitForm()">
        {fields_html}
        <div class="ag-ui-form-actions">
            <button type="submit" class="ag-ui-button" :disabled="isSubmitting">
                <span x-show="!isSubmitting">{submit_label}</span>
                <span x-show="isSubmitting" class="ag-ui-loading">
                    <span class="ag-ui-spinner"></span>
                    Submitting...
                </span>
            </button>
        </div>
    </form>
</div>'''