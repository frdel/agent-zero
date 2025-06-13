# import asyncio
# from dataclasses import dataclass
# import time
# from python.helpers.tool import Tool, Response
# from python.helpers import files, rfc_exchange
# from python.helpers.print_style import PrintStyle
# from python.helpers.browser import Browser as BrowserManager
# import uuid


# @dataclass
# class State:
#     browser: BrowserManager


# class Browser(Tool):

#     async def execute(self, **kwargs):
#         raise NotImplementedError

#     def get_log_object(self):
#         return self.agent.context.log.log(
#             type="browser",
#             heading=f"{self.agent.agent_name}: Using tool '{self.name}'",
#             content="",
#             kvps=self.args,
#         )

#     # async def after_execution(self, response, **kwargs):
#     #     await self.agent.hist_add_tool_result(self.name, response.message)

#     async def save_screenshot(self):
#         await self.prepare_state()
#         path = files.get_abs_path("tmp/browser", f"{uuid.uuid4()}.png")
#         await self.state.browser.screenshot(path, True)
#         return "img://" + path

#     async def prepare_state(self, reset=False):
#         self.state = self.agent.get_data("_browser_state")
#         if not self.state or reset:
#             self.state = State(browser=BrowserManager())
#         self.agent.set_data("_browser_state", self.state)

#     def update_progress(self, text):
#         progress = f"Browser: {text}"
#         self.log.update(progress=text)
#         self.agent.context.log.set_progress(progress)

#     def cleanup_history(self):
#         def cleanup_message(msg):
#             if not msg.ai and isinstance(msg.content, dict) and "tool_name" in msg.content and str(msg.content["tool_name"]).startswith("browser_"):
#                 if not msg.summary:
#                     msg.summary = "browser content removed to save space"

#         for msg in self.agent.history.current.messages:
#             cleanup_message(msg)
        
#         for prev in self.agent.history.topics:
#             if not prev.summary:
#                 for msg in prev.messages:
#                     cleanup_message(msg)
