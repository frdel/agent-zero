from tavily import TavilyClient, MissingAPIKeyError, InvalidAPIKeyError, UsageLimitExceededError
import models

def tavily_search(query: str, api_key=None):
    """
    Queries the Tavily API using the given parameters.

    Args:
        query (str): The query string to be processed.
        api_key (str, optional): The API key for authentication. Defaults to None.

    Returns:
        str: The result of the query, or an error message.
    """
    api_key = api_key or models.get_api_key("tavily")

    try:
        tavily_client = TavilyClient(api_key=api_key)
    except MissingAPIKeyError:
        return "Error: API key is missing. Please provide a valid API key."

    try:
        answer = tavily_client.qna_search(query=query)
    except InvalidAPIKeyError:
        return "Error: Invalid API key provided. Please check your API key."
    except UsageLimitExceededError:
        return "Error: Usage limit exceeded. Please check your plan's usage limits or consider upgrading."
    except Exception as e:
        return f"Error: {str(e)}"

    return answer