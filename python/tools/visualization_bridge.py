import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class VisualizationBridge(Tool):
    """
    Bridge tool to integrate with VisuaLearn visualization engine.
    Detects visualizable engineering concepts and generates simulation suggestions.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Catalog of available visualizations for engineering concepts
        self.visualization_catalog = {
            # Computer Science / Algorithms
            "bubble_sort": {
                "type": "algorithm_animation",
                "description": "Interactive bubble sort step-by-step visualization",
                "url_template": "/visualize/algorithms/bubble_sort",
                "subjects": ["computer_science", "algorithms"]
            },
            "quick_sort": {
                "type": "algorithm_animation", 
                "description": "Interactive quicksort partitioning visualization",
                "url_template": "/visualize/algorithms/quick_sort",
                "subjects": ["computer_science", "algorithms"]
            },
            "binary_tree": {
                "type": "data_structure",
                "description": "Interactive binary tree manipulation",
                "url_template": "/visualize/data_structures/binary_tree",
                "subjects": ["computer_science", "data_structures"]
            },
            "dijkstra_algorithm": {
                "type": "graph_algorithm",
                "description": "Step-by-step shortest path visualization",
                "url_template": "/visualize/algorithms/dijkstra",
                "subjects": ["computer_science", "graph_theory"]
            },
            
            # Mechanical Engineering
            "stress_strain": {
                "type": "physics_simulation",
                "description": "Interactive stress-strain curve visualization",
                "url_template": "/visualize/mechanics/stress_strain",
                "subjects": ["mechanical", "materials"]
            },
            "heat_transfer": {
                "type": "physics_simulation",
                "description": "Heat conduction and convection simulation",
                "url_template": "/visualize/thermodynamics/heat_transfer", 
                "subjects": ["mechanical", "thermodynamics"]
            },
            
            # Electrical Engineering
            "circuit_analysis": {
                "type": "circuit_simulation",
                "description": "Interactive circuit analysis with voltage/current visualization",
                "url_template": "/visualize/circuits/analysis",
                "subjects": ["electrical", "circuits"]
            },
            "fourier_transform": {
                "type": "signal_processing",
                "description": "Interactive FFT visualization with frequency domain",
                "url_template": "/visualize/signals/fourier",
                "subjects": ["electrical", "signal_processing"]
            },
            
            # Civil Engineering
            "beam_deflection": {
                "type": "structural_analysis",
                "description": "Beam deflection under different loads",
                "url_template": "/visualize/structures/beam_deflection",
                "subjects": ["civil", "structures"]
            },
            
            # Chemical Engineering
            "distillation_column": {
                "type": "process_simulation",
                "description": "Interactive distillation column operation",
                "url_template": "/visualize/processes/distillation",
                "subjects": ["chemical", "mass_transfer"]
            }
        }
    
    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "").lower()
        
        if action == "detect_visualizable":
            return await self.detect_visualizable_concepts()
        elif action == "suggest_visualization":
            return await self.suggest_visualization()
        elif action == "generate_link":
            return await self.generate_visualization_link()
        elif action == "track_usage":
            return await self.track_visualization_usage()
        else:
            return Response(message="Available actions: detect_visualizable, suggest_visualization, generate_link, track_usage", break_loop=False)
    
    async def detect_visualizable_concepts(self) -> Response:
        """Analyze content to detect concepts that can be visualized"""
        content = self.args.get("content", "").lower()
        subject_area = self.args.get("subject_area", "computer_science")
        
        detected_concepts = []
        
        # Scan content for visualizable keywords
        for concept_key, concept_data in self.visualization_catalog.items():
            # Check if concept keywords appear in content
            concept_keywords = concept_key.replace("_", " ").split()
            if any(keyword in content for keyword in concept_keywords):
                if subject_area in concept_data["subjects"] or "all" in concept_data["subjects"]:
                    detected_concepts.append({
                        "concept": concept_key,
                        "type": concept_data["type"],
                        "description": concept_data["description"],
                        "relevance_score": self._calculate_relevance(content, concept_keywords)
                    })
        
        # Sort by relevance
        detected_concepts.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        result = {
            "detected_concepts": detected_concepts[:3],  # Top 3 most relevant
            "content_analyzed": len(content) > 0,
            "subject_area": subject_area,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        return Response(message=f"Visualizable concepts detected: {json.dumps(result, indent=2)}", break_loop=False)
    
    async def suggest_visualization(self) -> Response:
        """Generate visualization suggestions based on learning context"""
        concept = self.args.get("concept", "")
        learning_style = self.args.get("learning_style", "visual")
        student_level = self.args.get("student_level", "intermediate")
        
        if concept not in self.visualization_catalog:
            return Response(message=f"No visualization available for concept: {concept}", break_loop=False)
        
        viz_data = self.visualization_catalog[concept]
        
        # Customize suggestion based on learning style
        if learning_style == "visual":
            suggestion_text = f"🎯 **Visual Learning Opportunity!**\n\n"
            suggestion_text += f"I can show you an interactive {viz_data['description']} that will help you visualize this concept step by step.\n\n"
        elif learning_style == "kinesthetic":
            suggestion_text = f"🎯 **Hands-On Learning Opportunity!**\n\n" 
            suggestion_text += f"Try this interactive {viz_data['description']} where you can manipulate parameters and see real-time results.\n\n"
        else:  # auditory
            suggestion_text = f"🎯 **Interactive Learning Opportunity!**\n\n"
            suggestion_text += f"Let me show you {viz_data['description']} with guided explanations as we explore together.\n\n"
        
        suggestion_text += f"**[🎮 Launch Interactive Simulation: {concept.title().replace('_', ' ')}]**\n"
        suggestion_text += f"*Click to open visualization engine*\n\n"
        suggestion_text += f"This simulation is perfect for {student_level} level understanding."
        
        return Response(message=suggestion_text, break_loop=False)
    
    async def generate_visualization_link(self) -> Response:
        """Generate actual link to visualization engine"""
        concept = self.args.get("concept", "")
        student_id = self.args.get("student_id", "default_student")
        session_context = self.args.get("context", {})
        
        if concept not in self.visualization_catalog:
            return Response(message=f"Cannot generate link for unknown concept: {concept}", break_loop=False)
        
        viz_data = self.visualization_catalog[concept]
        
        # Generate link with context parameters
        base_url = viz_data["url_template"]
        link_params = {
            "student_id": student_id,
            "context": json.dumps(session_context),
            "timestamp": datetime.now().isoformat(),
            "source": "agent_suggestion"
        }
        
        # In real implementation, this would generate actual URL
        visualization_link = {
            "concept": concept,
            "url": f"{base_url}?{self._encode_params(link_params)}",
            "type": viz_data["type"],
            "description": viz_data["description"],
            "launch_context": session_context
        }
        
        return Response(message=f"Visualization link generated: {json.dumps(visualization_link, indent=2)}", break_loop=False)
    
    async def track_visualization_usage(self) -> Response:
        """Track student interaction with visualizations"""
        usage_data = self.args.get("usage_data", {})
        concept = self.args.get("concept", "")
        interaction_time = self.args.get("interaction_time", 0)
        engagement_score = self.args.get("engagement_score", 0)
        
        tracking_info = {
            "concept": concept,
            "usage_timestamp": datetime.now().isoformat(),
            "interaction_duration": interaction_time,
            "engagement_score": engagement_score,
            "user_actions": usage_data.get("actions", []),
            "completion_status": usage_data.get("completed", False)
        }
        
        # This data would be saved to memory for learning style adaptation
        return Response(message=f"Visualization usage tracked: {json.dumps(tracking_info, indent=2)}", break_loop=False)
    
    def _calculate_relevance(self, content: str, keywords: list) -> float:
        """Calculate relevance score based on keyword frequency and context"""
        score = 0
        for keyword in keywords:
            score += content.count(keyword) * 0.3
        
        # Bonus for exact phrase matches
        phrase = " ".join(keywords)
        if phrase in content:
            score += 1.0
            
        return min(score, 5.0)  # Cap at 5.0
    
    def _encode_params(self, params: dict) -> str:
        """Encode parameters for URL (simplified)"""
        return "&".join([f"{k}={v}" for k, v in params.items()])
