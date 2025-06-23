# Canvas Tool Documentation

The Canvas Tool provides Agent Zero with the ability to create, display, and manage interactive visual artifacts similar to Claude's artifacts functionality. This tool enables agents to generate HTML, CSS, JavaScript, and other visual content that can be displayed in a dedicated canvas panel.

## Overview

The Canvas Tool consists of several integrated components:
- **Server-side Canvas Tool** (`python/tools/canvas_tool.py`) - Creates and manages canvas artifacts
- **Canvas Serve API** (`python/api/canvas_serve.py`) - Serves canvas files securely
- **Canvas Manager** (`webui/js/canvas.js`) - Client-side canvas functionality
- **Canvas UI Components** - HTML structure and CSS styling

## Features

### Canvas Display Modes
- **Side-by-side View**: Canvas appears alongside the chat interface
- **Fullscreen Mode**: Canvas takes over the entire screen for immersive viewing
- **Tabbed Interface**: Switch between Preview and Code views

### Supported Content Types
- **HTML**: Interactive web pages and applications
- **CSS**: Stylesheets and visual designs
- **JavaScript**: Dynamic and interactive content
- **Markdown**: Formatted text content (converted to HTML)

### Canvas Management
- **Real-time Updates**: Live streaming of canvas content as it's being created
- **Code Export**: Download canvas artifacts as files
- **Code Copying**: Copy source code to clipboard
- **Artifact Persistence**: Canvas artifacts are saved and can be reloaded

## Usage

### Basic Canvas Creation

Agents can create canvas artifacts using the Canvas Tool:

```python
await canvas_tool.execute(
    action="create",
    content="<html><body><h1>Hello World</h1></body></html>",
    type="html",
    title="My First Canvas",
    description="A simple HTML example"
)
```

### Canvas Actions

The Canvas Tool supports several actions:

#### Create Canvas
```python
action="create"
content="<html>...</html>"  # The content to display
type="html"                 # Content type: html, css, javascript, markdown
title="Canvas Title"        # Display title
description="Description"   # Optional description
```

#### Update Canvas
```python
action="update"
canvas_id="abc123"          # ID of existing canvas
content="<html>...</html>"  # New content
```

#### Show Canvas
```python
action="show"
canvas_id="abc123"          # Display existing canvas
```

#### List Canvas
```python
action="list"               # List all available canvas artifacts
```

## Architecture

### File Storage
Canvas artifacts are stored in the work directory structure:
```
work_dir/
  canvas/
    {canvas_id}/
      content.html          # Main content file
      metadata.json         # Canvas metadata
```

### URL Structure
Canvas artifacts are served via secure endpoints:
```
/canvas_serve/{canvas_id}/{filename}
```

### Security
- Canvas files are served through authenticated endpoints
- Path traversal protection prevents unauthorized file access
- Content is sandboxed within iframe elements

## Client-Side Interface

### Canvas Panel
The canvas panel provides a rich interface for viewing and interacting with artifacts:

- **Header**: Contains title, controls, and tabs
- **Preview Tab**: Displays the rendered content in an iframe
- **Code Tab**: Shows the source code with syntax highlighting
- **Controls**: Copy, export, refresh, and fullscreen buttons

### Keyboard Shortcuts
- `Ctrl/Cmd + K`: Toggle canvas visibility
- `Escape`: Close canvas (when visible)
- `F11`: Toggle fullscreen mode (when canvas is visible)

### Responsive Design
The canvas interface adapts to different screen sizes:
- Desktop: Side-by-side layout with chat interface
- Mobile: Fullscreen mode with hidden sidebar
- Fullscreen: Immersive experience hiding all UI elements

## Configuration

### Port Configuration
The canvas tool automatically adapts to the server port. To avoid conflicts with Apple AirPlay (port 5000), set a custom port:

```env
# .env file
WEB_UI_PORT=8080
```

### Canvas Settings
Canvas behavior can be customized through the web UI settings or configuration files.

## Integration with Messages

Canvas artifacts automatically appear in the chat interface as interactive cards showing:
- Artifact icon and title
- Content type badge
- Preview thumbnail
- Action buttons (Open, Copy)

## Troubleshooting

### Common Issues

#### 404 Canvas Not Found
- **Cause**: Port mismatch or missing canvas files
- **Solution**: Ensure server is running and canvas files exist in work_dir/canvas/

#### Canvas Not Loading
- **Cause**: Browser security restrictions or CORS issues
- **Solution**: Ensure proper authentication and valid URLs

#### Fullscreen Display Issues
- **Cause**: CSS conflicts or z-index problems
- **Solution**: Canvas automatically manages UI elements in fullscreen mode

#### UI Element Overlapping
- **Cause**: High z-index elements interfering with canvas
- **Solution**: Canvas hides conflicting UI elements when in fullscreen

### Debugging

Enable canvas debugging by checking browser console for messages prefixed with "Canvas:".

## Best Practices

### Content Creation
- Use responsive design principles for better mobile experience
- Include proper HTML structure with DOCTYPE declarations
- Test content in both preview and fullscreen modes

### Performance
- Optimize images and assets for faster loading
- Minimize large JavaScript libraries when possible
- Use efficient CSS for better rendering performance

### Security
- Avoid inline scripts that might be blocked by CSP
- Sanitize user input when creating dynamic content
- Use relative URLs for internal resources

## API Reference

### Canvas Tool Methods

#### `execute(**kwargs)`
Main entry point for canvas operations.

**Parameters:**
- `action` (str): Operation to perform (create, update, show, list)
- `content` (str): Content to display (for create/update)
- `type` (str): Content type (html, css, javascript, markdown)
- `title` (str): Display title
- `description` (str): Optional description
- `canvas_id` (str): Canvas ID (for update/show)

**Returns:**
- `Response`: Tool response with success/error status

### Canvas Serve API

#### `GET /canvas_serve/{canvas_id}/{filename}`
Serves canvas artifact files.

**Parameters:**
- `canvas_id` (str): Unique canvas identifier
- `filename` (str): File to serve (typically content.html)

**Returns:**
- File content with appropriate MIME type

### JavaScript Canvas Manager

#### `window.canvasManager`
Global canvas management instance.

**Methods:**
- `show()`: Display canvas panel
- `hide()`: Hide canvas panel
- `toggle()`: Toggle canvas visibility
- `toggleFullscreen()`: Toggle fullscreen mode
- `createArtifact(content, type, title)`: Create new artifact
- `updateArtifact(content, type)`: Update current artifact
- `displayFromUrl(url, title)`: Display from URL

## Version History

### Recent Updates
- Fixed port detection for dynamic server configuration
- Improved fullscreen layout and UI element management
- Enhanced artifact bubble contrast for better readability
- Added comprehensive error handling and debugging
- Implemented responsive design improvements

## Related Documentation

- [Agent Zero Architecture](architecture.md)
- [Tool Development Guide](contribution.md)
- [Web UI Configuration](installation.md)
- [Troubleshooting Guide](troubleshooting.md)