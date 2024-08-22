from agent import Agent
from python.helpers.tavily_search import tavily_search
from python.helpers.tool import Tool, Response

class OnlineKnowledge(Tool):
    def __init__(self, api_key=None):
        """
        Initializes the OnlineKnowledge tool.

        Args:
            api_key (str, optional): The API key for the Tavily API.
        """
        self.api_key = api_key

    def execute(self, **kwargs):
        """
        Executes the tool with the given arguments.

        Args:
            **kwargs: The keyword arguments.

        Returns:
            Response: The response object.
        """
        question = kwargs.get("question", "")
        if not question:
            return Response(message="Error: No question provided", break_loop=True)
        return Response(
            message=process_question(question, api_key=self.api_key),
            break_loop=False,
        )

def process_question(question, api_key=None):
    """
    Processes the question using the Tavily API.

    Args:
        question (str): The question to be processed.
        api_key (str, optional): The API key. Defaults to None.

    Returns:
        str: The processed result.
    """
    return str(tavily_search(query=question, api_key=api_key))