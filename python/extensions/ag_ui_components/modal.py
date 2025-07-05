from python.extensions.ag_ui_components.base import AGUIComponent

class Modal(AGUIComponent):
    """
    A modal dialog component.
    """

    def render(self, properties: dict) -> str:
        """
        Renders a modal dialog with header, body, and footer.
        """
        modal_id = properties.get("id", "ag-ui-modal")
        title = properties.get("title", "Modal")
        content = properties.get("content", "")
        size = properties.get("size", "medium")  # small, medium, large
        closable = properties.get("closable", True)
        show_footer = properties.get("show_footer", True)
        cancel_label = properties.get("cancel_label", "Cancel")
        confirm_label = properties.get("confirm_label", "OK")
        
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
        
        return f'''
<div class="ag-ui-modal {size_class}" x-data="aguiModal({{
    id: '{modal_id}',
    properties: {properties}
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