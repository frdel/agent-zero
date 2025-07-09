"""
Domain Detector Tool for Agent Zero
===================================

This tool provides intelligent domain detection capabilities including:
- Business domain identification from data patterns
- Industry-specific concept extraction
- Context-aware analysis frameworks
- Iterative refinement with evaluation
"""

import json
import os
from typing import Dict, Any, List, Optional
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle
from langchain_core.prompts import PromptTemplate
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage, HumanMessage


class DomainDetector(Tool):
    """
    Domain Detector Tool for intelligent business context identification.
    
    Provides:
    - Automated domain detection from data characteristics
    - Industry-specific concept extraction
    - Business framework application
    - Context-aware analytical guidance
    """
    
    def __init__(self, agent, name: str, method: str | None, args: dict, message: str, **kwargs):
        super().__init__(agent, name, method, args, message, **kwargs)
        
        # Domain detection will use agent's configured model
        
        # Define prompt templates
        self._setup_prompts()
        
        # Maximum analysis cycles for iterative improvement
        self.max_cycles = 3

    def _setup_prompts(self):
        """Setup all prompt templates for domain detection workflow"""
        
        # Domain identification prompt
        self.domain_prompt = PromptTemplate(
            input_variables=["profile", "memory"],
            template=(
                "Dataset profile (JSON):\n{profile}\n"
                "{memory}\n"
                "Determine the most precise domain / industry label (Wikipedia terminology).\n"
                "Return JSON response in this format: {{ 'domain':<string>, 'definition':<one sentence>, 'wiki_url':<url|''> }}"
            )
        )
        
        # Concept extraction prompt
        self.concept_prompt = PromptTemplate(
            input_variables=["profile", "domain_info", "memory"],
            template=(
                "Profile: {profile}\nDomain: {domain_info}\n"
                "{memory}\n"
                "List 4‑6 concept names (English) that should be analysed for this domain.\n"
                "Return the list in JSON format."
            )
        )
        
        # Analysis synthesis prompt
        self.analysis_prompt = PromptTemplate(
            input_variables=["profile", "domain_info", "concepts", "memory"],
            template=(
                "Profile: {profile}\nDomain: {domain_info}\nCore concepts: {concepts}\n"
                "{memory}\n"
                "Produce a JSON response exactly in this shape:\n"
                "{{ 'domain': <string>, 'core_concepts': [...], 'analysis': {{ 'descriptive':<paragraph>, 'predictive':<paragraph>, 'domain_related':<paragraph> }} }}\n"
                "You are \"InsightWriter-Advanced\", a principled business analyst in any domain (the sharpest one with the highest paid in the world) who turns raw tabular data into SHORT, HIGH-VALUE insights in any domain. Every insight you write is a masterpiece, with perfect sense of using BUSINESS-LENS TAXONOMY(Trend,Variance,Benchmark,Efficiency, and others you can find in the internet), BUSINESS FRAMEWORK(SWOT, PESTEL, 5 Forces, Value Chain,and others you can find in the internet) to support your insights."
            )
        )
        
        # Evaluation prompt
        self.eval_prompt = PromptTemplate(
            input_variables=["domain_info", "concepts", "analysis", "profile"],
            template=(
                "You are an evaluation agent.\n\n"
                "**Part A – Domain & Concepts**\n"
                "• correctness : is the domain label factually accurate for this dataset?\n"
                "• relevance   : do the concepts correspond to real columns / metrics present?\n"
                "• coverage    : do the concepts cover the major elements of the table?\n\n"
                "**Part B – Analysis JSON**\n"
                "• insightfulness : does the analysis provide meaningful, actionable understanding in terms of practical usefulness?\n"
                "• novelty        : does it reveal non‑obvious or surprise factor beyond simple column descriptions?\n\n"
                "• depth          : does the analysis drill into root causes, cross-variable interactions, and quantified impact (vs. surface-level facts)?\n\n"
                "Return a JSON response exactly in this format:\n"
                "{{ 'reason':<brief text>,\n  'scores': {{ 'correctness':#, 'relevance':#, 'coverage':#, 'insightfulness':#, 'novelty':# , 'depth':# }},\n  'domain_ok': <bool correctness==4>,\n  'concepts_ok': <bool relevance>=3 and coverage>=3> }}"
            )
        )
        
        # Reflection prompt
        self.reflect_prompt = PromptTemplate(
            input_variables=["evaluation", "memory"],
            template=(
                "Evaluation JSON: {evaluation}\n"
                "{memory}\n"
                "For every dimension with score ≤3, deliver ONE *piercing* bullet of self-critique:\n"
                "  – call out exactly what is weak or missing, then specify a concrete fix (e.g. 'Consider column YYYY …').\n"
                "NO praise, NO hedging—be blunt.\n"
                "Return ≤5 bullets only, in a valid JSON list format."
            )
        )
        
        # Chains will be replaced with direct agent model calls

    async def _call_agent_model(self, prompt_template: PromptTemplate, **kwargs) -> str:
        """Helper method to call agent's configured model with a prompt template"""
        prompt_text = prompt_template.format(**kwargs)
        
        chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a business domain analysis expert. Respond with valid JSON only when requested."),
            HumanMessage(content=prompt_text),
        ])
        
        response = await self.agent.call_chat_model(prompt=chat_prompt)
        return str(response)

    async def execute(self, **kwargs) -> Response:
        """
        Execute domain detection and analysis workflow.
        
        Expected args:
        - profile_data: Data profile from data_profiler_tool (JSON string or dict)
        - max_cycles: Maximum improvement cycles (optional, default: 3)
        """
        try:
            # Get required parameters
            profile_data = self.args.get("profile_data")
            
            if not profile_data:
                return Response(
                    message="Error: profile_data parameter is required. Please run data_profiler_tool first.",
                    break_loop=False
                )
            
            # Parse profile data if it's a string
            if isinstance(profile_data, str):
                try:
                    profile_data = json.loads(profile_data)
                except json.JSONDecodeError:
                    return Response(
                        message="Error: Invalid profile_data format. Expected JSON string or dict.",
                        break_loop=False
                    )
            
            # Get optional parameters
            max_cycles = int(self.args.get("max_cycles", self.max_cycles))
            
            # Run domain detection workflow
            result = await self._run_domain_analysis(profile_data, max_cycles)
            
            return Response(
                message=result,
                break_loop=False
            )
            
        except Exception as e:
            return Response(
                message=f"Error during domain detection: {str(e)}",
                break_loop=False
            )

    async def _run_domain_analysis(self, profile_data: Dict[str, Any], max_cycles: int) -> str:
        """Run the complete domain detection and analysis workflow"""
        
        # Initialize analysis state
        state = {
            "profile": profile_data,
            "memory": "[]",
            "iteration": 0,
            "max_cycles": max_cycles,
            "domain_fixed": False,
            "history": []
        }
        
        # Run iterative analysis workflow
        for cycle in range(max_cycles):
            state["iteration"] = cycle
            
            # Domain detection
            if not state.get("domain_info") or not state.get("domain_fixed"):
                state = await self._domain_step(state)
            
            # Concept extraction
            state = await self._concept_step(state)
            
            # Analysis synthesis
            state = await self._analysis_step(state)
            
            # Evaluation
            state = await self._evaluation_step(state)
            
            # Check for success or need for reflection
            if self._is_analysis_complete(state):
                break
            
            # Reflection for improvement
            if cycle < max_cycles - 1:  # Don't reflect on final cycle
                state = await self._reflection_step(state)
        
        # Format final response
        return self._format_domain_response(state)

    async def _domain_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute domain identification step"""
        
        memory_text = self._serialize_memory(state.get("memory", "[]"))
        profile_json = json.dumps(state["profile"]) if isinstance(state["profile"], dict) else state["profile"]
        
        content = await self._call_agent_model(
            self.domain_prompt,
            profile=profile_json,
            memory=memory_text
        )
        
        try:
            domain_info = json.loads(content)
            assert isinstance(domain_info, dict)
        except (json.JSONDecodeError, AssertionError):
            domain_info = {
                "domain": "Unknown",
                "definition": "Unable to determine domain from the data",
                "wiki_url": ""
            }
        
        # Ensure required keys
        for key in ("domain", "definition", "wiki_url"):
            domain_info.setdefault(key, "")
        
        state["domain_info"] = domain_info
        return state

    async def _concept_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute concept extraction step"""
        
        memory_text = self._serialize_memory(state.get("memory", "[]"))
        
        content = await self._call_agent_model(
            self.concept_prompt,
            profile=json.dumps(state["profile"]) if isinstance(state["profile"], dict) else state["profile"],
            domain_info=json.dumps(state["domain_info"]),
            memory=memory_text
        )
        
        try:
            concepts = json.loads(content)
            if not isinstance(concepts, list):
                concepts = [concepts]
        except json.JSONDecodeError:
            concepts = []
        
        state["concepts"] = concepts
        return state

    async def _analysis_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis synthesis step"""
        
        memory_text = self._serialize_memory(state.get("memory", "[]"))
        
        content = await self._call_agent_model(
            self.analysis_prompt,
            profile=json.dumps(state["profile"]) if isinstance(state["profile"], dict) else state["profile"],
            domain_info=json.dumps(state["domain_info"]),
            concepts=json.dumps(state["concepts"]),
            memory=memory_text
        )
        
        try:
            analysis = json.loads(content)
            assert isinstance(analysis, dict)
        except (json.JSONDecodeError, AssertionError):
            analysis = {
                "domain": state["domain_info"].get("domain", "Unknown"),
                "core_concepts": state["concepts"],
                "analysis": {
                    "descriptive": "Analysis failed",
                    "predictive": "Analysis failed",
                    "domain_related": "Analysis failed"
                }
            }
        
        state["analysis"] = analysis
        return state

    async def _evaluation_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute evaluation step"""
        
        try:
            content = await self._call_agent_model(
                self.eval_prompt,
                domain_info=json.dumps(state["domain_info"]),
                concepts=json.dumps(state["concepts"]),
                analysis=json.dumps(state["analysis"]),
                profile=json.dumps(state["profile"]) if isinstance(state["profile"], dict) else state["profile"]
            )
            evaluation_result = json.loads(content)
            
            # Validate evaluation structure
            required_keys = ["reason", "scores", "domain_ok", "concepts_ok"]
            for key in required_keys:
                if key not in evaluation_result:
                    raise ValueError(f"Missing required key in evaluation: {key}")
            
        except (json.JSONDecodeError, ValueError):
            evaluation_result = {
                "reason": "Evaluation failed",
                "scores": {
                    "correctness": 2, "relevance": 2, "coverage": 2,
                    "insightfulness": 2, "novelty": 2, "depth": 2
                },
                "domain_ok": False,
                "concepts_ok": False
            }
        
        # Update state with evaluation
        state.update({
            "evaluation": evaluation_result["reason"],
            "scores": evaluation_result["scores"],
            "domain_ok": evaluation_result["domain_ok"],
            "concepts_ok": evaluation_result["concepts_ok"]
        })
        
        # Fix domain if evaluation indicates it's correct
        if evaluation_result["domain_ok"]:
            state["domain_fixed"] = True
        
        # Update history
        history = state.get("history", [])
        history.append({
            "iteration": state.get("iteration", 0),
            "domain": state["domain_info"].get("domain", "Unknown"),
            "scores": evaluation_result["scores"],
            "analysis_summary": state["analysis"]["analysis"]["descriptive"][:100] + "..."
        })
        state["history"] = history
        
        return state

    async def _reflection_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute reflection step for improvement"""
        
        # Build evaluation payload
        eval_payload = {
            "reason": state["evaluation"],
            "scores": state["scores"],
            "domain_ok": state["domain_ok"],
            "concepts_ok": state["concepts_ok"]
        }
        
        # Get previous memory
        previous_memory = self._parse_memory(state.get("memory", "[]"))
        
        # Check which aspects need improvement
        needs_reflection = []
        scores = state["scores"]
        
        if scores.get("correctness", 0) < 4:
            needs_reflection.append("domain")
        if scores.get("relevance", 0) < 4 or scores.get("coverage", 0) < 4:
            needs_reflection.append("concepts")
        if scores.get("insightfulness", 0) < 4 or scores.get("novelty", 0) < 4 or scores.get("depth", 0) < 4:
            needs_reflection.append("analysis")
        
        if needs_reflection:
            try:
                content = await self._call_agent_model(
                    self.reflect_prompt,
                    evaluation=json.dumps(eval_payload),
                    memory="\n".join([f"- {ref}" for ref in previous_memory]) if previous_memory else ""
                )
                new_reflections = json.loads(content)
                
                if not isinstance(new_reflections, list):
                    new_reflections = [new_reflections]
                
                # Add context to reflections
                for i, reflection in enumerate(new_reflections):
                    if isinstance(reflection, str):
                        aspect = needs_reflection[i % len(needs_reflection)]
                        new_reflections[i] = f"[{aspect.upper()}] {reflection}"
                
                combined_reflections = previous_memory + new_reflections
                
            except (json.JSONDecodeError, ValueError):
                combined_reflections = previous_memory
        else:
            combined_reflections = previous_memory
        
        state["memory"] = json.dumps(combined_reflections)
        return state

    def _is_analysis_complete(self, state: Dict[str, Any]) -> bool:
        """Check if analysis meets completion criteria"""
        
        scores = state.get("scores", {})
        
        domain_concept_success = (
            scores.get("correctness", 0) >= 4 and
            scores.get("relevance", 0) >= 4 and
            scores.get("coverage", 0) >= 4
        )
        
        analysis_success = (
            scores.get("insightfulness", 0) >= 4 and
            scores.get("novelty", 0) >= 3 and
            scores.get("depth", 0) >= 4
        )
        
        return domain_concept_success and analysis_success

    def _serialize_memory(self, memory) -> str:
        """Serialize memory to JSON string format"""
        
        if memory in (None, "None"):
            return "[]"
        
        if isinstance(memory, str):
            try:
                parsed = json.loads(memory)
                if isinstance(parsed, list):
                    return json.dumps(parsed)
                return json.dumps([parsed])
            except json.JSONDecodeError:
                return json.dumps([memory])
        
        if isinstance(memory, list):
            return json.dumps(memory)
        
        if isinstance(memory, dict):
            return json.dumps([memory])
        
        return "[]"

    def _parse_memory(self, memory_text: str) -> List[str]:
        """Parse memory from JSON string to list"""
        
        if memory_text in (None, "None", "[]"):
            return []
        
        try:
            parsed = json.loads(memory_text)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            return [memory_text] if memory_text else []

    def _extract_content(self, response):
        """Extract content from LLM response"""
        
        if hasattr(response, 'content'):
            return response.content
        return str(response)

    def _format_domain_response(self, state: Dict[str, Any]) -> str:
        """Format the final domain detection response"""
        
        domain_info = state.get("domain_info", {})
        concepts = state.get("concepts", [])
        analysis = state.get("analysis", {})
        scores = state.get("scores", {})
        history = state.get("history", [])
        
        response_parts = [
            "# Domain Detection Results",
            "",
            f"## Identified Domain: {domain_info.get('domain', 'Unknown')}",
            "",
            f"**Definition:** {domain_info.get('definition', 'No definition available')}",
            "",
            f"**Wikipedia URL:** {domain_info.get('wiki_url', 'Not available')}",
            "",
            "## Core Domain Concepts",
            "",
            *[f"- {concept}" for concept in concepts],
            "",
            "## Domain Analysis",
            "",
            "### Descriptive Analysis",
            analysis.get("analysis", {}).get("descriptive", "Not available"),
            "",
            "### Predictive Analysis",
            analysis.get("analysis", {}).get("predictive", "Not available"),
            "",
            "### Domain-Specific Analysis",
            analysis.get("analysis", {}).get("domain_related", "Not available"),
            "",
            "## Quality Scores",
            "",
            f"- **Domain Correctness:** {scores.get('correctness', 0)}/4",
            f"- **Concept Relevance:** {scores.get('relevance', 0)}/4",
            f"- **Concept Coverage:** {scores.get('coverage', 0)}/4",
            f"- **Analysis Insightfulness:** {scores.get('insightfulness', 0)}/4",
            f"- **Analysis Novelty:** {scores.get('novelty', 0)}/4",
            f"- **Analysis Depth:** {scores.get('depth', 0)}/4",
            "",
            "## Analysis History",
            "",
            *[f"**Iteration {item['iteration']}:** {item['domain']} (Avg Score: {sum(item['scores'].values())/len(item['scores']):.1f})" 
              for item in history],
            "",
            "## Next Steps",
            "",
            "The domain has been successfully identified. You can now:",
            "- Use `insight_generator` with this domain context for deeper analysis",
            "- Apply `chart_creator` with domain-specific visualization recommendations",
            "- Leverage the identified concepts for targeted business insights"
        ]
        
        return "\n".join(response_parts)