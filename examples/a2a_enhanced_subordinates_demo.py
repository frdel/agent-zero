#!/usr/bin/env python3
"""
A2A Enhanced Subordinates Demo

This example demonstrates the new A2A-based subordinate system that enables:
- True parallel processing between subordinate agents
- Direct user communication with subordinates
- Scalable multi-agent workflows
- Agent hierarchy management

The demo shows a complex development workflow where multiple specialized
subordinates work together on a software project.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the parent directory to sys.path to import agent modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent import Agent, AgentConfig, AgentContext, UserMessage
from python.helpers.a2a_subordinate_manager import A2ASubordinateManager
from python.helpers.print_style import PrintStyle
import models


class A2ASubordinateDemo:
    """Demonstrates A2A-enhanced subordinate system"""
    
    def __init__(self):
        self.agent = None
        self.context = None
        
    async def setup_main_agent(self):
        """Setup main agent with A2A subordinate capabilities"""
        PrintStyle(font_color="cyan", bold=True).print("Setting up Main Agent with A2A Subordinates...")
        
        # Create agent configuration with A2A enabled
        config = AgentConfig(
            # Model configurations
            chat_model=models.ModelConfig('openai', 'gpt-4o', 8000, 50, False),
            utility_model=models.ModelConfig('openai', 'gpt-4o-mini', 4000, 100, False),
            embeddings_model=models.ModelConfig('openai', 'text-embedding-3-small', 8000, 500, False),
            browser_model=models.ModelConfig('openai', 'gpt-4o', 8000, 50, False),
            
            # Basic settings
            mcp_servers='',
            prompts_subdir='default',
            memory_subdir='a2a_subordinate_demo',
            
            # A2A settings
            a2a_enabled=True,
            a2a_server_port=8200,
            a2a_capabilities=['task_orchestration', 'subordinate_management', 'project_coordination'],
            
            # Subordinate settings
            a2a_subordinate_base_port=8210,
            a2a_subordinate_max_instances=5,
            a2a_subordinate_auto_cleanup=True,
        )
        
        # Create agent context and agent
        self.context = AgentContext(config=config, name="A2A Subordinate Demo")
        self.agent = Agent(0, config, self.context)
        
        PrintStyle(font_color="green").print("Main agent initialized successfully")
    
    async def run_development_workflow_demo(self):
        """Run a complex development workflow using A2A subordinates"""
        PrintStyle(font_color="cyan", bold=True).print("\n" + "="*60)
        PrintStyle(font_color="cyan", bold=True).print("A2A ENHANCED SUBORDINATES DEMO")
        PrintStyle(font_color="cyan", bold=True).print("Complex Software Development Workflow")
        PrintStyle(font_color="cyan", bold=True).print("="*60 + "\n")
        
        # Initialize subordinate manager
        manager = A2ASubordinateManager(self.context, base_port=8210)
        self.context.subordinate_manager = manager
        
        # Phase 1: Parallel Requirements Analysis
        await self._phase_1_requirements_analysis(manager)
        
        # Phase 2: Parallel Development Tasks
        await self._phase_2_parallel_development(manager)
        
        # Phase 3: Testing and Integration
        await self._phase_3_testing_integration(manager)
        
        # Phase 4: Documentation and Deployment
        await self._phase_4_documentation_deployment(manager)
        
        # Phase 5: Demonstrate User Interaction
        await self._phase_5_user_interaction_demo(manager)
        
        PrintStyle(font_color="green", bold=True).print("\n" + "="*60)
        PrintStyle(font_color="green", bold=True).print("A2A SUBORDINATE DEMO COMPLETED!")
        PrintStyle(font_color="green", bold=True).print("="*60)
    
    async def _phase_1_requirements_analysis(self, manager):
        """Phase 1: Parallel requirements analysis"""
        PrintStyle(font_color="yellow", bold=True).print("PHASE 1: Requirements Analysis (Parallel Processing)")
        PrintStyle(font_color="yellow").print("-" * 50)
        
        # Spawn researcher for market analysis
        researcher = await manager.spawn_subordinate(
            role="market_researcher",
            capabilities=["web_search", "analysis", "reporting"],
            shared_context={
                "project": "AI-powered task management app",
                "target_audience": "developers and project managers"
            }
        )
        
        # Spawn analyst for technical requirements
        tech_analyst = await manager.spawn_subordinate(
            role="technical_analyst", 
            capabilities=["technical_analysis", "architecture_design", "requirements_gathering"],
            shared_context={
                "project": "AI-powered task management app",
                "technology_stack": "Python, React, FastAPI"
            }
        )
        
        # Send parallel tasks
        market_task = manager.send_message_to_subordinate(
            role="market_researcher",
            message="Research the current market for AI-powered task management tools. Identify key competitors, market gaps, and user needs.",
            context_data={"research_scope": "comprehensive", "focus": "competitive_analysis"}
        )
        
        tech_task = manager.send_message_to_subordinate(
            role="technical_analyst",
            message="Define technical requirements for an AI-powered task management app. Include system architecture, database design, and API specifications.",
            context_data={"complexity": "enterprise_ready", "scalability": "high"}
        )
        
        # Wait for both tasks to complete (parallel execution)
        PrintStyle(font_color="cyan").print("Running parallel analysis tasks...")
        market_results, tech_results = await asyncio.gather(market_task, tech_task)
        
        PrintStyle(font_color="green").print("✓ Market research completed")
        PrintStyle(font_color="green").print("✓ Technical analysis completed")
        
        # Store results for next phase
        self.market_analysis = market_results
        self.tech_requirements = tech_results
        
        print()
    
    async def _phase_2_parallel_development(self, manager):
        """Phase 2: Parallel development tasks"""
        PrintStyle(font_color="yellow", bold=True).print("PHASE 2: Parallel Development Tasks")
        PrintStyle(font_color="yellow").print("-" * 50)
        
        # Spawn multiple specialized developers
        backend_dev = await manager.spawn_subordinate(
            role="backend_developer",
            capabilities=["python_development", "fastapi", "database_design", "api_development"],
            shared_context={
                "requirements": self.tech_requirements[:200] + "...",
                "tech_stack": "Python, FastAPI, PostgreSQL"
            }
        )
        
        frontend_dev = await manager.spawn_subordinate(
            role="frontend_developer",
            capabilities=["react_development", "typescript", "ui_design", "responsive_design"],
            shared_context={
                "requirements": self.tech_requirements[:200] + "...",
                "tech_stack": "React, TypeScript, Tailwind CSS"
            }
        )
        
        ai_specialist = await manager.spawn_subordinate(
            role="ai_specialist",
            capabilities=["machine_learning", "nlp", "ai_integration", "model_training"],
            shared_context={
                "project_focus": "AI task prioritization and smart suggestions",
                "ml_framework": "PyTorch, Transformers"
            }
        )
        
        # Assign parallel development tasks
        backend_task = manager.send_message_to_subordinate(
            role="backend_developer",
            message="Develop the FastAPI backend with user authentication, task management endpoints, and database models.",
            context_data={"priority": "core_functionality", "testing_required": True}
        )
        
        frontend_task = manager.send_message_to_subordinate(
            role="frontend_developer", 
            message="Create the React frontend with task dashboard, user interface, and responsive design.",
            context_data={"priority": "user_experience", "accessibility": True}
        )
        
        ai_task = manager.send_message_to_subordinate(
            role="ai_specialist",
            message="Develop AI components for task prioritization, smart suggestions, and natural language task input.",
            context_data={"priority": "ai_features", "accuracy_target": "85%"}
        )
        
        # Monitor parallel development
        PrintStyle(font_color="cyan").print("Running parallel development tasks...")
        
        # Simulate checking on progress (in real scenario, these would be long-running tasks)
        backend_results, frontend_results, ai_results = await asyncio.gather(
            backend_task, frontend_task, ai_task
        )
        
        PrintStyle(font_color="green").print("✓ Backend development completed")
        PrintStyle(font_color="green").print("✓ Frontend development completed")  
        PrintStyle(font_color="green").print("✓ AI components completed")
        
        # Store results
        self.backend_code = backend_results
        self.frontend_code = frontend_results
        self.ai_components = ai_results
        
        print()
    
    async def _phase_3_testing_integration(self, manager):
        """Phase 3: Testing and integration"""
        PrintStyle(font_color="yellow", bold=True).print("PHASE 3: Testing and Integration")
        PrintStyle(font_color="yellow").print("-" * 50)
        
        # Spawn testing specialists
        qa_tester = await manager.spawn_subordinate(
            role="qa_tester",
            capabilities=["automated_testing", "integration_testing", "performance_testing"],
            shared_context={
                "backend_info": self.backend_code[:150] + "...",
                "frontend_info": self.frontend_code[:150] + "..."
            }
        )
        
        integration_specialist = await manager.spawn_subordinate(
            role="integration_specialist",
            capabilities=["system_integration", "api_testing", "deployment"],
            shared_context={
                "components": ["backend", "frontend", "ai_module"],
                "integration_points": "API, database, AI services"
            }
        )
        
        # Run parallel testing
        qa_task = manager.send_message_to_subordinate(
            role="qa_tester",
            message="Create comprehensive test suites for all components. Include unit tests, integration tests, and performance tests.",
            context_data={"coverage_target": "90%", "test_types": ["unit", "integration", "e2e"]}
        )
        
        integration_task = manager.send_message_to_subordinate(
            role="integration_specialist",
            message="Integrate all components and ensure smooth communication between backend, frontend, and AI services.",
            context_data={"deployment_target": "production_ready", "monitoring": True}
        )
        
        PrintStyle(font_color="cyan").print("Running testing and integration...")
        qa_results, integration_results = await asyncio.gather(qa_task, integration_task)
        
        PrintStyle(font_color="green").print("✓ QA testing completed")
        PrintStyle(font_color="green").print("✓ System integration completed")
        
        print()
    
    async def _phase_4_documentation_deployment(self, manager):
        """Phase 4: Documentation and deployment"""
        PrintStyle(font_color="yellow", bold=True).print("PHASE 4: Documentation and Deployment")
        PrintStyle(font_color="yellow").print("-" * 50)
        
        # Spawn documentation and DevOps specialists
        tech_writer = await manager.spawn_subordinate(
            role="technical_writer",
            capabilities=["documentation", "api_docs", "user_guides"],
            shared_context={
                "project_overview": "AI-powered task management application",
                "audience": ["developers", "end_users", "administrators"]
            }
        )
        
        devops_engineer = await manager.spawn_subordinate(
            role="devops_engineer",
            capabilities=["deployment", "ci_cd", "monitoring", "docker"],
            shared_context={
                "tech_stack": "Python, React, PostgreSQL, Docker",
                "deployment_target": "AWS/GCP"
            }
        )
        
        # Parallel documentation and deployment
        docs_task = manager.send_message_to_subordinate(
            role="technical_writer",
            message="Create comprehensive documentation including API docs, user guides, and deployment instructions.",
            context_data={"formats": ["markdown", "online_docs"], "completeness": "production_ready"}
        )
        
        deployment_task = manager.send_message_to_subordinate(
            role="devops_engineer",
            message="Set up production deployment pipeline with Docker containers, CI/CD, and monitoring.",
            context_data={"environment": "cloud", "scalability": True, "monitoring": "comprehensive"}
        )
        
        PrintStyle(font_color="cyan").print("Running documentation and deployment setup...")
        docs_results, deployment_results = await asyncio.gather(docs_task, deployment_task)
        
        PrintStyle(font_color="green").print("✓ Documentation completed")
        PrintStyle(font_color="green").print("✓ Deployment pipeline ready")
        
        print()
    
    async def _phase_5_user_interaction_demo(self, manager):
        """Phase 5: Demonstrate direct user interaction"""
        PrintStyle(font_color="yellow", bold=True).print("PHASE 5: User Interaction Demo")
        PrintStyle(font_color="yellow").print("-" * 50)
        
        # Show all active subordinates
        subordinates = manager.get_all_subordinates()
        
        PrintStyle(font_color="cyan").print("Active Subordinates Available for Direct User Interaction:")
        for sub in subordinates:
            PrintStyle(font_color="white").print(f"  • {sub.role} ({sub.agent_id}) - {sub.status}")
            PrintStyle(font_color="gray").print(f"    URL: {sub.url}")
            PrintStyle(font_color="gray").print(f"    Capabilities: {', '.join(sub.capabilities[:3])}...")
        
        print()
        
        # Simulate user interaction with subordinates
        PrintStyle(font_color="cyan").print("Simulating direct user interactions...")
        
        # User asks backend developer about API endpoints
        if "backend_developer" in manager.subordinate_registry:
            PrintStyle(font_color="green").print("User → Backend Developer: 'What API endpoints did you create?'")
            response = await manager.send_message_to_subordinate(
                role="backend_developer",
                message="What API endpoints did you create for the task management app?",
                context_data={"sender": "user", "interaction_type": "direct_question"}
            )
            PrintStyle(font_color="blue").print(f"Backend Developer → User: {response[:100]}...")
        
        print()
        
        # User asks AI specialist about features
        if "ai_specialist" in manager.subordinate_registry:
            PrintStyle(font_color="green").print("User → AI Specialist: 'How does the task prioritization work?'")
            response = await manager.send_message_to_subordinate(
                role="ai_specialist",
                message="Can you explain how the AI task prioritization feature works?",
                context_data={"sender": "user", "interaction_type": "direct_question"}
            )
            PrintStyle(font_color="blue").print(f"AI Specialist → User: {response[:100]}...")
        
        print()
        
        # Show agent hierarchy
        hierarchy = manager.get_subordinate_hierarchy()
        PrintStyle(font_color="cyan").print("Agent Hierarchy:")
        for parent, children in hierarchy.items():
            PrintStyle(font_color="white").print(f"📍 {parent}")
            for child_id in children:
                subordinate = manager.subordinates.get(child_id)
                if subordinate:
                    PrintStyle(font_color="gray").print(f"  └── {subordinate.role} ({subordinate.status})")
        
        print()
    
    async def cleanup(self):
        """Cleanup all resources"""
        PrintStyle(font_color="yellow").print("Cleaning up demo resources...")
        
        if hasattr(self.context, 'subordinate_manager') and self.context.subordinate_manager:
            self.context.subordinate_manager.cleanup_all_subordinates()
        
        PrintStyle(font_color="green").print("Cleanup completed")


async def main():
    """Main demo execution"""
    demo = A2ASubordinateDemo()
    
    try:
        # Setup main agent
        await demo.setup_main_agent()
        
        # Run the development workflow demo
        await demo.run_development_workflow_demo()
        
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