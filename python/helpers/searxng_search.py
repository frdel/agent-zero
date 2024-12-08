from dataclasses import dataclass
from typing import List, Dict, Optional, Union
import asyncio
import aiohttp
from datetime import datetime
import re

@dataclass
class CategorySearch:
    category: str
    max_results: int

@dataclass
class BaseSearchResult:
    url: str
    title: str
    content: Optional[str]
    query: str
    category: str
    score: float = 0.0
    published_date: Optional[datetime] = None

@dataclass
class GeneralSearchResult(BaseSearchResult):
    category: str = "general"

@dataclass
class ImageSearchResult(BaseSearchResult):
    category: str = "images"
    img_src: Optional[str] = None
    img_format: Optional[str] = None
    thumb_src: Optional[str] = None

@dataclass
class VideoSearchResult(BaseSearchResult):
    category: str = "videos"
    video_url: Optional[str] = None
    length: Optional[str] = None
    thumbnail: Optional[str] = None

@dataclass
class FileSearchResult(BaseSearchResult):
    category: str = "files"
    file_size: Optional[str] = None
    magnet_link: Optional[str] = None
    seed: Optional[int] = None
    leech: Optional[int] = None

SearchResult = Union[GeneralSearchResult, ImageSearchResult, VideoSearchResult, FileSearchResult]

def _create_search_result(result: dict, category: str) -> SearchResult:
    base_args = {
        "url": result["url"],
        "title": result["title"],
        "content": result.get("content"),
        "query": result["query"],
        "category": category,
        "score": result.get("score", 0.0),
        "published_date": _parse_date(result.get("publishedDate") or result.get("metadata"))
    }

    if category == "images":
        return ImageSearchResult(
            **base_args,
            img_src=result.get("img_src"),
            img_format=result.get("format"),
            thumb_src=result.get("thumbnail_src")
        )
    elif category == "videos":
        return VideoSearchResult(
            **base_args,
            video_url=result.get("video_url"),
            length=result.get("length"),
            thumbnail=result.get("thumbnail")
        )
    elif category == "files":
        return FileSearchResult(
            **base_args,
            file_size=result.get("file_size"),
            magnet_link=result.get("magnet_link"),
            seed=result.get("seed"),
            leech=result.get("leech")
        )
    else:
        return GeneralSearchResult(**base_args)

async def _fetch_results(
    session: aiohttp.ClientSession, 
    base_url: str, 
    query: str, 
    category: Optional[str] = None,
    language: str = "en"
) -> List[dict]:
    params = {
        "q": query,
        "safesearch": "0",
        "format": "json",
        "language": language,
        "engines": "bing,duckduckgo,google,startpage,yandex",
    }
    if category:
        params["categories"] = category
    
    print(f"Fetching {category}: {query}")
    async with session.get(f"{base_url}/search", params=params) as response:
        if response.status != 200:
            print(f"Error: {response.status} {response.reason}")
            raise Exception(f"Search failed: {response.status} {response.reason}")
        
        data = await response.json()
        results = data.get("results", [])
        for result in results:
            result["query"] = query
            result["category"] = category
        
        print(f"Got {len(results)} results for {category}")
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
    category_limits: List[CategorySearch],
    language: str = "en"
) -> List[SearchResult]:
    print(f"\nSearching {len(queries)} queries in {len(category_limits)} categories")
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_results(session, base_url, query, cat_search.category, language)
            for query in queries
            for cat_search in category_limits
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_results = []
    category_counts = {cat.category: 0 for cat in category_limits}
    
    for result_group in results:
        if isinstance(result_group, BaseException):
            print(f"Search error: {result_group}")
            continue
        is_first_row=True
        for result in result_group:
            if not all(k in result for k in ["content", "title", "url", "query"]):
                continue

            category = result.get("category")
            if category not in category_counts:
                continue
                
                
            cat_limit = next(cat.max_results for cat in category_limits if cat.category == category)
            if category_counts[category] >= cat_limit:
                continue
                
            if is_first_row:
                print()
                print(f"---- Category {category} ----")
                for key in result.keys():
                    value = result[key]
                    if isinstance(value, str):
                        print(f"\t- {key} ({value[:40]}{'...' if len(value) > 40 else ''})")
                    else:
                        print(f"\t- {key} ({result[key]})")
                is_first_row = False

            result["score"] = _calculate_result_score(result)
            search_result = _create_search_result(result, category)
            all_results.append(search_result)
            category_counts[category] += 1

    print(f"Processing {len(all_results)} initial results")

    # Deduplicate keeping highest score
    url_scores = {}
    for result in all_results:
        if result.url not in url_scores or result.score > url_scores[result.url].score:
            url_scores[result.url] = result
    
    unique_results = list(url_scores.values())

    # Group and sort by category
    by_category = {}
    for r in unique_results:
        cat = r.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r)
    
    # Sort within categories and flatten
    final_results = []
    for category in sorted(by_category.keys()):
        category_results = sorted(by_category[category], key=lambda x: x.score, reverse=True)
        final_results.extend(category_results)

    print(f"Returning {len(final_results)} final results")
    return final_results

def parse_categories_settings(settings: str) -> List[CategorySearch]:
    results = []
    for setting in settings.split(","):
        try:
            if ":" in setting:
                category, max_results = setting.split(":")
                results.append(CategorySearch(category=category, max_results=int(max_results)))
            else:
                results.append(CategorySearch(category=setting, max_results=5))
        except ValueError:
            continue
    return results

async def main():
    search_categories = "general,images:3,videos:3,news,map:3,music:3,science:3,files:3,social_media:3,it:3"
    searches = parse_categories_settings(search_categories)
    
    print(f"Initialized searXNG search for categories: {', '.join(cat.category.capitalize() for cat in searches)}")
    
    results = await search(
        queries=["Camaleonte"],
        base_url="https://searxng-searxng.automa.016180.xyz",
        category_limits=searches,
        language="en"
    )
    
    print("\nResults by category:")
    current_category = None
    for result in results:
        if result.category != current_category:
            current_category = result.category
            print(f"\n=== {current_category} ===")
        
        # Print category-specific details
        if isinstance(result, ImageSearchResult):
            print(f"- {result.title} (score: {result.score:.2f}) [Image: {result.img_src}]")
        elif isinstance(result, VideoSearchResult):
            print(f"- {result.title} (score: {result.score:.2f}) [Length: {result.length}]")
        elif isinstance(result, FileSearchResult):
            print(f"- {result.title} (score: {result.score:.2f}) [Seeder: {result.seed}, Leecher: {result.leech}]")
        else:
            print(f"- {result.title} (score: {result.score:.2f})")

if __name__ == "__main__":
    asyncio.run(main())