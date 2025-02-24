import aiohttp
from python.helpers import runtime
import json
import os
from typing import List

URL = "http://localhost:8888/search"

def load_site_list() -> List[str]:
    try:
        site_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "data/search_sites.json")
        with open(site_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('sites', [])
    except Exception as e:
        print(f"Error loading search sites: {e}")
        return []

async def search(query: str):
    sites = load_site_list()
    if sites:
        # Combine sites with OR operator
        site_query = " OR ".join(f"site:{site}" for site in sites)
        search_query = f"({site_query}) {query}"
    else:
        search_query = query
        
    return await runtime.call_development_function(_search, query=search_query)

async def _search(query:str):
    async with aiohttp.ClientSession() as session:
        async with session.post(URL, data={"q": query, "format": "json"}) as response:
            return await response.json()
