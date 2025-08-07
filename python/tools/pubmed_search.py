import asyncio
from typing import Dict, List, Any
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
import aiohttp
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


class PubMedSearch(Tool):
    """
    Advanced PubMed literature search tool for biomedical research.
    Provides comprehensive search capabilities with result filtering and analysis.
    """
    
    async def execute(self, query: str = "", max_results: int = 20, date_range: str = "", 
                     sort_order: str = "relevance", include_abstracts: bool = True, **kwargs) -> Response:
        """
        Execute PubMed search with advanced filtering options.
        
        Args:
            query: Search query using PubMed query syntax
            max_results: Maximum number of results to return (1-200)
            date_range: Date range filter (e.g., "2020-2024", "last_5_years", "last_year")
            sort_order: Sort order ("relevance", "pub_date", "first_author", "journal")
            include_abstracts: Whether to fetch full abstracts
        """
        
        if not query.strip():
            return Response(message="Error: Search query cannot be empty", break_loop=False)
            
        try:
            # Validate and limit max_results
            max_results = min(max(1, int(max_results)), 200)
            
            # Build search parameters
            search_params = await self._build_search_params(query, date_range, sort_order)
            
            # Execute search
            pmids = await self._search_pubmed(search_params, max_results)
            
            if not pmids:
                return Response(message=f"No results found for query: {query}", break_loop=False)
            
            # Fetch article details
            articles = await self._fetch_article_details(pmids, include_abstracts)
            
            # Format results
            formatted_results = self._format_search_results(articles, query)
            
            return Response(message=formatted_results, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"PubMed search failed: {str(e)}", break_loop=False)
    
    async def _build_search_params(self, query: str, date_range: str, sort_order: str) -> Dict[str, str]:
        """Build search parameters for PubMed API."""
        params = {
            'db': 'pubmed',
            'term': query,
            'retmode': 'xml',
            'usehistory': 'y'
        }
        
        # Add date range filter
        if date_range:
            if date_range == "last_year":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=365)
                params['mindate'] = start_date.strftime("%Y/%m/%d")
                params['maxdate'] = end_date.strftime("%Y/%m/%d")
            elif date_range == "last_5_years":
                end_date = datetime.now()
                start_date = end_date - timedelta(days=5*365)
                params['mindate'] = start_date.strftime("%Y/%m/%d")
                params['maxdate'] = end_date.strftime("%Y/%m/%d")
            elif "-" in date_range:
                try:
                    start_year, end_year = date_range.split("-")
                    params['mindate'] = f"{start_year}/01/01"
                    params['maxdate'] = f"{end_year}/12/31"
                except:
                    pass  # Invalid date range format
        
        # Add sort order
        sort_mapping = {
            "relevance": "relevance",
            "pub_date": "pub+date",
            "first_author": "first+author",
            "journal": "journal"
        }
        params['sort'] = sort_mapping.get(sort_order, "relevance")
        
        return params
    
    async def _search_pubmed(self, params: Dict[str, str], max_results: int) -> List[str]:
        """Execute search against PubMed API."""
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params['retmax'] = str(max_results)
        
        async with aiohttp.ClientSession() as session:
            await self.agent.handle_intervention()
            
            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"PubMed API error: HTTP {response.status}")
                
                content = await response.text()
                
        # Parse XML response
        root = ET.fromstring(content)
        pmids = []
        
        for id_elem in root.findall('.//Id'):
            if id_elem.text:
                pmids.append(id_elem.text)
                
        return pmids
    
    async def _fetch_article_details(self, pmids: List[str], include_abstracts: bool) -> List[Dict[str, Any]]:
        """Fetch detailed article information from PubMed."""
        if not pmids:
            return []
            
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'xml'
        }
        
        async with aiohttp.ClientSession() as session:
            await self.agent.handle_intervention()
            
            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"PubMed fetch error: HTTP {response.status}")
                    
                content = await response.text()
        
        # Parse XML and extract article details
        root = ET.fromstring(content)
        articles = []
        
        for article_elem in root.findall('.//PubmedArticle'):
            article_data = self._parse_article_xml(article_elem, include_abstracts)
            if article_data:
                articles.append(article_data)
                
        return articles
    
    def _parse_article_xml(self, article_elem: ET.Element, include_abstracts: bool) -> Dict[str, Any]:
        """Parse individual article XML element."""
        try:
            # Extract PMID
            pmid_elem = article_elem.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else "Unknown"
            
            # Extract title
            title_elem = article_elem.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else "No title available"
            
            # Extract authors
            authors = []
            for author_elem in article_elem.findall('.//Author'):
                last_name = author_elem.find('.//LastName')
                first_name = author_elem.find('.//ForeName')
                if last_name is not None:
                    author_name = last_name.text
                    if first_name is not None:
                        author_name += f" {first_name.text}"
                    authors.append(author_name)
            
            # Extract journal
            journal_elem = article_elem.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else "Unknown journal"
            
            # Extract publication date
            pub_date_elem = article_elem.find('.//PubDate')
            pub_date = "Unknown date"
            if pub_date_elem is not None:
                year = pub_date_elem.find('.//Year')
                month = pub_date_elem.find('.//Month')
                if year is not None:
                    pub_date = year.text
                    if month is not None:
                        pub_date += f"-{month.text}"
            
            # Extract abstract if requested
            abstract = ""
            if include_abstracts:
                abstract_elem = article_elem.find('.//Abstract/AbstractText')
                if abstract_elem is not None:
                    abstract = abstract_elem.text or ""
            
            # Extract DOI
            doi = ""
            for id_elem in article_elem.findall('.//ArticleId'):
                id_type = id_elem.get('IdType')
                if id_type == 'doi':
                    doi = id_elem.text or ""
                    break
            
            return {
                'pmid': pmid,
                'title': title,
                'authors': authors,
                'journal': journal,
                'pub_date': pub_date,
                'abstract': abstract,
                'doi': doi,
                'pubmed_url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            }
            
        except Exception as e:
            PrintStyle(font_color="orange").print(f"Warning: Failed to parse article: {str(e)}")
            return None
    
    def _format_search_results(self, articles: List[Dict[str, Any]], query: str) -> str:
        """Format search results for display."""
        if not articles:
            return f"No articles found for query: {query}"
        
        result_text = f"PubMed Search Results for: '{query}'\n"
        result_text += f"Found {len(articles)} articles\n\n"
        
        for i, article in enumerate(articles, 1):
            result_text += f"{i}. **{article['title']}**\n"
            
            # Authors
            if article['authors']:
                author_list = ", ".join(article['authors'][:3])  # First 3 authors
                if len(article['authors']) > 3:
                    author_list += f", et al. ({len(article['authors'])} authors)"
                result_text += f"   Authors: {author_list}\n"
            
            # Journal and date
            result_text += f"   Journal: {article['journal']} ({article['pub_date']})\n"
            
            # PMID and DOI
            result_text += f"   PMID: {article['pmid']}"
            if article['doi']:
                result_text += f" | DOI: {article['doi']}"
            result_text += "\n"
            
            # PubMed URL
            result_text += f"   URL: {article['pubmed_url']}\n"
            
            # Abstract (if available)
            if article['abstract']:
                abstract_preview = article['abstract'][:300]
                if len(article['abstract']) > 300:
                    abstract_preview += "..."
                result_text += f"   Abstract: {abstract_preview}\n"
            
            result_text += "\n"
        
        # Add search tips
        result_text += "\n**Search Tips:**\n"
        result_text += "- Use MeSH terms for more precise results\n"
        result_text += "- Combine terms with AND, OR, NOT operators\n"
        result_text += "- Use quotes for exact phrases\n"
        result_text += "- Add [tiab] for title/abstract search\n"
        result_text += "- Use field tags like [au] for author search\n"
        
        return result_text