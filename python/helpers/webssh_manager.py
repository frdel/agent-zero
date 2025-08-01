import threading
import socket
import base64
from typing import Optional
from python.helpers.print_style import PrintStyle


class WebSSHManager:
    def __init__(self):
        self.server_port: Optional[int] = None
        self.server_thread: Optional[threading.Thread] = None
        self.server_host: str = "localhost"
        self.is_running: bool = False

    def _find_free_port(self) -> int:
        """Find a free port in the range 35000-45000"""
        import random

        for _ in range(100):  # Try up to 100 random ports
            port = random.randint(35000, 45000)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind((self.server_host, port))
                    return port
            except OSError:
                continue

        raise RuntimeError("Could not find a free port in range 35000-45000")

    def _run_webssh_server(self, port: int):
        """Run WebSSH server in background thread"""
        import sys
        import os

        # Save original state
        old_argv = sys.argv
        old_working_dir = os.getcwd()

        try:
            # Check if webssh is available
            try:
                from webssh.main import main as webssh_main
            except ImportError:
                PrintStyle(font_color="red").print("WebSSH not installed. Install with: pip install webssh")
                self.is_running = False
                return

            # Apply CORS patch and suppress logging before starting WebSSH
            self._patch_webssh_cors()

            # Set up WebSSH arguments
            sys.argv = [
                'webssh',  # Program name (doesn't need to be a real file in this context)
                f'--address={self.server_host}',
                f'--port={port}',
                '--policy=autoadd',
                '--logging=none',  # Disable all logging
                '--debug=true',  # Enable debug mode for wildcard origin
                '--timeout=3',
                '--delay=3',
                '--maxconn=20',
                '--origin=*',  # Allow iframe embedding (requires debug mode)
                '--xsrf=false',  # Disable XSRF for iframe compatibility
                '--xheaders=false'  # Disable X-headers processing
            ]

            PrintStyle(font_color="green").print(f"WebSSH server starting on {self.server_host}:{port}")

            # Mark as running before starting
            self.is_running = True

            # Start WebSSH main function
            try:
                webssh_main()
            except KeyboardInterrupt:
                pass  # Silent handling
            except SystemExit:
                pass  # Silent handling
            except Exception:
                self.is_running = False
                raise

        except ImportError:
            PrintStyle(font_color="red").print("WebSSH not installed. Install with: pip install webssh")
            self.is_running = False
        except Exception as e:
            PrintStyle(font_color="red").print(f"Failed to start WebSSH server: {e}")
            self.is_running = False
        finally:
            # Restore original state
            sys.argv = old_argv
            os.chdir(old_working_dir)
            self.is_running = False

    def _patch_webssh_cors(self):
        """Monkey patch WebSSH to handle CORS OPTIONS requests and suppress access logs"""
        try:
            import tornado.web
            import tornado.log
            import logging

            # Comprehensive Tornado logging suppression
            tornado.log.access_log.setLevel(logging.CRITICAL)
            tornado.log.gen_log.setLevel(logging.CRITICAL)
            tornado.log.app_log.setLevel(logging.CRITICAL)

            # Also suppress root logger that Tornado might use
            tornado_logger = logging.getLogger('tornado')
            tornado_logger.setLevel(logging.CRITICAL)

            # Suppress WebSSH specific loggers
            webssh_logger = logging.getLogger('webssh')
            webssh_logger.setLevel(logging.CRITICAL)

            # Disable 404 and other HTTP error logging
            original_log_exception = tornado.web.RequestHandler.log_exception
            original_write_error = tornado.web.RequestHandler.write_error

            def silent_log_exception(self, typ, value, tb):
                """Override log_exception to suppress HTTP errors"""
                if isinstance(value, tornado.web.HTTPError):
                    return  # Suppress all HTTP error logs
                return original_log_exception(self, typ, value, tb)

            def silent_write_error(self, status_code, **kwargs):
                """Override write_error to suppress error page generation logs"""
                # Call original but suppress any logging it might do
                try:
                    return original_write_error(self, status_code, **kwargs)
                except Exception:
                    pass  # Suppress any errors in error handling

            tornado.web.RequestHandler.log_exception = silent_log_exception
            tornado.web.RequestHandler.write_error = silent_write_error

            # Patch the finish method to inject error prevention JavaScript
            original_finish = tornado.web.RequestHandler.finish

            def patched_finish(self, chunk=None):
                """Inject JavaScript to prevent postMessage errors in WebSSH"""
                if chunk and isinstance(chunk, (str, bytes)):
                    error_prevention_script = '''
<script>
(function() {
    // Prevent WebSSH postMessage errors by patching cross_origin_connect
    if (typeof window.cross_origin_connect === 'function') {
        const original_cross_origin_connect = window.cross_origin_connect;
        window.cross_origin_connect = function(event) {
            try {
                // Only process if event.data is a string
                if (event && event.data && typeof event.data === 'string') {
                    return original_cross_origin_connect(event);
                }
            } catch (e) {
                console.debug('Prevented WebSSH postMessage error:', e);
            }
        };
    }

    // Alternative: patch the addEventListener for message events
    const originalAddEventListener = window.addEventListener;
    window.addEventListener = function(type, listener, options) {
        if (type === 'message' && typeof listener === 'function') {
            const safeListener = function(event) {
                try {
                    // Only call original listener if data is a string
                    if (event.data && typeof event.data === 'string') {
                        return listener(event);
                    }
                } catch (e) {
                    console.debug('Prevented postMessage error:', e);
                }
            };
            return originalAddEventListener.call(this, type, safeListener, options);
        }
        return originalAddEventListener.call(this, type, listener, options);
    };
})();
</script>'''

                    if isinstance(chunk, str):
                        if '</body>' in chunk:
                            chunk = chunk.replace('</body>', error_prevention_script + '</body>')
                        elif '</head>' in chunk:
                            chunk = chunk.replace('</head>', error_prevention_script + '</head>')
                    elif isinstance(chunk, bytes):
                        script_bytes = error_prevention_script.encode('utf-8')
                        if b'</body>' in chunk:
                            chunk = chunk.replace(b'</body>', script_bytes + b'</body>')
                        elif b'</head>' in chunk:
                            chunk = chunk.replace(b'</head>', script_bytes + b'</head>')

                return original_finish(self, chunk)

            tornado.web.RequestHandler.finish = patched_finish

            def options_handler(self, *args, **kwargs):
                """Handle OPTIONS requests for CORS"""
                self.set_header('Access-Control-Allow-Origin', '*')
                self.set_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.set_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
                self.set_header('Access-Control-Max-Age', '86400')
                self.finish()

            # Apply the CORS patch
            tornado.web.RequestHandler.options = options_handler

            PrintStyle(font_color="cyan").print("Applied CORS patch, log suppression, and WebSSH error prevention")

        except Exception as e:
            PrintStyle(font_color="yellow").print(f"CORS/logging patch failed: {e}")

    def start_server(self) -> bool:
        """Start WebSSH server on random port"""
        if self.is_running:
            return True

        try:
            self.server_port = self._find_free_port()

            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self._run_webssh_server,
                args=(self.server_port,),
                daemon=True,
                name="WebSSH-Server"
            )
            self.server_thread.start()

            # Give server time to start
            import time
            time.sleep(2)

            return self.is_running

        except Exception as e:
            PrintStyle(font_color="red").print(f"Failed to start WebSSH server: {e}")
            return False

    def stop_server(self):
        """Stop the WebSSH server"""
        PrintStyle(font_color="yellow").print("Stopping WebSSH server...")
        self.is_running = False
        self.server_port = None
        self.server_thread = None

    def get_connection_url(self, hostname: str, port: int, username: str, password: str, session_id: int = 0) -> Optional[str]:
        """Generate WebSSH connection URL with automatic login and tmux session attachment"""
        if not self.is_running or not self.server_port:
            return None

        # WebSSH requires password to be base64 encoded for URL parameters
        password_b64 = base64.b64encode(password.encode('utf-8')).decode('utf-8')

        # Command to attach to the specific tmux session
        tmux_session_name = f"a0-session-{session_id}"

        # Simplified command - try to attach to existing session, create if doesn't exist
        attach_command = f"tmux attach -t {tmux_session_name} || tmux new -s {tmux_session_name}"

        # URL encode the command (WebSSH expects regular URL encoding, not base64)
        import urllib.parse
        command_encoded = urllib.parse.quote(attach_command)

        # WebSSH URL format with automatic login parameters and tmux attachment
        url = f"http://{self.server_host}:{self.server_port}/"
        params = f"?hostname={hostname}&port={port}&username={username}&password={password_b64}&command={command_encoded}"

        return url + params

    def get_connection_details(self) -> dict:
        """Get current WebSSH server connection details"""
        return {
            "running": self.is_running,
            "host": self.server_host if self.is_running else None,
            "port": self.server_port if self.is_running else None,
            "url": f"http://{self.server_host}:{self.server_port}/" if self.is_running else None
        }


# Global WebSSH manager instance
webssh_manager = WebSSHManager()
