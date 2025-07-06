"""
UI Modification Tool for Agent Zero
Uses AG-UI to directly modify the Agent Zero web interface
"""

import json
from typing import Dict, Any, Optional
from python.helpers.tool import Tool, Response


class UIModificationTool(Tool):
    """
    A tool that uses AG-UI to directly modify Agent Zero's web interface.
    Automatically applies changes to colors, styles, layout, and other UI elements.
    """

    async def execute(self, **kwargs) -> Response:
        """Execute UI modification using AG-UI"""
        try:
            # Parse the request dynamically
            request_text = str(kwargs.get('request', ''))
            css_code = self.args.get("css", "")
            color = self.args.get("color", "")
            element = self.args.get("element", "")

            # Determine what UI change is being requested
            if css_code or "gradient" in request_text.lower() or "background" in request_text.lower():
                return await self._apply_ui_change(css_code, request_text)
            else:
                # Parse natural language request
                return await self._parse_and_apply_ui_request(request_text)

        except Exception as e:
            return Response(
                message=f"UI modification failed: {str(e)}",
                break_loop=False
            )

    async def _apply_ui_change(self, css_code: str, request_text: str) -> Response:
        """Apply UI changes using AG-UI to directly modify Agent Zero interface"""

        # If no CSS provided, generate it from the request
        if not css_code:
            css_code = self._generate_css_from_request(request_text)

        # Create AG-UI component that executes the CSS change immediately
        ag_ui_spec = {
            "type": "container",
            "id": f"ui-mod-{int(__import__('time').time() * 1000)}",
            "properties": {
                "auto_execute": True,
                "css_injection": css_code
            },
            "events": {
                "init": f"""
                // Apply CSS to Agent Zero interface immediately
                const style = document.createElement('style');
                style.textContent = `{css_code.replace('`', '\\`')}`;
                document.head.appendChild(style);
                console.log('✅ Agent Zero UI modified');
                """
            }
        }

        # Log as AG-UI component
        self.agent.context.log.log(
            type="ag_ui",
            heading="Agent Zero UI Modified",
            content=json.dumps(ag_ui_spec)
        )

        return Response(
            message="✅ Agent Zero interface updated.",
            break_loop=False
        )

    def _generate_css_from_request(self, request_text: str) -> str:
        """Generate CSS based on natural language request"""
        request_lower = request_text.lower()

        if "gradient" in request_lower and ("pink" in request_lower or "purple" in request_lower):
            return "body { background: linear-gradient(to right, #800080, #FFC0CB) !important; }"
        elif "blue" in request_lower and "background" in request_lower:
            return "body { background-color: #1976d2 !important; }"
        elif "dark" in request_lower and ("theme" in request_lower or "background" in request_lower):
            return "body { background-color: #121212 !important; color: #ffffff !important; }"
        elif "light" in request_lower and ("theme" in request_lower or "background" in request_lower):
            return "body { background-color: #ffffff !important; color: #000000 !important; }"
        else:
            # Default to a subtle background change
            return "body { background-color: #f5f5f5 !important; }"

    async def _parse_and_apply_ui_request(self, request_text: str) -> Response:
        """Parse natural language UI request and apply changes"""
        css_code = self._generate_css_from_request(request_text)
        return await self._apply_ui_change(css_code, request_text)



