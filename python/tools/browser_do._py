# import asyncio
# from python.helpers.tool import Tool, Response
# from python.tools.browser import Browser
# from python.helpers.browser import NoPageError
# import asyncio


# class BrowserDo(Browser):

#     async def execute(self, fill=[], press=[], click=[], execute="", **kwargs):
#         await self.prepare_state()
#         result = ""
#         try:
#             if fill:
#                 self.update_progress("Filling fields...")
#                 for f in fill:
#                     await self.state.browser.fill(f["selector"], f["text"])
#                     await self.state.browser.wait(0.5)
#             if press:
#                 self.update_progress("Pressing keys...")
#                 if fill:
#                     await self.state.browser.wait(1)
#                 for p in press:
#                     await self.state.browser.press(p)
#                     await self.state.browser.wait(0.5)
#             if click:
#                 self.update_progress("Clicking...")
#                 if fill:
#                     await self.state.browser.wait(1)
#                 for c in click:
#                     await self.state.browser.click(c)
#                     await self.state.browser.wait(0.5)
#             if execute:
#                 if fill or press or click:
#                     await self.state.browser.wait(1)
#                 self.update_progress("Executing...")
#                 result = await self.state.browser.execute(execute)
#                 self.log.update(result=result)

#             self.update_progress("Retrieving...")
#             await self.state.browser.wait_for_action()
#             dom = await self.state.browser.get_clean_dom()
#             if result:
#                 response = f"Result:\n{result}\n\nDOM:\n{dom}"
#             else:
#                 response = dom
#             self.update_progress("Taking screenshot...")
#             screenshot = await self.save_screenshot()
#             self.log.update(screenshot=screenshot)
#         except Exception as e:
#             response = str(e)
#             self.log.update(error=response)
            
#             try:
#                 screenshot = await self.save_screenshot()
#                 dom = await self.state.browser.get_clean_dom()
#                 response = f"Error:\n{response}\n\nDOM:\n{dom}"
#                 self.log.update(screenshot=screenshot)
#             except Exception:
#                 pass

#         self.cleanup_history()
#         self.update_progress("Done")
#         return Response(message=response, break_loop=False)
