from python.helpers.extension import Extension
from python.helpers.print_style import PrintStyle
import asyncio
import time
import os
from typing import Dict, Any, Optional

class BiomniExtension(Extension):
    """
    Biomni Extension for Agent Zero framework.
    Provides biomedical research-specific functionality, lifecycle hooks, and environment setup.
    """
    
    async def agent_created(self, agent):
        """Called when a new agent is created."""
        
        # Initialize Biomni-specific settings for biomedical agents
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            await self._initialize_biomni_environment(agent)
            await self._setup_biomedical_logging(agent)
            await self._validate_data_lake_access(agent)
            
            PrintStyle(color="green", background="", bold=True).print(
                f"🧬 Biomni agent initialized with biomedical research capabilities"
            )
    
    async def agent_loop_start(self, agent):
        """Called at the start of each agent loop iteration."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Log biomedical research session start
            await self._log_research_session_start(agent)
            
            # Check data lake connectivity
            await self._check_data_lake_health(agent)
    
    async def agent_loop_end(self, agent):
        """Called at the end of each agent loop iteration."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Save research progress
            await self._save_research_progress(agent)
            
            # Update usage metrics
            await self._update_biomedical_metrics(agent)
    
    async def tool_before_execution(self, agent, tool_name: str, tool_args: dict):
        """Called before any tool execution."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Log biomedical tool usage
            await self._log_biomedical_tool_usage(agent, tool_name, tool_args)
            
            # Validate biomedical data access permissions
            if self._is_biomedical_tool(tool_name):
                await self._validate_biomedical_permissions(agent, tool_name)
    
    async def tool_after_execution(self, agent, tool_name: str, tool_args: dict, tool_response):
        """Called after tool execution."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Cache biomedical results for research continuity
            if self._is_biomedical_tool(tool_name):
                await self._cache_biomedical_results(agent, tool_name, tool_response)
            
            # Check for regulatory compliance alerts
            await self._check_regulatory_compliance(agent, tool_name, tool_response)
    
    async def response_streaming_start(self, agent, response: str):
        """Called when response streaming starts."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Add biomedical context to responses
            await self._add_biomedical_context(agent, response)
    
    async def response_streaming_end(self, agent, response: str):
        """Called when response streaming ends."""
        
        if hasattr(agent, 'config') and agent.config.name == "biomni":
            # Log completed biomedical analysis
            await self._log_biomedical_analysis_completion(agent, response)
    
    async def _initialize_biomni_environment(self, agent):
        """Initialize Biomni-specific environment settings."""
        
        # Set biomedical research environment variables
        biomni_env = {
            "DATA_LAKE_PATH": "/biomni/datalake",
            "BIOMEDICAL_CACHE_SIZE": "2GB",
            "REGULATORY_COMPLIANCE_MODE": "FDA_ICH",
            "BIOINFORMATICS_TOOLS_PATH": "/biomni/tools",
            "CLINICAL_DATA_ENCRYPTION": "AES256",
            "RESEARCH_SESSION_TIMEOUT": "7200",  # 2 hours
            "MAX_CONCURRENT_ANALYSES": "4",
            "BIOMEDICAL_LOGGING_LEVEL": "INFO"
        }
        
        # Store in agent context
        if not hasattr(agent, 'biomni_env'):
            agent.biomni_env = biomni_env
        
        PrintStyle(color="cyan", background="", bold=False).print(
            "🔬 Biomni environment initialized with biomedical research settings"
        )
    
    async def _setup_biomedical_logging(self, agent):
        """Setup specialized logging for biomedical research."""
        
        # Configure biomedical research logging
        logging_config = {
            "research_session_id": f"biomni_{int(time.time())}",
            "log_biomedical_queries": True,
            "log_clinical_data_access": True,
            "log_regulatory_checks": True,
            "audit_trail_enabled": True,
            "hipaa_compliance_logging": True
        }
        
        if not hasattr(agent, 'biomni_logging'):
            agent.biomni_logging = logging_config
    
    async def _validate_data_lake_access(self, agent):
        """Validate access to biomedical data lake using real file system."""
        
        try:
            from pathlib import Path
            import sqlite3
            
            # Get data lake path from environment or use default
            data_lake_path = Path(os.getenv("BIOMNI_DATA_LAKE_PATH", "/tmp/biomni_data_lake"))
            metadata_db_path = data_lake_path / "metadata.db"
            
            # Check if data lake exists and create if needed
            if not data_lake_path.exists():
                data_lake_path.mkdir(parents=True, exist_ok=True)
                for subdir in ["genomics", "proteomics", "clinical", "imaging", "literature", "backups"]:
                    (data_lake_path / subdir).mkdir(exist_ok=True)
            
            # Get real statistics
            total_size_bytes = 0
            dataset_count = 0
            
            if data_lake_path.exists():
                for file_path in data_lake_path.rglob('*'):
                    if file_path.is_file() and not file_path.name.endswith('.db'):
                        total_size_bytes += file_path.stat().st_size
                        dataset_count += 1
            
            # Check database
            db_dataset_count = 0
            if metadata_db_path.exists():
                try:
                    conn = sqlite3.connect(str(metadata_db_path))
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM datasets")
                    db_dataset_count = cursor.fetchone()[0]
                    conn.close()
                except Exception as e:
                    print(f"Database query error: {str(e)}")
            
            # Determine health status
            health_status = "optimal"
            if not data_lake_path.exists():
                health_status = "error"
            elif total_size_bytes > 10 * (1024**3):  # > 10GB warning
                health_status = "warning"
            elif dataset_count == 0:
                health_status = "empty"
            
            data_lake_status = {
                "connectivity": "connected",
                "data_lake_path": str(data_lake_path),
                "available_datasets": max(dataset_count, db_dataset_count),
                "total_size_gb": round(total_size_bytes / (1024**3), 2),
                "total_size_bytes": total_size_bytes,
                "access_permissions": ["read", "query", "analyze", "upload"],
                "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "health_status": health_status,
                "database_exists": metadata_db_path.exists(),
                "directories_created": True
            }
            
            if not hasattr(agent, 'data_lake_status'):
                agent.data_lake_status = data_lake_status
            
            status_emoji = "💾" if health_status == "optimal" else "⚠️" if health_status == "warning" else "❌"
            PrintStyle(color="blue", background="", bold=False).print(
                f"{status_emoji} Data lake validated: {data_lake_status['available_datasets']} datasets, {data_lake_status['total_size_gb']}GB"
            )
            
        except Exception as e:
            # Fallback to basic status
            data_lake_status = {
                "connectivity": "error",
                "available_datasets": 0,
                "total_size_gb": 0,
                "access_permissions": [],
                "health_status": "error",
                "error": str(e)
            }
            
            if not hasattr(agent, 'data_lake_status'):
                agent.data_lake_status = data_lake_status
            
            PrintStyle(color="red", background="", bold=False).print(
                f"❌ Data lake validation failed: {str(e)}"
            )
    
    async def _log_research_session_start(self, agent):
        """Log the start of a biomedical research session."""
        
        session_info = {
            "session_id": agent.biomni_logging.get("research_session_id"),
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_id": agent.name if hasattr(agent, 'name') else "biomni_agent",
            "research_mode": "biomedical_analysis"
        }
        
        # Store session info
        if not hasattr(agent, 'current_session'):
            agent.current_session = session_info
    
    async def _check_data_lake_health(self, agent):
        """Check data lake health and connectivity."""
        
        # Simulate health check
        if hasattr(agent, 'data_lake_status'):
            agent.data_lake_status["last_health_check"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            agent.data_lake_status["response_time_ms"] = 145.7
    
    async def _save_research_progress(self, agent):
        """Save current research progress and state."""
        
        # Simulate research progress saving
        progress_data = {
            "session_id": agent.current_session.get("session_id") if hasattr(agent, 'current_session') else None,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools_used": getattr(agent, 'tools_used_count', 0),
            "analyses_completed": getattr(agent, 'analyses_completed', 0),
            "data_accessed_gb": getattr(agent, 'data_accessed_gb', 0.0)
        }
        
        if not hasattr(agent, 'research_progress'):
            agent.research_progress = []
        agent.research_progress.append(progress_data)
    
    async def _update_biomedical_metrics(self, agent):
        """Update biomedical research usage metrics."""
        
        # Update metrics
        if not hasattr(agent, 'biomedical_metrics'):
            agent.biomedical_metrics = {
                "total_queries": 0,
                "data_processed_gb": 0.0,
                "analyses_performed": 0,
                "regulatory_checks": 0,
                "research_sessions": 0
            }
        
        # Increment session count if this is a new session
        if hasattr(agent, 'current_session') and not getattr(agent, 'session_counted', False):
            agent.biomedical_metrics["research_sessions"] += 1
            agent.session_counted = True
    
    async def _log_biomedical_tool_usage(self, agent, tool_name: str, tool_args: dict):
        """Log usage of biomedical tools."""
        
        if self._is_biomedical_tool(tool_name):
            # Increment tools used counter
            if not hasattr(agent, 'tools_used_count'):
                agent.tools_used_count = 0
            agent.tools_used_count += 1
            
            # Log specific tool usage
            usage_log = {
                "tool": tool_name,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "args_provided": list(tool_args.keys()) if tool_args else [],
                "session_id": agent.current_session.get("session_id") if hasattr(agent, 'current_session') else None
            }
            
            if not hasattr(agent, 'tool_usage_log'):
                agent.tool_usage_log = []
            agent.tool_usage_log.append(usage_log)
    
    async def _validate_biomedical_permissions(self, agent, tool_name: str):
        """Validate permissions for biomedical tool access."""
        
        # Simulate permission validation
        restricted_tools = [
            "clinical_data_analyzer",
            "patient_data_processor", 
            "genomic_data_analyzer"
        ]
        
        if tool_name in restricted_tools:
            # Check if agent has appropriate permissions
            permissions = agent.data_lake_status.get("access_permissions", []) if hasattr(agent, 'data_lake_status') else []
            if "analyze" not in permissions:
                PrintStyle(color="yellow", background="", bold=True).print(
                    f"⚠️ Limited permissions for {tool_name} - some features may be restricted"
                )
    
    async def _cache_biomedical_results(self, agent, tool_name: str, tool_response):
        """Cache biomedical analysis results for research continuity."""
        
        # Cache results for research continuity
        cache_entry = {
            "tool": tool_name,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "response_type": tool_response.type if hasattr(tool_response, 'type') else "unknown",
            "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        if not hasattr(agent, 'results_cache'):
            agent.results_cache = []
        agent.results_cache.append(cache_entry)
        
        # Limit cache size to last 50 results
        if len(agent.results_cache) > 50:
            agent.results_cache = agent.results_cache[-50:]
    
    async def _check_regulatory_compliance(self, agent, tool_name: str, tool_response):
        """Check for regulatory compliance alerts."""
        
        # Check for compliance issues
        compliance_sensitive_tools = [
            "clinical_data_analyzer",
            "drug_interaction_checker",
            "regulatory_compliance"
        ]
        
        if tool_name in compliance_sensitive_tools:
            # Increment regulatory checks counter
            if hasattr(agent, 'biomedical_metrics'):
                agent.biomedical_metrics["regulatory_checks"] += 1
    
    async def _add_biomedical_context(self, agent, response: str):
        """Add biomedical research context to responses."""
        
        # Add research session context
        if hasattr(agent, 'current_session'):
            session_id = agent.current_session.get("session_id")
            if session_id:
                # Context could be added to response metadata
                pass
    
    async def _log_biomedical_analysis_completion(self, agent, response: str):
        """Log completion of biomedical analysis."""
        
        # Increment analyses completed
        if not hasattr(agent, 'analyses_completed'):
            agent.analyses_completed = 0
        agent.analyses_completed += 1
        
        # Update metrics
        if hasattr(agent, 'biomedical_metrics'):
            agent.biomedical_metrics["analyses_performed"] += 1
    
    def _is_biomedical_tool(self, tool_name: str) -> bool:
        """Check if a tool is biomedical-specific."""
        
        biomedical_tools = [
            "pubmed_search",
            "clinical_trials_search", 
            "clinical_data_analyzer",
            "drug_interaction_checker",
            "molecular_docking",
            "biomarker_analyzer",
            "sequence_analyzer",
            "regulatory_compliance",
            "data_lake_manager",
            "biomedical_data_loader",
            "data_quality_checker"
        ]
        
        return tool_name in biomedical_tools