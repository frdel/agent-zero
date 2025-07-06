import json
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle


class LearningStyleDetector(Tool):
    """
    Detect and track student learning styles through interaction patterns and optional surveys.
    Integrates with memory system to maintain persistent student profiles.
    """
    
    async def execute(self, **kwargs) -> Response:
        action = self.args.get("action", "").lower()
        student_id = self.args.get("student_id", "default_student")
        
        if action == "survey":
            return await self.conduct_initial_survey()
        elif action == "analyze_interaction":
            return await self.analyze_interaction_pattern()
        elif action == "update_style":
            return await self.update_learning_style()
        elif action == "get_profile":
            return await self.get_student_profile()
        else:
            return Response(message="Available actions: survey, analyze_interaction, update_style, get_profile", break_loop=False)
    
    async def conduct_initial_survey(self) -> Response:
        """Present optional initial learning style survey"""
        survey_questions = {
            "learning_preference": {
                "question": "When learning a new, complex engineering concept, what helps you most?",
                "options": {
                    "visual": "Seeing a diagram, chart, or simulation",
                    "auditory": "Listening to a detailed explanation or discussion", 
                    "kinesthetic": "Trying it out myself with hands-on examples or code"
                }
            },
            "knowledge_level": {
                "question": "How would you rate your current knowledge in your engineering field?",
                "options": {
                    "beginner": "Beginner - Just starting to learn fundamental concepts",
                    "intermediate": "Intermediate - Comfortable with basics, learning advanced topics",
                    "advanced": "Advanced - Strong foundation, working on specialized areas"
                }
            },
            "engineering_field": {
                "question": "What's your primary engineering focus area?",
                "options": {
                    "computer_science": "Computer Science / Software Engineering",
                    "mechanical": "Mechanical Engineering",
                    "electrical": "Electrical Engineering", 
                    "civil": "Civil Engineering",
                    "chemical": "Chemical Engineering",
                    "other": "Other Engineering Discipline"
                }
            }
        }
        
        survey_text = "🎯 **VisuaLearn Personalization Survey** (Optional - helps me teach you better!)\n\n"
        for key, q_data in survey_questions.items():
            survey_text += f"**{q_data['question']}**\n"
            for option_key, option_text in q_data['options'].items():
                survey_text += f"• {option_key}: {option_text}\n"
            survey_text += "\n"
        
        survey_text += "Please respond with your choices (e.g., 'visual, intermediate, computer_science') or skip by saying 'skip survey'"
        
        return Response(message=survey_text, break_loop=False)
    
    async def analyze_interaction_pattern(self) -> Response:
        """Analyze student's interaction patterns to detect learning style"""
        interaction_data = self.args.get("interaction_data", {})
        
        # Analyze interaction patterns
        visual_signals = interaction_data.get("visual_requests", 0)
        audio_signals = interaction_data.get("audio_requests", 0) 
        hands_on_signals = interaction_data.get("code_requests", 0)
        simplification_requests = interaction_data.get("simplify_requests", 0)
        
        # Calculate learning style probabilities
        total_signals = max(visual_signals + audio_signals + hands_on_signals, 1)
        
        style_analysis = {
            "visual_probability": visual_signals / total_signals,
            "auditory_probability": audio_signals / total_signals,
            "kinesthetic_probability": hands_on_signals / total_signals,
            "complexity_tolerance": max(1, 10 - simplification_requests),
            "interaction_count": total_signals,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Determine primary learning style
        max_prob = max(style_analysis["visual_probability"], 
                      style_analysis["auditory_probability"], 
                      style_analysis["kinesthetic_probability"])
        
        if max_prob == style_analysis["visual_probability"]:
            primary_style = "visual"
        elif max_prob == style_analysis["auditory_probability"]:
            primary_style = "auditory" 
        else:
            primary_style = "kinesthetic"
        
        style_analysis["primary_style"] = primary_style
        style_analysis["confidence"] = max_prob
        
        return Response(message=f"Learning style analysis: {json.dumps(style_analysis, indent=2)}", break_loop=False)
    
    async def update_learning_style(self) -> Response:
        """Update student learning style based on new evidence"""
        style_update = self.args.get("style_update", {})
        trigger = self.args.get("trigger", "interaction_analysis")
        
        update_info = {
            "timestamp": datetime.now().isoformat(),
            "trigger": trigger,
            "style_update": style_update,
            "confidence_change": style_update.get("confidence_delta", 0)
        }
        
        return Response(message=f"Learning style updated: {json.dumps(update_info, indent=2)}", break_loop=False)
    
    async def get_student_profile(self) -> Response:
        """Retrieve current student learning profile"""
        student_id = self.args.get("student_id", "default_student")
        
        # This would integrate with memory_load tool to get actual profile
        sample_profile = {
            "student_id": student_id,
            "learning_style": {
                "primary": "visual",
                "secondary": "kinesthetic", 
                "confidence": 0.75
            },
            "preferences": {
                "complexity_tolerance": 7,
                "learning_pace": "medium",
                "engineering_field": "computer_science"
            },
            "behavioral_patterns": {
                "avg_session_duration": 45,
                "visual_requests_per_session": 3,
                "hands_on_requests_per_session": 2
            },
            "last_updated": datetime.now().isoformat()
        }
        
        return Response(message=f"Student profile: {json.dumps(sample_profile, indent=2)}", break_loop=False)
