import requests
import json
from urllib.parse import urlencode
import os
def search(query: str) -> str:
    """
    Perform a search using the Google Search API.
    
    Args:
        query (str): The search query.
        results (int): The maximum number of results to return.
        region (str): The region for search results.
        time (str): The time range for search results.
        
    Returns:
        str: The search results in a formatted string.
    """
    params = {
        'key': os.getenv("API_KEY_GOOGLE"),
        'cx': os.getenv("CX_KEY_GOOGLE"),
        'q': query
    }

    url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
    resp = requests.get(url)
    
    if resp is None:
        return ""
    try:
        search_results = json.loads(resp.text)
    except Exception:
        return ""
    if search_results is None:
        return ""

    results = search_results.get("items", [])
    search_results = []

    # Normalizing results to match the format of the other search APIs
    for result in results:
        # skip youtube results
        if "youtube.com" in result["link"]:
            continue
        search_result = {
            "title": result["title"],
            "href": result["link"],
            "body": result["snippet"],
        }

        search_results.append(search_result)

    return json.dumps(search_results, indent=2)
