# import asyncio
# import re
# from bs4 import BeautifulSoup
# from playwright.async_api import (
#     async_playwright,
#     Browser as PlaywrightBrowser,
#     Page,
#     Frame,
#     BrowserContext,
# )

# from python.helpers import files


# class NoPageError(Exception):
#     pass


# class Browser:

#     load_timeout = 10000
#     interact_timeout = 3000
#     selector_name = "data-a0sel3ct0r"

#     def __init__(self, headless=True):
#         self.browser: PlaywrightBrowser = None  # type: ignore
#         self.context: BrowserContext = None  # type: ignore
#         self.page: Page = None  # type: ignore
#         self._playwright = None
#         self.headless = headless
#         self.contexts = {}
#         self.last_selector = ""
#         self.page_loaded = False
#         self.navigation_count = 0

#     async def __aenter__(self):
#         await self.start()
#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         await self.close()

#     async def start(self):
#         """Start browser session"""
#         self._playwright = await async_playwright().start()
#         if not self.browser:
#             self.browser = await self._playwright.chromium.launch(
#                 headless=self.headless, args=["--disable-http2"]
#             )
#         if not self.context:
#             self.context = await self.browser.new_context(
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.141 Safari/537.36"
#             )

#         self.page = await self.context.new_page()
#         await self.page.set_viewport_size({"width": 1200, "height": 1200})

#         # Inject the JavaScript to modify the attachShadow method
#         js_override = files.read_file("lib/browser/init_override.js")
#         await self.page.add_init_script(js_override)

#         # Setup frame handling
#         async def inject_script_into_frames(frame):
#             try:
#                 await self.wait_tick()
#                 if not frame.is_detached():
#                     async with asyncio.timeout(0.25):
#                         await frame.evaluate(js_override)
#                         print(f"Injected script into frame: {frame.url[:100]}")
#             except Exception as e:
#                 # Frame might have been detached during injection, which is normal
#                 print(
#                     f"Could not inject into frame (possibly detached): {str(e)[:100]}"
#                 )

#         self.page.on(
#             "frameattached",
#             lambda frame: asyncio.ensure_future(inject_script_into_frames(frame)),
#         )

#         # Handle page navigation events
#         async def handle_navigation(frame):
#             if frame == self.page.main_frame:
#                 print(f"Page navigated to: {frame.url[:100]}")
#                 self.page_loaded = False
#                 self.navigation_count += 1

#         async def handle_load(dummy):
#             print("Page load completed")
#             self.page_loaded = True

#         async def handle_request(request):
#             if (
#                 request.is_navigation_request()
#                 and request.frame == self.page.main_frame
#             ):
#                 print(f"Navigation started to: {request.url[:100]}")
#                 self.page_loaded = False
#                 self.navigation_count += 1

#         self.page.on("request", handle_request)
#         self.page.on("framenavigated", handle_navigation)
#         self.page.on("load", handle_load)

#     async def close(self):
#         """Close browser session"""
#         if self.browser:
#             await self.browser.close()
#         if self._playwright:
#             await self._playwright.stop()

#     async def open(self, url: str):
#         """Open a URL in the browser"""
#         self.last_selector = ""
#         self.contexts = {}
#         if self.page:
#             await self.page.close()
#         await self.start()
#         try:
#             await self.page.goto(
#                 url, wait_until="networkidle", timeout=Browser.load_timeout
#             )
#         except TimeoutError as e:
#             pass
#         except Exception as e:
#             print(f"Error opening page: {e}")
#             raise e
#         await self.wait_tick()

#     async def get_full_dom(self) -> str:
#         """Get full DOM with unique selectors"""
#         await self._check_page()
#         js_code = files.read_file("lib/browser/extract_dom.js")

#         # Get all frames
#         self.contexts = {}
#         frame_contents = {}

