import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import threading
import time

from aider.coders import Coder
from aider.models import Model
from aider.io import InputOutput
from aider.commands import Commands  # type: ignore
from aider.history import ChatSummary  # type: ignore
from aider.analytics import Analytics  # type: ignore

from python.helpers import settings
from python.helpers.settings import Settings
from python.helpers.print_style import PrintStyle

from models import get_api_key

# Grab all the API keys and normalize them to standard environment variables if not empty
for provider in ["OPENAI", "ANTHROPIC", "GROQ", "GOOGLE", "DEEPSEEK", "OPENROUTER", "SAMBANOVA", "MISTRALAI", "HUGGINGFACE", "CHUTES"]:
    api_key = get_api_key(provider)
    if api_key:
        os.environ[f"{provider}_API_KEY"] = api_key


class StreamingResponseCapture:
    """Captures streaming response chunks from aider's native streaming."""

    def __init__(self):
        self.chunks: List[str] = []
        self.full_response: str = ""
        self.callbacks: List[Callable[[str, str], None]] = []
        self.lock = threading.RLock()

    def add_callback(self, callback: Callable[[str, str], None]):
        """Add a callback to be called for each response chunk."""
        with self.lock:
            self.callbacks.append(callback)

    def add_chunk(self, chunk: str):
        """Add a chunk to the response and call callbacks."""
        with self.lock:
            self.chunks.append(chunk)
            self.full_response += chunk

            # Call callbacks for this chunk
            for callback in self.callbacks:
                try:
                    callback('chunk', chunk)
                except Exception as e:
                    PrintStyle().error(f"Chunk callback error: {e}")

    def complete_response(self, final_response: Optional[str] = None):
        """Mark the response as complete and call completion callbacks."""
        with self.lock:
            if final_response is not None:
                self.full_response = final_response

            # Call completion callbacks
            for callback in self.callbacks:
                try:
                    callback('completion', self.full_response)
                except Exception as e:
                    PrintStyle().error(f"Completion callback error: {e}")

    def get_full_response(self) -> str:
        """Get the complete accumulated response."""
        with self.lock:
            return self.full_response

    def get_chunks(self) -> List[str]:
        """Get all captured chunks."""
        with self.lock:
            return self.chunks.copy()

    def clear(self):
        """Clear all captured data."""
        with self.lock:
            self.chunks = []
            self.full_response = ""


