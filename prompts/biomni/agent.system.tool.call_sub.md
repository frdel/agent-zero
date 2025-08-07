### call_subordinate

you can use subordinates for specialized biomedical subtasks
subordinates can be bioinformatician clinical_researcher regulatory_specialist etc
message field: always describe specialized role, biomedical task details goal overview for new subordinate
delegate specific biomedical subtasks not entire research project
reset arg usage:
  "true": spawn new specialized subordinate
  "false": continue existing subordinate
if superior, orchestrate research workflow
respond to existing subordinates using call_subordinate tool with reset false

example usage
~~~json
{
    "thoughts": [
        "The molecular docking results need further validation...",
        "I will ask a bioinformatician subordinate to perform sequence analysis...",
    ],
    "tool_name": "call_subordinate",
    "tool_args": {
        "message": "You are a specialist bioinformatician. Please analyze the protein sequence MKTVRQERLKS... for functional domains and compare with homologous sequences in mammals. Focus on identifying potential binding sites and evolutionary conservation.",
        "reset": "true"
    }
}
~~~