class WorkflowTool:
    def __init__(self, agent_workflow_memory: AgentWorkflowMemory):
        self.awm = agent_workflow_memory

    async def execute(self, action: str, task: str, **kwargs):
        if action == "get_workflows":
            return await self.get_workflows(task)
        elif action == "apply_workflow":
            workflow_id = kwargs.get("workflow_id")
            context = kwargs.get("context", {})
            return await self.apply_workflow(workflow_id, context)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def get_workflows(self, task: str):
        relevant_workflows = await self.awm.get_relevant_workflows(task)
        return [{"id": i, "description": w.description} for i, w in enumerate(relevant_workflows)]

    async def apply_workflow(self, workflow_id: str, context: dict):
        workflow = self.awm.workflows[int(workflow_id)]
        return self.awm.apply_workflow(workflow, context)