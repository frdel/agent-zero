from python.helpers.tool import Tool, Response

class WorkflowTool(Tool):
    def __init__(self, agent, name, args, message):
        super().__init__(agent, name, args, message)
        self.awm = agent.config.awm if agent and agent.config else None

    def response(self, message):
        return Response(message=message, break_loop=False)

    async def execute(self, task: str = None, task_description: str = None, action: str = None, workflow_id: str = None, context: dict = None):
        # Use task_description if task is not provided
        task = task or task_description

        if not self.awm:
            return self.response("AWM not initialized")

        if action == "induce":
            await self.awm.induce_workflow([task])
            await self.awm.save_workflows()
            return self.response(f"Induced workflow for task: {task}")
        elif action == "update":
            await self.awm.update_workflows(task, "")
            await self.awm.save_workflows()
            return self.response(f"Updated workflows based on task: {task}")
        elif action == "get_workflows":
            if task:
                relevant_workflows = await self.awm.get_relevant_workflows(task)
                if not relevant_workflows:
                    await self.awm.induce_workflow([task])
                    await self.awm.save_workflows()
                    return self.response(f"No existing relevant workflows found for '{task}'. Induced new workflow.")
                workflow_descriptions = "\n".join([f"- {w.description}" for w in relevant_workflows])
                return self.response(f"Relevant workflows for '{task}':\n{workflow_descriptions}")
            else:
                all_workflows = await self.awm.get_all_workflows()
                workflow_descriptions = "\n".join([f"- {w.description}" for w in all_workflows])
                return self.response(f"All available workflows:\n{workflow_descriptions}")
        elif action == "apply_workflow":
            if workflow_id is None:
                return self.response("Workflow ID is required for apply_workflow action")
            if context is None:
                context = {}
            applied_workflow = await self.awm.apply_workflow(int(workflow_id), context)
            return self.response(f"Applied workflow: {applied_workflow}")
        else:
            return self.response(f"Unknown action: {action}")