
# Base class for custom AG-UI components

from abc import ABC, abstractmethod

class AGUIComponent(ABC):
    """
    Base class for custom AG-UI components.
    """

    @abstractmethod
    def render(self, properties: dict) -> str:
        """
        Renders the component to an HTML string.

        :param properties: A dictionary of properties for the component.
        :return: An HTML string representing the rendered component.
        """
        pass
