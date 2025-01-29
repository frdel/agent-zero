from python.helpers.tool import Tool, Response
from python.helpers.scheduler import scheduler


class ScheduledTaskRemoveTool(Tool):

    async def execute(self, **kwargs):
        # TODO: implement logic
        return Response(message=self.args["text"], break_loop=True)
