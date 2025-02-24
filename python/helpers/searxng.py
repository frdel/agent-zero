import aiohttp
from python.helpers import runtime
from typing import List

URL = "http://localhost:8888/search"

async def search(query: str, sites: List[str]):
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
