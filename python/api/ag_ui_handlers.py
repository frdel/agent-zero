from python.helpers.api import ApiHandler
from flask import Request, Response
from python.helpers import errors
import json

from python.tools.ag_ui_tool import AGUITool

class AGUIRender(ApiHandler):
    """
    Handles rendering of AG-UI components.
    """
    
    @classmethod
    def requires_auth(cls) -> bool:
        return True
    
    @classmethod 
    def requires_csrf(cls) -> bool:
        return True
    
    async def process(self, request: Request) -> Response:
        try:
            data = request.json or {}
            ag_ui_spec = data.get("ag_ui_spec")
            
            if not ag_ui_spec:
                return Response(
                    json.dumps({"status": "error", "message": "AG-UI specification not provided."}),
                    status=400,
                    mimetype='application/json'
                )

            # Create a mock agent context for the tool
            # Note: In real usage, this would be called with an actual agent instance
            class MockAgent:
                def __init__(self):
                    self.context = MockContext()
            
            class MockContext:
                def __init__(self):
                    self.log = MockLog()
            
            class MockLog:
                def log(self, **kwargs):
                    pass
            
            # Create tool instance with mock agent
            mock_agent = MockAgent()
            tool = AGUITool(
                agent=mock_agent,
                name="ag_ui_tool", 
                method=None,
                args={"ag_ui_spec": ag_ui_spec},
                message=""
            )
            
            response = await tool.execute()
            
            if hasattr(response, 'message') and 'Successfully generated' in response.message:
                # Extract UI components from the logged data
                # For now, generate a simple success response
                return Response(
                    json.dumps({"status": "success", "message": "AG-UI component rendered"}),
                    status=200,
                    mimetype='application/json'
                )
            else:
                return Response(
                    json.dumps({"status": "error", "message": getattr(response, 'message', 'Unknown error')}),
                    status=400,
                    mimetype='application/json'
                )
                
        except Exception as e:
            return Response(
                json.dumps({"status": "error", "message": f"Server error: {str(e)}"}),
                status=500,
                mimetype='application/json'
            )

class AGUIStateSet(ApiHandler):
    """
    Handles receiving AG-UI component state updates from the client.
    """
    
    @classmethod
    def requires_auth(cls) -> bool:
        return True
    
    @classmethod 
    def requires_csrf(cls) -> bool:
        return True
    
    async def process(self, request: Request) -> Response:
        try:
            data = request.json or {}
            component_id = data.get("component_id")
            state = data.get("state")

            if not component_id or state is None:
                return Response(
                    json.dumps({"status": "error", "message": "Component ID and state are required."}),
                    status=400,
                    mimetype='application/json'
                )

            # In a real implementation, this might store the state in a backend database.
            # For now, we'll just acknowledge that we received it.
            print(f"Received state for component {component_id}: {state}")

            return Response(
                json.dumps({"status": "success", "message": "State update received by server."}),
                status=200,
                mimetype='application/json'
            )
            
        except Exception as e:
            return Response(
                json.dumps({"status": "error", "message": f"Server error: {str(e)}"}),
                status=500,
                mimetype='application/json'
            )

class AGUIStateGet(ApiHandler):
    """
    Handles retrieving AG-UI component state from the server.
    """
    
    @classmethod
    def requires_auth(cls) -> bool:
        return True
    
    @classmethod 
    def requires_csrf(cls) -> bool:
        return True
    
    async def process(self, request: Request) -> Response:
        try:
            data = request.json or {}
            component_id = data.get("component_id")

            if not component_id:
                return Response(
                    json.dumps({"status": "error", "message": "Component ID is required."}),
                    status=400,
                    mimetype='application/json'
                )

            # In a real implementation, this would retrieve state from a backend database.
            # For now, we'll return empty state.
            return Response(
                json.dumps({"status": "success", "state": {}}),
                status=200,
                mimetype='application/json'
            )
            
        except Exception as e:
            return Response(
                json.dumps({"status": "error", "message": f"Server error: {str(e)}"}),
                status=500,
                mimetype='application/json'
            )

class AGUIEvent(ApiHandler):
    """
    Handles AG-UI events from the frontend.
    """
    
    @classmethod
    def requires_auth(cls) -> bool:
        return True
    
    @classmethod 
    def requires_csrf(cls) -> bool:
        return True
    
    async def process(self, request: Request) -> Response:
        try:
            data = request.json or {}
            event_type = data.get("type")
            component_id = data.get("componentId")
            event_data = data.get("data", {})
            timestamp = data.get("timestamp")

            if not event_type:
                return Response(
                    json.dumps({"status": "error", "message": "Event type is required."}),
                    status=400,
                    mimetype='application/json'
                )

            print(f"Received AG-UI event: {event_type} from component {component_id}")
            print(f"Event data: {event_data}")

            # Handle specific event types
            if event_type == "FORM_SUBMIT":
                return await self._handle_form_submit_event(component_id, event_data)
            elif event_type == "BUTTON_CLICK":
                return await self._handle_button_click_event(component_id, event_data)
            elif event_type in ["MODAL_OPEN", "MODAL_CLOSE"]:
                return await self._handle_modal_event(component_id, event_type, event_data)

            return Response(
                json.dumps({"status": "success", "message": "Event received."}),
                status=200,
                mimetype='application/json'
            )
            
        except Exception as e:
            return Response(
                json.dumps({"status": "error", "message": f"Server error: {str(e)}"}),
                status=500,
                mimetype='application/json'
            )
    
    async def _handle_form_submit_event(self, component_id, event_data):
        """Handle form submission events."""
        form_data = event_data.get("formData", {})
        print(f"Form {component_id} submitted with data: {form_data}")
        
        # Add your validation logic here
        errors = {}
        
        if errors:
            return Response(
                json.dumps({"status": "error", "message": "Validation failed.", "errors": errors}),
                status=400,
                mimetype='application/json'
            )
        
        return Response(
            json.dumps({"status": "success", "message": "Form submitted successfully."}),
            status=200,
            mimetype='application/json'
        )

    async def _handle_button_click_event(self, component_id, event_data):
        """Handle button click events."""
        button_id = event_data.get("buttonId")
        print(f"Button {button_id} clicked in component {component_id}")
        
        return Response(
            json.dumps({"status": "success", "message": "Button click processed."}),
            status=200,
            mimetype='application/json'
        )

    async def _handle_modal_event(self, component_id, action, event_data):
        """Handle modal events (open/close)."""
        print(f"Modal {component_id} {action}")
        
        return Response(
            json.dumps({"status": "success", "message": f"Modal {action} processed."}),
            status=200,
            mimetype='application/json'
        )

class AGUIFormSubmit(ApiHandler):
    """
    Handles AG-UI form submissions.
    """
    
    @classmethod
    def requires_auth(cls) -> bool:
        return True
    
    @classmethod 
    def requires_csrf(cls) -> bool:
        return True
    
    async def process(self, request: Request) -> Response:
        try:
            data = request.json or {}
            form_id = data.get("formId")
            form_data = data.get("data", {})

            if not form_id:
                return Response(
                    json.dumps({"status": "error", "message": "Form ID is required."}),
                    status=400,
                    mimetype='application/json'
                )

            print(f"Received form submission from {form_id}: {form_data}")

            # Process form data here
            # This is where you would validate, store, or process the form data

            return Response(
                json.dumps({"status": "success", "message": "Form submitted successfully.", "data": form_data}),
                status=200,
                mimetype='application/json'
            )
            
        except Exception as e:
            return Response(
                json.dumps({"status": "error", "message": f"Server error: {str(e)}"}),
                status=500,
                mimetype='application/json'
            )