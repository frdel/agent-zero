"""
searxng_search.py
----------------
A module for performing federated searches across multiple search engines using SearXNG.
The module aggregates results from different categories (general, images, videos, etc.),
applies scoring, and returns deduplicated results sorted by relevance.

Results Sorting Logic:
--------------------
Results are sorted using a two-tier system:
1. Primary sort: By descending score (-x.score)
    - Base score from search engine
    - Content length bonus (up to 0.5 for 1000+ chars)
    - Domain authority bonus (0.3 for .edu/.gov/.org/wikipedia/github)
2. Secondary sort: By category (x.category)
    - Maintains category grouping while respecting scores
    - Deduplication keeps highest scoring version of each URL
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import aiohttp
import re
from datetime import datetime

from python.helpers.dates_helper import parse_date

@dataclass
class CategorySearch:
    """
    Represents a search category configuration.
    
    Attributes:
        category (str): Search category identifier (e.g., 'general', 'images')
        max_results (int): Maximum number of results to return for this category
    """

    category: str
    max_results: int

@dataclass
class SearchResult:
    url: str
    title: str
    content: Optional[str]
    query: str
    category: str
    score: float = 0.0
    published_date: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_markdown(self) -> str:
        output = []
        output.append(f"### {self.title}\n")

        # Category-specific content formatting
        if self.category == "images":
            if "img_src" in self.metadata:
                output.append(f"![{self.content or self.title}]({self.metadata['img_src']})\n")
        elif self.category == "videos":
            if "thumbnail" in self.metadata and "video_url" in self.metadata:
                output.extend([
                    f"![{self.title}]({self.metadata['thumbnail']})\n",
                    f"[{self.title}]({self.metadata['video_url']})\n"
                ])
        elif self.category == "map":
            if "address" in self.metadata:
                addr = self.metadata["address"]
                output.append(
                    f"{addr.get('road', '')}, {addr.get('house_number', '')} "
                    f"({addr.get('postcode', '')}) {addr.get('locality', '')} "
                    f"{addr.get('country', '')}\n"
                )
        
        # Add content if available and category appropriate
        if self.content and self.category not in ["images"]:
            output.append(f"{self.content}\n")
        
        # Metadata section
        output.append("#### Metadata\n")
        output.append(f"- url: {self.url}\n")
        output.append(f"- score: {self.score}\n")
        output.append(f"- published_date: {self.published_date}\n")
        for key, value in self.metadata.items():
            if value is not None:
                output.append(f"- {key}: {value}\n")
        
        output.append("\n")
        return "".join(output)

def _create_search_result(result: dict, category: str) -> SearchResult:
    """
    Creates a SearchResult object with category-specific metadata.
    
    Special handling for:
    - Images: img_src, format, thumbnail
    - Videos: video_url, length, thumbnail
    - Files: size, magnet link, seed/leech counts
    
    Returns:
        SearchResult object with populated metadata
    """

    metadata = {k: v for k, v in result.items() if k not in 
                ['url', 'title', 'content', 'query', 'category', 'score', 'published_date']}
    
    # Add category-specific metadata
    if category == "images":
        metadata.update({
            "img_src": result.get("img_src"),
            "img_format": result.get("format"),
            "thumbnail_src": result.get("thumbnail_src")
        })
    elif category == "videos":
        metadata.update({
            "video_url": result.get("video_url"),
            "length": result.get("length"),
            "thumbnail": result.get("thumbnail")
        })
    elif category == "files":
        metadata.update({
            "file_size": result.get("file_size"),
            "magnet_link": result.get("magnet_link"),
            "seed": result.get("seed"),
            "leech": result.get("leech")
        })
    
    return SearchResult(
        url=result["url"],
        title=result["title"],
        content=result.get("content"),
        query=result["query"],
        category=category,
        score=result.get("score", 0.0),
        published_date=parse_date(result.get("publishedDate") or result.get("metadata")),
        metadata=metadata
    )

async def _fetch_results(
    session: aiohttp.ClientSession, 
    base_url: str, 
    query: str, 
    category: Optional[str] = None,
    language: str = "en"
) -> List[dict]:
    """
    Fetches results from SearXNG instance.
    
    Uses multiple search engines:
    - Bing
    - DuckDuckGo
    - Google
    - Startpage
    - Yandex
    
    Returns:
        List of raw search results with query and category added
    """

    params = {
        "q": query,
        "safesearch": "0",
        "format": "json",
        "language": language,
        "engines": "bing,duckduckgo,google,startpage,yandex",
    }
    if category:
        params["categories"] = category
    
    async with session.get(f"{base_url}/search", params=params) as response:
        if response.status != 200:
            raise Exception(f"Search failed: {response.status} {response.reason}")
        
        data = await response.json()
        results = data.get("results", [])
        for result in results:
            result["query"] = query
            result["category"] = category
        return results

def _calculate_result_score(result: dict) -> float:
    """
    Calculates relevance score for a search result.
    
    Scoring factors:
    - Base score from search engine
    - Content length (up to 0.5 bonus)
    - Domain authority (+0.3 for trusted domains)
    
    Returns:
        float: Calculated relevance score
    """

    base_score = result.get("score", 0)
    content = result.get("content", "")
    if content:
        base_score += min(len(content) / 1000, 0.5)
        url = result.get("url", "").lower()
        if any(domain in url for domain in [".edu", ".gov", ".org", "wikipedia.org", "github.com"]):
            base_score += 0.3
    return base_score

async def search(
    queries: List[str],
    base_url: str,
    category_limits: List[CategorySearch],
    language: str = "en"
) -> List[SearchResult]:
    """
    Performs concurrent searches across multiple categories and engines.
    
    Args:
        queries: List of search terms
        base_url: SearXNG instance URL
        category_limits: List of CategorySearch configs
        language: ISO language code
    
    Returns:
        Sorted, deduplicated list of SearchResult objects
    """
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_results(session, base_url, query, cat_search.category, language)
            for query in queries
            for cat_search in category_limits
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_results = []
    category_counts = {cat.category: 0 for cat in category_limits}
    
    for i, result_group in enumerate(results):
        if isinstance(result_group, BaseException):
            print(f"Error in result group {i}: {result_group}")
            continue
            
        
        for result in result_group:
            if not all(k in result for k in ["title", "url", "query"]):
                # print(f"Skipping result - missing required fields: {result.keys()}")
                continue
            
            category = result.get("category")
            if category not in category_counts:
                # print(f"Skipping result - unknown category: {category}")
                continue
            
            cat_limit = next(cat.max_results for cat in category_limits if cat.category == category)
            if category_counts[category] >= cat_limit:
                # print(f"Skipping result - category {category} limit reached")
                continue
            
            result["score"] = _calculate_result_score(result)
            search_result = _create_search_result(result, category)
            all_results.append(search_result)
            category_counts[category] += 1
            
    
    # Deduplicate and sort
    url_scores = {}
    for result in all_results:
        if result.url not in url_scores or result.score > url_scores[result.url].score:
            url_scores[result.url] = result
    
    final_results = sorted(url_scores.values(), key=lambda x: (-x.score, x.category))
    
    return final_results

def to_markdown(results: List[SearchResult], query: str) -> str:
    """
    Converts search results to formatted markdown.
    
    Format:
    - Results grouped by category
    - Each result includes metadata section
    - Special formatting for images/videos
    
    Returns:
        Formatted markdown string
    """

    print(f"\nGenerating markdown for {len(results)} results")
    print(f"Query: {query}")

    if len(results) == 0:
        return '''# SearXNG Search Results
The query did not return any result.
'''
    
    output = [
        "# SearXNG Search Results\n",
        f"The following are the search results for query `{query}` divided by category and ordered by relevance.\n"
    ]
    
    current_category = None
    for i, result in enumerate(results):
        
        if result.category != current_category:
            current_category = result.category
            output.append(f"\n## Category {current_category.capitalize()}\n")
        
        markdown = result.to_markdown()
        output.append(markdown)
    
    final_markdown = "".join(output)
    return final_markdown

def parse_categories_settings(settings: str) -> List[CategorySearch]:
    """
    Parses category configuration string.
    
    Format: "category1:limit1,category2:limit2"
    Default limit is 5 if not specified
    
    Returns:
        List of CategorySearch objects
    """

    return [
        CategorySearch(
            category=setting.split(":")[0],
            max_results=int(setting.split(":")[1]) if ":" in setting else 5
        )
        for setting in settings.split(",")
        if setting
    ]

async def main():
    try:
        search_categories = "general,images:3,videos:3,news,map:3,music:3,science:3,files:3"
        print(f"Parsing categories: {search_categories}")
        searches = parse_categories_settings(search_categories)
        
        results = await search(
            queries=["Camaleonte"],
            base_url="http://localhost:8080",
            category_limits=searches,
            language="en"
        )
        
        markdown = to_markdown(results, "Camaleonte")
        print("\nFinal output:")
        print(markdown)
        
    except Exception as e:
        print(f"\nError in main: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())