#         # Extract content from each frame
#         i = -1
#         for frame in self.page.frames:
#             try:
#                 if frame.url:  # and frame != self.page.main_frame:
#                     i += 1
#                     frame_mark = self._num_to_alpha(i)

#                     # Check if frame is still valid
#                     await self.wait_tick()
#                     if not frame.is_detached():
#                         try:
#                             # short timeout to identify and skip unresponsive frames
#                             async with asyncio.timeout(0.25):
#                                 await frame.evaluate("window.location.href")
#                         except TimeoutError as e:
#                             print(f"Skipping unresponsive frame: {frame.url}")
#                             continue

#                         await frame.wait_for_load_state(
#                             "domcontentloaded", timeout=1000
#                         )

#                         async with asyncio.timeout(1):
#                             content = await frame.evaluate(
#                                 js_code, [frame_mark, self.selector_name]
#                             )
#                             self.contexts[frame_mark] = frame
#                             frame_contents[frame.url] = content
#                     else:
#                         print(f"Warning: Frame was detached: {frame.url}")
#             except Exception as e:
#                 print(f"Error extracting from frame {frame.url}: {e}")

#         # # Get main frame content
#         # main_mark = self._num_to_alpha(0)
#         # main_content = ""
#         # try:
#         #     async with asyncio.timeout(1):
#         #         main_content = await self.page.evaluate(js_code, [main_mark, self.selector_name])
#         #         self.contexts[main_mark] = self.page
#         # except Exception as e:
#         #     print(f"Error when extracting from main frame: {e}")

#         # Replace iframe placeholders with actual content
#         # for url, content in frame_contents.items():
#         #     placeholder = f'<iframe src="{url}"'
#         #     main_content = main_content.replace(placeholder, f'{placeholder}>\n<!-- IFrame Content Start -->\n{content}\n<!-- IFrame Content End -->\n</iframe')

#         # return main_content + "".join(frame_contents.values())
#         return "".join(frame_contents.values())

#     def strip_html_dom(self, html_content: str) -> str:
#         """Clean and strip HTML content"""
#         if not html_content:
#             return ""

#         soup = BeautifulSoup(html_content, "html.parser")

#         for tag in soup.find_all(
#             ["br", "hr", "style", "script", "noscript", "meta", "link", "svg"]
#         ):
#             tag.decompose()

#         for tag in soup.find_all(True):
#             if tag.attrs and "invisible" in tag.attrs:
#                 tag.decompose()

#         for tag in soup.find_all(True):
#             allowed_attrs = [
#                 self.selector_name,
#                 "aria-label",
#                 "placeholder",
#                 "name",
#                 "value",
#                 "type",
#             ]
#             attrs = {
#                 "selector" if key == self.selector_name else key: tag.attrs[key]
#                 for key in allowed_attrs
#                 if key in tag.attrs and tag.attrs[key]
#             }
#             tag.attrs = attrs

#         def remove_empty(tag_name: str) -> None:
#             for tag in soup.find_all(tag_name):
#                 if not tag.attrs:
#                     tag.unwrap()

#         remove_empty("span")
#         remove_empty("p")
#         remove_empty("strong")

#         return soup.prettify(formatter="minimal")

#     def process_html_with_selectors(self, html_content: str) -> str:
#         """Process HTML content and add selectors to interactive elements"""
#         if not html_content:
#             return ""

#         html_content = re.sub(r"\s+", " ", html_content)
#         soup = BeautifulSoup(html_content, "html.parser")

#         structural_tags = [
#             "html",
#             "head",
#             "body",
#             "div",
#             "span",
#             "section",
#             "main",
#             "article",
#             "header",
#             "footer",
#             "nav",
#             "ul",
#             "ol",
#             "li",
#             "tr",
#             "td",
#             "th",
#         ]
#         for tag in structural_tags:
#             for element in soup.find_all(tag):
#                 element.unwrap()

#         out = str(soup).strip()
#         out = re.sub(r">\s*<", "><", out)
#         out = re.sub(r'aria-label="', 'label="', out)

