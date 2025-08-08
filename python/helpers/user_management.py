"""
User management system for Agent Zero multitenancy.
Handles user authentication, user context, and user data isolation.
"""

import json
import os
import bcrypt
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from python.helpers import files
import re
from python.helpers.print_style import PrintStyle

# Silence all debug output in this module

def _silent_print(*args, **kwargs):
    return None

print = _silent_print  # type: ignore


def _log_migration(message: str) -> None:
    try:
        PrintStyle.info(message)
    except Exception:
        pass

# Thread-local storage for current user context
_thread_local = threading.local()

# One-time guard for Stage 6 migrations
_migrations_lock = threading.Lock()
_stage6_migrations_done: bool = False
_integrity_users_done: bool = False


# RFC-accessible functions for system command execution
def _execute_system_command_in_container(command: List[str], capture_output: bool, text: bool, check: bool, input_data: str) -> dict:
    """This function will be executed inside the Docker container via RFC"""
    import subprocess
    try:
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=text,
            check=check,
            input=input_data
        )
        # Return serializable dictionary
        return {
            'args': result.args,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        # Return a mock result dictionary for consistency
        return {
            'args': command,
            'returncode': 1,
            'stdout': "",
            'stderr': str(e)
        }


def _write_file_as_root_in_container(file_path: str, content: str, permissions: str) -> dict:
    """Write file with root permissions inside the container"""
    import subprocess

    try:
        # Create parent directory
        parent_dir_cmd = ['dirname', file_path]
        parent_result = subprocess.run(parent_dir_cmd, capture_output=True, text=True)
        if parent_result.returncode == 0:
            parent_dir = parent_result.stdout.strip()
            subprocess.run(['mkdir', '-p', parent_dir], capture_output=True)

        # Write content using cat with here-doc to avoid shell escaping issues
        write_cmd = ['sh', '-c', f'cat > "{file_path}" << \'EOF\'\n{content}\nEOF']
        write_result = subprocess.run(write_cmd, capture_output=True, text=True)

        success = write_result.returncode == 0

        if success and permissions:
            # Set permissions
            subprocess.run(['chmod', permissions, file_path], capture_output=True)

        return {
            'success': success,
            'returncode': write_result.returncode,
            'stderr': write_result.stderr if write_result.stderr else ""
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': 1,
            'stderr': str(e)
        }


def _check_file_exists_in_container(file_path: str) -> bool:
    """Check if file exists inside the container - RFC accessible"""
    import subprocess
    try:
        result = subprocess.run(['test', '-e', file_path], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def _create_directory_in_container(dir_path: str) -> bool:
    """Create directory inside the container - RFC accessible"""
    import subprocess
    try:
        result = subprocess.run(['mkdir', '-p', dir_path], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def _write_migration_marker_in_container(marker_path: str, content: str) -> dict:
    """Write migration marker file inside the container - RFC accessible"""
    import subprocess
    import tempfile

    try:
        # Create parent directory first
        parent_dir = subprocess.run(['dirname', marker_path], capture_output=True, text=True)
        if parent_dir.returncode == 0:
            subprocess.run(['mkdir', '-p', parent_dir.stdout.strip()], capture_output=True)

        # Write to temp file then move to target
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        # Move temp file to target location
        result = subprocess.run(['mv', temp_path, marker_path], capture_output=True)

        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stderr': result.stderr.decode() if result.stderr else ""
        }
    except Exception as e:
        return {
            'success': False,
            'returncode': 1,
            'stderr': str(e)
        }


# Global default sudo commands configuration
class DefaultSudoCommands:
    """Management of default sudo commands for regular users"""

    DEFAULT_COMMANDS = [
        "apt update", "apt install", "apt remove", "apt upgrade",
        "pip install", "pip uninstall", "pip upgrade",
        "systemctl status", "systemctl restart", "systemctl stop", "systemctl start",
        "mount", "umount",
        "chmod", "chown", "chgrp",
        "mkdir -p", "rm -rf",
        "docker ps", "docker logs", "docker exec",
        "git clone", "git pull", "git push",
        "wget", "curl",
        "unzip", "tar -xzf", "tar -czf"
    ]

    @staticmethod
    def get_default_commands() -> List[str]:
        """Get current default commands (from admin settings or fallback)"""
        try:
            # Try to get from admin settings via AdminSudoManager
            manager = get_admin_sudo_manager()
            return manager.get_global_default_commands()
        except Exception:
            # Fallback to hardcoded defaults if admin settings not available
            return DefaultSudoCommands.DEFAULT_COMMANDS.copy()

    @staticmethod
    def validate_sudo_command(command: str) -> bool:
        """Validate that a sudo command is safe and properly formatted"""
        if not command or not command.strip():
            return False

        # Basic validation - no shell injection patterns
        dangerous_patterns = [';', '&&', '||', '|', '>', '<', '`', '$', '\\']
        for pattern in dangerous_patterns:
            if pattern in command:
                return False

        return True

    @staticmethod
    def sanitize_command_list(commands: List[str]) -> List[str]:
        """Sanitize and validate a list of sudo commands"""
        sanitized = []
        for cmd in commands:
            if isinstance(cmd, str) and DefaultSudoCommands.validate_sudo_command(cmd):
                sanitized.append(cmd.strip())
        return sanitized


@dataclass
class User:
    """User data model"""
    username: str
    password_hash: str
    is_admin: bool
    created_at: datetime
    system_username: str = ""  # Linux system username (root for admins, a0-username for regular users)
    sudo_commands: List[str] = field(default_factory=list)  # Whitelisted sudo commands for regular users
    system_user_created: bool = False  # Track if system user has been created
    venv_path: str = ""  # Path to user's Python virtual environment
    venv_created: bool = False  # Track if venv has been created
    plaintext_password: str = ""  # Plaintext password for SSH authentication (dev/container use)

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for JSON serialization"""
        return {
            'username': self.username,
            'password_hash': self.password_hash,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat(),
            'system_username': self.system_username,
            'sudo_commands': self.sudo_commands,
            'system_user_created': self.system_user_created,
            'venv_path': self.venv_path,
            'venv_created': self.venv_created,
            'plaintext_password': self.plaintext_password
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create user from dictionary"""
        return cls(
            username=data['username'],
            password_hash=data['password_hash'],
            is_admin=data['is_admin'],
            created_at=datetime.fromisoformat(data['created_at']),
            system_username=data.get('system_username', ''),
            sudo_commands=data.get('sudo_commands', []),
            system_user_created=data.get('system_user_created', False),
            venv_path=data.get('venv_path', ''),
            venv_created=data.get('venv_created', False),
            plaintext_password=data.get('plaintext_password', '')
        )


class UserManager:
    """Manages user authentication and user data persistence"""

    # Class-level flag to ensure migration only runs once across all instances
    _global_migration_checked = False

    def __init__(self, user_file: Optional[str] = None):
        self.user_file = user_file or os.path.join(files.get_base_dir(), "tmp", "users.json")
        self.users: Dict[str, User] = {}
        self.system_router = SystemCommandRouter()
        # Central storage for current username to support non-request contexts
        self._central_current_username: Optional[str] = None
        self._load_users()

    def _load_users(self) -> None:
        """Load users from the JSON file"""
        if os.path.exists(self.user_file):
            try:
                with open(self.user_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for username, user_data in data.items():
                        self.users[username] = User.from_dict(user_data)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # If file is corrupted, start fresh but log the error
                print(f"Warning: Could not load users file {self.user_file}: {e}")
                self.users = {}

    def _save_users(self) -> None:
        """Save users to the JSON file"""
        os.makedirs(os.path.dirname(self.user_file), exist_ok=True)

        data = {}
        for username, user in self.users.items():
            data[username] = user.to_dict()

        with open(self.user_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_user(self, username: str, password: str, is_admin: bool) -> User:
        """Create a new user"""
        if username in self.users:
            raise ValueError(f"User '{username}' already exists")

        # Hash the password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Generate system username
        if is_admin:
            system_username = "root"  # Admin users map to root
        else:
            system_username = f"a0-{username}"  # Regular users get prefixed usernames

        # Get default sudo commands for regular users
        sudo_commands = [] if is_admin else DefaultSudoCommands.get_default_commands()

        # Generate venv path
        venv_path = self.get_user_venv_path(username)

        # Create user
        user = User(
            username=username,
            password_hash=password_hash,
            is_admin=is_admin,
            created_at=datetime.now(timezone.utc),
            system_username=system_username,
            sudo_commands=sudo_commands,
            system_user_created=False,  # Will be set to True when system user is actually created
            venv_path=venv_path,
            venv_created=False,  # Will be set to True when venv is actually created
            plaintext_password=password  # Store plaintext password for SSH authentication
        )

        # Store user
        self.users[username] = user
        self._save_users()

        # Ensure user data directories exist
        self.ensure_user_data_directories(username)

        # Create system user first (if not in testing/restricted environment)
        self.ensure_system_user(username)

        # Create user's virtual environment (after system user exists)
        self.create_user_venv(username)

        return user

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user with username and password"""
        user = self.users.get(username)
        if not user:
            return False

        return bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8'))

    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username"""
        return self.users.get(username)

    def list_users(self) -> List[User]:
        """List all users"""
        return list(self.users.values())

    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        if username not in self.users:
            return False

        # Check if this is the only admin user
        user_to_delete = self.users[username]
        if user_to_delete.is_admin:
            admin_count = sum(1 for user in self.users.values() if user.is_admin)
            if admin_count <= 1:
                raise ValueError("Cannot delete the only admin user")

        # Delete user's virtual environment
        self.delete_user_venv(username)

        # Delete system user and sudoers entry
        self.remove_sudoers_entry(username)
        self.delete_system_user(username)

        # Delete user
        del self.users[username]
        self._save_users()

        return True

    def update_user(self, username: str, password: Optional[str] = None, is_admin: Optional[bool] = None) -> bool:
        """Update user information"""
        user = self.users.get(username)
        if not user:
            return False

        # Update password if provided
        if password is not None:
            user.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user.plaintext_password = password  # Also update plaintext for SSH authentication

        # Update admin status if provided
        if is_admin is not None:
            # Check if we're trying to remove admin rights from the only admin
            if not is_admin and user.is_admin:
                admin_count = sum(1 for u in self.users.values() if u.is_admin)
                if admin_count <= 1:
                    raise ValueError("Cannot remove admin rights from the only admin user")
            user.is_admin = is_admin

        self._save_users()
        return True

    def update_user_sudo_commands(self, username: str, sudo_commands: List[str]) -> bool:
        """Update sudo commands for a user (regular users only)"""
        user = self.users.get(username)
        if not user:
            return False

        if user.is_admin:
            # Admin users don't use sudo commands (they have root access)
            return True

        # Sanitize and validate commands
        sanitized_commands = DefaultSudoCommands.sanitize_command_list(sudo_commands)
        user.sudo_commands = sanitized_commands

        self._save_users()

        # Update sudoers entry if system user exists
        if user.system_user_created:
            self.setup_sudoers_entry(username)

        return True

    def get_system_username(self, username: str) -> str:
        """Get system username for Agent Zero user"""
        user = self.users.get(username)
        if not user:
            return ""
        return user.system_username

    def is_admin_user(self, username: str) -> bool:
        """Check if user is admin (maps to root)"""
        user = self.users.get(username)
        return user.is_admin if user else False

    def get_current_username_safe(self) -> str:
        """Get current username using the most reliable method available"""
        # First try Flask session (most reliable for concurrent users)
        try:
            from flask import has_request_context, session
            if has_request_context():
                username = session.get('username')
                if username and isinstance(username, str):
                    return username
        except (ImportError, RuntimeError):
            pass

        # Next, try centrally stored username (set during authentication)
        try:
            if self._central_current_username:
                return self._central_current_username
        except Exception:
            pass

        # Fallback to thread-local storage
        try:
            return get_current_username()
        except RuntimeError:
            pass

        # Last resort: return default
        return "default"

    def get_user_venv_path(self, username: str) -> str:
        """Get the virtual environment path for a user"""
        from python.helpers import files

        user = self.users.get(username)
        if user and user.is_admin:
            # Admin users use the main project virtual environment
            # Check if we're in a container environment
            if os.path.exists("/a0"):
                # In container, look for existing venv patterns
                container_venv_options = [
                    "/a0/.venv",
                    "/a0/venv",
                    "/usr/local/lib/python3.12/site-packages"  # fallback to system python
                ]
                for venv_path in container_venv_options:
                    if os.path.exists(venv_path):
                        return venv_path
                # If no venv found, return the expected path
                return "/a0/.venv"
            else:
                # On host, use the standard .venv
                base_dir = files.get_base_dir()
                return os.path.join(base_dir, ".venv")

        # Regular users get their own venv
        # In development mode (Docker), use container paths
        if self.system_router.is_development:
            return f"/a0/venvs/{username}"
        else:
            # In production mode, use host paths
            base_dir = files.get_base_dir()
            return os.path.join(base_dir, "venvs", username)

    def create_user_venv(self, username: str, force_recreate: bool = False) -> bool:
        """Create a Python virtual environment for the user by copying the working venv"""
        user = self.users.get(username)
        if not user:
            return False

        venv_path = self.get_user_venv_path(username)

        # Admin users use the existing main venv or system Python
        if user.is_admin:
            if os.path.exists(venv_path):
                print(f"✅ Admin user '{username}' using existing virtual environment at: {venv_path}")
                user.venv_path = venv_path
                user.venv_created = True
                self._save_users()
                return True
            else:
                # In container environment, admin uses system Python
                print(f"✅ Admin user '{username}' using system Python environment")
                user.venv_path = venv_path  # Store the expected path even if it doesn't exist
                user.venv_created = True
                self._save_users()
                return True

        # Check if venv already exists for regular users
        venv_exists = False
        if self.system_router.is_development:
            from python.helpers import runtime
            try:
                result = runtime.call_development_function_sync(
                    _execute_system_command_in_container,
                    command=['test', '-d', venv_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    input_data=""
                )
                venv_exists = result['returncode'] == 0
            except Exception:
                venv_exists = False
        else:
            venv_exists = os.path.exists(venv_path)

        if venv_exists and not force_recreate:
            if user.venv_created and user.venv_path == venv_path:
                return True  # Already exists and is tracked

        # Remove existing venv if force_recreate
        if venv_exists and force_recreate:
            if self.system_router.is_development:
                self.system_router.run_system_command([
                    'rm', '-rf', venv_path
                ], capture_output=True, text=True, check=False)
            else:
                shutil.rmtree(venv_path)

        try:
            # Find the working source venv to copy from
            source_venv = None
            system_username = user.system_username

            if self.system_router.is_development:
                # In development mode, find the working venv in container
                potential_sources = ['/opt/venv', '/a0/.venv', '/a0/venv']
                from python.helpers import runtime

                for potential_source in potential_sources:
                    try:
                        result = runtime.call_development_function_sync(
                            _execute_system_command_in_container,
                            command=['test', '-d', potential_source],
                            capture_output=True,
                            text=True,
                            check=False,
                            input_data=""
                        )
                        if result['returncode'] == 0:
                            source_venv = potential_source
                            break
                    except Exception:
                        continue
            else:
                # In production mode, use the main .venv
                from python.helpers import files
                base_dir = files.get_base_dir()
                potential_source = os.path.join(base_dir, ".venv")
                if os.path.exists(potential_source):
                    source_venv = potential_source

            if not source_venv:
                print(f"❌ No source venv found to copy for user '{username}'")
                return False

            # Create venv directory structure with proper permissions
            venv_dir = os.path.dirname(venv_path)

            if self.system_router.is_development:
                # In container, create /a0/venvs with proper ownership
                self.system_router.run_system_command([
                    'mkdir', '-p', venv_dir
                ], capture_output=True, text=True, check=False)

                # Set ownership of venvs directory to allow user creation
                self.system_router.run_system_command([
                    'chown', 'root:a0-users', venv_dir
                ], capture_output=True, text=True, check=False)

                # Set permissions to allow group members to create subdirectories
                self.system_router.run_system_command([
                    'chmod', '775', venv_dir
                ], capture_output=True, text=True, check=False)
            else:
                # On host, use standard directory creation
                self.system_router.run_system_command([
                    'mkdir', '-p', venv_dir
                ], capture_output=True, text=True, check=False)

            print(f"Creating Python virtual environment for user '{username}' by copying {source_venv}")

            # Copy the working venv to user's location
            result_cp = self.system_router.run_system_command([
                'cp', '-r', source_venv, venv_path
            ], capture_output=True, text=True, check=False)

            if result_cp.returncode != 0:
                print(f"❌ Failed to copy venv: {result_cp.stderr}")
                return False

            # Set ownership to the target user
            if system_username and not user.is_admin:
                result_chown = self.system_router.run_system_command([
                    'chown', '-R', f'{system_username}:a0-users', venv_path
                ], capture_output=True, text=True, check=False)

                if result_chown.returncode != 0:
                    print(f"⚠️ Warning: Failed to set venv ownership: {result_chown.stderr}")
                else:
                    print(f"✅ Set venv ownership to {system_username}:a0-users")

                # Also ensure execute permissions on activate script
                activate_script = f"{venv_path}/bin/activate"
                chmod_result = self.system_router.run_system_command([
                    'chmod', '755', activate_script
                ], capture_output=True, text=True, check=False)

                if chmod_result.returncode == 0:
                    print("✅ Set execute permissions on activate script")
                else:
                    print(f"⚠️ Warning: Failed to set execute permissions: {chmod_result.stderr}")

            # Update the venv's configuration files to point to the new location
            if self.system_router.is_development:
                from python.helpers import runtime

                # Update pyvenv.cfg to point to correct paths
                pyvenv_cfg = f"{venv_path}/pyvenv.cfg"
                try:
                    # Read current config
                    result = runtime.call_development_function_sync(
                        _execute_system_command_in_container,
                        command=['cat', pyvenv_cfg],
                        capture_output=True,
                        text=True,
                        check=False,
                        input_data=""
                    )

                    if result['returncode'] == 0:
                        # Update the home path in the config
                        old_config = result['stdout']
                        new_config = old_config.replace(source_venv, venv_path)

                        # Write updated config
                        temp_config = f"/tmp/pyvenv_cfg_{username}"
                        runtime.call_development_function_sync(
                            _execute_system_command_in_container,
                            command=['bash', '-c', f'echo "{new_config}" > {temp_config}'],
                            capture_output=True,
                            text=True,
                            check=False,
                            input_data=""
                        )

                        runtime.call_development_function_sync(
                            _execute_system_command_in_container,
                            command=['mv', temp_config, pyvenv_cfg],
                            capture_output=True,
                            text=True,
                            check=False,
                            input_data=""
                        )

                except Exception as e:
                    print(f"⚠️ Warning: Could not update venv config: {e}")

            # Test the venv works
            if self.system_router.is_development:
                test_result = self.system_router.run_system_command([
                    f'{venv_path}/bin/python3', '--version'
                ], capture_output=True, text=True, check=False)

                if test_result.returncode == 0:
                    print(f"✅ Venv test successful: {test_result.stdout.strip()}")
                else:
                    print(f"⚠️ Venv test failed: {test_result.stderr}")

            # Update user record
            user.venv_path = venv_path
            user.venv_created = True
            self._save_users()

            print(f"✅ Virtual environment created successfully for user '{username}'")
            return True

        except Exception as e:
            print(f"❌ Unexpected error creating virtual environment for user '{username}': {e}")
            return False

    def delete_user_venv(self, username: str) -> bool:
        """Delete a user's virtual environment"""
        user = self.users.get(username)
        if not user:
            return False

        # Admin users use the main venv - don't delete it
        if user.is_admin:
            print(f"Cannot delete main virtual environment for admin user '{username}'")
            return False

        venv_path = user.venv_path or self.get_user_venv_path(username)

        try:
            if os.path.exists(venv_path):
                print(f"Deleting virtual environment for user '{username}': {venv_path}")
                shutil.rmtree(venv_path)

            # Update user record
            user.venv_path = ""
            user.venv_created = False
            self._save_users()

            print(f"✅ Virtual environment deleted for user '{username}'")
            return True

        except Exception as e:
            print(f"❌ Error deleting virtual environment for user '{username}': {e}")
            return False

    def ensure_user_venv(self, username: str) -> bool:
        """Ensure user has a virtual environment (create if missing)"""
        user = self.users.get(username)
        if not user:
            return False

        if user.venv_created and user.venv_path and os.path.exists(user.venv_path):
            return True  # Already exists

        return self.create_user_venv(username)

    def ensure_a0_users_group(self) -> bool:
        """Ensure the a0-users group exists for shared access"""
        try:
            # Check if group exists
            result = self.system_router.run_system_command(['getent', 'group', 'a0-users'], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return True  # Group already exists

            # Create a0-users group
            print("Creating a0-users group for shared access...")
            result = self.system_router.run_system_command(['groupadd', 'a0-users'], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print("✅ a0-users group created successfully")
                return True
            else:
                print(f"❌ Failed to create a0-users group: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Unexpected error creating a0-users group: {e}")
            return False

    def setup_webapp_user_permissions(self) -> bool:
        """Add the current web app user to a0-users group"""
        try:
            # In development mode, skip webapp user setup since host user doesn't exist in container
            if self.system_router.is_development:
                print("ℹ️  Skipping webapp user setup in development mode (container environment)")
                return True

            # Get current user (web app user)
            current_user = os.getenv('USER', 'www-data')  # fallback to www-data

            # Check if user exists first
            result = self.system_router.run_system_command(['id', current_user], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"ℹ️  Web app user '{current_user}' does not exist, skipping group setup")
                return True

            # Check if user is already in group
            result = self.system_router.run_system_command(['groups', current_user], capture_output=True, text=True, check=False)
            if result.returncode == 0 and 'a0-users' in result.stdout:
                return True  # Already in group

            # Add web app user to a0-users group
            print(f"Adding web app user '{current_user}' to a0-users group...")
            result = self.system_router.run_system_command(['usermod', '-a', '-G', 'a0-users', current_user], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"✅ Web app user '{current_user}' added to a0-users group")
                return True
            else:
                print(f"❌ Failed to add web app user to group: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Unexpected error setting up web app user permissions: {e}")
            return False

    def create_system_user(self, username: str) -> bool:
        """Create a Linux system user for the Agent Zero user"""
        user = self.users.get(username)
        if not user:
            return False

        if user.system_user_created:
            return True  # Already created

        try:
            # Skip system user creation for admin users (they use root)
            if user.is_admin:
                print(f"Admin user '{username}' maps to root - no system user creation needed")
                user.system_user_created = True
                self._save_users()
                return True

            system_username = user.system_username
            if not system_username:
                print(f"❌ No system username configured for user '{username}'")
                return False

            # Check if system user already exists
            result = self.system_router.run_system_command(['id', system_username], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"System user '{system_username}' already exists")
                user.system_user_created = True
                self._save_users()
                return True

            # Create system user with restricted shell
            print(f"Creating system user: {system_username}")
            result = self.system_router.run_system_command([
                'useradd',
                '--create-home',
                '--shell', '/bin/bash',
                '--comment', f'Agent Zero user for {username}',
                system_username
            ], capture_output=True, text=True, check=False)

            if result.returncode != 0:
                print(f"❌ Failed to create system user: {result.stderr}")
                return False

            # Set password for the system user for SSH authentication
            if user.plaintext_password:
                print(f"Setting password for system user: {system_username}")
                # Use chpasswd to set password
                password_input = f"{system_username}:{user.plaintext_password}"
                result = self.system_router.run_system_command([
                    'chpasswd'
                ], capture_output=True, text=True, check=False, input_data=password_input)
                if result.returncode != 0:
                    print(f"⚠️ Warning: Failed to set password for system user: {result.stderr}")
                else:
                    print(f"✅ Password set for system user: {system_username}")

            # Set up user directories and permissions
            self._setup_system_user_directories(username, system_username)

            # Add user to a0-users group
            result = self.system_router.run_system_command([
                'usermod', '-a', '-G', 'a0-users', system_username
            ], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"❌ Failed to add user to a0-users group: {result.stderr}")

            # Update user record
            user.system_user_created = True
            self._save_users()

            print(f"✅ System user '{system_username}' created successfully for Agent Zero user '{username}'")
            return True

        except Exception as e:
            print(f"❌ Unexpected error creating system user for '{username}': {e}")
            return False

    def delete_system_user(self, username: str) -> bool:
        """Delete the Linux system user for the Agent Zero user"""
        user = self.users.get(username)
        if not user:
            return False

        # Skip deletion for admin users (they don't have dedicated system users)
        if user.is_admin:
            user.system_user_created = False
            self._save_users()
            return True

        system_username = user.system_username
        if not system_username:
            return True  # Nothing to delete

        try:
            # Check if system user exists
            result = self.system_router.run_system_command(['id', system_username], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"System user '{system_username}' does not exist")
                user.system_user_created = False
                self._save_users()
                return True

            # Delete system user and home directory
            print(f"Deleting system user: {system_username}")
            result = self.system_router.run_system_command(['userdel', '--remove', system_username], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"❌ Failed to delete system user: {result.stderr}")
                return False

            # Update user record
            user.system_user_created = False
            self._save_users()

            print(f"✅ System user '{system_username}' deleted successfully")
            return True

        except Exception as e:
            print(f"❌ Unexpected error deleting system user for '{username}': {e}")
            return False

    def setup_sudoers_entry(self, username: str) -> bool:
        """Set up sudoers entry for regular users with whitelisted commands"""
        user = self.users.get(username)
        if not user:
            return False

        # Skip sudoers setup for admin users (they use root)
        if user.is_admin:
            return True

        system_username = user.system_username
        if not system_username or not user.sudo_commands:
            return True  # No commands to whitelist

        try:
            # Create sudoers entry file
            sudoers_file = f"/etc/sudoers.d/a0-{username}"
            temp_file = f"/tmp/sudoers-{username}"

            # Generate proper sudoers content - each command on separate line
            sudoers_content = f"# Agent Zero sudo commands for user {username}\n"

            for cmd in user.sudo_commands:
                # Convert command to proper sudoers format
                if " " in cmd:
                    # Commands with arguments: find full path dynamically
                    parts = cmd.split(" ", 1)
                    base_cmd = parts[0]
                    args = parts[1] if len(parts) > 1 else ""

                    # Use 'which' to find the actual full path
                    full_cmd = self._find_command_path(base_cmd)
                    if full_cmd:
                        if args:
                            sudoers_content += f"{system_username} ALL=(ALL) NOPASSWD: {full_cmd} {args}\n"
                        else:
                            sudoers_content += f"{system_username} ALL=(ALL) NOPASSWD: {full_cmd}\n"
                    else:
                        print(f"⚠️ Warning: Command '{base_cmd}' not found, skipping")
                else:
                    # Single command without arguments
                    full_cmd = self._find_command_path(cmd)
                    if full_cmd:
                        sudoers_content += f"{system_username} ALL=(ALL) NOPASSWD: {full_cmd}\n"
                    else:
                        print(f"⚠️ Warning: Command '{cmd}' not found, skipping")

            # Write sudoers file to temp location first
            print(f"Setting up sudoers entry for system user: {system_username}")

            # Use system router to write temp file in container
            temp_write_success = self.system_router.write_file_as_root(temp_file, sudoers_content, "644")
            if not temp_write_success:
                print("❌ Failed to write temporary sudoers file")
                return False

            # Validate syntax BEFORE installing
            result = self.system_router.run_system_command(['visudo', '-c', '-f', temp_file], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print("❌ Invalid sudoers syntax in generated file:")
                print(f"   Error: {result.stderr}")
                print(f"   Content: {sudoers_content}")
                # Clean up temp file using system router
                self.system_router.run_system_command(['rm', '-f', temp_file], capture_output=True, text=True, check=False)
                return False

            # Only install if syntax is valid - use system router for file operations
            success = self.system_router.write_file_as_root(sudoers_file, sudoers_content, "440")
            if not success:
                print("❌ Cannot install sudoers file - system command failed")
                # Clean up temp file using system router
                self.system_router.run_system_command(['rm', '-f', temp_file], capture_output=True, text=True, check=False)
                return False

            # Clean up temp file using system router
            self.system_router.run_system_command(['rm', '-f', temp_file], capture_output=True, text=True, check=False)

            print(f"✅ Sudoers entry created for '{system_username}' with {len(user.sudo_commands)} whitelisted commands")
            return True

        except Exception as e:
            print(f"❌ Error setting up sudoers entry for '{username}': {e}")
            return False

    def _find_command_path(self, command: str) -> str | None:
        """Find the full path of a command using 'which'"""
        try:
            result = self.system_router.run_system_command(['which', command], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # Fallback to common locations - these would need RFC routing too in dev mode
                common_paths = ['/usr/bin/', '/bin/', '/usr/local/bin/']
                for path in common_paths:
                    full_path = f"{path}{command}"
                    # In development mode, we can't check os.path.exists on container paths
                    # so we'll just return the first common path match
                    if self.system_router.is_development:
                        return full_path
                    elif os.path.exists(full_path):
                        return full_path
                return None
        except Exception:
            return None

    def validate_sudo_command_safety(self, command: str) -> bool:
        """Validate that a sudo command is safe and properly formatted"""
        if not command or not command.strip():
            return False

        command = command.strip()

        # Basic length check
        if len(command) > 200:
            print(f"⚠️ Command too long (>{200} chars): {command[:50]}...")
            return False

        # Dangerous patterns that could lead to security issues
        dangerous_patterns = [
            ';',      # Command chaining
            '&&',     # Command chaining
            '||',     # Command chaining
            '|',      # Pipes (could be used maliciously)
            '>',      # Output redirection
            '<',      # Input redirection
            '`',      # Command substitution
            '$(',     # Command substitution
            '${',     # Variable substitution
            '\\',     # Escape sequences
            '\n',     # Newlines
            '\r',     # Carriage returns
            '\t',     # Tabs in inappropriate places
        ]

        for pattern in dangerous_patterns:
            if pattern in command:
                print(f"⚠️ Dangerous pattern '{pattern}' found in command: {command}")
                return False

        # Check for suspicious keywords
        suspicious_keywords = [
            'sudo',      # Recursive sudo
            'su',        # Switch user
            'passwd',    # Password changes
            'shadow',    # Shadow file access
            '/etc/passwd',   # User file access
            '/etc/shadow',   # Shadow file access
            'visudo',    # Sudoers editing
            'chmod 777',  # Dangerous permissions
            'rm -rf /',  # System destruction
            'dd if=',    # Disk operations
            'mkfs',      # Filesystem operations
            'fdisk',     # Disk partitioning
            'crontab',   # Cron access
            'systemctl enable',  # Service auto-start
        ]

        command_lower = command.lower()
        for keyword in suspicious_keywords:
            if keyword in command_lower:
                print(f"⚠️ Suspicious keyword '{keyword}' found in command: {command}")
                return False

        # Validate that command exists and is executable
        if ' ' in command:
            base_cmd = command.split(' ', 1)[0]
        else:
            base_cmd = command

        # Check if the base command exists
        cmd_path = self._find_command_path(base_cmd)
        if not cmd_path:
            print(f"⚠️ Command not found: {base_cmd}")
            return False

        # Additional validation for specific commands
        if base_cmd in ['rm', 'rmdir']:
            # Ensure rm commands don't target critical directories
            critical_dirs = ['/', '/etc', '/bin', '/usr', '/var', '/sys', '/proc']
            for critical_dir in critical_dirs:
                if critical_dir in command:
                    print(f"⚠️ Dangerous rm command targeting critical directory: {command}")
                    return False

        if base_cmd == 'chmod':
            # Prevent overly permissive chmod commands
            if '777' in command or '666' in command:
                print(f"⚠️ Overly permissive chmod command: {command}")
                return False

        return True

    def sanitize_system_username(self, username: str) -> str:
        """Ensure system username follows safe naming conventions"""
        if not username:
            return ""

        # Remove any dangerous characters
        # Only allow lowercase letters, numbers, hyphens, and underscores
        sanitized = re.sub(r'[^a-z0-9\-_]', '', username.lower())

        # Ensure it starts with a letter or underscore (Linux requirement)
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = f"u{sanitized}"

        # Limit length (Linux usernames should be <= 32 chars)
        if len(sanitized) > 32:
            sanitized = sanitized[:32]

        # Ensure it's not empty after sanitization
        if not sanitized:
            sanitized = "user"

        # Prevent reserved usernames
        reserved_names = [
            'root', 'bin', 'daemon', 'sys', 'adm', 'tty', 'disk', 'lp', 'mail',
            'news', 'uucp', 'man', 'proxy', 'kmem', 'dialout', 'fax', 'voice',
            'cdrom', 'floppy', 'tape', 'sudo', 'audio', 'dip', 'www-data',
            'backup', 'operator', 'list', 'irc', 'src', 'gnats', 'shadow',
            'utmp', 'video', 'sasl', 'plugdev', 'staff', 'games', 'users',
            'nogroup', 'systemd', 'mysql', 'postgres', 'apache', 'nginx'
        ]

        if sanitized in reserved_names:
            sanitized = f"a0-{sanitized}"

        return sanitized

    def validate_user_creation_input(self, username: str, password: str, is_admin: bool) -> tuple[bool, str]:
        """Validate user creation input for security"""
        # Username validation
        if not username or len(username.strip()) == 0:
            return False, "Username cannot be empty"

        username = username.strip()

        if len(username) < 3:
            return False, "Username must be at least 3 characters long"

        if len(username) > 50:
            return False, "Username cannot be longer than 50 characters"

        # Check for valid characters in username
        if not re.match(r'^[a-zA-Z0-9_\-]+$', username):
            return False, "Username can only contain letters, numbers, underscores, and hyphens"

        # Username should start with a letter
        if not username[0].isalpha():
            return False, "Username must start with a letter"

        # Password validation
        if not password or len(password) == 0:
            return False, "Password cannot be empty"

        if len(password) < 6:
            return False, "Password must be at least 6 characters long"

        if len(password) > 128:
            return False, "Password cannot be longer than 128 characters"

        # Check if username already exists
        if username in self.users:
            return False, f"User '{username}' already exists"

        # Admin user validation
        if is_admin:
            # Ensure we don't create too many admin users
            admin_count = sum(1 for user in self.users.values() if user.is_admin)
            if admin_count >= 5:  # Reasonable limit
                return False, "Too many admin users already exist (maximum 5 allowed)"

        return True, "Valid"

    def validate_system_environment(self) -> dict[str, bool]:
        """Validate that the system environment supports the security features"""
        checks = {
            'sudo_available': False,
            'visudo_available': False,
            'useradd_available': False,
            'userdel_available': False,
            'which_available': False,
            'chmod_available': False,
            'chown_available': False,
            'sudoers_directory_writable': False,
            'tmp_directory_writable': False
        }

        # Check if required commands are available
        required_commands = {
            'sudo': 'sudo_available',
            'visudo': 'visudo_available',
            'useradd': 'useradd_available',
            'userdel': 'userdel_available',
            'which': 'which_available',
            'chmod': 'chmod_available',
            'chown': 'chown_available'
        }

        for cmd, check_key in required_commands.items():
            try:
                result = subprocess.run(['which', cmd], capture_output=True, check=False)
                checks[check_key] = result.returncode == 0
            except Exception:
                checks[check_key] = False

        # Check directory permissions
        try:
            # Test if we can write to /tmp
            test_file = '/tmp/a0_test_write'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            checks['tmp_directory_writable'] = True
        except Exception:
            checks['tmp_directory_writable'] = False

        try:
            # Test if sudoers directory is accessible (not necessarily writable by us)
            checks['sudoers_directory_writable'] = os.path.exists('/etc/sudoers.d')
        except Exception:
            checks['sudoers_directory_writable'] = False

        return checks

    def security_audit_user(self, username: str) -> Dict[str, Any]:
        """Perform a security audit of a user's configuration"""
        user = self.users.get(username)
        if not user:
            return {'error': f"User '{username}' not found"}

        audit = {
            'username': username,
            'is_admin': user.is_admin,
            'system_username': user.system_username,
            'system_user_created': user.system_user_created,
            'sudo_commands_count': len(user.sudo_commands),
            'venv_created': user.venv_created,
            'issues': [],
            'warnings': [],
            'recommendations': []
        }

        # Check for security issues
        if user.is_admin and user.sudo_commands:
            audit['warnings'].append("Admin user has sudo commands (not needed - admins have root access)")

        if not user.is_admin and not user.sudo_commands:
            audit['warnings'].append("Regular user has no sudo commands (limited system access)")

        if user.system_user_created and not user.sudo_commands:
            audit['issues'].append("System user created but no sudo commands configured")

        if not user.venv_created:
            audit['recommendations'].append("Create Python virtual environment for user isolation")

        # Validate sudo commands
        invalid_commands = []
        for cmd in user.sudo_commands:
            if not self.validate_sudo_command_safety(cmd):
                invalid_commands.append(cmd)

        if invalid_commands:
            audit['issues'].append(f"Invalid/unsafe sudo commands: {invalid_commands}")

        # Check system username
        if user.system_username:
            sanitized = self.sanitize_system_username(user.username)
            expected = "root" if user.is_admin else f"a0-{sanitized}"
            if user.system_username != expected:
                audit['warnings'].append(f"Unusual system username: {user.system_username} (expected: {expected})")

        return audit

    def run_security_validation(self) -> Dict[str, Any]:
        """Run comprehensive security validation of the system"""
        print("🔒 Running Stage 7: Security & Validation...")

        validation_report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'environment_checks': self.validate_system_environment(),
            'user_audits': {},
            'global_issues': [],
            'recommendations': [],
            'overall_status': 'unknown'
        }

        # Audit all users
        for username in self.users.keys():
            validation_report['user_audits'][username] = self.security_audit_user(username)

        # Global security checks
        admin_count = sum(1 for user in self.users.values() if user.is_admin)
        if admin_count == 0:
            validation_report['global_issues'].append("No admin users found - system may be inaccessible")
        elif admin_count > 5:
            validation_report['global_issues'].append(f"Too many admin users ({admin_count}) - security risk")

        # Check environment capabilities
        env_checks = validation_report['environment_checks']
        missing_capabilities = [cmd for cmd, available in env_checks.items() if not available]
        if missing_capabilities:
            validation_report['recommendations'].append(
                f"Missing system capabilities: {missing_capabilities} - some features may not work"
            )

        # Determine overall status
        total_issues = len(validation_report['global_issues'])
        total_user_issues = sum(len(audit.get('issues', [])) for audit in validation_report['user_audits'].values())

        if total_issues == 0 and total_user_issues == 0:
            validation_report['overall_status'] = 'secure'
        elif total_issues > 0 or total_user_issues > 2:
            validation_report['overall_status'] = 'issues_found'
        else:
            validation_report['overall_status'] = 'warnings_only'

        # Print summary
        print(f"✅ Security validation completed - Status: {validation_report['overall_status']}")
        print(f"   Environment checks: {len([c for c in env_checks.values() if c])}/{len(env_checks)} passed")
        print(f"   Users audited: {len(validation_report['user_audits'])}")
        print(f"   Global issues: {total_issues}")
        print(f"   User issues: {total_user_issues}")

        return validation_report

    def remove_sudoers_entry(self, username: str) -> bool:
        """Remove sudoers entry for a user"""
        try:
            sudoers_file = f"/etc/sudoers.d/a0-{username}"

            # Check if sudoers file exists and remove it using system router
            file_exists = False
            if self.system_router.is_development:
                from python.helpers import runtime
                try:
                    result = runtime.call_development_function_sync(
                        _execute_system_command_in_container,
                        command=['test', '-f', sudoers_file],
                        capture_output=True,
                        text=True,
                        check=False,
                        input_data=""
                    )
                    file_exists = result['returncode'] == 0
                except Exception:
                    file_exists = False
            else:
                file_exists = os.path.exists(sudoers_file)

            if file_exists:
                print(f"Removing sudoers entry: {sudoers_file}")
                result = self.system_router.run_system_command(['rm', '-f', sudoers_file], capture_output=True, text=True, check=False)
                if result.returncode == 0:
                    print(f"✅ Sudoers entry removed for user '{username}'")
                else:
                    print(f"❌ Failed to remove sudoers entry: {result.stderr}")
            return True

        except Exception as e:
            print(f"❌ Error removing sudoers entry for '{username}': {e}")
            return False

    def _setup_system_user_directories(self, username: str, system_username: str) -> None:
        """Set up directories and permissions for system user"""
        try:
            from python.helpers import files

            # Get user data directories
            user_dirs = ['memory', 'knowledge', 'logs', 'tmp']
            base_dir = files.get_base_dir()

            for data_type in user_dirs:
                user_data_path = os.path.join(base_dir, data_type, username)

                # Check if directory exists using RFC-compatible method
                dir_exists = False
                if self.system_router.is_development:
                    from python.helpers import runtime
                    try:
                        result = runtime.call_development_function_sync(
                            _execute_system_command_in_container,
                            command=['test', '-d', user_data_path],
                            capture_output=True,
                            text=True,
                            check=False,
                            input_data=""
                        )
                        dir_exists = result['returncode'] == 0
                    except Exception:
                        dir_exists = False
                else:
                    dir_exists = os.path.exists(user_data_path)

                if dir_exists:
                    # Set ownership to system user but keep group as a0-users for web app access
                    self.system_router.run_system_command([
                        'chown', '-R', f'{system_username}:a0-users', user_data_path
                    ], capture_output=True, text=True, check=False)
                    # Set permissions: owner can read/write, group can read/write, others no access
                    self.system_router.run_system_command([
                        'chmod', '-R', '750', user_data_path
                    ], capture_output=True, text=True, check=False)

            # Set up venv directory permissions if it exists
            venv_path = self.get_user_venv_path(username)

            # Check if venv exists using RFC-compatible method
            venv_exists = False
            if self.system_router.is_development:
                from python.helpers import runtime
                try:
                    result = runtime.call_development_function_sync(
                        _execute_system_command_in_container,
                        command=['test', '-d', venv_path],
                        capture_output=True,
                        text=True,
                        check=False,
                        input_data=""
                    )
                    venv_exists = result['returncode'] == 0
                except Exception:
                    venv_exists = False
            else:
                venv_exists = os.path.exists(venv_path)

            if venv_exists:
                self.system_router.run_system_command([
                    'chown', '-R', f'{system_username}:a0-users', venv_path
                ], capture_output=True, text=True, check=False)
                self.system_router.run_system_command([
                    'chmod', '-R', '750', venv_path
                ], capture_output=True, text=True, check=False)

            print(f"✅ Directory permissions set up for system user '{system_username}'")

        except Exception as e:
            print(f"❌ Error setting up directories for system user '{system_username}': {e}")

    def ensure_system_user(self, username: str) -> bool:
        """Ensure system user exists for Agent Zero user (verify flag against actual system)."""
        user = self.users.get(username)
        if not user:
            return False

        # Admin users map to root; nothing to create
        if user.is_admin:
            user.system_user_created = True
            return True

        # Ensure system_username is set
        if not user.system_username:
            user.system_username = f"a0-{username}"

        # Verify actual presence regardless of stored flag
        try:
            result = self.system_router.run_system_command(['id', user.system_username], capture_output=True, text=True, check=False)
            exists = result.returncode == 0
        except Exception:
            exists = False

        if exists:
            # Keep flag in sync and ensure sudoers entry exists
            if not user.system_user_created:
                user.system_user_created = True
                self._save_users()
            self.setup_sudoers_entry(username)
            return True
        else:
            # If flag claimed created but not present, correct it
            if user.system_user_created:
                user.system_user_created = False
                self._save_users()

        # Create system user now
        if not self.create_system_user(username):
            return False

        # Set up sudoers entry for regular users
        if not user.is_admin:
            self.setup_sudoers_entry(username)

        return True

    def setup_system_user_infrastructure(self) -> None:
        """Set up the system user infrastructure (groups, permissions)"""
        print("🔄 Setting up system user infrastructure...")

        # Ensure a0-users group exists
        self.ensure_a0_users_group()

        # Set up web app user permissions
        self.setup_webapp_user_permissions()

        print("✅ System user infrastructure setup completed")

    def migrate_system_usernames_for_existing_users(self) -> None:
        """Update existing users to have proper system usernames and sudo commands"""
        print("🔄 Migrating system usernames for existing users...")

        migrated_count = 0
        for username, user in self.users.items():
            # Skip if user already has system username configured
            if user.system_username:
                continue

            # Generate system username based on admin status
            if user.is_admin:
                user.system_username = "root"
            else:
                user.system_username = f"a0-{username}"

            # Set default sudo commands for regular users (if they don't have any)
            if not user.is_admin and not user.sudo_commands:
                user.sudo_commands = DefaultSudoCommands.get_default_commands()

            migrated_count += 1
            print(f"   Updated user '{username}': system_username='{user.system_username}', sudo_commands={len(user.sudo_commands)}")

        if migrated_count > 0:
            self._save_users()
            print(f"✅ Migrated {migrated_count} existing users with system usernames")
        else:
            print("ℹ️  All existing users already have system usernames configured")

    def migrate_users_to_system_users(self) -> None:
        """One-time migration to create Linux system users for existing Agent Zero users"""
        print("🔄 Migrating existing users to system users...")

        # Ensure system infrastructure is set up first
        self.setup_system_user_infrastructure()

        migrated_count = 0
        failed_count = 0

        for username, user in self.users.items():
            if not user.system_user_created:
                print(f"Creating system user for: {username}")
                success = self.ensure_system_user(username)
                if success:
                    migrated_count += 1
                else:
                    failed_count += 1
                    print(f"⚠️ Failed to create system user for: {username}")

        # Summary (global stage6 marker is written elsewhere)
        if migrated_count > 0:
            print(f"✅ Successfully created system users for {migrated_count} existing users")
        if failed_count > 0:
            print(f"⚠️ Failed to create system users for {failed_count} users (this is normal in development environments)")

        print("ℹ️  System users migration completed")

    def setup_default_sudo_commands(self) -> None:
        """Add current global default sudo commands to existing users"""
        from python.helpers import files

        migration_marker = os.path.join(files.get_base_dir(), "tmp", ".sudo_defaults_migrated")

        # Skip if already migrated
        if os.path.exists(migration_marker):
            print("ℹ️  Sudo defaults migration already completed")
            return

        print("🔄 Migrating sudo defaults for existing users...")

        try:
            # Get admin sudo manager
            admin_manager = get_admin_sudo_manager()
            current_defaults = admin_manager.get_global_default_commands()

            migrated_count = 0
            for username, user in self.users.items():
                if not user.is_admin:  # Only apply to regular users
                    if not user.sudo_commands:  # Only if they don't have any commands yet
                        user.sudo_commands = current_defaults.copy()
                        migrated_count += 1
                        print(f"   Applied {len(current_defaults)} default commands to user: {username}")

            if migrated_count > 0:
                self._save_users()
                print(f"✅ Applied default sudo commands to {migrated_count} existing users")
            else:
                print("ℹ️  All existing users already have sudo commands configured")

            # Create migration marker
            os.makedirs(os.path.dirname(migration_marker), exist_ok=True)
            with open(migration_marker, 'w') as f:
                f.write(f"Sudo defaults migration completed at: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Applied defaults to: {migrated_count} users\n")
                f.write(f"Default commands count: {len(current_defaults)}\n")

        except Exception as e:
            print(f"⚠️ Error during sudo defaults migration: {e}")
            print("ℹ️  This is normal if admin settings are not yet available")

    def migrate_global_defaults(self) -> None:
        """Migrate from hardcoded defaults to admin-editable defaults"""
        from python.helpers import files

        migration_marker = os.path.join(files.get_base_dir(), "tmp", ".global_defaults_migrated")

        # Skip if already migrated
        if os.path.exists(migration_marker):
            print("ℹ️  Global defaults migration already completed")
            return

        print("🔄 Migrating to admin-editable global defaults...")

        try:
            # Initialize admin sudo manager and ensure defaults are stored
            admin_manager = get_admin_sudo_manager()

            # This will automatically store factory defaults in admin settings if not present
            current_defaults = admin_manager.get_global_default_commands()

            print(f"✅ Initialized admin-editable defaults with {len(current_defaults)} commands")

            # Create migration marker
            os.makedirs(os.path.dirname(migration_marker), exist_ok=True)
            with open(migration_marker, 'w') as f:
                f.write(f"Global defaults migration completed at: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Initialized with {len(current_defaults)} default commands\n")

        except Exception as e:
            print(f"⚠️ Error during global defaults migration: {e}")
            print("ℹ️  This is normal if admin settings are not yet available")

    def migrate_file_permissions(self) -> None:
        """Migrate existing file permissions to support both web app and system users"""
        from python.helpers import files

        migration_marker = os.path.join(files.get_base_dir(), "tmp", ".file_permissions_migrated")

        # Skip if already migrated
        if os.path.exists(migration_marker):
            print("ℹ️  File permissions migration already completed")
            return

        print("🔄 Migrating file permissions for system user support...")

        try:
            base_dir = files.get_base_dir()
            user_dirs = ['memory', 'knowledge', 'logs', 'tmp', 'venvs']

            migrated_dirs = 0
            failed_dirs = 0

            for data_type in user_dirs:
                data_dir = os.path.join(base_dir, data_type)
                if os.path.exists(data_dir):
                    try:
                        # Ensure all user subdirectories have proper group permissions
                        for item in os.listdir(data_dir):
                            user_data_path = os.path.join(data_dir, item)
                            if os.path.isdir(user_data_path):
                                # Get the user for this directory
                                user = self.get_user(item)
                                if user and user.system_user_created:
                                    system_username = user.system_username
                                    if system_username and system_username != "root":
                                        # Set ownership and permissions for system user
                                        try:
                                            subprocess.run([
                                                'sudo', 'chown', '-R',
                                                f'{system_username}:a0-users', user_data_path
                                            ], check=False, capture_output=True)
                                            subprocess.run([
                                                'sudo', 'chmod', '-R', '750', user_data_path
                                            ], check=False, capture_output=True)
                                            migrated_dirs += 1
                                        except Exception as e:
                                            print(f"⚠️ Could not update permissions for {user_data_path}: {e}")
                                            failed_dirs += 1

                    except Exception as e:
                        print(f"⚠️ Error processing directory {data_dir}: {e}")
                        failed_dirs += 1

            # Create migration marker
            os.makedirs(os.path.dirname(migration_marker), exist_ok=True)
            with open(migration_marker, 'w') as f:
                f.write(f"File permissions migration completed at: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Successfully updated: {migrated_dirs} directories\n")
                f.write(f"Failed updates: {failed_dirs} directories\n")

            if migrated_dirs > 0:
                print(f"✅ Updated permissions for {migrated_dirs} user directories")
            if failed_dirs > 0:
                print(f"⚠️ Failed to update {failed_dirs} directories (this is normal in development environments)")

            print("ℹ️  File permissions migration completed")

        except Exception as e:
            print(f"⚠️ Error during file permissions migration: {e}")
            print("ℹ️  This is normal in environments without sudo privileges")

    def run_stage6_migrations(self) -> None:
        """Run all Stage 6 migrations for backwards compatibility (once per process + marker)."""
        global _stage6_migrations_done
        if _stage6_migrations_done:
            return
        from python.helpers import files
        done_marker = os.path.join(files.get_base_dir(), "tmp", ".stage6_migrations_done")
        running_marker = os.path.join(files.get_base_dir(), "tmp", ".stage6_migrations_running")

        # If a completed marker exists, skip entirely
        try:
            if self._check_file_exists(done_marker):
                _stage6_migrations_done = True
                return
        except Exception:
            pass

        # If a running marker exists, skip (another process/thread is handling it)
        try:
            if self._check_file_exists(running_marker):
                return
        except Exception:
            pass

        with _migrations_lock:
            if _stage6_migrations_done:
                return
            try:
                if self._check_file_exists(done_marker):
                    _stage6_migrations_done = True
                    return
                if self._check_file_exists(running_marker):
                    return
            except Exception:
                pass

            # Try to atomically create the running marker
            created_running = False
            try:
                os.makedirs(os.path.dirname(running_marker), exist_ok=True)
                fd = os.open(running_marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(f"Stage 6 running at: {datetime.now(timezone.utc).isoformat()}\n")
                created_running = True
            except FileExistsError:
                # Another process beat us
                return
            except Exception:
                # Best effort: proceed without atomic marker
                pass

            _log_migration("Running Stage 6 migrations...")

            # Ensure existing users have proper system_username first
            _log_migration("[1/5] Initializing system usernames for existing users...")
            try:
                self.migrate_system_usernames_for_existing_users()
            except Exception as e:
                _log_migration(f"System username initialization skipped/failed: {e}")

            _log_migration("[2/5] Migrating Agent Zero users to system users...")
            self.migrate_users_to_system_users()

            _log_migration("[3/5] Ensuring default sudo commands for existing users...")
            self.setup_default_sudo_commands()

            _log_migration("[4/5] Migrating to admin-editable global defaults...")
            self.migrate_global_defaults()

            _log_migration("[5/5] Updating file permissions for system user support...")
            self.migrate_file_permissions()

            _stage6_migrations_done = True
            try:
                # Write done marker
                with open(done_marker, 'w') as f:
                    f.write(f"Stage 6 completed at: {datetime.now(timezone.utc).isoformat()}\n")
            except Exception:
                pass
            finally:
                if created_running:
                    try:
                        if os.path.exists(running_marker):
                            os.remove(running_marker)
                    except Exception:
                        pass

            _log_migration("Stage 6 migrations completed.")

    def migrate_venvs_for_existing_users(self) -> None:
        """Create virtual environments for existing users who don't have them"""
        # Check if venv migration was already completed
        venv_migration_marker = os.path.join(files.get_base_dir(), "tmp", ".venv_migration_completed")

        # Check marker existence using RFC in development mode
        marker_exists = self._check_file_exists(venv_migration_marker)
        if marker_exists:
            return

        print("🔄 Migrating virtual environments for existing users...")

        migrated_count = 0
        for username, user in self.users.items():
            if not user.venv_created or not user.venv_path:
                print(f"Creating venv for existing user: {username}")
                success = self.create_user_venv(username)
                if success:
                    migrated_count += 1
                else:
                    print(f"❌ Failed to create venv for user: {username}")

        if migrated_count > 0:
            print(f"✅ Created virtual environments for {migrated_count} existing users")
        else:
            print("ℹ️  All existing users already have virtual environments")

        # Mark venv migration as completed using RFC
        marker_content = f"Venv migration completed at: {datetime.now()}"
        self._write_migration_marker(venv_migration_marker, marker_content)

    def _check_file_exists(self, file_path: str) -> bool:
        """Check if file exists, using RFC in development mode"""
        from python.helpers.runtime import is_development

        if is_development():
            # Use existing RFC command execution
            from python.helpers import runtime
            try:
                result = runtime.call_development_function_sync(
                    _execute_system_command_in_container,
                    command=['test', '-e', file_path],
                    capture_output=True,
                    text=True,
                    check=False,
                    input_data=""
                )
                return result['returncode'] == 0
            except Exception:
                # Fallback to direct check if RFC fails
                return os.path.exists(file_path)
        else:
            # Direct check in production
            return os.path.exists(file_path)

    def _write_migration_marker(self, marker_path: str, content: str) -> bool:
        """Write migration marker, using RFC in development mode"""
        from python.helpers.runtime import is_development

        if is_development():
            # Use fixed RFC file write function
            from python.helpers import runtime
            try:
                result = runtime.call_development_function_sync(
                    _write_file_as_root_in_container,
                    file_path=marker_path,
                    content=content,
                    permissions="644"
                )
                return result.get('success', False) if isinstance(result, dict) else False
            except Exception as e:
                print(f"RFC write failed: {e}")
                return False
        else:
            # Direct write in production
            try:
                os.makedirs(os.path.dirname(marker_path), exist_ok=True)
                with open(marker_path, 'w') as f:
                    f.write(content)
                return True
            except Exception:
                return False

    def ensure_default_admin(self) -> User:
        """Ensure that the default admin user exists"""
        admin_user = self.get_user("admin")
        if not admin_user:
            admin_user = self.create_user("admin", "agent0", True)
        return admin_user

    def migrate_existing_data(self, base_dir: str) -> None:
        """Migrate existing data to admin user directory"""
        # This will be used to migrate existing data to the admin user
        # when upgrading from single-user to multi-user system
        # Note: ensure_default_admin() should already be called by the caller,
        # no need to call it again here to avoid recursive calls

        data_dirs = ['memory', 'knowledge', 'logs', 'tmp']

        for data_dir in data_dirs:
            old_path = os.path.join(base_dir, data_dir)
            new_path = os.path.join(base_dir, data_dir, 'admin')

            if os.path.exists(old_path) and not os.path.exists(new_path):
                # Create admin directory
                os.makedirs(new_path, exist_ok=True)

                # Move existing files to admin directory
                for item in os.listdir(old_path):
                    if item != 'admin':  # Don't move the admin directory itself
                        old_item_path = os.path.join(old_path, item)
                        new_item_path = os.path.join(new_path, item)

                        if os.path.isfile(old_item_path):
                            shutil.move(old_item_path, new_item_path)
                        elif os.path.isdir(old_item_path):
                            if not os.path.exists(new_item_path):
                                shutil.move(old_item_path, new_item_path)
                            else:
                                # If target exists, merge contents
                                for subitem in os.listdir(old_item_path):
                                    shutil.move(
                                        os.path.join(old_item_path, subitem),
                                        os.path.join(new_item_path, subitem)
                                    )
                                os.rmdir(old_item_path)

    def ensure_user_data_directories(self, username: str) -> None:
        """Ensure all user-specific data directories exist"""
        from python.helpers import files

        # Define all user data directory structures
        user_dirs = {
            'memory': ['default', 'embeddings'],
            'knowledge': {
                'default': ['main', 'fragments', 'solutions', 'instruments'],
                'custom': ['main', 'fragments', 'solutions', 'instruments']
            },
            'logs': [],
            'tmp': ['chats', 'scheduler', 'uploads', 'exports']
        }

        base_dir = files.get_base_dir()

        for data_type, subdirs in user_dirs.items():
            if isinstance(subdirs, dict):
                # Knowledge has nested structure
                for subdir, areas in subdirs.items():
                    for area in areas:
                        dir_path = os.path.join(base_dir, data_type, username, subdir, area)
                        os.makedirs(dir_path, exist_ok=True)
            else:
                # Simple list of subdirectories
                user_base = os.path.join(base_dir, data_type, username)
                os.makedirs(user_base, exist_ok=True)

                for subdir in subdirs:
                    dir_path = os.path.join(user_base, subdir)
                    os.makedirs(dir_path, exist_ok=True)

    def migrate_global_to_admin_if_needed(self) -> None:
        """One-time migration of global data to admin user directories"""
        # Skip if already checked globally (prevent multiple calls during startup)
        if UserManager._global_migration_checked:
            return

        UserManager._global_migration_checked = True

        from python.helpers import files

        migration_marker = os.path.join(files.get_base_dir(), "tmp", ".multitenancy_migrated")

        # Skip if already migrated
        if os.path.exists(migration_marker):
            return

        print("🔄 Migrating existing data to admin user...")

        # Ensure admin user data directories exist (but don't call ensure_default_admin to avoid recursion)
        self.ensure_user_data_directories("admin")

        # Get base directory for migration patterns
        base_dir = files.get_base_dir()

        # Migration patterns for each data type
        migrations = [
            # Memory: /memory/default → /memory/admin/default
            {
                'source_pattern': 'memory/default',
                'target_pattern': 'memory/admin/default',
                'description': 'Memory database'
            },
            {
                'source_pattern': 'memory/embeddings',
                'target_pattern': 'memory/admin/embeddings',
                'description': 'Memory embeddings cache'
            },
            # Knowledge: /knowledge/custom → /knowledge/admin/custom
            {
                'source_pattern': 'knowledge/custom',
                'target_pattern': 'knowledge/admin/custom',
                'description': 'Custom knowledge'
            },
            {
                'source_pattern': 'knowledge/default',
                'target_pattern': 'knowledge/admin/default',
                'description': 'Default knowledge (shared)'
            },
            # Logs: /logs/* → /logs/admin/*
            {
                'source_pattern': 'logs',
                'target_pattern': 'logs/admin',
                'description': 'Log files',
                'exclude_subdirs': ['admin']  # Don't move admin subdir
            },
            # Tmp data: /tmp/* → /tmp/admin/*
            {
                'source_pattern': 'tmp/chats',
                'target_pattern': 'tmp/admin/chats',
                'description': 'Chat history'
            },
            {
                'source_pattern': 'tmp/scheduler',
                'target_pattern': 'tmp/admin/scheduler',
                'description': 'Scheduled tasks'
            },
            {
                'source_pattern': 'tmp/uploads',
                'target_pattern': 'tmp/admin/uploads',
                'description': 'Uploaded files'
            },
            {
                'source_pattern': 'tmp/settings.json',
                'target_pattern': 'tmp/admin/settings.json',
                'description': 'Settings file'
            }
        ]

        migrated_items = []

        for migration in migrations:
            source_path = os.path.join(base_dir, migration['source_pattern'])
            target_path = os.path.join(base_dir, migration['target_pattern'])

            if os.path.exists(source_path):
                # Create target directory
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                if os.path.isfile(source_path):
                    # Move file
                    if not os.path.exists(target_path):
                        try:
                            shutil.move(source_path, target_path)
                            migrated_items.append(f"✅ {migration['description']}: {migration['source_pattern']} → {migration['target_pattern']}")
                        except PermissionError:
                            print(f"⚠️  Skipping {migration['source_pattern']} - permission denied")
                        except Exception as e:
                            print(f"⚠️  Skipping {migration['source_pattern']} - error: {e}")
                elif os.path.isdir(source_path):
                    # Move directory (with exclusions)
                    exclude_subdirs = migration.get('exclude_subdirs', [])

                    if not os.path.exists(target_path):
                        # Target doesn't exist, move entire directory
                        try:
                            shutil.move(source_path, target_path)
                            migrated_items.append(f"✅ {migration['description']}: {migration['source_pattern']} → {migration['target_pattern']}")
                        except PermissionError:
                            print(f"⚠️  Skipping {migration['source_pattern']} - permission denied")
                        except Exception as e:
                            print(f"⚠️  Skipping {migration['source_pattern']} - error: {e}")
                    else:
                        # Target exists, merge contents
                        for item in os.listdir(source_path):
                            if item in exclude_subdirs:
                                continue

                            source_item = os.path.join(source_path, item)
                            target_item = os.path.join(target_path, item)

                            if not os.path.exists(target_item):
                                try:
                                    shutil.move(source_item, target_item)
                                    migrated_items.append(f"📁 Moved {item} from {migration['description']}")
                                except PermissionError:
                                    print(f"⚠️  Skipping {item} - permission denied")
                                except Exception as e:
                                    print(f"⚠️  Skipping {item} - error: {e}")

        # Create migration marker
        with open(migration_marker, 'w') as f:
            f.write(f"Migration completed at: {os.popen('date').read().strip()}\n")
            f.write("Migrated items:\n")
            f.write("\n".join(migrated_items))

        if migrated_items:
            print(f"✅ Migration completed! Moved {len(migrated_items)} items to admin user.")
        else:
            print("ℹ️  No data to migrate (fresh installation).")

    def ensure_system_users_integrity(self) -> dict:
        """Idempotently ensure all users have corresponding Linux accounts and sudoers as needed."""
        created = 0
        updated_sudoers = 0
        for username, user in self.users.items():
            # Admin maps to root; skip sudoers
            if self.ensure_system_user(username):
                if not user.is_admin:
                    # setup_sudoers_entry is also called inside ensure_system_user when creating
                    # but we call again to ensure it's present and updated
                    if self.setup_sudoers_entry(username):
                        updated_sudoers += 1
                    # Ensure the user's shell loads their venv on login
                    try:
                        self.setup_user_shell_init(username)
                    except Exception:
                        pass
                # Count as created if flag is now true and previously was false
                # (we cannot detect prior value reliably here, so approximate by checking presence)
                try:
                    res = self.system_router.run_system_command(['id', user.system_username], capture_output=True, text=True, check=False)
                    if res.returncode == 0:
                        created += 1
                except Exception:
                    pass
        return {"ensured_users": created, "sudoers_updated": updated_sudoers}

    def setup_user_shell_init(self, username: str) -> bool:
        """Ensure the user's shell profile sources their virtual environment on login."""
        user = self.users.get(username)
        if not user:
            return False
        if user.is_admin:
            return True
        system_username = user.system_username or f"a0-{username}"
        venv_path = user.venv_path or self.get_user_venv_path(username)
        if not venv_path:
            return False

        home_dir = f"/home/{system_username}"
        activate_path = f"{venv_path}/bin/activate"
        conditional_line = f"[ -r {activate_path} ] && . {activate_path}"
        profile_files = [".bashrc", ".profile"]

        # Preemptively normalize venv ownership/permissions (best-effort)
        try:
            # Ensure entire venv directory is owned by the system user (recursive)
            self.system_router.run_system_command(
                ["chown", "-R", f"{system_username}:a0-users", venv_path],
                capture_output=True,
                text=True,
                check=False,
            )
            # Ensure directories are traversable and activate is readable
            self.system_router.run_system_command(
                ["bash", "-lc", f"find {venv_path} -type d -exec chmod 755 {{}} +"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.system_router.run_system_command(
                ["chmod", "755", f"{activate_path}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            pass

        for pf in profile_files:
            file_path = f"{home_dir}/{pf}"
            # Touch file
            self.system_router.run_system_command(["bash", "-lc", f"touch {file_path}"], capture_output=True, text=True, check=False)
            # Clean up any broken or duplicate lines referencing the activate script
            # Remove every line that contains the activate path to start clean
            self.system_router.run_system_command(
                [
                    "bash",
                    "-lc",
                    f"sed -i '\\|{activate_path}|d' {file_path}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            # Ensure only one correct conditional source line is present
            self.system_router.run_system_command(
                [
                    "bash",
                    "-lc",
                    f"grep -qxF '{conditional_line}' {file_path} || echo '{conditional_line}' >> {file_path}",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            # Fix ownership
            self.system_router.run_system_command(["chown", f"{system_username}:a0-users", file_path], capture_output=True, text=True, check=False)
            self.system_router.run_system_command(["touch", f"{home_dir}/.hushlogin"], capture_output=True, text=True, check=False)
        return True

    def set_central_current_username(self, username: Optional[str]) -> None:
        """Set or clear the centrally stored current username"""
        self._central_current_username = username

    def run_integrity_pass_once(self) -> None:
        """Run integrity pass exactly once per installation (guarded by file marker and in-process flag)."""
        global _integrity_users_done
        if _integrity_users_done:
            return
        from python.helpers import files
        done_marker = os.path.join(files.get_base_dir(), "tmp", ".integrity_users_done")
        running_marker = os.path.join(files.get_base_dir(), "tmp", ".integrity_users_running")

        # Fast path: if marker exists, skip
        try:
            if os.path.exists(done_marker):
                _integrity_users_done = True
                return
        except Exception:
            pass

        # Single-process guard using existing migrations lock
        with _migrations_lock:
            if _integrity_users_done:
                return
            try:
                if os.path.exists(done_marker):
                    _integrity_users_done = True
                    return
            except Exception:
                pass

            # Atomically create running marker to prevent concurrent executions across processes
            created_running = False
            try:
                os.makedirs(os.path.dirname(running_marker), exist_ok=True)
                fd = os.open(running_marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(f"Integrity running at: {datetime.now(timezone.utc).isoformat()}\n")
                created_running = True
            except FileExistsError:
                return
            except Exception:
                # Proceed without running marker if atomic create fails for non-critical reasons
                pass

            try:
                # Run integrity and write done marker (best-effort)
                info = self.ensure_system_users_integrity()
                try:
                    os.makedirs(os.path.dirname(done_marker), exist_ok=True)
                    with open(done_marker, 'w') as f:
                        f.write(f"Integrity ensured at: {datetime.now(timezone.utc).isoformat()}\n")
                        f.write(json.dumps(info))
                except Exception:
                    pass
                _integrity_users_done = True
            finally:
                if created_running:
                    try:
                        if os.path.exists(running_marker):
                            os.remove(running_marker)
                    except Exception:
                        pass


# Global user manager instance
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """Get the global user manager instance"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
        _user_manager.ensure_default_admin()
        try:
            _user_manager.run_stage6_migrations()
            # Perform integrity pass only once per installation
            try:
                _user_manager.run_integrity_pass_once()
            except Exception as e:
                _log_migration(f"Integrity pass skipped/failed: {e}")
        except Exception as e:
            _log_migration(f"Migration initialization error: {e}")
    return _user_manager


def get_current_user() -> User:
    """Get the current user from thread-local storage"""
    user = getattr(_thread_local, 'current_user', None)
    if user is None:
        raise RuntimeError("No authenticated user in current context")
    return user


def set_current_user(user: Optional[User]) -> None:
    """Set the current user in thread-local storage"""
    _thread_local.current_user = user


def get_current_username() -> str:
    """Get the current username"""
    return get_current_user().username


def is_current_user_admin() -> bool:
    """Check if the current user is an admin"""
    return get_current_user().is_admin


def require_admin() -> None:
    """Raise an exception if the current user is not an admin"""
    if not is_current_user_admin():
        raise PermissionError("Admin privileges required")


class AdminSudoManager:
    """Manages global default sudo commands for new regular users"""

    GLOBAL_SUDO_DEFAULTS_KEY = "system_sudo_default_commands"

    def __init__(self):
        self.user_manager = None  # Will be set when needed to avoid circular imports

    def _get_user_manager(self):
        """Get user manager instance, avoiding circular imports"""
        if self.user_manager is None:
            self.user_manager = get_user_manager()
        return self.user_manager

    def _get_admin_settings(self) -> dict:
        """Get admin user settings where global defaults are stored"""
        try:
            from python.helpers.settings import get_settings

            # Use admin settings directly (since global defaults are stored in admin settings)
            # We temporarily set admin as current user to access their settings
            current_user_backup = getattr(_thread_local, 'current_user', None)

            try:
                admin_user = self._get_user_manager().get_user("admin")
                if admin_user:
                    _thread_local.current_user = admin_user
                    settings = get_settings()
                    # Convert Settings object to plain dict for easier access
                    settings_dict = {}
                    for key in settings:
                        settings_dict[key] = settings[key]
                    return settings_dict
                else:
                    raise RuntimeError("Admin user not found")
            finally:
                # Restore original user context
                _thread_local.current_user = current_user_backup

        except Exception as e:
            print(f"Warning: Could not get admin settings: {e}")
            return {}

    def _update_admin_settings(self, key: str, value: Any) -> bool:
        """Update admin user settings"""
        try:
            from python.helpers.settings import set_settings_delta

            # Temporarily set admin as current user to update their settings
            current_user_backup = getattr(_thread_local, 'current_user', None)

            try:
                admin_user = self._get_user_manager().get_user("admin")
                if admin_user:
                    _thread_local.current_user = admin_user
                    set_settings_delta({key: value})
                    return True
                else:
                    raise RuntimeError("Admin user not found")
            finally:
                # Restore original user context
                _thread_local.current_user = current_user_backup

        except Exception as e:
            print(f"Error updating admin settings: {e}")
            return False

    def get_global_default_commands(self) -> List[str]:
        """Get current global default sudo commands"""
        try:
            admin_settings = self._get_admin_settings()
            commands = admin_settings.get(self.GLOBAL_SUDO_DEFAULTS_KEY, [])

            # If no commands in settings, use factory defaults
            if not commands:
                commands = DefaultSudoCommands.DEFAULT_COMMANDS.copy()
                # Store them in admin settings for future use
                self._update_admin_settings(self.GLOBAL_SUDO_DEFAULTS_KEY, commands)

            return commands
        except Exception as e:
            print(f"Warning: Could not get global default commands: {e}")
            return DefaultSudoCommands.DEFAULT_COMMANDS.copy()

    def update_global_default_commands(self, commands: List[str]) -> bool:
        """Update global default commands (admin only)"""
        try:
            # Validate and sanitize commands
            sanitized_commands = DefaultSudoCommands.sanitize_command_list(commands)

            if not sanitized_commands:
                print("Error: No valid commands provided")
                return False

            # Update admin settings
            success = self._update_admin_settings(self.GLOBAL_SUDO_DEFAULTS_KEY, sanitized_commands)

            if success:
                print(f"✅ Updated global default sudo commands ({len(sanitized_commands)} commands)")

            return success
        except Exception as e:
            print(f"Error updating global default commands: {e}")
            return False

    def reset_to_factory_defaults(self) -> bool:
        """Reset to hardcoded factory defaults"""
        try:
            factory_defaults = DefaultSudoCommands.DEFAULT_COMMANDS.copy()
            success = self._update_admin_settings(self.GLOBAL_SUDO_DEFAULTS_KEY, factory_defaults)

            if success:
                print(f"✅ Reset to factory defaults ({len(factory_defaults)} commands)")

            return success
        except Exception as e:
            print(f"Error resetting to factory defaults: {e}")
            return False

    def apply_defaults_to_user(self, username: str, merge: bool = True) -> bool:
        """Apply current defaults to specific user"""
        try:
            user_manager = self._get_user_manager()
            user = user_manager.get_user(username)

            if not user:
                print(f"Error: User '{username}' not found")
                return False

            if user.is_admin:
                print(f"Info: Skipping admin user '{username}' (admins don't use sudo commands)")
                return True

            current_defaults = self.get_global_default_commands()

            if merge:
                # Merge with existing commands (union)
                existing_commands = set(user.sudo_commands)
                new_commands = set(current_defaults)
                merged_commands = list(existing_commands.union(new_commands))
            else:
                # Replace existing commands
                merged_commands = current_defaults.copy()

            # Update user's sudo commands
            success = user_manager.update_user_sudo_commands(username, merged_commands)

            if success:
                action = "merged with" if merge else "replaced"
                print(f"✅ Applied default commands to user '{username}' ({action} existing)")

            return success
        except Exception as e:
            print(f"Error applying defaults to user '{username}': {e}")
            return False

    def apply_defaults_to_all_users(self, merge: bool = True) -> bool:
        """Apply current defaults to all users (admin operation)"""
        try:
            user_manager = self._get_user_manager()
            users = user_manager.list_users()

            success_count = 0
            total_users = 0

            for user in users:
                if not user.is_admin:  # Skip admin users
                    total_users += 1
                    if self.apply_defaults_to_user(user.username, merge):
                        success_count += 1

            if success_count == total_users:
                action = "merged with" if merge else "replaced"
                print(f"✅ Applied default commands to all {total_users} regular users ({action} existing)")
                return True
            else:
                print(f"⚠️ Applied defaults to {success_count}/{total_users} users (some failures)")
                return False

        except Exception as e:
            print(f"Error applying defaults to all users: {e}")
            return False

    def get_factory_defaults(self) -> List[str]:
        """Get the hardcoded factory default commands"""
        return DefaultSudoCommands.DEFAULT_COMMANDS.copy()


# Global admin sudo manager instance
_admin_sudo_manager: Optional[AdminSudoManager] = None


def get_admin_sudo_manager() -> AdminSudoManager:
    """Get the global admin sudo manager instance"""
    global _admin_sudo_manager
    if _admin_sudo_manager is None:
        _admin_sudo_manager = AdminSudoManager()
    return _admin_sudo_manager


class SystemCommandRouter:
    """Routes system commands through RFC in development mode or executes directly in production mode"""

    def __init__(self):
        from python.helpers import runtime
        self.is_development = runtime.is_development()

    def run_system_command(
        self,
        command: List[str],
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        input_data: str | None = None,
    ) -> subprocess.CompletedProcess:
        """
        Execute a system command, routing through RFC in development mode
        """
        if self.is_development:
            return self._run_command_via_rfc(command, capture_output, text, check, input_data)
        else:
            return self._run_command_direct(command, capture_output, text, check, input_data)

    def _run_command_direct(self, command: List[str], capture_output: bool, text: bool, check: bool, input_data: str | None) -> subprocess.CompletedProcess:
        """Execute command directly on the host system"""
        try:
            return subprocess.run(
                command,
                capture_output=capture_output,
                text=text,
                check=check,
                input=input_data
            )
        except Exception as e:
            # Return a mock CompletedProcess for consistency
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr=str(e)
            )

    def _run_command_via_rfc(
        self,
        command: List[str],
        capture_output: bool,
        text: bool,
        check: bool,
        input_data: str | None,
    ) -> subprocess.CompletedProcess:
        """Execute command via RFC to the Docker container"""
        from python.helpers import runtime

        try:
            # Use the synchronous RFC call wrapper
            result_dict = runtime.call_development_function_sync(
                _execute_system_command_in_container,
                command=command,
                capture_output=capture_output,
                text=text,
                check=check,
                input_data=input_data
            )

            # Convert dictionary back to CompletedProcess
            return subprocess.CompletedProcess(
                args=result_dict['args'],
                returncode=result_dict['returncode'],
                stdout=result_dict['stdout'],
                stderr=result_dict['stderr']
            )
        except Exception as e:
            print(f"❌ RFC system command failed: {e}")
            # Return a mock CompletedProcess for consistency
            return subprocess.CompletedProcess(
                args=command,
                returncode=1,
                stdout="",
                stderr=f"RFC Error: {str(e)}"
            )

    # This method now calls the module-level function

    def write_file_as_root(self, file_path: str, content: str, permissions: str = "644") -> bool:
        """Write a file with root permissions, routing through RFC in development mode"""
        if self.is_development:
            return self._write_file_as_root_via_rfc(file_path, content, permissions)
        else:
            return self._write_file_as_root_direct(file_path, content, permissions)

    def _write_file_as_root_direct(self, file_path: str, content: str, permissions: str) -> bool:
        """Write file with root permissions directly"""
        import tempfile
        try:
            # Write to temp file first
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name

            # Move to final location with sudo
            result = subprocess.run(['sudo', 'mv', temp_path, file_path], capture_output=True)
            if result.returncode != 0:
                os.remove(temp_path)  # Clean up temp file
                return False

            # Set permissions
            subprocess.run(['sudo', 'chmod', permissions, file_path])
            subprocess.run(['sudo', 'chown', 'root:root', file_path])
            return True
        except Exception:
            return False

    def _write_file_as_root_via_rfc(self, file_path: str, content: str, permissions: str) -> bool:
        """Write file with root permissions via RFC"""
        from python.helpers import runtime

        try:
            from python.helpers.system_commands_rfc import write_file_as_root
            result = runtime.call_development_function_sync(
                write_file_as_root,
                file_path=file_path,
                content=content,
                permissions=permissions
            )
            return result
        except Exception as e:
            print(f"❌ RFC file write failed: {e}")
            return False

    # This method now calls the module-level function
