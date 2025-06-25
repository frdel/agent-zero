import os
import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import memory
from python.helpers.searxng import search as searxng
from python.helpers.document_query import DocumentQueryHelper
from python.tools.memory_load import DEFAULT_THRESHOLD as DEFAULT_MEMORY_THRESHOLD

class SakanaResearch(Tool):
    
    async def execute(self, research_query="", research_type="comprehensive", depth="medium", focus_areas="", max_papers=20, **kwargs):
        """
        Main research execution method supporting multiple research strategies:
        - comprehensive: Full literature review with gap analysis
        - targeted: Focused search on specific topics
        - citation_analysis: Follow citation chains for deep investigation
        - trend_analysis: Identify emerging patterns and trends
        """
        
        if not research_query:
            return Response(message="Research query is required", break_loop=False)
            
        research_context = {
            "query": research_query,
            "type": research_type,
            "depth": depth,
            "focus_areas": focus_areas.split(",") if focus_areas else [],
            "max_papers": int(max_papers),
            "timestamp": datetime.now().isoformat()
        }
        
        PrintStyle(font_color="#2E86AB", bold=True).print(f"Starting {research_type} research: {research_query}")
        
        results = await self._execute_research_strategy(research_context)
        
        await self.agent.handle_intervention(results)
        return Response(message=results, break_loop=False)
    
    async def literature_review(self, topic="", max_papers=15, **kwargs):
        """Comprehensive literature review with synthesis"""
        return await self.execute(research_query=topic, research_type="comprehensive", max_papers=max_papers)
    
    async def paper_analysis(self, paper_url="", analysis_focus="methodology,results,limitations", **kwargs):
        """Deep analysis of a specific paper"""
        if not paper_url:
            return Response(message="Paper URL is required for analysis", break_loop=False)
            
        helper = DocumentQueryHelper(self.agent)
        analysis_queries = self._generate_analysis_queries(analysis_focus)
        
        try:
            found, analysis_results = await helper.document_qa(paper_url, analysis_queries)
            if not found:
                return Response(message=f"Could not access or analyze paper at {paper_url}", break_loop=False)
                
            formatted_analysis = self._format_paper_analysis(paper_url, analysis_results, analysis_focus)
            await self._save_paper_analysis(paper_url, formatted_analysis)
            
            return Response(message=formatted_analysis, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error analyzing paper: {str(e)}", break_loop=False)
    
    async def research_gap_analysis(self, domain="", current_knowledge="", **kwargs):
        """Identify research gaps in a domain"""
        research_context = {
            "query": f"research gaps in {domain}",
            "type": "gap_analysis", 
            "domain": domain,
            "current_knowledge": current_knowledge,
            "timestamp": datetime.now().isoformat()
        }
        
        # Search for recent work in the domain
        recent_work = await self._search_recent_publications(domain)
        
        # Analyze current state and identify gaps
        gap_analysis = await self._analyze_research_gaps(domain, recent_work, current_knowledge)
        
        # Save findings to memory
        await self._save_research_findings("gap_analysis", gap_analysis, research_context)
        
        return Response(message=gap_analysis, break_loop=False)
    
    async def _execute_research_strategy(self, context: Dict) -> str:
        """Execute the specified research strategy"""
        strategy = context["type"]
        
        if strategy == "comprehensive":
            return await self._comprehensive_research(context)
        elif strategy == "targeted":
            return await self._targeted_research(context)
        elif strategy == "citation_analysis":
            return await self._citation_analysis(context)
        elif strategy == "trend_analysis":
            return await self._trend_analysis(context)
        elif strategy == "gap_analysis":
            return await self._gap_analysis_research(context)
        else:
            return await self._comprehensive_research(context)
    
    async def _comprehensive_research(self, context: Dict) -> str:
        """Comprehensive literature review with multi-source search"""
        query = context["query"]
        max_papers = context["max_papers"]
        
        # Parallel search across multiple sources
        tasks = [
            self._academic_search(query, max_papers//2),
            self._web_search(query),
            self._memory_search(query),
        ]
        
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        academic_results, web_results, memory_results = search_results
        
        # Deep analysis of top papers
        top_papers = self._extract_top_papers(academic_results, context["depth"])
        analyzed_papers = await self._batch_analyze_papers(top_papers)
        
        # Synthesize findings
        synthesis = await self._synthesize_research_findings(
            query, analyzed_papers, web_results, memory_results, context
        )
        
        # Save comprehensive research to memory
        await self._save_research_findings("comprehensive", synthesis, context)
        
        return synthesis
    
    async def _academic_search(self, query: str, limit: int = 10) -> Dict:
        """Search academic sources with enhanced queries"""
        academic_queries = [
            f"{query} research paper",
            f"{query} academic study",
            f"{query} literature review",
            f"survey {query}",
            f"{query} methodology"
        ]
        
        all_results = {"results": []}
        
        for academic_query in academic_queries[:3]:  # Limit to prevent overwhelming
            try:
                result = await searxng(academic_query)
                if result and "results" in result:
                    # Filter for academic sources
                    academic_results = self._filter_academic_sources(result["results"])
                    all_results["results"].extend(academic_results)
            except Exception as e:
                handle_error(e)
                continue
        
        # Remove duplicates and limit results
        unique_results = self._deduplicate_results(all_results["results"])
        all_results["results"] = unique_results[:limit]
        
        return all_results
    
    async def _web_search(self, query: str) -> Dict:
        """Enhanced web search for research context"""
        try:
            return await searxng(f"{query} research recent developments")
        except Exception as e:
            handle_error(e)
            return {"results": []}
    
    async def _memory_search(self, query: str) -> str:
        """Search existing memory for relevant research"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.search_similarity_threshold(
                query=query, limit=10, threshold=DEFAULT_MEMORY_THRESHOLD
            )
            return memory.Memory.format_docs_plain(docs)
        except Exception as e:
            handle_error(e)
            return "No relevant memory found"
    
    def _filter_academic_sources(self, results: List[Dict]) -> List[Dict]:
        """Filter results to prioritize academic sources"""
        academic_domains = [
            'arxiv.org', 'pubmed.ncbi.nlm.nih.gov', 'scholar.google.com',
            'ieee.org', 'acm.org', 'springer.com', 'sciencedirect.com',
            'nature.com', 'science.org', 'plos.org', 'biorxiv.org'
        ]
        
        academic_results = []
        other_results = []
        
        for result in results:
            url = result.get('url', '').lower()
            if any(domain in url for domain in academic_domains):
                academic_results.append(result)
            else:
                other_results.append(result)
        
        # Prioritize academic sources
        return academic_results + other_results
    
    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results based on URL and title similarity"""
        seen_urls = set()
        seen_titles = set()
        unique_results = []
        
        for result in results:
            url = result.get('url', '')
            title = result.get('title', '').lower()
            
            if url not in seen_urls and title not in seen_titles:
                seen_urls.add(url)
                seen_titles.add(title)
                unique_results.append(result)
        
        return unique_results
    
    def _extract_top_papers(self, search_results: Dict, depth: str) -> List[Dict]:
        """Extract top papers based on relevance and source quality"""
        if isinstance(search_results, Exception) or not search_results.get("results"):
            return []
        
        papers = search_results["results"]
        
        # Score papers based on academic indicators
        scored_papers = []
        for paper in papers:
            score = self._calculate_paper_score(paper)
            scored_papers.append((score, paper))
        
        # Sort by score and return top papers
        scored_papers.sort(key=lambda x: x[0], reverse=True)
        
        depth_limits = {"shallow": 3, "medium": 5, "deep": 8}
        limit = depth_limits.get(depth, 5)
        
        return [paper for score, paper in scored_papers[:limit]]
    
    def _calculate_paper_score(self, paper: Dict) -> float:
        """Calculate relevance score for academic papers"""
        score = 0.0
        
        url = paper.get('url', '').lower()
        title = paper.get('title', '').lower()
        content = paper.get('content', '').lower()
        
        # Academic source bonus
        academic_domains = ['arxiv.org', 'pubmed', 'ieee.org', 'acm.org']
        if any(domain in url for domain in academic_domains):
            score += 2.0
        
        # Title indicators
        research_terms = ['research', 'study', 'analysis', 'survey', 'review']
        score += sum(0.5 for term in research_terms if term in title)
        
        # Recent publication bonus (heuristic based on URL patterns)
        current_year = datetime.now().year
        for year in range(current_year-2, current_year+1):
            if str(year) in url or str(year) in title:
                score += 1.0
                break
        
        return score
    
    async def _batch_analyze_papers(self, papers: List[Dict]) -> List[Dict]:
        """Analyze multiple papers in parallel"""
        if not papers:
            return []
        
        helper = DocumentQueryHelper(self.agent)
        analysis_queries = [
            "What is the main research question or hypothesis?",
            "What methodology is used?",
            "What are the key findings and results?",
            "What are the limitations mentioned?",
            "What future work is suggested?"
        ]
        
        analysis_tasks = []
        for paper in papers:
            url = paper.get('url', '')
            if url:
                analysis_tasks.append(helper.document_qa(url, analysis_queries))
        
        analysis_results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        
        analyzed_papers = []
        for i, result in enumerate(analysis_results):
            if isinstance(result, Exception):
                continue
            
            found, qa_results = result
            if found and qa_results:
                analyzed_papers.append({
                    **papers[i],
                    'analysis': qa_results,
                    'analyzed_at': datetime.now().isoformat()
                })
        
        return analyzed_papers
    
    async def _synthesize_research_findings(self, query: str, analyzed_papers: List[Dict], 
                                          web_results: Dict, memory_results: str, context: Dict) -> str:
        """Synthesize all research findings into comprehensive report"""
        
        synthesis_sections = []
        
        # Executive Summary
        synthesis_sections.append("# Research Synthesis Report")
        synthesis_sections.append(f"**Query**: {query}")
        synthesis_sections.append(f"**Research Type**: {context['type']}")
        synthesis_sections.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        synthesis_sections.append("")
        
        # Key Findings
        synthesis_sections.append("## Key Findings")
        if analyzed_papers:
            key_findings = self._extract_key_findings(analyzed_papers)
            synthesis_sections.extend(key_findings)
        else:
            synthesis_sections.append("No detailed paper analysis available.")
        synthesis_sections.append("")
        
        # Methodological Approaches
        synthesis_sections.append("## Common Methodological Approaches")
        methodologies = self._extract_methodologies(analyzed_papers)
        synthesis_sections.extend(methodologies)
        synthesis_sections.append("")
        
        # Research Gaps and Limitations
        synthesis_sections.append("## Identified Research Gaps and Limitations")
        gaps = self._identify_research_gaps(analyzed_papers)
        synthesis_sections.extend(gaps)
        synthesis_sections.append("")
        
        # Recent Developments
        synthesis_sections.append("## Recent Developments")
        if web_results and web_results.get("results"):
            recent_info = self._extract_recent_developments(web_results["results"])
            synthesis_sections.extend(recent_info)
        else:
            synthesis_sections.append("No recent developments found.")
        synthesis_sections.append("")
        
        # Related Knowledge
        if memory_results and memory_results.strip():
            synthesis_sections.append("## Related Knowledge from Memory")
            synthesis_sections.append(memory_results)
            synthesis_sections.append("")
        
        # Future Research Directions
        synthesis_sections.append("## Suggested Future Research Directions")
        future_directions = self._suggest_future_research(analyzed_papers, context)
        synthesis_sections.extend(future_directions)
        
        return "\n".join(synthesis_sections)
    
    def _extract_key_findings(self, analyzed_papers: List[Dict]) -> List[str]:
        """Extract key findings from analyzed papers"""
        findings = []
        
        for i, paper in enumerate(analyzed_papers, 1):
            title = paper.get('title', f'Paper {i}')
            analysis = paper.get('analysis', '')
            
            findings.append(f"### {title}")
            if analysis:
                # Extract key results from analysis
                if "key findings" in analysis.lower() or "results" in analysis.lower():
                    findings.append(f"- {analysis[:200]}...")
                else:
                    findings.append(f"- Analysis available but key findings not clearly extracted")
            else:
                findings.append(f"- No detailed analysis available")
            findings.append("")
        
        return findings
    
    def _extract_methodologies(self, analyzed_papers: List[Dict]) -> List[str]:
        """Extract common methodologies from papers"""
        methodologies = []
        method_patterns = set()
        
        for paper in analyzed_papers:
            analysis = paper.get('analysis', '').lower()
            
            # Look for methodology keywords
            methods = re.findall(r'\b(machine learning|deep learning|statistical|experimental|survey|qualitative|quantitative|case study|meta-analysis)\b', analysis)
            method_patterns.update(methods)
        
        if method_patterns:
            methodologies.append("Common approaches identified:")
            for method in sorted(method_patterns):
                methodologies.append(f"- {method.title()}")
        else:
            methodologies.append("No clear methodological patterns identified.")
        
        return methodologies
    
    def _identify_research_gaps(self, analyzed_papers: List[Dict]) -> List[str]:
        """Identify research gaps from paper limitations"""
        gaps = []
        limitations = []
        
        for paper in analyzed_papers:
            analysis = paper.get('analysis', '').lower()
            
            # Look for limitations and future work
            if 'limitation' in analysis or 'future work' in analysis:
                # Extract relevant sentences
                sentences = analysis.split('.')
                for sentence in sentences:
                    if any(keyword in sentence for keyword in ['limitation', 'future', 'gap', 'need']):
                        limitations.append(sentence.strip())
        
        if limitations:
            gaps.append("Identified limitations and gaps:")
            for limitation in limitations[:5]:  # Limit to prevent overwhelming
                if limitation:
                    gaps.append(f"- {limitation[:150]}...")
        else:
            gaps.append("No explicit research gaps identified in the analyzed papers.")
        
        return gaps
    
    def _extract_recent_developments(self, web_results: List[Dict]) -> List[str]:
        """Extract recent developments from web search results"""
        developments = []
        
        for result in web_results[:5]:  # Limit to top 5 results
            title = result.get('title', '')
            content = result.get('content', '')
            url = result.get('url', '')
            
            if title and content:
                developments.append(f"### {title}")
                developments.append(f"Source: {url}")
                developments.append(f"{content[:200]}...")
                developments.append("")
        
        return developments if developments else ["No recent developments found in web sources."]
    
    def _suggest_future_research(self, analyzed_papers: List[Dict], context: Dict) -> List[str]:
        """Suggest future research directions based on analysis"""
        suggestions = []
        
        # Base suggestions on research gaps and domain
        query = context.get('query', '')
        
        suggestions.append(f"Based on the analysis of research on '{query}', the following areas show potential:")
        suggestions.append("")
        
        # Generic suggestions based on common research patterns
        if analyzed_papers:
            suggestions.append("1. **Methodological Improvements**: Addressing limitations identified in current approaches")
            suggestions.append("2. **Cross-Domain Applications**: Applying successful methods to related domains")
            suggestions.append("3. **Scalability Studies**: Investigating performance at larger scales")
            suggestions.append("4. **Comparative Analysis**: Systematic comparison of different approaches")
            suggestions.append("5. **Real-World Validation**: Testing theoretical findings in practical applications")
        else:
            suggestions.append("1. **Foundational Research**: Establishing baseline studies in this area")
            suggestions.append("2. **Literature Mapping**: Comprehensive review of existing work")
            suggestions.append("3. **Methodology Development**: Creating standardized approaches")
        
        return suggestions
    
    async def _save_research_findings(self, research_type: str, findings: str, context: Dict):
        """Save research findings to memory for future reference"""
        try:
            db = await memory.Memory.get(self.agent)
            
            metadata = {
                "type": "research_findings",
                "research_type": research_type,
                "query": context.get("query", ""),
                "timestamp": context.get("timestamp", datetime.now().isoformat()),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=findings,
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
            PrintStyle(font_color="#28B463").print(f"Research findings saved to memory: {research_type}")
            
        except Exception as e:
            handle_error(e)
            PrintStyle(font_color="#E74C3C").print(f"Failed to save research findings: {str(e)}")
    
    def _generate_analysis_queries(self, focus: str) -> List[str]:
        """Generate analysis queries based on focus areas"""
        base_queries = [
            "What is the main research question or objective?",
            "What methodology or approach is used?",
            "What are the key findings or results?",
            "What are the main contributions of this work?",
            "What limitations are acknowledged?",
            "What future work is suggested?"
        ]
        
        focus_areas = focus.lower().split(",")
        specialized_queries = []
        
        for area in focus_areas:
            area = area.strip()
            if area == "methodology":
                specialized_queries.extend([
                    "What experimental design is used?",
                    "What data collection methods are employed?",
                    "How is the data analyzed?"
                ])
            elif area == "results":
                specialized_queries.extend([
                    "What are the quantitative results?",
                    "What statistical significance is reported?",
                    "How do results compare to baselines?"
                ])
            elif area == "limitations":
                specialized_queries.extend([
                    "What are the study limitations?",
                    "What assumptions are made?",
                    "What potential biases are discussed?"
                ])
        
        return base_queries + specialized_queries
    
    def _format_paper_analysis(self, url: str, analysis: str, focus: str) -> str:
        """Format paper analysis results"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        formatted = f"""# Paper Analysis Report

**URL**: {url}
**Analysis Focus**: {focus}
**Generated**: {timestamp}

## Analysis Results

{analysis}

## Summary

This analysis was conducted using AI-Scientist methodology focusing on {focus}. 
The paper has been analyzed for key insights, methodological approaches, and contributions to the field.

---
*Generated by SakanaAI Research Tool*
"""
        return formatted
    
    async def _save_paper_analysis(self, url: str, analysis: str):
        """Save individual paper analysis to memory"""
        try:
            db = await memory.Memory.get(self.agent)
            
            metadata = {
                "type": "paper_analysis",
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "agent": self.agent.agent_name
            }
            
            await db.insert(
                text=analysis,
                area=memory.Memory.Area.RESEARCH,
                metadata=metadata
            )
            
        except Exception as e:
            handle_error(e)
    
    async def _search_recent_publications(self, domain: str) -> Dict:
        """Search for recent publications in a domain"""
        current_year = datetime.now().year
        queries = [
            f"{domain} research {current_year}",
            f"{domain} advances {current_year}",
            f"recent {domain} publications"
        ]
        
        all_results = {"results": []}
        
        for query in queries:
            try:
                result = await searxng(query)
                if result and "results" in result:
                    all_results["results"].extend(result["results"])
            except Exception as e:
                handle_error(e)
                continue
        
        # Deduplicate and limit
        unique_results = self._deduplicate_results(all_results["results"])
        all_results["results"] = unique_results[:15]
        
        return all_results
    
    async def _analyze_research_gaps(self, domain: str, recent_work: Dict, current_knowledge: str) -> str:
        """Analyze research gaps in a domain"""
        
        gap_analysis = f"""# Research Gap Analysis: {domain}

**Analysis Date**: {datetime.now().strftime('%Y-%m-%d')}
**Domain**: {domain}

## Current State of Research

"""
        
        if recent_work.get("results"):
            gap_analysis += "### Recent Publications Found:\n"
            for i, paper in enumerate(recent_work["results"][:5], 1):
                title = paper.get('title', f'Paper {i}')
                url = paper.get('url', 'No URL')
                content = paper.get('content', 'No summary available')
                
                gap_analysis += f"{i}. **{title}**\n"
                gap_analysis += f"   - URL: {url}\n"
                gap_analysis += f"   - Summary: {content[:150]}...\n\n"
        else:
            gap_analysis += "Limited recent publications found in this domain.\n\n"
        
        gap_analysis += "## Potential Research Gaps Identified\n\n"
        
        # Analyze gaps based on current knowledge
        if current_knowledge:
            gap_analysis += f"### Based on Current Knowledge:\n{current_knowledge}\n\n"
        
        # Generic gap analysis
        gap_analysis += """### Common Gap Areas to Investigate:

1. **Methodological Gaps**: Are there limitations in current research methods?
2. **Application Gaps**: Are there unexplored applications of existing knowledge?
3. **Scale Gaps**: Have approaches been tested at different scales?
4. **Cross-Domain Gaps**: Are there opportunities for interdisciplinary work?
5. **Validation Gaps**: Are there claims that need empirical validation?
6. **Accessibility Gaps**: Are current solutions accessible to all relevant stakeholders?

## Recommendations for Future Research

Based on this analysis, researchers should consider:

- Systematic literature reviews to map the current landscape
- Identification of underexplored methodological approaches
- Investigation of real-world applications and their challenges
- Cross-domain knowledge transfer opportunities
- Replication studies to validate existing findings

---
*Generated by SakanaAI Research Gap Analysis Tool*
"""
        
        return gap_analysis
    
    async def _targeted_research(self, context: Dict) -> str:
        """Execute targeted research on specific aspects"""
        query = context["query"]
        focus_areas = context.get("focus_areas", [])
        
        targeted_queries = [query]
        for area in focus_areas:
            targeted_queries.append(f"{query} {area}")
        
        # Search with targeted queries
        search_tasks = [searxng(q) for q in targeted_queries[:3]]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # Combine and analyze results
        combined_results = {"results": []}
        for result in search_results:
            if not isinstance(result, Exception) and result.get("results"):
                combined_results["results"].extend(result["results"])
        
        # Deduplicate and analyze top results
        unique_results = self._deduplicate_results(combined_results["results"])
        top_papers = unique_results[:context.get("max_papers", 10)]
        
        # Generate targeted report
        report = await self._generate_targeted_report(query, top_papers, focus_areas)
        
        await self._save_research_findings("targeted", report, context)
        return report
    
    async def _generate_targeted_report(self, query: str, papers: List[Dict], focus_areas: List[str]) -> str:
        """Generate a targeted research report"""
        
        report = f"""# Targeted Research Report: {query}

**Focus Areas**: {', '.join(focus_areas) if focus_areas else 'General'}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Relevant Sources Found

"""
        
        for i, paper in enumerate(papers[:8], 1):
            title = paper.get('title', f'Source {i}')
            url = paper.get('url', 'No URL available')
            content = paper.get('content', 'No content available')
            
            report += f"### {i}. {title}\n"
            report += f"**URL**: {url}\n"
            report += f"**Summary**: {content[:200]}...\n\n"
        
        if focus_areas:
            report += "## Focus Area Analysis\n\n"
            for area in focus_areas:
                report += f"### {area.title()}\n"
                relevant_papers = [p for p in papers if area.lower() in p.get('title', '').lower() or area.lower() in p.get('content', '').lower()]
                if relevant_papers:
                    report += f"Found {len(relevant_papers)} sources specifically related to {area}.\n"
                else:
                    report += f"Limited specific sources found for {area}. Consider broader search terms.\n"
                report += "\n"
        
        report += """## Research Strategy Recommendations

1. **Deep Dive**: Select top 3-5 most relevant sources for detailed analysis
2. **Citation Analysis**: Follow citation chains from key papers
3. **Expert Consultation**: Identify and contact leading researchers in this area
4. **Methodology Review**: Analyze research methods used across sources
5. **Gap Identification**: Look for areas not covered by existing work

---
*Generated by SakanaAI Targeted Research Tool*
"""
        
        return report
    
    async def _citation_analysis(self, context: Dict) -> str:
        """Perform citation chain analysis"""
        # This would ideally integrate with academic APIs
        # For now, implement basic citation following through search
        
        query = context["query"]
        
        # Search for highly cited papers
        citation_queries = [
            f"{query} highly cited",
            f"{query} seminal paper",
            f"{query} survey review",
            f"{query} foundation"
        ]
        
        citation_results = await asyncio.gather(
            *[searxng(q) for q in citation_queries], 
            return_exceptions=True
        )
        
        # Analyze and format citation analysis
        analysis = f"""# Citation Analysis: {query}

**Analysis Type**: Citation Chain Investigation
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Highly Cited and Foundational Work

"""
        
        for i, result in enumerate(citation_results):
            if not isinstance(result, Exception) and result.get("results"):
                analysis += f"### Search Strategy {i+1}: {citation_queries[i]}\n"
                for j, paper in enumerate(result["results"][:3], 1):
                    title = paper.get('title', f'Paper {j}')
                    url = paper.get('url', '')
                    content = paper.get('content', '')
                    
                    analysis += f"{j}. **{title}**\n"
                    analysis += f"   - {url}\n"
                    analysis += f"   - {content[:150]}...\n\n"
        
        analysis += """## Citation Analysis Insights

- Focus on papers that appear across multiple search strategies
- Look for authors who appear frequently in the domain
- Identify foundational papers that are referenced by many others
- Follow citation chains both forward and backward from key papers

## Next Steps for Citation Analysis

1. **Forward Citations**: Find papers that cite the foundational work
2. **Backward Citations**: Examine references in key papers
3. **Author Networks**: Identify prolific authors and their collaborations
4. **Timeline Analysis**: Understand the evolution of ideas over time

---
*Generated by SakanaAI Citation Analysis Tool*
"""
        
        await self._save_research_findings("citation_analysis", analysis, context)
        return analysis
    
    async def _trend_analysis(self, context: Dict) -> str:
        """Analyze trends in research area"""
        query = context["query"]
        current_year = datetime.now().year
        
        # Search for trends across different time periods
        trend_queries = []
        for year in range(current_year-3, current_year+1):
            trend_queries.append(f"{query} {year}")
        
        trend_results = await asyncio.gather(
            *[searxng(q) for q in trend_queries[-2:]], # Last 2 years
            return_exceptions=True
        )
        
        # Also search for explicit trend information
        trend_search = await searxng(f"{query} trends emerging developments")
        
        trend_analysis = f"""# Trend Analysis: {query}

**Analysis Period**: {current_year-3} to {current_year}
**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Recent Developments

"""
        
        if not isinstance(trend_search, Exception) and trend_search.get("results"):
            for i, result in enumerate(trend_search["results"][:5], 1):
                title = result.get('title', f'Development {i}')
                content = result.get('content', '')
                url = result.get('url', '')
                
                trend_analysis += f"### {title}\n"
                trend_analysis += f"**Source**: {url}\n"
                trend_analysis += f"**Summary**: {content[:200]}...\n\n"
        
        trend_analysis += """## Trend Indicators to Monitor

1. **Publication Volume**: Increasing number of papers in recent years
2. **Interdisciplinary Growth**: Expansion into related fields
3. **Industry Adoption**: Commercial applications and startups
4. **Conference Tracks**: New conference sessions dedicated to the topic
5. **Funding Patterns**: Research grants and investment trends
6. **Open Source Projects**: Community-driven development

## Emerging Patterns

Based on the search results, key patterns to watch include:
- Integration with AI/ML technologies
- Focus on real-world applications
- Emphasis on scalability and performance
- Growing attention to ethical considerations
- Cross-domain applications

---
*Generated by SakanaAI Trend Analysis Tool*
"""
        
        await self._save_research_findings("trend_analysis", trend_analysis, context)
        return trend_analysis
    
    async def _gap_analysis_research(self, context: Dict) -> str:
        """Research focused on identifying gaps"""
        domain = context.get("domain", context["query"])
        current_knowledge = context.get("current_knowledge", "")
        
        return await self._analyze_research_gaps(domain, 
                                               await self._search_recent_publications(domain), 
                                               current_knowledge)