class StreamingAiderWrapper:
    """Clean wrapper that uses aider's native streaming capability."""

    def __init__(self, coder: Coder):
        self.coder = coder
        self.response_capture = StreamingResponseCapture()

    def add_response_callback(self, callback: Callable[[str, str], None]):
        """Add a callback for streaming responses."""
        self.response_capture.add_callback(callback)

    def run_with_streaming(self, message: str, debug: bool = False) -> Dict[str, Any]:
        """
        Run aider with native streaming support and chunk callbacks.
        """
        # Clear previous responses
        self.response_capture.clear()
        initial_time = time.time()

        # Store original working directory (but don't change it)
        original_cwd = os.getcwd()

        if debug:
            PrintStyle().debug("Starting aider execution with native streaming")
            PrintStyle().debug(f"Web server working directory: {original_cwd}")
            PrintStyle().debug(f"Coder root: {getattr(self.coder, 'root', 'None')}")
            PrintStyle().debug(f"Files in chat: {len(getattr(self.coder, 'abs_fnames', []))}")
            PrintStyle().debug(f"Stream enabled: {getattr(self.coder, 'stream', False)}")

        try:
            # DON'T change the global working directory - this causes issues in web servers
            # Instead, ensure aider knows its correct root context
            if hasattr(self.coder, 'root') and self.coder.root:
                if debug:
                    PrintStyle().debug(f"Aider will operate in root: {self.coder.root}")
                    PrintStyle().debug(f"Root exists: {os.path.exists(self.coder.root)}")

                # Ensure the root directory exists
                if not os.path.exists(self.coder.root):
                    os.makedirs(self.coder.root, exist_ok=True)
                    if debug:
                        PrintStyle().debug(f"Created root directory: {self.coder.root}")

            # Create a custom write method to capture streaming chunks
            original_print = None
            original_tool_output = None

            # Try to intercept console output from aider
            if hasattr(self.coder.io, 'console'):
                # Rich console might have different output methods
                if hasattr(self.coder.io.console, 'print'):
                    original_print = self.coder.io.console.print

                    def streaming_print(*args, **kwargs):
                        # Capture the content
                        content = ' '.join(str(arg) for arg in args)
                        if content and content.strip():
                            self.response_capture.add_chunk(content)

                        # Call original print method
                        return original_print(*args, **kwargs)

                    self.coder.io.console.print = streaming_print

            # Also try to capture from io methods - using correct signature
            if hasattr(self.coder.io, 'tool_output'):
                original_tool_output = self.coder.io.tool_output

                def streaming_tool_output(*messages, log_only=False, bold=False):
                    # Capture the messages
                    for message in messages:
                        if message and isinstance(message, str) and message.strip():
                            self.response_capture.add_chunk(str(message))

                    # Call original method with proper signature
                    return original_tool_output(*messages, log_only=log_only, bold=bold)

                self.coder.io.tool_output = streaming_tool_output

            if debug:
                PrintStyle().debug(f"About to call coder.run() with message: {message[:100]}...")

            # Execute aider - this should stream if stream=True
            # Aider will use its configured root directory for all operations
            result = self.coder.run(message)

            if debug:
                PrintStyle().debug(f"coder.run() completed with result type: {type(result)}")
                PrintStyle().debug(f"Result content: {str(result)[:200]}...")

            # Restore original methods
            if original_print:
                self.coder.io.console.print = original_print
            if original_tool_output:
                self.coder.io.tool_output = original_tool_output

            # Complete the response
            response_content = str(result) if result else ""
            self.response_capture.complete_response(response_content)

            # Get captured data
            full_response = self.response_capture.get_full_response()
            chunks = self.response_capture.get_chunks()

            if debug:
                PrintStyle().debug(f"Full response length: {len(full_response)}")
                PrintStyle().debug(f"Number of chunks: {len(chunks)}")

            return {
                'success': True,
                'result': result,
                'response': full_response,
                'chunks': chunks,
                'execution_time': time.time() - initial_time,
                'model': self.coder.main_model.name,
            }

        except Exception as e:
            if debug:
                PrintStyle().debug(f"Exception during aider execution: {e}")
                import traceback
                PrintStyle().debug(f"Traceback: {traceback.format_exc()}")

            return {
                'success': False,
                'error': str(e),
                'response': self.response_capture.get_full_response(),
                'chunks': self.response_capture.get_chunks(),
                'execution_time': time.time() - initial_time,
                'model': self.coder.main_model.name if hasattr(self.coder, 'main_model') else 'unknown'
            }
        finally:
            # Note: We don't need to restore working directory since we never changed it
            if debug:
                PrintStyle().debug(f"Execution completed, staying in web server cwd: {original_cwd}")
                if hasattr(self.coder, 'root'):
                    PrintStyle().debug(f"Aider operated in root: {self.coder.root}")

    async def run_with_streaming_async(self, message: str,
                                       response_callback: Optional[Callable[[str, str], None]] = None,
                                       debug: bool = False) -> Dict[str, Any]:
        """
        Async version that uses native aider streaming.
        """
        if response_callback:
            self.add_response_callback(response_callback)

        try:
            # Execute directly in the same thread to avoid issues
            result = self.run_with_streaming(message, debug=debug)
            return result
        finally:
            # No callback cleanup needed as they're managed by response_capture
            pass


