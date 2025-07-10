
from python.extensions.ag_ui_components.base import AGUIComponent

class Button(AGUIComponent):
    """
    A simple button component.
    """

    def render(self, properties: dict) -> str:
        """
        Renders a button with the given label.
        """
        label = properties.get("label", "Click me")
        return f'<button class="ag-ui-button">{label}</button>'
