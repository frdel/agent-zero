import re
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import memory
from python.helpers.searxng import search as searxng

class SakanaCitationManager(Tool):
    
    async def execute(self, action="extract", text="", url="", citation_style="apa", **kwargs):
        """
        Citation management tool for academic research.
        
        Actions:
        - extract: Extract citations from text or URL
        - format: Format citations in specified style
        - verify: Verify citation accuracy
        - search: Search for citation information
        - generate: Generate bibliography from citations
        - validate: Validate citation completeness
        """
        
        if action == "extract":
            return await self._extract_citations(text, url)
        elif action == "format":
            return await self._format_citations(text, citation_style)
        elif action == "verify":
            return await self._verify_citations(text, url)
        elif action == "search":
            return await self._search_citation_info(text)
        elif action == "generate":
            return await self._generate_bibliography(text, citation_style)
        elif action == "validate":
            return await self._validate_citations(text)
        else:
            return Response(message=f"Unknown action: {action}. Available actions: extract, format, verify, search, generate, validate", break_loop=False)
    
    async def extract_citations(self, text="", url="", **kwargs):
        """Extract citations from text or URL"""
        return await self.execute(action="extract", text=text, url=url)
    
    async def format_citations(self, text="", citation_style="apa", **kwargs):
        """Format citations in specified style"""
        return await self.execute(action="format", text=text, citation_style=citation_style)
    
    async def generate_bibliography(self, text="", citation_style="apa", **kwargs):
        """Generate bibliography from citations"""
        return await self.execute(action="generate", text=text, citation_style=citation_style)
    
    async def verify_citations(self, text="", url="", **kwargs):
        """Verify citation accuracy"""
        return await self.execute(action="verify", text=text, url=url)
    
    async def _extract_citations(self, text: str, url: str) -> Response:
        """Extract citations from text or URL"""
        try:
            citations = []
            
            if url:
                # Extract citations from URL content
                # This would typically involve web scraping or API calls
                # For now, provide a framework for future implementation
                citations.append({
                    "type": "url",
                    "url": url,
                    "title": "Document from URL",
                    "access_date": datetime.now().strftime("%Y-%m-%d"),
                    "note": "URL-based citation - manual verification required"
                })
            
            if text:
                # Extract citations from text using patterns
                extracted_citations = self._parse_citations_from_text(text)
                citations.extend(extracted_citations)
            
            if not citations:
                return Response(message="No citations found in the provided text or URL", break_loop=False)
            
            # Format extracted citations
            citation_report = f"# Extracted Citations\n\nFound {len(citations)} citation(s):\n\n"
            
            for i, citation in enumerate(citations, 1):
                citation_report += f"## Citation {i}\n"
                for key, value in citation.items():
                    citation_report += f"**{key.title()}**: {value}\n"
                citation_report += "\n"
            
            # Save citations to memory
            await self._save_citations(citations)
            
            await self.agent.handle_intervention(citation_report)
            return Response(message=citation_report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error extracting citations: {str(e)}", break_loop=False)
    
    async def _format_citations(self, text: str, style: str) -> Response:
        """Format citations in specified academic style"""
        try:
            # Extract existing citations from text
            citations = self._parse_citations_from_text(text)
            
            if not citations:
                return Response(message="No citations found to format", break_loop=False)
            
            # Format citations according to style
            formatted_citations = []
            for citation in citations:
                formatted = self._format_single_citation(citation, style)
                formatted_citations.append(formatted)
            
            result = f"# Formatted Citations ({style.upper()} Style)\n\n"
            
            for i, formatted_citation in enumerate(formatted_citations, 1):
                result += f"{i}. {formatted_citation}\n\n"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error formatting citations: {str(e)}", break_loop=False)
    
    async def _verify_citations(self, text: str, url: str) -> Response:
        """Verify citation accuracy through web search"""
        try:
            citations = self._parse_citations_from_text(text) if text else []
            
            if url:
                citations.append({
                    "type": "url",
                    "url": url,
                    "title": "URL Document"
                })
            
            if not citations:
                return Response(message="No citations found to verify", break_loop=False)
            
            verification_results = []
            
            for citation in citations:
                result = await self._verify_single_citation(citation)
                verification_results.append(result)
            
            # Generate verification report
            report = f"# Citation Verification Report\n\nVerified {len(citations)} citation(s):\n\n"
            
            for i, (citation, verification) in enumerate(zip(citations, verification_results), 1):
                report += f"## Citation {i}\n"
                report += f"**Original**: {citation.get('title', 'Unknown')}\n"
                report += f"**Status**: {verification['status']}\n"
                report += f"**Details**: {verification['details']}\n\n"
            
            await self.agent.handle_intervention(report)
            return Response(message=report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error verifying citations: {str(e)}", break_loop=False)
    
    async def _search_citation_info(self, query: str) -> Response:
        """Search for citation information"""
        try:
            if not query:
                return Response(message="Query is required for citation search", break_loop=False)
            
            # Search for academic papers and citations
            search_queries = [
                f"{query} academic paper",
                f"{query} research citation",
                f'"{query}" author publication'
            ]
            
            all_results = []
            
            for search_query in search_queries[:2]:  # Limit searches
                try:
                    results = await searxng(search_query)
                    if results and "results" in results:
                        # Filter for academic sources
                        academic_results = [r for r in results["results"] 
                                         if any(domain in r.get("url", "").lower() 
                                               for domain in ["arxiv", "pubmed", "scholar", "ieee", "acm"])]
                        all_results.extend(academic_results[:3])  # Top 3 per query
                except Exception as e:
                    continue
            
            if not all_results:
                return Response(message=f"No academic sources found for '{query}'", break_loop=False)
            
            # Format search results as potential citations
            citation_candidates = []
            for result in all_results:
                citation = self._extract_citation_from_search_result(result)
                citation_candidates.append(citation)
            
            report = f"# Citation Search Results for '{query}'\n\nFound {len(citation_candidates)} potential citation(s):\n\n"
            
            for i, citation in enumerate(citation_candidates, 1):
                report += f"## Candidate {i}\n"
                for key, value in citation.items():
                    report += f"**{key.title()}**: {value}\n"
                report += "\n"
            
            await self.agent.handle_intervention(report)
            return Response(message=report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error searching citations: {str(e)}", break_loop=False)
    
    async def _generate_bibliography(self, text: str, style: str) -> Response:
        """Generate formatted bibliography"""
        try:
            citations = self._parse_citations_from_text(text)
            
            if not citations:
                return Response(message="No citations found to generate bibliography", break_loop=False)
            
            # Sort citations alphabetically by author/title
            sorted_citations = sorted(citations, key=lambda x: x.get('author', x.get('title', '')).lower())
            
            bibliography = f"# Bibliography ({style.upper()} Style)\n\n"
            
            for citation in sorted_citations:
                formatted = self._format_single_citation(citation, style)
                bibliography += f"{formatted}\n\n"
            
            bibliography += f"\n---\n*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
            bibliography += f"*Total citations: {len(citations)}*"
            
            # Save bibliography to memory
            await self._save_bibliography(bibliography, style)
            
            await self.agent.handle_intervention(bibliography)
            return Response(message=bibliography, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error generating bibliography: {str(e)}", break_loop=False)
    
    async def _validate_citations(self, text: str) -> Response:
        """Validate citation completeness and format"""
        try:
            citations = self._parse_citations_from_text(text)
            
            if not citations:
                return Response(message="No citations found to validate", break_loop=False)
            
            validation_report = f"# Citation Validation Report\n\n"
            
            required_fields = ["title", "author", "year"]
            recommended_fields = ["journal", "volume", "pages", "doi"]
            
            valid_count = 0
            issues = []
            
            for i, citation in enumerate(citations, 1):
                citation_issues = []
                
                # Check required fields
                for field in required_fields:
                    if not citation.get(field):
                        citation_issues.append(f"Missing required field: {field}")
                
                # Check recommended fields
                missing_recommended = [field for field in recommended_fields if not citation.get(field)]
                if missing_recommended:
                    citation_issues.append(f"Missing recommended fields: {', '.join(missing_recommended)}")
                
                # Check DOI format
                doi = citation.get("doi", "")
                if doi and not re.match(r"10\.\d+/.*", doi):
                    citation_issues.append("Invalid DOI format")
                
                # Check year format
                year = citation.get("year", "")
                if year and not re.match(r"\d{4}", str(year)):
                    citation_issues.append("Invalid year format")
                
                if not citation_issues:
                    valid_count += 1
                else:
                    issues.append({
                        "citation_number": i,
                        "title": citation.get("title", "Unknown"),
                        "issues": citation_issues
                    })
            
            validation_report += f"**Total Citations**: {len(citations)}\n"
            validation_report += f"**Valid Citations**: {valid_count}\n"
            validation_report += f"**Citations with Issues**: {len(issues)}\n\n"
            
            if issues:
                validation_report += "## Issues Found\n\n"
                for issue in issues:
                    validation_report += f"### Citation {issue['citation_number']}: {issue['title']}\n"
                    for problem in issue['issues']:
                        validation_report += f"- {problem}\n"
                    validation_report += "\n"
            else:
                validation_report += "All citations are valid and complete.\n"
            
            await self.agent.handle_intervention(validation_report)
            return Response(message=validation_report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error validating citations: {str(e)}", break_loop=False)
    
    def _parse_citations_from_text(self, text: str) -> List[Dict]:
        """Parse citations from text using various patterns"""
        citations = []
        
        # Pattern for DOI-based citations
        doi_pattern = r"doi:\s*(10\.\d+/[^\s]+)"
        dois = re.findall(doi_pattern, text, re.IGNORECASE)
        
        for doi in dois:
            citations.append({
                "type": "journal_article",
                "doi": doi,
                "title": "Article with DOI",
                "note": "Extracted from DOI - complete metadata needed"
            })
        
        # Pattern for URL citations
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        
        for url in urls:
            if any(domain in url.lower() for domain in ["arxiv", "pubmed", "ieee", "acm"]):
                citations.append({
                    "type": "online_source",
                    "url": url,
                    "title": "Online Academic Source",
                    "access_date": datetime.now().strftime("%Y-%m-%d"),
                    "note": "Extracted from URL - metadata verification needed"
                })
        
        # Pattern for year-based citations (Author, Year)
        year_pattern = r"([A-Z][a-z]+(?:\s+et\s+al\.?)?),?\s*\((\d{4})\)"
        year_matches = re.findall(year_pattern, text)
        
        for author, year in year_matches:
            citations.append({
                "type": "academic_reference",
                "author": author,
                "year": year,
                "title": "Referenced Work",
                "note": "Extracted from in-text citation - complete metadata needed"
            })
        
        return citations
    
    def _format_single_citation(self, citation: Dict, style: str) -> str:
        """Format a single citation in the specified style"""
        
        if style.lower() == "apa":
            return self._format_apa_citation(citation)
        elif style.lower() == "mla":
            return self._format_mla_citation(citation)
        elif style.lower() == "ieee":
            return self._format_ieee_citation(citation)
        else:
            return self._format_generic_citation(citation)
    
    def _format_apa_citation(self, citation: Dict) -> str:
        """Format citation in APA style"""
        parts = []
        
        # Author
        author = citation.get("author", "Unknown Author")
        parts.append(f"{author}.")
        
        # Year
        year = citation.get("year", "n.d.")
        parts.append(f"({year}).")
        
        # Title
        title = citation.get("title", "Untitled")
        if citation.get("type") == "journal_article":
            parts.append(f"{title}.")
        else:
            parts.append(f"*{title}*.")
        
        # Journal/Source
        journal = citation.get("journal")
        if journal:
            volume = citation.get("volume", "")
            issue = citation.get("issue", "")
            pages = citation.get("pages", "")
            
            source_part = f"*{journal}*"
            if volume:
                source_part += f", {volume}"
            if issue:
                source_part += f"({issue})"
            if pages:
                source_part += f", {pages}"
            parts.append(f"{source_part}.")
        
        # DOI/URL
        doi = citation.get("doi")
        url = citation.get("url")
        if doi:
            parts.append(f"https://doi.org/{doi}")
        elif url:
            parts.append(f"Retrieved from {url}")
        
        return " ".join(parts)
    
    def _format_mla_citation(self, citation: Dict) -> str:
        """Format citation in MLA style"""
        parts = []
        
        # Author (Last, First)
        author = citation.get("author", "Unknown Author")
        parts.append(f"{author}.")
        
        # Title
        title = citation.get("title", "Untitled")
        if citation.get("type") == "journal_article":
            parts.append(f'"{title}."')
        else:
            parts.append(f"*{title}*.")
        
        # Source information
        journal = citation.get("journal")
        if journal:
            parts.append(f"*{journal}*,")
            
            volume = citation.get("volume")
            issue = citation.get("issue")
            if volume:
                vol_part = f"vol. {volume}"
                if issue:
                    vol_part += f", no. {issue}"
                parts.append(f"{vol_part},")
        
        # Date
        year = citation.get("year", "n.d.")
        parts.append(f"{year},")
        
        # Pages
        pages = citation.get("pages")
        if pages:
            parts.append(f"pp. {pages}.")
        
        return " ".join(parts)
    
    def _format_ieee_citation(self, citation: Dict) -> str:
        """Format citation in IEEE style"""
        parts = []
        
        # Author
        author = citation.get("author", "Unknown Author")
        parts.append(f"{author},")
        
        # Title
        title = citation.get("title", "Untitled")
        parts.append(f'"{title},"')
        
        # Journal
        journal = citation.get("journal")
        if journal:
            parts.append(f"*{journal}*,")
            
            volume = citation.get("volume")
            issue = citation.get("issue")
            if volume:
                vol_part = f"vol. {volume}"
                if issue:
                    vol_part += f", no. {issue}"
                parts.append(f"{vol_part},")
        
        # Pages and year
        pages = citation.get("pages")
        year = citation.get("year", "n.d.")
        if pages:
            parts.append(f"pp. {pages}, {year}.")
        else:
            parts.append(f"{year}.")
        
        return " ".join(parts)
    
    def _format_generic_citation(self, citation: Dict) -> str:
        """Format citation in generic style"""
        elements = []
        for key, value in citation.items():
            if key not in ["type", "note"] and value:
                elements.append(f"{key.title()}: {value}")
        return "; ".join(elements)
    
    async def _verify_single_citation(self, citation: Dict) -> Dict:
        """Verify a single citation through web search"""
        try:
            title = citation.get("title", "")
            author = citation.get("author", "")
            
            if not title and not author:
                return {
                    "status": "Cannot verify",
                    "details": "Insufficient information for verification"
                }
            
            # Construct search query
            search_terms = []
            if title:
                search_terms.append(f'"{title}"')
            if author:
                search_terms.append(author)
            
            query = " ".join(search_terms)
            
            # Search for the citation
            results = await searxng(query)
            
            if results and "results" in results and results["results"]:
                # Check if any results seem to match
                for result in results["results"][:3]:
                    result_title = result.get("title", "").lower()
                    result_content = result.get("content", "").lower()
                    
                    if title and title.lower() in result_title:
                        return {
                            "status": "Likely verified",
                            "details": f"Found matching title in search results: {result.get('url', '')}"
                        }
                    elif author and author.lower() in result_content:
                        return {
                            "status": "Partially verified",
                            "details": f"Found author reference: {result.get('url', '')}"
                        }
                
                return {
                    "status": "Uncertain",
                    "details": "Search results found but no clear match"
                }
            else:
                return {
                    "status": "Not found",
                    "details": "No search results found"
                }
        
        except Exception as e:
            return {
                "status": "Verification failed",
                "details": f"Error during verification: {str(e)}"
            }
    
    def _extract_citation_from_search_result(self, result: Dict) -> Dict:
        """Extract citation information from search result"""
        citation = {
            "type": "search_result",
            "title": result.get("title", "Unknown Title"),
            "url": result.get("url", ""),
            "content_preview": result.get("content", "")[:200] + "..." if result.get("content") else ""
        }
        
        # Try to extract year from URL or content
        url = result.get("url", "")
        content = result.get("content", "")
        
        year_match = re.search(r"(20\d{2})", url + " " + content)
        if year_match:
            citation["year"] = year_match.group(1)
        
        # Try to extract DOI
        doi_match = re.search(r"10\.\d+/[^\s]+", content)
        if doi_match:
            citation["doi"] = doi_match.group(0)
        
        return citation
    
    async def _save_citations(self, citations: List[Dict]):
        """Save citations to memory"""
        try:
            db = await memory.Memory.get(self.agent)
            
            citations_text = json.dumps(citations, indent=2)
            metadata = {
                "type": "citations",
                "count": len(citations),
                "extracted_at": datetime.now().isoformat(),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=f"Extracted Citations:\n\n{citations_text}",
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
        except Exception as e:
            handle_error(e)
    
    async def _save_bibliography(self, bibliography: str, style: str):
        """Save bibliography to memory"""
        try:
            db = await memory.Memory.get(self.agent)
            
            metadata = {
                "type": "bibliography",
                "style": style,
                "generated_at": datetime.now().isoformat(),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=bibliography,
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
        except Exception as e:
            handle_error(e)