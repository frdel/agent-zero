import aiohttp
from python.helpers import runtime
from python.helpers.errors import handle_error
from python.helpers.print_style import PrintStyle
from typing import List, Dict, Any
from datetime import datetime

URL = "http://localhost:8888/search"

async def search(query: str, sites: List[str]) -> Dict[str, Any]:
    """
    Enhanced search function that supports site-specific searches
    
    Args:
        query: The search query
        sites: List of sites to search
        language: Not used, kept for backward compatibility
        
    Returns:
        Dict containing search results and metadata
    """
    try:
        # Build site-specific query
        if sites:
            # Combine sites with OR operator
            site_queries = []
            for site in sites:
                site = site.strip()
                if site:
                    site_queries.append(f"site:{site}")
            if site_queries:
                site_query = " OR ".join(site_queries)
                search_query = f"{query} ({site_query})"
            else:
                search_query = query
        else:
            search_query = query

        # Clean and encode the search query
        search_query = search_query.strip()
        if not search_query:
            return {"results": [], "error": "Empty search query"}

        # Basic search parameters
        params = {
            "q": search_query,
            "format": "json"
        }
        
        # Debug log
        PrintStyle.standard(f"Sending search request with query: {search_query}")
            
        result = await runtime.call_development_function(_search, **params)
        
        # Debug log
        if isinstance(result, dict):
            result_count = len(result.get("results", []))
            PrintStyle.standard(f"Received {result_count} search results")
        
        # Ensure result has the expected structure
        if not isinstance(result, dict):
            return {"results": [], "error": "Invalid response format"}
            
        # Add default results list if missing
        if "results" not in result:
            result["results"] = []
            
        return result
        
    except Exception as e:
        handle_error(e)
        return {"results": [], "error": str(e)}

async def _search(q: str, **kwargs) -> Dict[str, Any]:
    """
    Internal search function that makes the actual API call
    
    Args:
        q: Search query
        **kwargs: Additional search parameters
        
    Returns:
        Dict containing search results
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Basic parameters
            params = {"q": q, "format": "json"}
            
            # Debug log
            PrintStyle.standard(f"Making request to {URL} with params: {params}")

            async with session.get(URL, params=params) as response:
                # Debug log
                PrintStyle.standard(f"Received response with status: {response.status}")
                
                if response.status != 200:
                    error_text = await response.text()
                    PrintStyle.standard(f"Error response: {error_text[:200]}")
                    return {
                        "results": [], 
                        "error": f"Search failed with status {response.status}. Details: {error_text[:200]}"
                    }
                    
                try:
                    result = await response.json()
                    # Debug log
                    PrintStyle.standard(f"Successfully parsed JSON response")
                except Exception as e:
                    return {"results": [], "error": f"Failed to parse response: {str(e)}"}
                
                # Ensure result has results list
                if not isinstance(result, dict):
                    return {"results": [], "error": "Invalid response format"}
                if "results" not in result:
                    result["results"] = []
                
                # Add timestamp and clean results
                for item in result["results"]:
                    item["timestamp"] = datetime.now().isoformat()
                    # Ensure all required fields exist
                    for field in ["title", "url", "content"]:
                        if field not in item or not item[field]:
                            item[field] = f"No {field} available"
                    
                return result
                
    except Exception as e:
        handle_error(e)
        return {"results": [], "error": f"Search request failed: {str(e)}"}
