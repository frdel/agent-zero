from dataclasses import dataclass
from typing import List, Dict, Optional
import asyncio
import aiohttp
from datetime import datetime
import re

@dataclass
class CategorySearch:
    category: str
    max_results: int

@dataclass
class SearchResult:
    url: str
    title: str
    content: Optional[str]
    query: str
    category: Optional[str] = None
    score: float = 0.0
    published_date: Optional[datetime] = None

async def _fetch_results(
    session: aiohttp.ClientSession, 
    base_url: str, 
    query: str, 
    category: Optional[str] = None
) -> List[dict]:
    params = {
        "q": query,
        "safesearch": "0",
        "format": "json",
        "language": "en",
        "engines": "bing,duckduckgo,google,startpage,yandex",
    }
    if category:
        params["categories"] = category
    
    print(f"\nFetching results for query '{query}' in category '{category}'")
    print(f"URL: {base_url}/search")
    print(f"Params: {params}")
    
    async with session.get(f"{base_url}/search", params=params) as response:
        if response.status != 200:
            print(f"Error response: {response.status} {response.reason}")
            raise Exception(f"Search failed: {response.status} {response.reason}")
        
        data = await response.json()
        results = data.get("results", [])
        print(f"Received {len(results)} results from search")
        
        for result in results:
            result["query"] = query
            result["category"] = category
        return results

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{2}/\d{2}/\d{4})',
        r'(\d{4})'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, date_str):
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d')
            except ValueError:
                try:
                    return datetime.strptime(match.group(1), '%m/%d/%Y')
                except ValueError:
                    try:
                        return datetime.strptime(match.group(1), '%Y')
                    except ValueError:
                        continue
    return None

def _calculate_result_score(result: dict) -> float:
    base_score = result.get("score", 0)
    
    content = result.get("content", "")
    if content:
        base_score += min(len(content) / 1000, 0.5)
        
        url = result.get("url", "").lower()
        reputable_domains = [".edu", ".gov", ".org", "wikipedia.org", "github.com"]
        if any(domain in url for domain in reputable_domains):
            base_score += 0.3
            
    return base_score

async def search(
    queries: List[str],
    base_url: str,
    category_limits: List[CategorySearch]
) -> List[SearchResult]:
    print(f"\nStarting search with {len(queries)} queries across {len(category_limits)} categories")
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for query in queries:
            for cat_search in category_limits:
                tasks.append(_fetch_results(session, base_url, query, cat_search.category))
        print(f"Created {len(tasks)} search tasks")
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f"Received {len(results)} result groups")
    
    all_results = []
    category_counts = {cat.category: 0 for cat in category_limits}
    
    for result_group in results:
        if isinstance(result_group, BaseException):
            print(f"Error in result group: {result_group}")
            continue
            
        print(f"Processing result group with {len(result_group)} results")
        
        for result in result_group:
            if not all(k in result for k in ["content", "title", "url", "query"]):
                print(f"Skipping result missing required fields. Available fields: {result.keys()}")
                continue
                
            category = result.get("category")
            if category not in category_counts:
                print(f"Skipping unknown category: {category}")
                continue
                
            cat_limit = next(cat.max_results for cat in category_limits if cat.category == category)
            if category_counts[category] >= cat_limit:
                print(f"Reached limit for category {category}: {category_counts[category]}/{cat_limit}")
                continue
                
            result["score"] = _calculate_result_score(result)
            print(f"Added result for category {category} with score {result['score']}: {result['title']}")
            
            published_date = None
            if "publishedDate" in result:
                published_date = _parse_date(result["publishedDate"])
            elif "metadata" in result:
                published_date = _parse_date(result["metadata"])
            
            search_result = SearchResult(
                url=result["url"],
                title=result["title"],
                content=result.get("content"),
                query=result["query"],
                category=category,
                score=result["score"],
                published_date=published_date
            )
            
            all_results.append(search_result)
            category_counts[category] += 1

    print(f"\nTotal results before deduplication: {len(all_results)}")

    # Deduplicate results keeping highest score per URL
    url_scores = {}
    for result in all_results:
        if result.url not in url_scores or result.score > url_scores[result.url].score:
            url_scores[result.url] = result
    
    print(f"Results after deduplication: {len(url_scores)}")

    # Get deduplicated results
    unique_results = list(url_scores.values())

    # Group by category and sort by score
    by_category = {}
    for r in unique_results:
        cat = r.category or 'unknown'
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)
    
    print("\nResults by category:")
    for cat, results in by_category.items():
        print(f"{cat}: {len(results)} results")

    # Sort within each category and flatten
    final_results = []
    for category in sorted(by_category.keys()):
        category_results = sorted(by_category[category], key=lambda x: x.score, reverse=True)
        final_results.extend(category_results)

    print(f"\nFinal results count: {len(final_results)}")
    return final_results

def parse_categories_settings(settings: str) -> List[CategorySearch]:
    results = []
    settings_list = settings.split(",")
    for setting in settings_list:
        category = ''
        max_search_results = 5
        
        try:
            if ":" in setting:
                category, max_results = setting.split(":")
                max_search_results = int(max_results)
            else:
                category = setting
        except ValueError:
            continue
            
        results.append(CategorySearch(category=category, max_results=max_search_results))
    return results

async def main():
    search_categories = "general,images:3,videos:3,news,map:3,music:3,science:3,files:3,social_media:3,it:3"
    
    searches = parse_categories_settings(search_categories)
    cats = [category.category.capitalize() for category in searches]
    
    print(f"Initialized searXNG search for categories: {', '.join(cats)}")
    print("Waiting for search results...")
    
    results = await search(
        queries=["Camaleonte"],
        base_url="https://searxng-searxng.automa.016180.xyz",
        category_limits=searches
    )
    
    print(f"Received {len(results)} search results.\n")
    
    current_category = None
    for result in results:
        if result.category != current_category:
            current_category = result.category
            print(f"\n=== {current_category} ===")
        print(f"- {result.title} (score: {result.score:.2f})")

if __name__ == "__main__":
    asyncio.run(main())