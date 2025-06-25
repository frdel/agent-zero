import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.errors import handle_error
from python.helpers import memory
from python.extensions.research_workflow._10_research_session_start import get_research_session
from python.extensions.research_workflow._20_research_tool_tracking import get_research_tool_usage
from python.extensions.research_workflow._30_research_artifact_tracking import get_research_artifacts
from python.extensions.research_workflow._90_research_session_summary import get_session_summary, force_session_summary

class ResearchMemory(Tool):
    
    async def execute(self, action="search", query="", artifact_type="", limit=10, **kwargs):
        """
        Research memory management tool for SakanaAI integration.
        
        Actions:
        - search: Search research artifacts by query
        - list_papers: List all research papers
        - list_experiments: List all experiment designs  
        - list_reviews: List all peer reviews
        - list_findings: List all research findings
        - session_status: Get current research session status
        - session_summary: Generate current session summary
        - timeline: Get research timeline
        - clear: Clear research artifacts by type
        """
        
        if action == "search":
            return await self._search_research_artifacts(query, artifact_type, limit)
        elif action == "list_papers":
            return await self._list_research_papers(limit)
        elif action == "list_experiments":
            return await self._list_experiment_designs(limit)
        elif action == "list_reviews":
            return await self._list_peer_reviews(limit)
        elif action == "list_findings":
            return await self._list_research_findings(query, limit)
        elif action == "session_status":
            return await self._get_session_status()
        elif action == "session_summary":
            return await self._generate_session_summary()
        elif action == "timeline":
            return await self._get_research_timeline()
        elif action == "clear":
            return await self._clear_research_artifacts(artifact_type)
        else:
            return Response(message=f"Unknown action: {action}. Available actions: search, list_papers, list_experiments, list_reviews, list_findings, session_status, session_summary, timeline, clear", break_loop=False)
    
    async def search(self, query="", artifact_type="", limit=10, **kwargs):
        """Search research artifacts"""
        return await self.execute(action="search", query=query, artifact_type=artifact_type, limit=limit)
    
    async def list_papers(self, limit=20, **kwargs):
        """List research papers"""
        return await self.execute(action="list_papers", limit=limit)
    
    async def list_experiments(self, limit=10, **kwargs):
        """List experiment designs"""
        return await self.execute(action="list_experiments", limit=limit)
    
    async def list_reviews(self, limit=10, **kwargs):
        """List peer reviews"""
        return await self.execute(action="list_reviews", limit=limit)
    
    async def session_status(self, **kwargs):
        """Get research session status"""
        return await self.execute(action="session_status")
    
    async def timeline(self, **kwargs):
        """Get research timeline"""
        return await self.execute(action="timeline")
    
    async def _search_research_artifacts(self, query: str, artifact_type: str, limit: int) -> Response:
        """Search research artifacts with optional type filtering"""
        try:
            db = await memory.Memory.get(self.agent)
            
            if not query:
                query = "research"
            
            docs = await db.search_research_artifacts(
                query=query, 
                artifact_type=artifact_type if artifact_type else None, 
                limit=limit
            )
            
            if not docs:
                message = f"No research artifacts found"
                if artifact_type:
                    message += f" of type '{artifact_type}'"
                if query != "research":
                    message += f" matching '{query}'"
                return Response(message=message, break_loop=False)
            
            formatted_results = memory.Memory.format_research_docs(docs)
            
            search_summary = f"Found {len(docs)} research artifact(s)"
            if artifact_type:
                search_summary += f" of type '{artifact_type}'"
            if query != "research":
                search_summary += f" matching '{query}'"
            
            result = f"{search_summary}\n\n{formatted_results}"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error searching research artifacts: {str(e)}", break_loop=False)
    
    async def _list_research_papers(self, limit: int) -> Response:
        """List all research papers"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.get_research_papers(limit=limit)
            
            if not docs:
                return Response(message="No research papers found in memory", break_loop=False)
            
            formatted_results = memory.Memory.format_research_docs(docs)
            result = f"Found {len(docs)} research paper(s):\n\n{formatted_results}"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error listing research papers: {str(e)}", break_loop=False)
    
    async def _list_experiment_designs(self, limit: int) -> Response:
        """List all experiment designs"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.get_experiment_designs(limit=limit)
            
            if not docs:
                return Response(message="No experiment designs found in memory", break_loop=False)
            
            formatted_results = memory.Memory.format_research_docs(docs)
            result = f"Found {len(docs)} experiment design(s):\n\n{formatted_results}"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error listing experiment designs: {str(e)}", break_loop=False)
    
    async def _list_peer_reviews(self, limit: int) -> Response:
        """List all peer reviews"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.get_peer_reviews(limit=limit)
            
            if not docs:
                return Response(message="No peer reviews found in memory", break_loop=False)
            
            formatted_results = memory.Memory.format_research_docs(docs)
            result = f"Found {len(docs)} peer review(s):\n\n{formatted_results}"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error listing peer reviews: {str(e)}", break_loop=False)
    
    async def _list_research_findings(self, query: str, limit: int) -> Response:
        """List research findings with optional filtering"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.get_research_findings(query=query, limit=limit)
            
            if not docs:
                message = "No research findings found"
                if query:
                    message += f" matching '{query}'"
                return Response(message=message, break_loop=False)
            
            formatted_results = memory.Memory.format_research_docs(docs)
            result = f"Found {len(docs)} research finding(s)"
            if query:
                result += f" matching '{query}'"
            result += f":\n\n{formatted_results}"
            
            await self.agent.handle_intervention(result)
            return Response(message=result, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error listing research findings: {str(e)}", break_loop=False)
    
    async def _get_session_status(self) -> Response:
        """Get current research session status"""
        try:
            session_summary = get_session_summary(self.agent)
            
            status_report = f"""# Research Session Status

**Session Active**: {session_summary['session_active']}
**Session ID**: {session_summary['session_id']}
**Start Time**: {session_summary['start_time']}
**Last Activity**: {session_summary['last_activity']}

## Activity Summary
- **Tools Used**: {session_summary['tools_used']}
- **Artifacts Created**: {session_summary['artifacts_created']}
- **Topics Explored**: {session_summary['topics_explored']}

## Detailed Statistics
"""
            
            if session_summary['session_active']:
                # Get detailed information if session is active
                tool_usage = get_research_tool_usage(self.agent)
                artifacts = get_research_artifacts(self.agent)
                
                status_report += f"""
### Tools Used ({tool_usage['total_tools']} total)
{', '.join(tool_usage['tools_used']) if tool_usage['tools_used'] else 'None'}

### Artifacts Created ({artifacts['total_count']} total)
"""
                for artifact_type, count in artifacts.get('by_type', {}).items():
                    status_report += f"- {artifact_type}: {count}\n"
                
                status_report += f"""
**Last Tool Used**: {tool_usage.get('last_tool', 'None')}
**Last Artifact**: {artifacts.get('last_artifact', 'None')}
"""
            else:
                status_report += "\nNo active research session."
            
            await self.agent.handle_intervention(status_report)
            return Response(message=status_report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error getting session status: {str(e)}", break_loop=False)
    
    async def _generate_session_summary(self) -> Response:
        """Generate session summary"""
        try:
            session_data = get_research_session(self.agent)
            
            if not session_data.get("active", False):
                return Response(message="No active research session to summarize", break_loop=False)
            
            # Force generation of session summary
            await force_session_summary(self.agent)
            
            return Response(message="Research session summary generated and saved to memory", break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error generating session summary: {str(e)}", break_loop=False)
    
    async def _get_research_timeline(self) -> Response:
        """Get research timeline"""
        try:
            db = await memory.Memory.get(self.agent)
            docs = await db.get_research_timeline(days_back=30)
            
            if not docs:
                return Response(message="No recent research activity found", break_loop=False)
            
            # Sort by timestamp
            sorted_docs = sorted(docs, key=lambda x: x.metadata.get('timestamp', ''), reverse=True)
            
            timeline_report = f"# Research Timeline (Last 30 Days)\n\nFound {len(sorted_docs)} recent research artifacts:\n\n"
            
            for i, doc in enumerate(sorted_docs[:20], 1):  # Limit to 20 most recent
                doc_type = doc.metadata.get('type', 'Unknown')
                timestamp = doc.metadata.get('timestamp', 'Unknown')
                agent = doc.metadata.get('agent', 'Unknown')
                
                timeline_report += f"**{i}. {doc_type}** ({timestamp})\n"
                timeline_report += f"   Agent: {agent}\n"
                timeline_report += f"   Preview: {doc.page_content[:100]}...\n\n"
            
            await self.agent.handle_intervention(timeline_report)
            return Response(message=timeline_report, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error getting research timeline: {str(e)}", break_loop=False)
    
    async def _clear_research_artifacts(self, artifact_type: str) -> Response:
        """Clear research artifacts by type"""
        try:
            db = await memory.Memory.get(self.agent)
            
            if artifact_type:
                removed_docs = await db.delete_research_artifacts(artifact_type=artifact_type)
                message = f"Removed {len(removed_docs)} research artifacts of type '{artifact_type}'"
            else:
                removed_docs = await db.delete_research_artifacts()
                message = f"Removed {len(removed_docs)} research artifacts (all types)"
            
            PrintStyle(font_color="#E74C3C").print(message)
            return Response(message=message, break_loop=False)
            
        except Exception as e:
            handle_error(e)
            return Response(message=f"Error clearing research artifacts: {str(e)}", break_loop=False)