def create_streaming_aider_coder(
    files: Optional[List[str]] = None,
    read_only_files: Optional[List[str]] = None,
    git_repo_path: Optional[str] = None,
    auto_commits: bool = True,
    verbose: bool = False,
    stream: bool = True,
    dry_run: bool = False,
    suppress_terminal_output: bool = True,  # Kept for compatibility but not used
    max_reflections: int = 10,  # Allow more reflection attempts for complex operations
    **kwargs
) -> tuple[StreamingAiderWrapper, StreamingResponseCapture]:
    """
    Create an aider Coder instance with native streaming support.

    Args:
        model_name: The model to use
        files: List of files to add to the chat
        read_only_files: List of read-only files to add
        git_repo_path: Path to git repository directory
        auto_commits: Whether to auto-commit changes
        verbose: Enable verbose output
        stream: Enable streaming responses (now actually used!)
        dry_run: Don't actually make changes
        suppress_terminal_output: Compatibility arg (ignored)
        max_reflections: Allow more reflection attempts for complex operations
        **kwargs: Additional parameters

    Returns:
        tuple: (StreamingAiderWrapper, StreamingResponseCapture)
    """
    try:
        conf: Settings = settings.get_settings()
        model_name = conf["coding_model_name"]
        model_provider = conf["coding_model_provider"]
        model_name = model_provider.lower() + "/" + model_name
        model_ctx_history = int(conf["coding_model_ctx_history"] * conf["chat_model_ctx_length"])

        # Determine working directory but don't change global cwd
        if git_repo_path:
            repo_path = Path(git_repo_path).resolve()
            if not repo_path.exists():
                repo_path.mkdir(parents=True, exist_ok=True)
            # Don't change global working directory - problematic in web servers
            # os.chdir(repo_path)  # REMOVED
        else:
            repo_path = Path.cwd()

        # Create main model
        main_model = Model(model_name)
        main_model.max_chat_history_tokens = model_ctx_history

        # Create InputOutput with the specific root path
        io = InputOutput(
            yes=True,  # Auto-confirm all prompts for programmatic use
            chat_history_file=None,  # Don't save chat history
            input_history_file=None,  # Don't save input history
            llm_history_file=None,  # Don't save LLM conversation logs
            pretty=False,  # Disable pretty printing for cleaner output
            encoding='utf-8',
            dry_run=dry_run,
            root=str(repo_path),  # Set the root explicitly
        )

        # Initialize git repo if it doesn't exist
        repo = None
        if git_repo_path:
            try:
                from aider.repo import GitRepo

                # Ensure we're working with absolute paths
                abs_repo_path = str(repo_path)

                # Create GitRepo with explicit context to avoid cwd issues
                repo = GitRepo(
                    io=io,
                    fnames=[],
                    git_dname=abs_repo_path,
                    models=[main_model],
                )

                # Explicitly set the repo's root to avoid any cwd confusion
                if hasattr(repo, 'root'):
                    repo.root = abs_repo_path

            except Exception:
                # If git repo creation fails, initialize git manually
                if not (repo_path / ".git").exists():
                    import subprocess
                    subprocess.run(["git", "init"], cwd=str(repo_path), capture_output=True)
                    subprocess.run(["git", "config", "user.email", "aider@example.com"], cwd=str(repo_path), capture_output=True)
                    subprocess.run(["git", "config", "user.name", "Aider"], cwd=str(repo_path), capture_output=True)

                # Try again to create GitRepo with explicit path context
                try:
                    from aider.repo import GitRepo
                    abs_repo_path = str(repo_path)

                    repo = GitRepo(
                        io=io,
                        fnames=[],
                        git_dname=abs_repo_path,
                        models=[main_model],
                    )

                    # Explicitly set path attributes to avoid cwd confusion
                    if hasattr(repo, 'root'):
                        repo.root = abs_repo_path

                except Exception:
                    # If still fails, continue without git repo
                    repo = None

        # Create enhanced components
        commands = Commands(io, None)  # Coder will be set later
        analytics = Analytics()

        # Ensure max_tokens is an integer for ChatSummary
        max_tokens = main_model.max_chat_history_tokens
        if max_tokens is None:
            max_tokens = 4096  # Default fallback
        elif isinstance(max_tokens, float):
            max_tokens = int(max_tokens)

        summarizer = ChatSummary(
            [main_model.weak_model, main_model],
            max_tokens,
        )

        # Convert files and read_only_files to absolute paths
        abs_files = None
        if files:
            abs_files = []
            for file_path in files:
                if file_path:
                    path_obj = Path(file_path)
                    if path_obj.is_absolute():
                        abs_files.append(str(path_obj.resolve()))
                    else:
                        abs_files.append(str((repo_path / path_obj).resolve()))

        abs_read_only_files = None
        if read_only_files:
            abs_read_only_files = []
            for file_path in read_only_files:
                if file_path:
                    path_obj = Path(file_path)
                    if path_obj.is_absolute():
                        abs_read_only_files.append(str(path_obj.resolve()))
                    else:
                        abs_read_only_files.append(str((repo_path / path_obj).resolve()))

        # Create coder instance with streaming enabled and explicit root
        coder = Coder.create(
            main_model=main_model,
            io=io,
            repo=repo,
            fnames=abs_files,
            read_only_fnames=abs_read_only_files,
            show_diffs=True,
            auto_commits=auto_commits,
            dirty_commits=True,
            dry_run=dry_run,
            verbose=verbose,
            stream=stream,  # This is the key - use native streaming
            use_git=bool(repo),
            auto_lint=False,
            auto_test=False,
            commands=commands,
            summarizer=summarizer,
            analytics=analytics,
            suggest_shell_commands=True,
            edit_format=None,  # Use model's default edit format
            restore_chat_history=False,
            map_refresh="auto",
            auto_copy_context=False,
            auto_accept_architect=True,
            cache_prompts=False,  # Disable caching to prevent threading issues
            num_cache_warming_pings=0,  # Disable cache warming
            **kwargs
        )

        # Configure max_reflections to allow more attempts for complex operations
        if hasattr(coder, 'max_reflections'):
            coder.max_reflections = max_reflections

        # CRITICAL FIX: Override path resolution to prevent path doubling
        # Store the original abs_root_path method and replace it
        if hasattr(coder, 'abs_root_path'):
            def fixed_abs_root_path(path):
                """Fixed version that prevents path doubling by ensuring absolute path handling."""
                if not path:
                    return str(repo_path)

                # Convert to Path object for proper handling
                path_obj = Path(path)

                # If it's already absolute, use it as-is (prevents doubling)
                if path_obj.is_absolute():
                    result = str(path_obj.resolve())
                    return result

                # Get both absolute and relative representations of repo_path
                repo_path_str = str(repo_path)

                # For paths like "/a0/share/calculator", extract "share/calculator" as the relative part
                repo_relative_suffix = str(repo_path).split("/")[-2:] if len(str(repo_path).split("/")) >= 2 else []
                repo_relative_suffix_path = "/".join(repo_relative_suffix) if repo_relative_suffix else ""

                # Check if this relative path would create a duplicate when resolved
                # This prevents multiple concatenations of the same path
                if repo_path_str in path:
                    # Path already contains full repo path - likely already resolved incorrectly
                    # Try to extract the actual relative part
                    if path.startswith(repo_path_str):
                        # Remove the repo path prefix to get the true relative path
                        relative_part = path[len(repo_path_str):].lstrip('/')
                        if relative_part:
                            result = str((repo_path / relative_part).resolve())
                            return result

                    # If path contains repo path but doesn't start with it, it might be malformed
                    # Return the original path as absolute if it exists
                    if path_obj.exists():
                        result = str(path_obj.resolve())
                        return result

                # Check if path starts with the relative suffix of repo path
                # e.g., if repo_path is "/a0/share/calculator" and path is "share/calculator/web/file.html"
                if repo_relative_suffix_path and path.startswith(repo_relative_suffix_path + "/"):
                    # Extract the part after the relative suffix
                    suffix_after_repo = path[len(repo_relative_suffix_path + "/"):]
                    result = str((repo_path / suffix_after_repo).resolve())
                    return result

                # Special case for exact match with relative suffix
                if repo_relative_suffix_path and path == repo_relative_suffix_path:
                    result = str(repo_path.resolve())
                    return result

                # Handle relative paths with navigation (../) to prevent escaping repo boundaries
                if ".." in path:
                    # Resolve the relative path against repo_path
                    potential_result = (repo_path / path_obj).resolve()

                    # Check if the resolved path is still within the repo_path boundaries
                    try:
                        # This will raise ValueError if potential_result is not within repo_path
                        potential_result.relative_to(repo_path)
                        result = str(potential_result)
                        return result
                    except ValueError:
                        # Path escapes repo boundaries - constrain it to repo root
                        # Extract just the filename/basename and put it in repo root
                        safe_filename = path_obj.name if path_obj.name else "file"
                        result = str((repo_path / safe_filename).resolve())
                        return result

                # Normal relative path resolution
                result = str((repo_path / path_obj).resolve())
                return result

            # Replace the method
            coder.abs_root_path = fixed_abs_root_path

        # CRITICAL FIX: Override InputOutput root resolution if needed
        if hasattr(coder.io, 'abs_root_path'):
            def fixed_io_abs_root_path(path):
                """Fixed IO version that prevents path doubling."""
                if not path:
                    return str(repo_path)

                path_obj = Path(path)
                if path_obj.is_absolute():
                    result = str(path_obj.resolve())
                    return result

                # Same logic as above to prevent multiple concatenations
                repo_path_str = str(repo_path)

                # For paths like "/a0/share/calculator", extract "share/calculator" as the relative part
                repo_relative_suffix = str(repo_path).split("/")[-2:] if len(str(repo_path).split("/")) >= 2 else []
                repo_relative_suffix_path = "/".join(repo_relative_suffix) if repo_relative_suffix else ""

                if repo_path_str in path:
                    if path.startswith(repo_path_str):
                        relative_part = path[len(repo_path_str):].lstrip('/')
                        if relative_part:
                            result = str((repo_path / relative_part).resolve())
                            return result

                    if path_obj.exists():
                        result = str(path_obj.resolve())
                        return result

                # Check for relative suffix match
                if repo_relative_suffix_path and path.startswith(repo_relative_suffix_path + "/"):
                    suffix_after_repo = path[len(repo_relative_suffix_path + "/"):]
                    result = str((repo_path / suffix_after_repo).resolve())
                    return result

                if repo_relative_suffix_path and path == repo_relative_suffix_path:
                    result = str(repo_path.resolve())
                    return result

                # Handle relative paths with navigation
                if ".." in path:
                    potential_result = (repo_path / path_obj).resolve()
                    try:
                        potential_result.relative_to(repo_path)
                        result = str(potential_result)
                        return result
                    except ValueError:
                        safe_filename = path_obj.name if path_obj.name else "file"
                        result = str((repo_path / safe_filename).resolve())
                        return result

                result = str((repo_path / path_obj).resolve())
                return result

            coder.io.abs_root_path = fixed_io_abs_root_path

        # CRITICAL FIX: Ensure GitRepo doesn't cause path doubling
        if hasattr(coder, 'repo') and coder.repo and hasattr(coder.repo, 'abs_root_path'):
            def fixed_repo_abs_root_path(path):
                """Fixed GitRepo version that prevents path doubling."""
                if not path:
                    return str(repo_path)

                path_obj = Path(path)
                if path_obj.is_absolute():
                    result = str(path_obj.resolve())
                    return result

                # Same logic as above to prevent multiple concatenations
                repo_path_str = str(repo_path)

                # For paths like "/a0/share/calculator", extract "share/calculator" as the relative part
                repo_relative_suffix = str(repo_path).split("/")[-2:] if len(str(repo_path).split("/")) >= 2 else []
                repo_relative_suffix_path = "/".join(repo_relative_suffix) if repo_relative_suffix else ""

                if repo_path_str in path:
                    if path.startswith(repo_path_str):
                        relative_part = path[len(repo_path_str):].lstrip('/')
                        if relative_part:
                            result = str((repo_path / relative_part).resolve())
                            return result

                    if path_obj.exists():
                        result = str(path_obj.resolve())
                        return result

                # Check for relative suffix match
                if repo_relative_suffix_path and path.startswith(repo_relative_suffix_path + "/"):
                    suffix_after_repo = path[len(repo_relative_suffix_path + "/"):]
                    result = str((repo_path / suffix_after_repo).resolve())
                    return result

                if repo_relative_suffix_path and path == repo_relative_suffix_path:
                    result = str(repo_path.resolve())
                    return result

                # Handle relative paths with navigation
                if ".." in path:
                    potential_result = (repo_path / path_obj).resolve()
                    try:
                        potential_result.relative_to(repo_path)
                        result = str(potential_result)
                        return result
                    except ValueError:
                        safe_filename = path_obj.name if path_obj.name else "file"
                        result = str((repo_path / safe_filename).resolve())
                        return result

                result = str((repo_path / path_obj).resolve())
                return result

            coder.repo.abs_root_path = fixed_repo_abs_root_path

        # Explicitly set the root directory to ensure proper context
        coder.root = str(repo_path)

        # If the coder has a repo_map, ensure it uses the correct base directory
        if hasattr(coder, 'repo_map') and coder.repo_map:
            # Set all directory-related attributes to avoid any cwd confusion
            if hasattr(coder.repo_map, 'root'):
                coder.repo_map.root = str(repo_path)

            # Set git_dname if it exists to ensure proper git context
            if hasattr(coder.repo_map, 'git_dname'):
                coder.repo_map.git_dname = str(repo_path)

            # Set working directory context if available
            if hasattr(coder.repo_map, 'working_dir'):
                coder.repo_map.working_dir = str(repo_path)

            # Set base directory if available
            if hasattr(coder.repo_map, 'base_dir'):
                coder.repo_map.base_dir = str(repo_path)

            # Force refresh of repo map with new paths
            if hasattr(coder.repo_map, 'refresh'):
                try:
                    coder.repo_map.refresh()
                except Exception:
                    pass  # Non-critical operation

        # Disable threading features that conflict with web servers
        coder.ok_to_warm_cache = False

        # Update commands reference
        commands.coder = coder

        # Create the streaming wrapper
        streaming_wrapper = StreamingAiderWrapper(coder)
        response_capture = streaming_wrapper.response_capture

        return streaming_wrapper, response_capture

    except Exception as e:
        PrintStyle().error(f"Error creating aider coder: {e}")
        import traceback
        traceback.print_exc()
        raise


# Cleanup function for application shutdown
def cleanup_aider_resources():
    """Call this during application shutdown to clean up aider resources."""
    pass  # Simplified - no resources to clean up
