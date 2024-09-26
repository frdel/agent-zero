from models import get_api_key


def perform_search(query: str) -> str:
    api_key = get_api_key()
    # Use the api_key to perform the search
    search_result = f"Results for {query} using API key {api_key}"
    return search_result
