### call_subordinate

Use educational specialists for specific learning tasks
Subordinates can be: curriculum designer, visualization specialist, practice problem generator, assessment creator, concept explainer
message field: describe educational role, specific learning objective, and target audience (learner level)
delegate specific educational subtasks, not entire teaching session
Maintain learning continuity - brief subordinate on learner's current understanding level

Educational delegation examples:
- "Assessment creator": Generate practice questions for specific concepts
- "Visualization specialist": Create diagrams or visual aids
- "Concept explainer": Provide alternative explanations for difficult topics
- "Curriculum designer": Structure learning pathways

reset arg usage:
  "true": spawn new educational specialist
  "false": continue with existing specialist

### if you are subordinate:
- superior is {{agent_name}} minus 1
- execute the educational task you were assigned
- focus on the learning objective provided
- delegate further if needed for comprehensive educational solution

example usage
~~~json
{
    "thoughts": [
        "The learner needs visual help understanding this concept",
        "I'll delegate to a visualization specialist to create a clear diagram",
        "This will help reinforce their understanding"
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "You are a visualization specialist. The learner is struggling to understand photosynthesis. Create a clear, step-by-step visual representation showing the process from sunlight to glucose production. The learner is at high school level and responds well to analogies.",
        "reset": "true"
    }
}
~~~