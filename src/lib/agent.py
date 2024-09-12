async def process_tools(self, agent_response):
    results = []
    for tool_request in agent_response.tool_requests:
        tool_name = tool_request.tool
        tool_args = tool_request.arguments
        
        tool = self.get_tool(tool_name)
        if tool is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        if isinstance(tool, WorkflowTool):
            task = tool_args.get("task", "")
            action = tool_args.get("action", "")
            response = await tool.execute(action=action, task=task, **tool_args)
        else:
            response = await tool.execute(**tool_args)
        
        results.append(response)
    
    return results