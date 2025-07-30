#!/usr/bin/env python3
"""
A2A Task Delegator Tool

Implements the complete flowchart workflow:
1. Task Analysis - Analyzes incoming tasks and breaks them down
2. Expertise Matching - Matches tasks to appropriate subordinate capabilities  
3. Task Delegation - Delegates tasks to specific subordinates
4. Independent Operation - Manages subordinate execution in separate contexts
5. Results Integration - Integrates results back to main conversation
6. Feedback Loop - Learns from delegation outcomes

This tool provides intelligent task delegation based on task complexity,
subordinate expertise, and workload balancing.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from python.helpers.a2a_subordinate_manager import A2ASubordinateManager, SubordinateInfo
from python.helpers.a2a_handler import A2AError


@dataclass
class TaskAnalysis:
    """Analysis result for a given task"""
    task_type: str
    complexity: str  # "simple", "medium", "complex", "multi_step"
    required_capabilities: List[str]
    estimated_duration: int  # minutes
    can_parallelize: bool
    sub_tasks: List[str] = field(default_factory=list)
    priority: str = "medium"  # "low", "medium", "high", "urgent"
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ExpertiseMatch:
    """Expertise matching result"""
    subordinate_role: str
    agent_id: str
    match_score: float  # 0.0 to 1.0
    available: bool
    current_workload: int
    specializations: List[str]
    reasons: List[str] = field(default_factory=list)


@dataclass
class DelegationPlan:
    """Complete delegation plan for task execution"""
    task_id: str
    main_task: str
    sub_tasks: List[Dict[str, Any]]
    delegation_strategy: str  # "sequential", "parallel", "hybrid"
    expected_completion_time: int
    success_probability: float
    fallback_plan: Optional[str] = None


class A2aTaskDelegator(Tool):
    """
    Intelligent A2A Task Delegator
    
    Implements the complete flowchart workflow for task analysis,
    expertise matching, delegation, and result integration.
    """
    
    def __init__(self, agent, name: str, method, args: dict, message: str, loop_data: Any):
        super().__init__(agent, name, method, args, message, loop_data)
        
        # Initialize subordinate manager
        if not hasattr(self.agent.context, 'subordinate_manager') or self.agent.context.subordinate_manager is None:
            self.agent.context.subordinate_manager = A2ASubordinateManager(
                agent_context=self.agent.context,
                base_port=getattr(self.agent.config, 'a2a_subordinate_base_port', 8100)
            )
        
        self.subordinate_manager = self.agent.context.subordinate_manager
        
        # Task analysis patterns and capabilities mapping
        self.task_patterns = self._load_task_patterns()
        self.capability_requirements = self._load_capability_requirements()
        self.delegation_history = []  # Learn from previous delegations
    
    async def execute(
        self,
        task_description: str = "",
        auto_delegate: str = "true",
        strategy: str = "intelligent",  # "intelligent", "parallel", "sequential"  
        max_subordinates: int = 3,
        timeout: int = 600,  # 10 minutes
        analyze_only: str = "false",
        **kwargs
    ) -> Response:
        """
        Execute intelligent task delegation workflow
        
        Args:
            task_description: The task to analyze and potentially delegate
            auto_delegate: "true" to auto-delegate, "false" to return plan only
            strategy: Delegation strategy ("intelligent", "parallel", "sequential")
            max_subordinates: Maximum number of subordinates to use
            timeout: Total timeout for all delegated tasks
            analyze_only: "true" to only analyze task without delegation
        """
        if not task_description.strip():
            return Response(
                message="Error: Task description is required for delegation analysis",
                break_loop=False
            )
        
        try:
            # Step 1: Task Analysis
            PrintStyle(font_color="cyan", bold=True).print("🔍 Step 1: Task Analysis")
            task_analysis = await self._analyze_task(task_description)
            
            self._print_task_analysis(task_analysis)
            
            if analyze_only.lower() == "true":
                return self._format_analysis_response(task_analysis)
            
            # Step 2: Check Subagent Expertise  
            PrintStyle(font_color="cyan", bold=True).print("🎯 Step 2: Expertise Matching")
            expertise_matches = await self._match_expertise(task_analysis)
            
            self._print_expertise_matches(expertise_matches)
            
            # Step 3: Task Delegation Planning
            PrintStyle(font_color="cyan", bold=True).print("📋 Step 3: Delegation Planning")
            delegation_plan = await self._create_delegation_plan(
                task_description, task_analysis, expertise_matches, strategy, max_subordinates
            )
            
            self._print_delegation_plan(delegation_plan)
            
            if auto_delegate.lower() != "true":
                return self._format_plan_response(delegation_plan)
            
            # Step 4: Execute Delegation
            PrintStyle(font_color="cyan", bold=True).print("🚀 Step 4: Task Delegation & Execution")
            results = await self._execute_delegation_plan(delegation_plan, timeout)
            
            # Step 5: Results Integration
            PrintStyle(font_color="cyan", bold=True).print("🔄 Step 5: Results Integration")
            integrated_result = await self._integrate_results(task_description, results)
            
            # Step 6: Feedback Loop (learn from this delegation)
            await self._record_delegation_feedback(delegation_plan, results, True)
            
            return Response(
                message=integrated_result,
                break_loop=False
            )
            
        except Exception as e:
            error_msg = f"Task delegation failed: {str(e)}"
            PrintStyle(font_color="red").print(error_msg)
            return Response(message=error_msg, break_loop=False)
    
    async def _analyze_task(self, task_description: str) -> TaskAnalysis:
        """Step 1: Analyze incoming task and break it down"""
        
        # Basic task classification
        task_type = self._classify_task_type(task_description)
        complexity = self._assess_complexity(task_description)
        required_capabilities = self._extract_required_capabilities(task_description)
        
        # Check if task can be parallelized
        can_parallelize = self._can_parallelize(task_description)
        sub_tasks = self._identify_sub_tasks(task_description) if can_parallelize else []
        
        # Estimate duration based on complexity and task type
        estimated_duration = self._estimate_duration(task_type, complexity, len(sub_tasks))
        
        # Determine priority
        priority = self._determine_priority(task_description)
        
        return TaskAnalysis(
            task_type=task_type,
            complexity=complexity,
            required_capabilities=required_capabilities,
            estimated_duration=estimated_duration,
            can_parallelize=can_parallelize,
            sub_tasks=sub_tasks,
            priority=priority
        )
    
    async def _match_expertise(self, task_analysis: TaskAnalysis) -> List[ExpertiseMatch]:
        """Step 2: Match task requirements to subordinate expertise"""
        
        # Get all available subordinates
        subordinates = self.subordinate_manager.get_all_subordinates()
        expertise_matches = []
        
        for subordinate in subordinates:
            # Calculate match score based on capabilities
            match_score = self._calculate_match_score(
                task_analysis.required_capabilities,
                subordinate.capabilities
            )
            
            # Check availability 
            available = subordinate.status in ['ready', 'idle']
            current_workload = 1 if subordinate.status == 'busy' else 0
            
            # Get specializations for this role
            specializations = self._get_role_specializations(subordinate.role)
            
            # Generate reasons for match score
            reasons = self._generate_match_reasons(
                task_analysis.required_capabilities,
                subordinate.capabilities,
                specializations
            )
            
            expertise_match = ExpertiseMatch(
                subordinate_role=subordinate.role,
                agent_id=subordinate.agent_id,
                match_score=match_score,
                available=available,
                current_workload=current_workload,
                specializations=specializations,
                reasons=reasons
            )
            
            expertise_matches.append(expertise_match)
        
        # Sort by match score and availability
        expertise_matches.sort(
            key=lambda x: (x.available, x.match_score, -x.current_workload),
            reverse=True
        )
        
        return expertise_matches
    
    async def _create_delegation_plan(
        self,
        task_description: str,
        task_analysis: TaskAnalysis,
        expertise_matches: List[ExpertiseMatch],
        strategy: str,
        max_subordinates: int
    ) -> DelegationPlan:
        """Step 3: Create delegation plan"""
        
        task_id = str(uuid.uuid4())
        
        # Determine delegation strategy
        if strategy == "intelligent":
            if task_analysis.can_parallelize and len(task_analysis.sub_tasks) > 1:
                delegation_strategy = "parallel"
            elif task_analysis.complexity in ["complex", "multi_step"]:
                delegation_strategy = "hybrid"
            else:
                delegation_strategy = "sequential"
        else:
            delegation_strategy = strategy
        
        # Create sub-task assignments
        sub_tasks = []
        
        if delegation_strategy == "parallel" and task_analysis.sub_tasks:
            # Assign sub-tasks to best matching subordinates
            available_matches = [m for m in expertise_matches if m.available][:max_subordinates]
            
            for i, sub_task in enumerate(task_analysis.sub_tasks[:len(available_matches)]):
                match = available_matches[i]
                sub_tasks.append({
                    "task": sub_task,
                    "assigned_to": match.subordinate_role,
                    "agent_id": match.agent_id,
                    "match_score": match.match_score,
                    "estimated_duration": task_analysis.estimated_duration // len(task_analysis.sub_tasks)
                })
        else:
            # Assign main task to best match
            if expertise_matches and expertise_matches[0].available:
                best_match = expertise_matches[0]
                sub_tasks.append({
                    "task": task_description,
                    "assigned_to": best_match.subordinate_role,
                    "agent_id": best_match.agent_id,
                    "match_score": best_match.match_score,
                    "estimated_duration": task_analysis.estimated_duration
                })
        
        # Calculate expected completion time
        if delegation_strategy == "parallel":
            expected_completion_time = max([st["estimated_duration"] for st in sub_tasks]) if sub_tasks else task_analysis.estimated_duration
        else:
            expected_completion_time = sum([st["estimated_duration"] for st in sub_tasks]) if sub_tasks else task_analysis.estimated_duration
        
        # Calculate success probability based on match scores and subordinate availability
        if sub_tasks:
            avg_match_score = sum([st["match_score"] for st in sub_tasks]) / len(sub_tasks)
            success_probability = min(0.95, avg_match_score * 0.9 + 0.1)
        else:
            success_probability = 0.1  # Low if no subordinates available
        
        return DelegationPlan(
            task_id=task_id,
            main_task=task_description,
            sub_tasks=sub_tasks,
            delegation_strategy=delegation_strategy,
            expected_completion_time=expected_completion_time,
            success_probability=success_probability,
            fallback_plan="Execute task directly if all delegations fail"
        )
    
    async def _execute_delegation_plan(
        self, 
        delegation_plan: DelegationPlan, 
        total_timeout: int
    ) -> List[Dict[str, Any]]:
        """Step 4: Execute the delegation plan"""
        
        if not delegation_plan.sub_tasks:
            return [{
                "success": False,
                "error": "No subordinates available for delegation",
                "task": delegation_plan.main_task
            }]
        
        results = []
        
        if delegation_plan.delegation_strategy == "parallel":
            # Execute all sub-tasks in parallel
            tasks = []
            for sub_task in delegation_plan.sub_tasks:
                task = asyncio.create_task(
                    self._execute_single_delegation(
                        sub_task["task"],
                        sub_task["assigned_to"],
                        sub_task["estimated_duration"] + 60  # Add buffer
                    )
                )
                tasks.append((sub_task, task))
            
            # Wait for all tasks to complete
            for sub_task, task in tasks:
                try:
                    result = await asyncio.wait_for(task, timeout=total_timeout)
                    results.append({
                        "sub_task": sub_task["task"],
                        "assigned_to": sub_task["assigned_to"],
                        "success": True,
                        "result": result,
                        "execution_time": sub_task["estimated_duration"]
                    })
                except asyncio.TimeoutError:
                    results.append({
                        "sub_task": sub_task["task"],
                        "assigned_to": sub_task["assigned_to"],
                        "success": False,
                        "error": "Task timed out",
                        "execution_time": total_timeout
                    })
                except Exception as e:
                    results.append({
                        "sub_task": sub_task["task"],
                        "assigned_to": sub_task["assigned_to"],
                        "success": False,
                        "error": str(e),
                        "execution_time": 0
                    })
        
        else:
            # Execute tasks sequentially
            for sub_task in delegation_plan.sub_tasks:
                try:
                    result = await self._execute_single_delegation(
                        sub_task["task"],
                        sub_task["assigned_to"],
                        sub_task["estimated_duration"] + 60
                    )
                    results.append({
                        "sub_task": sub_task["task"],
                        "assigned_to": sub_task["assigned_to"],
                        "success": True,
                        "result": result,
                        "execution_time": sub_task["estimated_duration"]
                    })
                except Exception as e:
                    results.append({
                        "sub_task": sub_task["task"],
                        "assigned_to": sub_task["assigned_to"],
                        "success": False,
                        "error": str(e),
                        "execution_time": 0
                    })
                    # Continue with next task even if one fails
        
        return results
    
    async def _execute_single_delegation(
        self, 
        task: str, 
        subordinate_role: str, 
        timeout: int
    ) -> str:
        """Execute a single task delegation to a subordinate"""
        
        try:
            # Use the existing subordinate communication
            response = await self.subordinate_manager.send_message_to_subordinate(
                role=subordinate_role,
                message=task,
                context_data={
                    "delegation_context": "intelligent_delegation",
                    "parent_task": task,
                    "independent_operation": True
                },
                timeout=timeout
            )
            return response
            
        except Exception as e:
            raise Exception(f"Delegation to {subordinate_role} failed: {str(e)}")
    
    async def _integrate_results(
        self, 
        original_task: str, 
        results: List[Dict[str, Any]]
    ) -> str:
        """Step 5: Integrate results back to main conversation"""
        
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]
        
        # Build integrated response
        response_parts = []
        response_parts.append(f"**Task Delegation Results for:** {original_task}\n")
        
        if successful_results:
            response_parts.append("**✅ Successfully Completed Sub-tasks:**\n")
            for result in successful_results:
                subordinate = result["assigned_to"]
                task = result["sub_task"]
                response = result["result"]
                
                response_parts.append(f"**@{subordinate}** - {task}")
                response_parts.append(f"```\n{response}\n```\n")
        
        if failed_results:
            response_parts.append("**❌ Failed Sub-tasks:**\n")
            for result in failed_results:
                subordinate = result["assigned_to"]
                task = result["sub_task"]
                error = result.get("error", "Unknown error")
                
                response_parts.append(f"**@{subordinate}** - {task}")
                response_parts.append(f"*Error: {error}*\n")
        
        # Add summary
        total_tasks = len(results)
        successful_count = len(successful_results)
        
        response_parts.append(f"**Summary:** {successful_count}/{total_tasks} tasks completed successfully")
        
        if successful_count == total_tasks:
            response_parts.append("🎉 All delegated tasks completed successfully!")
        elif successful_count > 0:
            response_parts.append("⚠️ Partial success - some tasks completed")
        else:
            response_parts.append("❌ All delegated tasks failed - executing fallback")
        
        return "\n".join(response_parts)
    
    async def _record_delegation_feedback(
        self, 
        delegation_plan: DelegationPlan, 
        results: List[Dict[str, Any]], 
        overall_success: bool
    ):
        """Step 6: Record feedback for learning (feedback loop)"""
        
        feedback_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": delegation_plan.main_task[:100],
            "strategy": delegation_plan.delegation_strategy,
            "subordinates_used": len(delegation_plan.sub_tasks),
            "success_rate": len([r for r in results if r.get("success")]) / len(results) if results else 0,
            "actual_completion_time": sum([r.get("execution_time", 0) for r in results]),
            "expected_completion_time": delegation_plan.expected_completion_time,
            "overall_success": overall_success
        }
        
        self.delegation_history.append(feedback_record)
        
        # Keep only last 50 delegations for learning
        if len(self.delegation_history) > 50:
            self.delegation_history = self.delegation_history[-50:]
        
        PrintStyle(font_color="green").print(
            f"📊 Feedback recorded: {feedback_record['success_rate']:.1%} success rate"
        )
    
    # Helper methods for task analysis
    def _classify_task_type(self, task_description: str) -> str:
        """Classify the type of task"""
        task_lower = task_description.lower()
        
        for pattern, task_type in self.task_patterns.items():
            if any(keyword in task_lower for keyword in pattern):
                return task_type
        
        return "general"
    
    def _assess_complexity(self, task_description: str) -> str:
        """Assess task complexity"""
        task_lower = task_description.lower()
        
        # Simple indicators
        simple_indicators = ["simple", "basic", "quick", "list", "show", "display"]
        # Complex indicators  
        complex_indicators = ["complex", "detailed", "comprehensive", "analyze", "research", "implement", "build", "create", "develop"]
        # Multi-step indicators
        multi_step_indicators = ["and", "then", "after", "first", "second", "step", "phase"]
        
        complexity_score = 0
        
        if any(indicator in task_lower for indicator in complex_indicators):
            complexity_score += 3
        
        if any(indicator in task_lower for indicator in multi_step_indicators):
            complexity_score += 2
            
        if len(task_description.split()) > 20:  # Long descriptions are usually complex
            complexity_score += 1
            
        if any(indicator in task_lower for indicator in simple_indicators):
            complexity_score -= 1
        
        if complexity_score >= 4:
            return "complex"
        elif complexity_score >= 2:
            return "medium"
        else:
            return "simple"
    
    def _extract_required_capabilities(self, task_description: str) -> List[str]:
        """Extract required capabilities from task description"""
        task_lower = task_description.lower()
        required_capabilities = []
        
        for capability, keywords in self.capability_requirements.items():
            if any(keyword in task_lower for keyword in keywords):
                required_capabilities.append(capability)
        
        return required_capabilities if required_capabilities else ["general_task_execution"]
    
    def _can_parallelize(self, task_description: str) -> bool:
        """Determine if task can be parallelized"""
        task_lower = task_description.lower()
        
        # Indicators that task can be split
        parallel_indicators = [
            "and", "also", "plus", "additionally", "furthermore",
            "multiple", "several", "various", "different"
        ]
        
        # Indicators that task should be sequential
        sequential_indicators = [
            "then", "after", "next", "following", "subsequently",
            "first", "second", "finally", "depends on", "requires"
        ]
        
        parallel_score = sum(1 for indicator in parallel_indicators if indicator in task_lower)
        sequential_score = sum(1 for indicator in sequential_indicators if indicator in task_lower)
        
        return parallel_score > sequential_score and parallel_score > 0
    
    def _identify_sub_tasks(self, task_description: str) -> List[str]:
        """Break down task into sub-tasks"""
        # Simple splitting by common separators
        potential_subtasks = []
        
        # Split by "and", periods followed by action words, etc.
        import re
        
        # Split by coordinating conjunctions
        parts = re.split(r'\s+and\s+|\s+also\s+|\s+plus\s+|\s+additionally\s+', task_description)
        
        if len(parts) > 1:
            potential_subtasks.extend([part.strip() for part in parts if len(part.strip()) > 10])
        
        # Split by numbered lists
        numbered_parts = re.findall(r'\d+\.\s*([^.]+)', task_description)
        if numbered_parts:
            potential_subtasks.extend([part.strip() for part in numbered_parts])
        
        # If no clear sub-tasks found, return empty list
        return potential_subtasks[:5] if potential_subtasks else []  # Max 5 sub-tasks
    
    def _estimate_duration(self, task_type: str, complexity: str, num_subtasks: int) -> int:
        """Estimate task duration in minutes"""
        base_durations = {
            "coding": 30,
            "analysis": 20,
            "research": 25,
            "testing": 15,
            "writing": 20,
            "general": 15
        }
        
        complexity_multipliers = {
            "simple": 0.5,
            "medium": 1.0,
            "complex": 2.0,
            "multi_step": 1.5
        }
        
        base_duration = base_durations.get(task_type, 15)
        multiplier = complexity_multipliers.get(complexity, 1.0)
        subtask_factor = 1 + (num_subtasks * 0.2)  # Each subtask adds 20%
        
        return int(base_duration * multiplier * subtask_factor)
    
    def _determine_priority(self, task_description: str) -> str:
        """Determine task priority"""
        task_lower = task_description.lower()
        
        urgent_indicators = ["urgent", "asap", "immediately", "critical", "emergency"]
        high_indicators = ["important", "priority", "deadline", "soon"]
        low_indicators = ["when you can", "no rush", "eventually", "low priority"]
        
        if any(indicator in task_lower for indicator in urgent_indicators):
            return "urgent"
        elif any(indicator in task_lower for indicator in high_indicators):
            return "high"
        elif any(indicator in task_lower for indicator in low_indicators):
            return "low"
        else:
            return "medium"
    
    def _calculate_match_score(self, required_capabilities: List[str], subordinate_capabilities: List[str]) -> float:
        """Calculate how well subordinate capabilities match task requirements"""
        if not required_capabilities:
            return 0.5  # Neutral score if no specific requirements
        
        matched_capabilities = set(required_capabilities) & set(subordinate_capabilities)
        return len(matched_capabilities) / len(required_capabilities)
    
    def _get_role_specializations(self, role: str) -> List[str]:
        """Get specializations for a subordinate role"""
        specializations = {
            "coder": ["programming", "debugging", "code_review", "software_development"],
            "analyst": ["data_analysis", "reporting", "statistics", "visualization"],
            "researcher": ["web_search", "information_gathering", "fact_checking", "summarization"],
            "tester": ["testing", "quality_assurance", "validation", "debugging"],
            "writer": ["content_creation", "documentation", "editing", "communication"],
            "specialist": ["problem_solving", "analysis", "consultation"],
            "assistant": ["general_assistance", "coordination", "communication"]
        }
        
        return specializations.get(role.lower(), ["general_task_execution"])
    
    def _generate_match_reasons(self, required_caps: List[str], subordinate_caps: List[str], specializations: List[str]) -> List[str]:
        """Generate human-readable reasons for match score"""
        reasons = []
        
        matched = set(required_caps) & set(subordinate_caps)
        if matched:
            reasons.append(f"Has {len(matched)} required capabilities: {', '.join(matched)}")
        
        missing = set(required_caps) - set(subordinate_caps)
        if missing:
            reasons.append(f"Missing {len(missing)} capabilities: {', '.join(missing)}")
        
        relevant_specializations = set(specializations) & set(required_caps)
        if relevant_specializations:
            reasons.append(f"Specialized in: {', '.join(relevant_specializations)}")
        
        return reasons if reasons else ["General capability match"]
    
    def _load_task_patterns(self) -> Dict[Tuple[str, ...], str]:
        """Load task classification patterns"""
        return {
            ("code", "program", "implement", "develop", "build", "create function"): "coding",
            ("analyze", "data", "statistics", "report", "dashboard"): "analysis", 
            ("research", "find", "search", "investigate", "lookup"): "research",
            ("test", "check", "validate", "verify", "debug"): "testing",
            ("write", "document", "explain", "summarize", "draft"): "writing",
            ("help", "assist", "support", "general"): "general"
        }
    
    def _load_capability_requirements(self) -> Dict[str, List[str]]:
        """Load capability requirements mapping"""
        return {
            "code_execution": ["code", "program", "implement", "develop", "script", "function"],
            "data_analysis": ["analyze", "data", "statistics", "metrics", "trends", "insights"],
            "web_search": ["search", "find", "lookup", "research", "investigate"],
            "file_management": ["file", "folder", "directory", "save", "load", "organize"],
            "testing": ["test", "check", "validate", "verify", "debug", "quality"],
            "debugging": ["debug", "fix", "error", "bug", "issue", "problem"],
            "visualization": ["chart", "graph", "plot", "visual", "dashboard", "diagram"],
            "documentation": ["document", "write", "explain", "guide", "manual"],
            "communication": ["message", "email", "notify", "communicate", "contact"]
        }
    
    # Response formatting methods
    def _format_analysis_response(self, analysis: TaskAnalysis) -> Response:
        """Format task analysis results"""
        response_parts = [
            f"**📋 Task Analysis Results**",
            f"**Type:** {analysis.task_type}",
            f"**Complexity:** {analysis.complexity}",
            f"**Priority:** {analysis.priority}",
            f"**Estimated Duration:** {analysis.estimated_duration} minutes",
            f"**Can Parallelize:** {'Yes' if analysis.can_parallelize else 'No'}",
            f"**Required Capabilities:** {', '.join(analysis.required_capabilities)}"
        ]
        
        if analysis.sub_tasks:
            response_parts.append(f"**Sub-tasks Identified:**")
            for i, sub_task in enumerate(analysis.sub_tasks, 1):
                response_parts.append(f"{i}. {sub_task}")
        
        return Response(message="\n".join(response_parts), break_loop=False)
    
    def _format_plan_response(self, plan: DelegationPlan) -> Response:
        """Format delegation plan results"""
        response_parts = [
            f"**📋 Delegation Plan**",
            f"**Strategy:** {plan.delegation_strategy}",
            f"**Expected Completion:** {plan.expected_completion_time} minutes",
            f"**Success Probability:** {plan.success_probability:.1%}",
            ""
        ]
        
        if plan.sub_tasks:
            response_parts.append("**Task Assignments:**")
            for i, sub_task in enumerate(plan.sub_tasks, 1):
                response_parts.append(
                    f"{i}. **@{sub_task['assigned_to']}** - {sub_task['task']} "
                    f"(Match: {sub_task['match_score']:.1%}, ~{sub_task['estimated_duration']}min)"
                )
        else:
            response_parts.append("**⚠️ No subordinates available for delegation**")
        
        if plan.fallback_plan:
            response_parts.append(f"**Fallback:** {plan.fallback_plan}")
        
        response_parts.append("\nUse `auto_delegate=true` to execute this plan.")
        
        return Response(message="\n".join(response_parts), break_loop=False)
    
    def _print_task_analysis(self, analysis: TaskAnalysis):
        """Print task analysis to console"""
        PrintStyle(font_color="green").print(f"   Task Type: {analysis.task_type}")
        PrintStyle(font_color="green").print(f"   Complexity: {analysis.complexity}")
        PrintStyle(font_color="green").print(f"   Required Capabilities: {', '.join(analysis.required_capabilities)}")
        PrintStyle(font_color="green").print(f"   Estimated Duration: {analysis.estimated_duration} minutes")
        PrintStyle(font_color="green").print(f"   Can Parallelize: {analysis.can_parallelize}")
        if analysis.sub_tasks:
            PrintStyle(font_color="green").print(f"   Sub-tasks: {len(analysis.sub_tasks)} identified")
    
    def _print_expertise_matches(self, matches: List[ExpertiseMatch]):
        """Print expertise matches to console"""
        for match in matches[:3]:  # Show top 3 matches
            status = "✅ Available" if match.available else "❌ Busy"
            PrintStyle(font_color="green").print(
                f"   @{match.subordinate_role}: {match.match_score:.1%} match, {status}"
            )
    
    def _print_delegation_plan(self, plan: DelegationPlan):
        """Print delegation plan to console"""
        PrintStyle(font_color="green").print(f"   Strategy: {plan.delegation_strategy}")
        PrintStyle(font_color="green").print(f"   Tasks to delegate: {len(plan.sub_tasks)}")
        PrintStyle(font_color="green").print(f"   Expected completion: {plan.expected_completion_time} minutes")
        PrintStyle(font_color="green").print(f"   Success probability: {plan.success_probability:.1%}")