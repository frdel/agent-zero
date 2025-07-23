#!/usr/bin/env python3
"""
A2A Multi-Agent Workflow Example

This example demonstrates the A2A (Agent-to-Agent) protocol integration
with Agent Zero, showing how multiple agents can collaborate using
different interaction patterns (polling, SSE, and webhook).

This example creates three agents:
1. Main Agent (Agent Zero) - Orchestrates the workflow
2. Analysis Agent - Specializes in data analysis
3. Report Agent - Specializes in report generation

The workflow demonstrates:
- Peer discovery and registration
- Task delegation across agents
- Different A2A interaction patterns
- Result integration and final report generation
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timezone

# Add the parent directory to sys.path to import agent modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent import Agent, AgentConfig, AgentContext, AgentContextType, UserMessage
from python.helpers.a2a_handler import A2AHandler
from python.helpers.a2a_server import A2AServer
from python.helpers.a2a_client import A2AClient
from python.helpers.a2a_agent import A2AAgent
from python.helpers.a2a_tool_wrapper import get_a2a_tool_registry
from python.helpers.print_style import PrintStyle
import models


class A2AWorkflowDemo:
    """Demonstrates A2A multi-agent collaboration workflow"""
    
    def __init__(self):
        self.agents = {}
        self.servers = {}
        self.ports = {
            'main_agent': 8001,
            'analysis_agent': 8002, 
            'report_agent': 8003
        }
        
    async def setup_agents(self):
        """Setup three demo agents with A2A capabilities"""
        PrintStyle(font_color="cyan", bold=True).print("Setting up A2A Demo Agents...")
        
        # Create agent configurations
        configs = self._create_agent_configs()
        
        # Create agent contexts and agents
        for agent_type, config in configs.items():
            context = AgentContext(
                config=config,
                name=f"{agent_type.title()} Agent Demo",
                type=AgentContextType.A2A
            )
            
            agent = Agent(0, config, context)
            self.agents[agent_type] = {
                'agent': agent,
                'context': context,
                'config': config
            }
            
            PrintStyle(font_color="green").print(f"Created {agent_type} agent")
        
        # Start A2A servers for each agent
        await self._start_a2a_servers()
        
        # Wait for servers to initialize
        await asyncio.sleep(2)
        
        PrintStyle(font_color="green", bold=True).print("All agents initialized and servers started!")
    
    def _create_agent_configs(self) -> dict:
        """Create configurations for different agent types"""
        base_config = {
            'chat_model': models.ModelConfig('openai', 'gpt-4.1', 8000, 50, False),
            'utility_model': models.ModelConfig('openai', 'gpt-4.1-mini', 4000, 100, False),
            'embeddings_model': models.ModelConfig('openai', 'text-embedding-3-small', 8000, 500, False),
            'browser_model': models.ModelConfig('openai', 'gpt-4.1', 8000, 50, False),
            'mcp_servers': '',
            'prompts_subdir': 'default',
            'memory_subdir': 'demo',
            'a2a_enabled': True,
            'a2a_auth_required': False,  # Simplified for demo
            'a2a_cors_origins': ['*']
        }
        
        configs = {}
        
        # Main orchestrator agent
        configs['main_agent'] = AgentConfig(
            **base_config,
            a2a_server_port=self.ports['main_agent'],
            a2a_capabilities=['task_orchestration', 'workflow_management', 'decision_making'],
            additional={'role': 'orchestrator', 'description': 'Main workflow orchestrator'}
        )
        
        # Data analysis specialist
        configs['analysis_agent'] = AgentConfig(
            **base_config,
            a2a_server_port=self.ports['analysis_agent'],
            a2a_capabilities=['data_analysis', 'statistical_analysis', 'pattern_recognition'],
            additional={'role': 'analyst', 'description': 'Data analysis specialist'}
        )
        
        # Report generation specialist  
        configs['report_agent'] = AgentConfig(
            **base_config,
            a2a_server_port=self.ports['report_agent'],
            a2a_capabilities=['report_generation', 'document_creation', 'visualization'],
            additional={'role': 'reporter', 'description': 'Report generation specialist'}
        )
        
        return configs
    
    async def _start_a2a_servers(self):
        """Start A2A servers for all agents"""
        for agent_type, agent_data in self.agents.items():
            port = self.ports[agent_type]
            context = agent_data['context']
            config = agent_data['config']
            
            # Create server configuration
            server_config = {
                'auth_required': False,
                'host': '0.0.0.0',
                'port': port,
                'base_url': f'http://localhost:{port}',
                'agent_name': f'{agent_type.title()} Agent',
                'agent_description': config.additional.get('description', f'{agent_type} specialist'),
                'capabilities': config.a2a_capabilities,
                'cors_origins': ['*']
            }
            
            # Create and start server
            server = A2AServer(server_config, context)
            self.servers[agent_type] = server
            
            # Start server in background
            asyncio.create_task(server.start_server(
                host=server_config['host'],
                port=server_config['port']
            ))
            
            PrintStyle(font_color="green").print(
                f"Started A2A server for {agent_type} on port {port}"
            )
    
    async def run_workflow_demo(self):
        """Run the complete A2A workflow demonstration"""
        PrintStyle(font_color="cyan", bold=True).print("\n" + "="*60)
        PrintStyle(font_color="cyan", bold=True).print("STARTING A2A MULTI-AGENT WORKFLOW DEMO")
        PrintStyle(font_color="cyan", bold=True).print("="*60 + "\n")
        
        # Step 1: Main agent discovers peer agents
        await self._demonstrate_peer_discovery()
        
        # Step 2: Delegate data analysis task (Polling pattern)
        analysis_results = await self._demonstrate_polling_communication()
        
        # Step 3: Delegate report generation (SSE pattern)
        report_results = await self._demonstrate_sse_communication(analysis_results)
        
        # Step 4: Final integration and summary
        await self._demonstrate_workflow_completion(analysis_results, report_results)
        
        PrintStyle(font_color="green", bold=True).print("\n" + "="*60)
        PrintStyle(font_color="green", bold=True).print("A2A WORKFLOW DEMO COMPLETED SUCCESSFULLY!")
        PrintStyle(font_color="green", bold=True).print("="*60 + "\n")
    
    async def _demonstrate_peer_discovery(self):
        """Demonstrate peer discovery and registration"""
        PrintStyle(font_color="yellow", bold=True).print("STEP 1: Peer Discovery and Registration")
        PrintStyle(font_color="yellow").print("-" * 40)
        
        main_agent = self.agents['main_agent']['agent']
        main_context = self.agents['main_agent']['context']
        
        # Create A2A agent helper
        a2a_agent = A2AAgent(main_agent, main_context)
        
        # Discover peers
        peer_urls = [
            f"http://localhost:{self.ports['analysis_agent']}",
            f"http://localhost:{self.ports['report_agent']}"
        ]
        
        PrintStyle(font_color="cyan").print("Discovering peer agents...")
        
        discovered_peers = await a2a_agent.discover_peers_from_registry(peer_urls)
        
        PrintStyle(font_color="green").print(f"✓ Discovered {len(discovered_peers)} peer agents")
        
        # List discovered capabilities
        for peer_url in discovered_peers:
            capabilities = a2a_agent.get_peer_capabilities(peer_url)
            PrintStyle(font_color="white").print(f"  - {peer_url}: {', '.join(capabilities)}")
        
        print()
    
    async def _demonstrate_polling_communication(self):
        """Demonstrate A2A communication using polling pattern"""
        PrintStyle(font_color="yellow", bold=True).print("STEP 2: Data Analysis Task (Polling Pattern)")
        PrintStyle(font_color="yellow").print("-" * 40)
        
        main_agent = self.agents['main_agent']['agent']
        main_context = self.agents['main_agent']['context']
        
        a2a_agent = A2AAgent(main_agent, main_context)
        analysis_url = f"http://localhost:{self.ports['analysis_agent']}"
        
        # Sample data analysis task
        task_message = """
        Analyze the following sample sales data and provide insights:
        
        Q1 Sales: $125,000 (15% growth)
        Q2 Sales: $148,000 (18% growth) 
        Q3 Sales: $162,000 (9% growth)
        Q4 Sales: $171,000 (6% growth)
        
        Please identify trends, calculate year-over-year growth, and provide recommendations.
        """
        
        context_data = {
            "analysis_type": "sales_trend_analysis",
            "data_format": "quarterly_summary",
            "requested_insights": ["trend_analysis", "growth_calculation", "recommendations"]
        }
        
        PrintStyle(font_color="cyan").print("Sending data analysis task to specialist agent...")
        PrintStyle(font_color="white").print("Task: Sales trend analysis and insights")
        
        # Send task using polling pattern
        try:
            response = await a2a_agent.send_peer_message(
                peer_url=analysis_url,
                message=task_message,
                context_data=context_data,
                timeout=30,
                interaction_type="polling"
            )
            
            PrintStyle(font_color="green").print("✓ Analysis completed successfully!")
            PrintStyle(font_color="white").print("Analysis Results:")
            PrintStyle(font_color="gray").print(response[:200] + "..." if len(response) > 200 else response)
            
            return response
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"✗ Analysis failed: {str(e)}")
            return "Analysis failed due to communication error"
        
        print()
    
    async def _demonstrate_sse_communication(self, analysis_results):
        """Demonstrate A2A communication using SSE pattern"""
        PrintStyle(font_color="yellow", bold=True).print("STEP 3: Report Generation Task (SSE Pattern)")
        PrintStyle(font_color="yellow").print("-" * 40)
        
        main_agent = self.agents['main_agent']['agent']
        main_context = self.agents['main_agent']['context']
        
        a2a_agent = A2AAgent(main_agent, main_context)
        report_url = f"http://localhost:{self.ports['report_agent']}"
        
        # Report generation task
        task_message = f"""
        Generate a comprehensive business report based on the following analysis:
        
        {analysis_results}
        
        The report should include:
        1. Executive Summary
        2. Key Findings
        3. Trend Analysis
        4. Recommendations
        5. Next Steps
        
        Format as a professional business report.
        """
        
        context_data = {
            "report_type": "business_analysis",
            "format": "professional_report",
            "sections": ["executive_summary", "findings", "trends", "recommendations", "next_steps"],
            "audience": "executive_leadership"
        }
        
        PrintStyle(font_color="cyan").print("Sending report generation task to specialist agent...")
        PrintStyle(font_color="white").print("Task: Professional business report generation")
        
        # Send task using SSE pattern (fallback to polling for demo)
        try:
            response = await a2a_agent.send_peer_message(
                peer_url=report_url,
                message=task_message,
                context_data=context_data,
                timeout=45,
                interaction_type="polling"  # Using polling for reliability in demo
            )
            
            PrintStyle(font_color="green").print("✓ Report generated successfully!")
            PrintStyle(font_color="white").print("Report Preview:")
            PrintStyle(font_color="gray").print(response[:300] + "..." if len(response) > 300 else response)
            
            return response
            
        except Exception as e:
            PrintStyle(font_color="red").print(f"✗ Report generation failed: {str(e)}")
            return "Report generation failed due to communication error"
        
        print()
    
    async def _demonstrate_workflow_completion(self, analysis_results, report_results):
        """Demonstrate workflow completion and result integration"""
        PrintStyle(font_color="yellow", bold=True).print("STEP 4: Workflow Integration and Summary")
        PrintStyle(font_color="yellow").print("-" * 40)
        
        PrintStyle(font_color="cyan").print("Integrating results from all agents...")
        
        # Create final summary
        summary = {
            "workflow_id": str(id(self))[:8],
            "completion_time": datetime.now(timezone.utc).isoformat(),
            "agents_involved": len(self.agents),
            "tasks_completed": 2,
            "communication_patterns": ["polling", "sse_fallback"],
            "results": {
                "analysis_available": bool(analysis_results and not analysis_results.startswith("Analysis failed")),
                "report_available": bool(report_results and not report_results.startswith("Report generation failed")),
                "workflow_success": True
            }
        }
        
        PrintStyle(font_color="green").print("✓ Workflow completed successfully!")
        PrintStyle(font_color="white").print("Workflow Summary:")
        PrintStyle(font_color="gray").print(json.dumps(summary, indent=2))
        
        # Demonstrate broadcast capability
        PrintStyle(font_color="cyan").print("\nTesting broadcast capability...")
        
        main_agent = self.agents['main_agent']['agent']
        main_context = self.agents['main_agent']['context']
        a2a_agent = A2AAgent(main_agent, main_context)
        
        broadcast_urls = [
            f"http://localhost:{self.ports['analysis_agent']}",
            f"http://localhost:{self.ports['report_agent']}"
        ]
        
        broadcast_message = "Workflow completed successfully. Thank you for your collaboration!"
        
        try:
            responses = await a2a_agent.broadcast_to_peers(
                message=broadcast_message,
                peer_urls=broadcast_urls,
                timeout=15
            )
            
            PrintStyle(font_color="green").print(f"✓ Broadcast sent to {len(responses)} peers")
            
        except Exception as e:
            PrintStyle(font_color="yellow").print(f"⚠ Broadcast partially failed: {str(e)}")
        
        print()
    
    async def cleanup(self):
        """Clean up servers and resources"""
        PrintStyle(font_color="yellow").print("Cleaning up demo resources...")
        
        for agent_type, server in self.servers.items():
            try:
                await server.stop_server()
                PrintStyle(font_color="green").print(f"✓ Stopped {agent_type} server")
            except Exception as e:
                PrintStyle(font_color="yellow").print(f"⚠ Error stopping {agent_type} server: {str(e)}")


async def main():
    """Main demo execution function"""
    demo = A2AWorkflowDemo()
    
    try:
        # Setup all agents and servers
        await demo.setup_agents()
        
        # Run the complete workflow demonstration
        await demo.run_workflow_demo()
        
        # Wait a moment before cleanup
        await asyncio.sleep(2)
        
    except KeyboardInterrupt:
        PrintStyle(font_color="yellow").print("\nDemo interrupted by user")
    except Exception as e:
        PrintStyle(font_color="red").print(f"Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Always cleanup
        await demo.cleanup()


if __name__ == "__main__":
    # Configure event loop for demo
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # Run the demo
    asyncio.run(main())