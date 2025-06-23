import asyncio
import json
import os
import uuid
import time
from datetime import datetime
from python.helpers.tool import Tool, Response
from python.helpers import files
from python.helpers.print_style import PrintStyle


class CanvasTool(Tool):
    """
    Canvas Tool for Agent Zero - Enables creation and management of canvas artifacts
    Similar to Claude's artifacts functionality
    """

    async def execute(self, **kwargs):
        """
        Execute canvas operations based on the action parameter
        
        Actions:
        - create: Create a new canvas artifact
        - update: Update existing canvas content
        - show: Display existing canvas
        - list: List all canvas artifacts
        """
        
        action = self.args.get("action", "create").lower()
        
        try:
            if action == "create":
                return await self._create_canvas()
            elif action == "update":
                return await self._update_canvas()
            elif action == "show":
                return await self._show_canvas()
            elif action == "list":
                return await self._list_canvas()
            else:
                return Response(
                    message=f"Unknown canvas action: {action}. Supported actions: create, update, show, list",
                    break_loop=False
                )
        except Exception as e:
            error_msg = f"Canvas tool error: {str(e)}"
            PrintStyle(font_color="red", padding=True).print(error_msg)
            return Response(message=error_msg, break_loop=False)

    async def _create_canvas(self):
        """Create a new canvas artifact"""
        
        # Extract parameters
        content = self.args.get("content", "")
        content_type = self.args.get("type", "html").lower()
        title = self.args.get("title", f"Canvas Artifact {datetime.now().strftime('%H:%M')}")
        description = self.args.get("description", "")
        
        if not content:
            return Response(
                message="Canvas content is required to create an artifact",
                break_loop=False
            )
        
        # Generate unique canvas ID
        canvas_id = str(uuid.uuid4())[:8]
        
        # Create canvas directory structure
        canvas_dir = files.get_abs_path("work_dir", "canvas", canvas_id)
        os.makedirs(canvas_dir, exist_ok=True)
        
        # Prepare content based on type
        file_content, file_extension = self._prepare_content(content, content_type)
        
        # Save the main content file
        content_file = os.path.join(canvas_dir, f"content.{file_extension}")
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # Create metadata file
        metadata = {
            "id": canvas_id,
            "title": title,
            "description": description,
            "type": content_type,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "file_path": content_file,
            "url": f"/canvas_serve/{canvas_id}/content.{file_extension}"
        }
        
        metadata_file = os.path.join(canvas_dir, "metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Store in agent's data for quick access
        if not hasattr(self.agent, 'canvas_artifacts'):
            self.agent.canvas_artifacts = {}
        self.agent.canvas_artifacts[canvas_id] = metadata
        
        # Trigger canvas display in UI
        await self._trigger_canvas_display(canvas_id, metadata)
        
        result_message = f"✅ Canvas artifact '{title}' created successfully!\n"
        result_message += f"📋 ID: {canvas_id}\n"
        result_message += f"🎨 Type: {content_type.upper()}\n"
        result_message += f"📝 Description: {description}\n"
        result_message += f"🌐 The canvas is now visible in the UI with your {content_type} content."
        
        return Response(message=result_message, break_loop=False)

    async def _update_canvas(self):
        """Update existing canvas artifact"""
        
        canvas_id = self.args.get("canvas_id", "")
        content = self.args.get("content", "")
        
        if not canvas_id:
            return Response(
                message="Canvas ID is required to update an artifact",
                break_loop=False
            )
        
        if not content:
            return Response(
                message="New content is required to update the canvas",
                break_loop=False
            )
        
        # Find existing canvas
        canvas_dir = files.get_abs_path("work_dir", "canvas", canvas_id)
        metadata_file = os.path.join(canvas_dir, "metadata.json")
        
        if not os.path.exists(metadata_file):
            return Response(
                message=f"Canvas with ID {canvas_id} not found",
                break_loop=False
            )
        
        # Load existing metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Prepare updated content
        content_type = metadata.get("type", "html")
        file_content, file_extension = self._prepare_content(content, content_type)
        
        # Update the content file
        content_file = os.path.join(canvas_dir, f"content.{file_extension}")
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # Update metadata
        metadata["updated_at"] = datetime.now().isoformat()
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Update in agent's data
        if hasattr(self.agent, 'canvas_artifacts'):
            self.agent.canvas_artifacts[canvas_id] = metadata
        
        # Trigger canvas refresh in UI
        await self._trigger_canvas_display(canvas_id, metadata)
        
        result_message = f"✅ Canvas artifact '{metadata.get('title', canvas_id)}' updated successfully!\n"
        result_message += f"🔄 The canvas content has been refreshed in the UI."
        
        return Response(message=result_message, break_loop=False)

    async def _show_canvas(self):
        """Display existing canvas artifact"""
        
        canvas_id = self.args.get("canvas_id", "")
        
        if not canvas_id:
            return Response(
                message="Canvas ID is required to show an artifact",
                break_loop=False
            )
        
        # Find existing canvas
        canvas_dir = files.get_abs_path("work_dir", "canvas", canvas_id)
        metadata_file = os.path.join(canvas_dir, "metadata.json")
        
        if not os.path.exists(metadata_file):
            return Response(
                message=f"Canvas with ID {canvas_id} not found",
                break_loop=False
            )
        
        # Load metadata
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Trigger canvas display in UI
        await self._trigger_canvas_display(canvas_id, metadata)
        
        result_message = f"🎨 Displaying canvas artifact '{metadata.get('title', canvas_id)}'\n"
        result_message += f"📋 ID: {canvas_id}\n"
        result_message += f"🎯 Type: {metadata.get('type', 'unknown').upper()}\n"
        result_message += f"📅 Created: {metadata.get('created_at', 'unknown')}\n"
        result_message += f"🔄 Updated: {metadata.get('updated_at', 'unknown')}"
        
        return Response(message=result_message, break_loop=False)

    async def _list_canvas(self):
        """List all canvas artifacts"""
        
        canvas_base_dir = files.get_abs_path("work_dir", "canvas")
        
        if not os.path.exists(canvas_base_dir):
            return Response(
                message="No canvas artifacts found. Create your first canvas artifact!",
                break_loop=False
            )
        
        artifacts = []
        for item in os.listdir(canvas_base_dir):
            canvas_dir = os.path.join(canvas_base_dir, item)
            metadata_file = os.path.join(canvas_dir, "metadata.json")
            
            if os.path.isdir(canvas_dir) and os.path.exists(metadata_file):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    artifacts.append(metadata)
                except Exception:
                    continue
        
        if not artifacts:
            return Response(
                message="No canvas artifacts found. Create your first canvas artifact!",
                break_loop=False
            )
        
        # Sort by creation date (newest first)
        artifacts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        result_message = f"📋 Found {len(artifacts)} canvas artifact(s):\n\n"
        
        for i, artifact in enumerate(artifacts, 1):
            result_message += f"{i}. **{artifact.get('title', 'Untitled')}** (ID: {artifact.get('id', 'unknown')})\n"
            result_message += f"   🎯 Type: {artifact.get('type', 'unknown').upper()}\n"
            result_message += f"   📅 Created: {artifact.get('created_at', 'unknown')}\n"
            if artifact.get('description'):
                result_message += f"   📝 Description: {artifact.get('description')}\n"
            result_message += "\n"
        
        return Response(message=result_message, break_loop=False)

    def _prepare_content(self, content, content_type):
        """Prepare content based on type and return (content, file_extension)"""
        
        if content_type == "html":
            # Wrap in full HTML document if not already
            if not content.strip().lower().startswith('<!doctype') and not content.strip().lower().startswith('<html'):
                full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Canvas Artifact</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .canvas-content {{
            max-width: 100%;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="canvas-content">
        {content}
    </div>
</body>
</html>"""
                return full_html, "html"
            return content, "html"
        
        elif content_type == "css":
            return content, "css"
        
        elif content_type == "javascript" or content_type == "js":
            return content, "js"
        
        elif content_type == "python":
            # For Python, we might want to create an HTML page that displays the code
            python_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Code</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background-color: #f8f8f8;
        }}
        .code-container {{
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
        }}
        pre {{
            margin: 0;
            white-space: pre-wrap;
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="code-container">
        <h3>Python Code</h3>
        <pre><code>{content}</code></pre>
    </div>
</body>
</html>"""
            return python_html, "html"
        
        elif content_type == "markdown" or content_type == "md":
            # Convert basic markdown to HTML
            html_content = self._basic_markdown_to_html(content)
            return html_content, "html"
        
        else:
            # Default to HTML
            return content, "html"

    def _basic_markdown_to_html(self, markdown):
        """Convert basic markdown to HTML"""
        html = markdown
        html = html.replace('\n# ', '\n<h1>').replace('# ', '<h1>')
        html = html.replace('\n## ', '\n<h2>').replace('## ', '<h2>')
        html = html.replace('\n### ', '\n<h3>').replace('### ', '<h3>')
        
        # Close headers (simple approach)
        html = html.replace('<h1>', '<h1>').replace('\n', '</h1>\n').replace('</h1>\n<h1>', '\n<h1>')
        html = html.replace('<h2>', '<h2>').replace('\n', '</h2>\n').replace('</h2>\n<h2>', '\n<h2>')
        html = html.replace('<h3>', '<h3>').replace('\n', '</h3>\n').replace('</h3>\n<h3>', '\n<h3>')
        
        # Bold and italic
        html = html.replace('**', '<strong>').replace('**', '</strong>')
        html = html.replace('*', '<em>').replace('*', '</em>')
        html = html.replace('`', '<code>').replace('`', '</code>')
        
        # Line breaks
        html = html.replace('\n\n', '</p><p>').replace('\n', '<br>')
        html = f"<p>{html}</p>"
        
        # Wrap in full HTML
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Markdown Content</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
        }}
        h1, h2, h3 {{ color: #2c3e50; }}
        code {{ 
            background-color: #f1f1f1; 
            padding: 2px 4px; 
            border-radius: 3px; 
            font-family: monospace; 
        }}
    </style>
</head>
<body>
    {html}
</body>
</html>"""

    async def _trigger_canvas_display(self, canvas_id, metadata):
        """Trigger canvas display in the UI via log message"""
        
        # Create a special log entry that the frontend can intercept
        log_data = {
            "type": "canvas",
            "action": "display",
            "canvas_id": canvas_id,
            "metadata": metadata
        }
        
        # Add to agent's log with special canvas type
        self.agent.context.log.log(
            type="canvas",
            heading=f"Canvas: {metadata.get('title', 'Untitled')}",
            content=f"Canvas artifact created with ID: {canvas_id}",
            kvps=log_data
        )
        
        # Also store in agent data for access by extensions
        if not hasattr(self.agent, 'active_canvas'):
            self.agent.active_canvas = {}
        self.agent.active_canvas = {
            "id": canvas_id,
            "metadata": metadata,
            "url": metadata.get("url", ""),
            "timestamp": time.time()
        }