#         # out = re.sub(r'selector="(\d+[a-zA-Z]+)"', r'selector=\1', out)
#         return out

#     async def get_clean_dom(self) -> str:
#         """Get clean DOM with selectors"""
#         full_dom = await self.get_full_dom()
#         clean_dom = self.strip_html_dom(full_dom)
#         return self.process_html_with_selectors(clean_dom)

#     async def click(self, selector: str):
#         await self._check_page()
#         ctx, selector = self._parse_selector(selector)
#         self.last_selector = selector
#         # js_code = files.read_file("lib/browser/click.js")
#         # result = await self.page.evaluate(js_code, [selector])
#         # if not result:
#         result = await ctx.hover(selector, force=True, timeout=Browser.interact_timeout)
#         await self.wait_tick()
#         result = await ctx.click(selector, force=True, timeout=Browser.interact_timeout)
#         await self.wait_tick()

#         # await self.page.wait_for_load_state("networkidle")
#         return result

#     async def press(self, key: str):
#         await self._check_page()
#         if self.last_selector:
#             await self.page.press(
#                 self.last_selector, key, timeout=Browser.interact_timeout
#             )
#         else:
#             await self.page.keyboard.press(key)

#     async def fill(self, selector: str, text: str):
#         await self._check_page()
#         ctx, selector = self._parse_selector(selector)
#         self.last_selector = selector
#         try:
#             await self.click(selector)
#         except Exception as e:
#             pass
#         await ctx.fill(selector, text, force=True, timeout=Browser.interact_timeout)
#         await self.wait_tick()

#     async def execute(self, js_code: str):
#         await self._check_page()
#         result = await self.page.evaluate(js_code)
#         return result

#     async def screenshot(self, path: str, full_page=False):
#         await self._check_page()
#         await self.page.screenshot(path=path, full_page=full_page)

#     def _parse_selector(self, selector: str) -> tuple[Page | Frame, str]:
#         try:
#             ctx = self.page
#             # Check if selector is our UID, return
#             if re.match(r"^\d+[a-zA-Z]+$", selector):
#                 alpha_part = "".join(filter(str.isalpha, selector))
#                 ctx = self.contexts[alpha_part]
#                 selector = f"[{self.selector_name}='{selector}']"
#             return (ctx, selector)
#         except Exception as e:
#             raise Exception(f"Error evaluating selector: {selector}")

#     async def _check_page(self):
#         for _ in range(2):
#             try:
#                 await self.wait_tick()
#                 self.page = self.context.pages[0]
#                 if not self.page:
#                     raise NoPageError(
#                         "No page is open in the browser. Please open a URL first."
#                     )
#                 # await self.page.wait_for_load_state("networkidle",)
#                 async with asyncio.timeout(self.load_timeout / 1000):
#                     if not self.page_loaded:
#                         while not self.page_loaded:
#                             await asyncio.sleep(0.1)
#                         await self.wait_tick()
#                 return
#             except TimeoutError as e:
#                 self.page_loaded = True
#                 return
#             except NoPageError as e:
#                 raise e
#             except Exception as e:
#                 print(f"Error checking page: {e}")

#     def _num_to_alpha(self, num: int) -> str:
#         if num < 0:
#             return ""

#         result = ""
#         while num >= 0:
#             result = chr(num % 26 + 97) + result
#             num = num // 26 - 1

#         return result

#     async def wait_tick(self):
#         if self.page:
#             await self.page.evaluate("window.location.href")

#     async def wait(self, seconds: float = 1.0):
#         await asyncio.sleep(seconds)
#         await self.wait_tick()

#     async def wait_for_action(self):
#         nav_count = self.navigation_count
#         for _ in range(5):
#             await self._check_page()
#             if nav_count != self.navigation_count:
#                 print("Navigation detected")
#                 await asyncio.sleep(1)
#                 return
#             await asyncio.sleep(0.1)
