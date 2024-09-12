from typing import List

class WorkflowStep:
    def __init__(self, observation: str, reasoning: str, action: str):
        self.observation = observation
        self.reasoning = reasoning
        self.action = action

class Workflow:
    def __init__(self, description: str, steps: List[WorkflowStep]):
        self.description = description
        self.steps = steps