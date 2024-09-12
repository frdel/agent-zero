import json
from typing import List, Dict, Any, Optional
import asyncio
from openai import APIError, AsyncOpenAI, AuthenticationError, RateLimitError
import aiofiles
import backoff
from .workflow import Workflow, WorkflowStep
from .embedding_memory import EmbeddingMemory
import os

class AgentWorkflowMemory:
    def __init__(self, api_key: str, is_online_mode: bool = True, embedding_memory: Optional[EmbeddingMemory] = None):
        self.workflows: List[Workflow] = []
        self.openai = AsyncOpenAI(api_key=api_key)
        self.max_workflows: int = 100
        self.workflow_usage_history: List[str] = []
        self.is_online_mode = is_online_mode
        self.embedding_memory = embedding_memory

    async def induce_workflow(self, experiences: List[str]) -> None:
        try:
            if self.is_online_mode:
                await self.online_workflow_induction(experiences)
            else:
                await self.offline_workflow_induction(experiences)
            
            print(f"Number of workflows after induction: {len(self.workflows)}")
            for workflow in self.workflows:
                print(f"Workflow description: {workflow.description}")
                print(f"Number of steps: {len(workflow.steps)}")
        except AuthenticationError as auth_error:
            print('OpenAI API Authentication Error:', str(auth_error))
            print('Please check your API key and ensure it is valid.')
            await self.use_fallback_workflow_induction(experiences)
        except RateLimitError as rate_error:
            print('OpenAI API Rate Limit Error:', str(rate_error))
            await self.retry_with_backoff(lambda: self.induce_workflow(experiences))
        except Exception as error:
            print('Error inducing workflow:', str(error))
            await self.use_fallback_workflow_induction(experiences)

    async def online_workflow_induction(self, experiences: List[str]) -> None:
        prompt = f"""Given the following web navigation tasks, extract common workflows:

        Tasks:
        {chr(10).join(experiences)}

        For each workflow, provide:
        1. A brief description
        2. A list of steps, where each step includes:
           - Observation
           - Reasoning
           - Action

        Format the output as follows:

        ## Workflow Name
        Description: Brief description of the workflow
        Steps:
        1. Observation: What the agent observes
           Reasoning: Why the agent takes this action
           Action: The action taken

        2. Observation: ...
           Reasoning: ...
           Action: ...

        ## Next Workflow Name
        ..."""

        response = await self.openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        workflows_text = response.choices[0].message.content
        if workflows_text:
            self.parse_and_store_workflows(workflows_text)
        else:
            raise Exception('No workflow text generated')

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def retry_with_backoff(self, fn):
        await fn()

    async def use_fallback_workflow_induction(self, experiences: List[str]) -> None:
        fallback_workflows = [
            Workflow(
                description=f"Fallback workflow for: {exp[:50]}...",
                steps=[WorkflowStep(
                    observation='Fallback observation',
                    reasoning='Using fallback due to API error',
                    action=exp
                )]
            ) for exp in experiences
        ]
        self.workflows.extend(fallback_workflows)

    async def offline_workflow_induction(self, experiences: List[str]) -> None:
        common_actions = ['click', 'type', 'select', 'submit']
        
        for exp in experiences:
            steps = []
            for action in exp.split('\n'):
                action_type = next((a for a in common_actions if a in action.lower()), 'perform')
                steps.append(WorkflowStep(
                    observation=f"Observed need to {action_type}",
                    reasoning="Action required based on task description",
                    action=action.strip()
                ))
            
            self.workflows.append(Workflow(
                description=f"Workflow induced offline: {exp[:50]}...",
                steps=steps
            ))

    def parse_and_store_workflows(self, workflows_text: str) -> None:
        workflows = [w.strip() for w in workflows_text.split('## ') if w.strip()]
        
        for workflow in workflows:
            lines = workflow.split('\n')
            name = lines[0].strip()
            description = next((line.replace('Description:', '').strip() for line in lines if line.startswith('Description:')), '')
            
            steps = []
            current_step = {}
            for line in lines[lines.index('Steps:') + 1:]:
                if line.startswith('Observation:'):
                    if current_step:
                        steps.append(WorkflowStep(**current_step))
                        current_step = {}
                    current_step['observation'] = line.replace('Observation:', '').strip()
                elif line.startswith('Reasoning:'):
                    current_step['reasoning'] = line.replace('Reasoning:', '').strip()
                elif line.startswith('Action:'):
                    current_step['action'] = line.replace('Action:', '').strip()
            
            if current_step:
                steps.append(WorkflowStep(**current_step))

            self.workflows.append(Workflow(description, steps))

    async def get_relevant_workflows(self, task: str) -> List[Workflow]:
        if self.is_online_mode and self.embedding_memory:
            context = await self.embedding_memory.get_relevant_context(task)
            return await self.select_workflows_with_context(task, context)
        else:
            return await self.select_workflows(task)

    async def select_workflows(self, task: str) -> List[Workflow]:
        # Simple keyword matching for offline mode
        keywords = task.lower().split()
        return [
            workflow for workflow in self.workflows
            if any(keyword in workflow.description.lower() for keyword in keywords)
        ]

    async def select_workflows_with_context(self, task: str, context: List[Any]) -> List[Workflow]:
        if not self.workflows:
            print("No workflows available for selection.")
            return []

        prompt = f"""Given the task: "{task}" and the following context:

        {json.dumps(context, indent=2)}

        Select the most relevant workflows from the following list:

        {json.dumps([{"index": i, "description": w.description} for i, w in enumerate(self.workflows)], indent=2)}

        Return the indices of the selected workflows as a JSON list."""

        response = await self.openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            content = response.choices[0].message.content.strip()
            # Check if the content is wrapped in backticks and remove them if present
            if content.startswith('```') and content.endswith('```'):
                content = content[3:-3].strip()
            selected_indices = json.loads(content)
            return [self.workflows[i] for i in selected_indices if 0 <= i < len(self.workflows)]
        except json.JSONDecodeError as e:
            print(f"Error decoding workflow selection response: {e}")
            print(f"Raw response: {response.choices[0].message.content}")
            # Fallback to simple keyword matching
            return await self.select_workflows(task)
        except Exception as e:
            print(f"Unexpected error in select_workflows_with_context: {e}")
            # Fallback to simple keyword matching
            return await self.select_workflows(task)

    async def generalize_workflow(self, workflow: Workflow):
        generalized = await self._apply_generalization_methods(workflow)
        await self.store_generalized_workflow(generalized)

    async def _apply_generalization_methods(self, workflow: Workflow) -> Workflow:
        workflow = await self._cross_task_generalization(workflow)
        workflow = await self._cross_website_generalization(workflow)
        workflow = await self._cross_domain_generalization(workflow)
        return workflow

    async def _cross_task_generalization(self, workflow: Workflow) -> Workflow:
        prompt = f"""Generalize the following workflow to make it applicable across different tasks:

        {json.dumps(workflow.__dict__, indent=2)}

        Provide the generalized workflow in the same JSON format."""

        response = await self.openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            generalized_data = json.loads(response.choices[0].message.content)
            return Workflow(**generalized_data)
        except json.JSONDecodeError:
            print("Error decoding cross-task generalization response")
            return workflow

    async def _cross_website_generalization(self, workflow: Workflow) -> Workflow:
        prompt = f"""Generalize the following workflow to make it applicable across different websites:

        {json.dumps(workflow.__dict__, indent=2)}

        Provide the generalized workflow in the same JSON format."""

        response = await self.openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            generalized_data = json.loads(response.choices[0].message.content)
            return Workflow(**generalized_data)
        except json.JSONDecodeError:
            print("Error decoding cross-website generalization response")
            return workflow

    async def _cross_domain_generalization(self, workflow: Workflow) -> Workflow:
        prompt = f"""Generalize the following workflow to make it applicable across different domains:

        {json.dumps(workflow.__dict__, indent=2)}

        Provide the generalized workflow in the same JSON format."""

        response = await self.openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            generalized_data = json.loads(response.choices[0].message.content)
            return Workflow(**generalized_data)
        except json.JSONDecodeError:
            print("Error decoding cross-domain generalization response")
            return workflow

    async def store_generalized_workflow(self, workflow: Workflow):
        if self.embedding_memory:
            await self.embedding_memory.store(workflow.description, workflow)
        if len(self.workflows) >= self.max_workflows:
            self.workflows.pop(0)  # Remove the oldest workflow
        self.workflows.append(workflow)

    async def evaluate_workflow(self, workflow: Workflow) -> dict:
        coverage = await self._calculate_coverage(workflow)
        function_overlap = await self._calculate_function_overlap(workflow)
        utility_rate = await self._calculate_utility_rate(workflow)

        return {
            "coverage": coverage,
            "function_overlap": function_overlap,
            "utility_rate": utility_rate,
        }

    async def _calculate_coverage(self, workflow: Workflow) -> float:
        # Calculate the percentage of common web tasks covered by the workflow
        common_tasks = ["navigation", "form filling", "data extraction", "interaction"]
        covered_tasks = sum(1 for task in common_tasks if any(task.lower() in step.action.lower() for step in workflow.steps))
        return covered_tasks / len(common_tasks)

    async def _calculate_function_overlap(self, workflow: Workflow) -> float:
        # Calculate the overlap of functionality with other workflows
        overlapping_steps = sum(1 for step in workflow.steps if any(step.action in other_workflow.steps for other_workflow in self.workflows if other_workflow != workflow))
        return overlapping_steps / len(workflow.steps) if workflow.steps else 0

    async def _calculate_utility_rate(self, workflow: Workflow) -> float:
        # Calculate the utility rate based on usage history
        workflow_uses = self.workflow_usage_history.count(workflow.description)
        total_uses = len(self.workflow_usage_history)
        return workflow_uses / total_uses if total_uses > 0 else 0

    async def update_workflows(self, task: str, solution: str) -> None:
        experience = f"{task}\n{solution}"
        await self.induce_workflow([experience])
        self.prune_workflows()
        await self.adapt_workflows(experience)

    async def adapt_workflows(self, experience: str) -> None:
        relevant_workflows = await self.get_relevant_workflows(experience)
        for workflow in relevant_workflows:
            self.update_workflow_steps(workflow, experience)
            self.update_workflow_variables(workflow, experience)

    def update_workflow_steps(self, workflow: Workflow, experience: str) -> None:
        experience_steps = experience.split('\n')
        for step in experience_steps:
            if not any(s.action == step for s in workflow.steps):
                workflow.steps.append(WorkflowStep(
                    observation='New step from experience',
                    reasoning='Added based on new experience',
                    action=step
                ))

    def update_workflow_variables(self, workflow: Workflow, experience: str) -> None:
        # Do nothing to preserve the original workflow
        pass

    def prune_workflows(self) -> None:
        if len(self.workflows) > self.max_workflows:
            sorted_workflows = sorted(self.workflows, 
                key=lambda w: self.workflow_usage_history.count(w.description), 
                reverse=True)
            self.workflows = sorted_workflows[:self.max_workflows]

    def track_workflow_usage(self, workflow_id: str) -> None:
        self.workflow_usage_history.append(workflow_id)
        if len(self.workflow_usage_history) > 100:
            self.workflow_usage_history = self.workflow_usage_history[-100:]

    def apply_workflow(self, workflow: Workflow, context: Dict[str, Any]) -> List[str]:
        # Return the original steps without any variable replacement
        return [step.action for step in workflow.steps]

    def apply_step(self, step: WorkflowStep, context: Dict[str, Any]) -> str:
        # Return the original action without any variable replacement
        return step.action

    async def save_workflows(self) -> None:
        try:
            workflows_data = [
                {
                    "description": w.description,
                    "steps": [
                        {
                            "observation": s.observation,
                            "reasoning": s.reasoning,
                            "action": s.action
                        } for s in w.steps
                    ]
                } for w in self.workflows
            ]
            async with aiofiles.open('workflows.json', 'w') as f:
                await f.write(json.dumps(workflows_data, indent=2))
        except Exception as error:
            print('Error saving workflows:', error)

    async def load_workflows(self) -> None:
        try:
            async with aiofiles.open('workflows.json', 'r') as f:
                data = await f.read()
            workflows_data = json.loads(data)
            self.workflows = [
                Workflow(
                    description=w["description"],
                    steps=[
                        WorkflowStep(
                            observation=s["observation"],
                            reasoning=s["reasoning"],
                            action=s["action"]
                        ) for s in w["steps"]
                    ]
                ) for w in workflows_data
            ]
        except FileNotFoundError:
            print('No existing workflows file found. Starting with an empty workflow list.')
            self.workflows = []
        except json.JSONDecodeError:
            print('Error decoding workflows file. Starting with an empty workflow list.')
            self.workflows = []
        except Exception as error:
            print('Error loading workflows:', error)
            self.workflows = []

    async def get_all_workflows(self) -> List[Workflow]:
        return self.workflows

    async def apply_workflow(self, workflow_id: int, context: dict) -> str:
        if workflow_id < 0 or workflow_id >= len(self.workflows):
            return f"Invalid workflow ID: {workflow_id}"
        workflow = self.workflows[workflow_id]
        applied_steps = [self.apply_step(step, context) for step in workflow.steps]
        return "\n".join(applied_steps)

    def apply_step(self, step: WorkflowStep, context: dict) -> str:
        # Return the original action without any variable replacement
        return step.action

async def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable")
    
    agent_memory = AgentWorkflowMemory(api_key)
    
    # Induce a workflow
    await agent_memory.induce_workflow(["Navigate to website", "Click login button", "Enter username", "Enter password", "Click submit"])
    
    # Get relevant workflows
    relevant_workflows = await agent_memory.get_relevant_workflows("Login to a website")
    
    # Apply a workflow
    if relevant_workflows:
        actions = agent_memory.apply_workflow(relevant_workflows[0], {"username": "user123", "password": "pass123"})
        print("Actions to take:", actions)
    
    # Save workflows
    await agent_memory.save_workflows()
    
    # Load workflows
    await agent_memory.load_workflows()
    
    # Analyze workflow quality
    quality_metrics = await agent_memory.evaluate_workflow(relevant_workflows[0])
    print("Workflow quality metrics:", quality_metrics)

if __name__ == "__main__":
    asyncio.run(main())