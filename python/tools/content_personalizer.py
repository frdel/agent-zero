import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class ContentPersonalizer(Tool):
    """
    Personalizes educational content based on student learning profile.
    Adapts explanations, examples, and complexity based on individual preferences.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Engineering example databases for different fields
        self.engineering_examples = {
            "computer_science": {
                "data_structures": ["social media friend connections", "file system organization", "database indexing"],
                "algorithms": ["GPS route finding", "search engine ranking", "video compression"],
                "networking": ["internet routing", "video streaming", "online gaming latency"]
            },
            "mechanical": {
                "stress_analysis": ["bridge design", "aircraft wing loading", "pressure vessel safety"],
                "thermodynamics": ["car engine efficiency", "HVAC system design", "power plant operation"],
                "materials": ["smartphone durability", "athletic equipment design", "building materials"]
            },
            "electrical": {
                "circuits": ["smartphone charging", "LED lighting systems", "electric vehicle charging"],
                "signal_processing": ["noise cancellation headphones", "medical imaging", "wireless communication"],
                "power_systems": ["solar panel efficiency", "electric grid stability", "battery management"]
            },
            "civil": {
                "structures": ["skyscraper stability", "bridge earthquake resistance", "stadium roof design"],
                "fluid_mechanics": ["water supply systems", "flood control", "pipeline design"],
                "materials": ["concrete durability", "road surface design", "earthquake-resistant buildings"]
            },
            "chemical": {
                "mass_transfer": ["pharmaceutical production", "water purification", "oil refining"],
                "reaction_engineering": ["battery chemistry", "polymer manufacturing", "food processing"],
                "process_control": ["chemical plant safety", "quality control", "environmental compliance"]
            }
        }
    
    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "").lower()
        
        if action == "personalize_explanation":
            return await self.personalize_explanation()
        elif action == "generate_examples":
            return await self.generate_examples()
        elif action == "adjust_complexity":
            return await self.adjust_complexity()
        elif action == "adapt_teaching_style":
            return await self.adapt_teaching_style()
        else:
            return Response(message="Available actions: personalize_explanation, generate_examples, adjust_complexity, adapt_teaching_style", break_loop=False)
    
    async def personalize_explanation(self) -> Response:
        """Personalize explanation based on student profile"""
        content = self.args.get("content", "")
        student_profile = self.args.get("student_profile", {})
        topic = self.args.get("topic", "")
        
        learning_style = student_profile.get("learning_style", {}).get("primary", "visual")
        engineering_field = student_profile.get("engineering_field", "computer_science")
        complexity_level = student_profile.get("complexity_tolerance", 5)
        
        personalized_content = self._adapt_content_to_style(content, learning_style)
        personalized_content = self._adjust_content_complexity(personalized_content, complexity_level)
        personalized_content = self._add_field_specific_context(personalized_content, engineering_field, topic)
        
        result = {
            "original_content": content,
            "personalized_content": personalized_content,
            "adaptations_applied": {
                "learning_style": learning_style,
                "complexity_level": complexity_level,
                "engineering_field": engineering_field
            },
            "personalization_timestamp": datetime.now().isoformat()
        }
        
        return Response(message=f"Content personalized: {json.dumps(result, indent=2)}", break_loop=False)
    
    async def generate_examples(self) -> Response:
        """Generate relevant examples based on student's engineering field"""
        concept = self.args.get("concept", "")
        engineering_field = self.args.get("engineering_field", "computer_science")
        learning_style = self.args.get("learning_style", "visual")
        
        if engineering_field not in self.engineering_examples:
            engineering_field = "computer_science"  # Default fallback
        
        # Find relevant subcategory
        subcategory = self._find_best_subcategory(concept, engineering_field)
        examples = self.engineering_examples[engineering_field].get(subcategory, [])
        
        if not examples:
            # Use default examples from computer science
            examples = ["system optimization", "user interface design", "data analysis"]
        
        # Format examples based on learning style
        formatted_examples = self._format_examples_for_style(examples, learning_style, concept)
        
        result = {
            "concept": concept,
            "engineering_field": engineering_field,
            "subcategory": subcategory,
            "examples": formatted_examples,
            "learning_style_adaptation": learning_style
        }
        
        return Response(message=f"Examples generated: {json.dumps(result, indent=2)}", break_loop=False)
    
    async def adjust_complexity(self) -> Response:
        """Adjust explanation complexity based on student comprehension"""
        content = self.args.get("content", "")
        complexity_adjustment = self.args.get("complexity_adjustment", 0)  # -2 to +2
        current_level = self.args.get("current_level", 5)  # 1-10 scale
        
        new_level = max(1, min(10, current_level + complexity_adjustment))
        
        if complexity_adjustment < 0:
            # Simplify content
            adjusted_content = self._simplify_content(content, abs(complexity_adjustment))
            adjustment_type = "simplified"
        elif complexity_adjustment > 0:
            # Add more detail/complexity
            adjusted_content = self._add_complexity(content, complexity_adjustment)
            adjustment_type = "enhanced"
        else:
            adjusted_content = content
            adjustment_type = "unchanged"
        
        result = {
            "original_content": content,
            "adjusted_content": adjusted_content,
            "complexity_change": {
                "from_level": current_level,
                "to_level": new_level,
                "adjustment": complexity_adjustment,
                "type": adjustment_type
            },
            "adjustment_timestamp": datetime.now().isoformat()
        }
        
        return Response(message=f"Complexity adjusted: {json.dumps(result, indent=2)}", break_loop=False)
    
    async def adapt_teaching_style(self) -> Response:
        """Adapt teaching approach based on student responses and patterns"""
        student_feedback = self.args.get("student_feedback", {})
        interaction_history = self.args.get("interaction_history", [])
        current_topic = self.args.get("topic", "")
        
        # Analyze feedback patterns
        confusion_indicators = student_feedback.get("confusion_signals", 0)
        engagement_level = student_feedback.get("engagement_score", 5)
        preferred_pace = student_feedback.get("pace_preference", "medium")
        
        # Determine teaching adaptations needed
        adaptations = []
        
        if confusion_indicators > 2:
            adaptations.append("use_simpler_language")
            adaptations.append("add_more_examples")
        
        if engagement_level < 3:
            adaptations.append("increase_interactivity")
            adaptations.append("suggest_hands_on_activity")
        
        if preferred_pace == "slow":
            adaptations.append("break_into_smaller_steps")
            adaptations.append("add_more_repetition")
        
        adaptation_plan = {
            "topic": current_topic,
            "detected_needs": {
                "confusion_level": confusion_indicators,
                "engagement_level": engagement_level,
                "pace_preference": preferred_pace
            },
            "adaptations_to_apply": adaptations,
            "expected_outcomes": self._predict_adaptation_outcomes(adaptations),
            "adaptation_timestamp": datetime.now().isoformat()
        }
        
        return Response(message=f"Teaching style adaptation: {json.dumps(adaptation_plan, indent=2)}", break_loop=False)
    
    def _adapt_content_to_style(self, content: str, learning_style: str) -> str:
        """Adapt content presentation for specific learning style"""
        if learning_style == "visual":
            return f"Let me paint a picture of this concept:\n\n{content}\n\n[Visual learner tip: Would you like to see a diagram or simulation of this?]"
        elif learning_style == "auditory":
            return f"Let's talk through this step by step:\n\n{content}\n\n[Auditory learner tip: Feel free to ask questions as we go!]"
        elif learning_style == "kinesthetic":
            return f"Let's explore this hands-on:\n\n{content}\n\n[Kinesthetic learner tip: Ready to try some interactive examples?]"
        else:
            return content
    
    def _adjust_content_complexity(self, content: str, complexity_level: int) -> str:
        """Adjust content complexity based on tolerance level"""
        if complexity_level <= 3:
            return f"**Simplified explanation:**\n\n{content}\n\n*Let me know if you'd like me to break this down further!*"
        elif complexity_level >= 8:
            return f"**Detailed analysis:**\n\n{content}\n\n*I can dive deeper into the technical details if you're interested.*"
        else:
            return content
    
    def _add_field_specific_context(self, content: str, engineering_field: str, topic: str) -> str:
        """Add engineering field-specific context and examples"""
        field_contexts = {
            "computer_science": "In software engineering applications",
            "mechanical": "In mechanical system design",
            "electrical": "In electrical system analysis", 
            "civil": "In structural engineering projects",
            "chemical": "In chemical process engineering"
        }
        
        context = field_contexts.get(engineering_field, "In engineering applications")
        return f"{content}\n\n**{context}:** This concept is particularly important for {topic} because it directly impacts system performance and design decisions."
    
    def _find_best_subcategory(self, concept: str, engineering_field: str) -> str:
        """Find the most relevant subcategory for examples"""
        concept_lower = concept.lower()
        subcategories = self.engineering_examples.get(engineering_field, {}).keys()
        
        for subcategory in subcategories:
            if any(word in concept_lower for word in subcategory.split("_")):
                return subcategory
        
        return list(subcategories)[0] if subcategories else "general"
    
    def _format_examples_for_style(self, examples: list, learning_style: str, concept: str) -> list:
        """Format examples according to learning style preference"""
        if learning_style == "visual":
            return [f"🎯 Visualize: {example} - imagine how {concept} works here" for example in examples]
        elif learning_style == "kinesthetic":
            return [f"🔧 Try this: {example} - hands-on exploration of {concept}" for example in examples]
        else:
            return [f"💭 Consider: {example} - let's discuss how {concept} applies" for example in examples]
    
    def _simplify_content(self, content: str, simplification_level: int) -> str:
        """Simplify content by reducing technical jargon and complexity"""
        simplified = content.replace("utilize", "use").replace("implement", "do").replace("optimize", "improve")
        return f"**Simplified version:**\n\n{simplified}\n\n*Breaking this down into simpler terms...*"
    
    def _add_complexity(self, content: str, complexity_level: int) -> str:
        """Add more technical detail and depth to content"""
        return f"{content}\n\n**Technical deep-dive:** Let me add more engineering detail and mathematical foundations to this explanation..."
    
    def _predict_adaptation_outcomes(self, adaptations: list) -> list:
        """Predict likely outcomes of teaching adaptations"""
        outcome_mapping = {
            "use_simpler_language": "improved comprehension",
            "add_more_examples": "better concept retention", 
            "increase_interactivity": "higher engagement",
            "suggest_hands_on_activity": "enhanced practical understanding",
            "break_into_smaller_steps": "reduced cognitive overload",
            "add_more_repetition": "stronger knowledge consolidation"
        }
        
        return [outcome_mapping.get(adaptation, "general improvement") for adaptation in adaptations]
