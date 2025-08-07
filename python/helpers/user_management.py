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


# Thread-local storage for current user context
_thread_local = threading.local()


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
        # For now, return hardcoded defaults
        # Later will be enhanced to read from admin settings
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
            'venv_created': self.venv_created
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
            venv_created=data.get('venv_created', False)
        )


class UserManager:
    """Manages user authentication and user data persistence"""

    # Class-level flag to ensure migration only runs once across all instances
    _global_migration_checked = False

    def __init__(self, user_file: Optional[str] = None):
        self.user_file = user_file or os.path.join(files.get_base_dir(), "tmp", "users.json")
        self.users: Dict[str, User] = {}
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
            venv_created=False  # Will be set to True when venv is actually created
        )

        # Store user
        self.users[username] = user
        self._save_users()

        # Ensure user data directories exist
        self.ensure_user_data_directories(username)

        # Create user's virtual environment
        self.create_user_venv(username)

        # Create system user (if not in testing/restricted environment)
        self.ensure_system_user(username)

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

    def get_user_venv_path(self, username: str) -> str:
        """Get the virtual environment path for a user"""
        base_dir = files.get_base_dir()
        return os.path.join(base_dir, "venvs", username)

    def create_user_venv(self, username: str, force_recreate: bool = False) -> bool:
        """Create a Python virtual environment for the user"""
        user = self.users.get(username)
        if not user:
            return False

        venv_path = self.get_user_venv_path(username)

        # Check if venv already exists
        if os.path.exists(venv_path) and not force_recreate:
            if user.venv_created and user.venv_path == venv_path:
                return True  # Already exists and is tracked

        # Remove existing venv if force_recreate
        if os.path.exists(venv_path) and force_recreate:
            shutil.rmtree(venv_path)

        try:
            # Create venv directory
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)

            # Create virtual environment
            print(f"Creating Python virtual environment for user '{username}' at: {venv_path}")
            subprocess.run([
                "python3", "-m", "venv", venv_path
            ], capture_output=True, text=True, check=True)

            # Copy base requirements if they exist
            main_venv_requirements = os.path.join(files.get_base_dir(), "requirements.txt")
            if os.path.exists(main_venv_requirements):
                print(f"Installing base requirements in user venv for '{username}'...")
                pip_path = os.path.join(venv_path, "bin", "pip")
                subprocess.run([
                    pip_path, "install", "-r", main_venv_requirements
                ], capture_output=True, text=True, check=True)

            # Update user record
            user.venv_path = venv_path
            user.venv_created = True
            self._save_users()

            print(f"✅ Virtual environment created successfully for user '{username}'")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating virtual environment for user '{username}': {e}")
            if e.stdout:
                print(f"STDOUT: {e.stdout}")
            if e.stderr:
                print(f"STDERR: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error creating virtual environment for user '{username}': {e}")
            return False

    def delete_user_venv(self, username: str) -> bool:
        """Delete a user's virtual environment"""
        user = self.users.get(username)
        if not user:
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
            result = subprocess.run(['getent', 'group', 'a0-users'], capture_output=True, text=True)
            if result.returncode == 0:
                return True  # Group already exists

            # Create a0-users group
            print("Creating a0-users group for shared access...")
            subprocess.run(['sudo', 'groupadd', 'a0-users'], check=True)
            print("✅ a0-users group created successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating a0-users group: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error creating a0-users group: {e}")
            return False

    def setup_webapp_user_permissions(self) -> bool:
        """Add the current web app user to a0-users group"""
        try:
            # Get current user (web app user)
            current_user = os.getenv('USER', 'www-data')  # fallback to www-data

            # Check if user is already in group
            result = subprocess.run(['groups', current_user], capture_output=True, text=True)
            if 'a0-users' in result.stdout:
                return True  # Already in group

            # Add web app user to a0-users group
            print(f"Adding web app user '{current_user}' to a0-users group...")
            subprocess.run(['sudo', 'usermod', '-a', '-G', 'a0-users', current_user], check=True)
            print(f"✅ Web app user '{current_user}' added to a0-users group")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error adding web app user to a0-users group: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error setting up web app permissions: {e}")
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
            result = subprocess.run(['id', system_username], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"System user '{system_username}' already exists")
                user.system_user_created = True
                self._save_users()
                return True

            # Create system user with restricted shell
            print(f"Creating system user: {system_username}")
            subprocess.run([
                'sudo', 'useradd',
                '--create-home',
                '--shell', '/bin/bash',
                '--comment', f'Agent Zero user for {username}',
                system_username
            ], check=True)

            # Set up user directories and permissions
            self._setup_system_user_directories(username, system_username)

            # Add user to a0-users group
            subprocess.run(['sudo', 'usermod', '-a', '-G', 'a0-users', system_username], check=True)

            # Update user record
            user.system_user_created = True
            self._save_users()

            print(f"✅ System user '{system_username}' created successfully for Agent Zero user '{username}'")
            return True

        except subprocess.CalledProcessError as e:
            system_username = user.system_username or "unknown"
            print(f"❌ Error creating system user '{system_username}' for '{username}': {e}")
            return False
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
            result = subprocess.run(['id', system_username], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"System user '{system_username}' does not exist")
                user.system_user_created = False
                self._save_users()
                return True

            # Delete system user and home directory
            print(f"Deleting system user: {system_username}")
            subprocess.run(['sudo', 'userdel', '--remove', system_username], check=True)

            # Update user record
            user.system_user_created = False
            self._save_users()

            print(f"✅ System user '{system_username}' deleted successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error deleting system user '{system_username}': {e}")
            return False
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
            sudoers_content = f"# Agent Zero sudo commands for user {username}\n"
            sudoers_content += f"{system_username} ALL=(ALL) NOPASSWD: "

            # Add each whitelisted command
            escaped_commands = []
            for cmd in user.sudo_commands:
                # Escape command for sudoers format
                escaped_cmd = cmd.replace('"', '\\"')
                escaped_commands.append(f'"{escaped_cmd}"')

            sudoers_content += ", ".join(escaped_commands)
            sudoers_content += "\n"

            # Write sudoers file
            print(f"Setting up sudoers entry for system user: {system_username}")
            with open(f"/tmp/sudoers-{username}", 'w') as f:
                f.write(sudoers_content)

            # Move to sudoers directory with proper permissions
            subprocess.run(['sudo', 'mv', f"/tmp/sudoers-{username}", sudoers_file], check=True)
            subprocess.run(['sudo', 'chmod', '440', sudoers_file], check=True)
            subprocess.run(['sudo', 'chown', 'root:root', sudoers_file], check=True)

            # Validate sudoers syntax
            result = subprocess.run(['sudo', 'visudo', '-c'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Invalid sudoers syntax, removing file: {sudoers_file}")
                subprocess.run(['sudo', 'rm', '-f', sudoers_file], check=True)
                return False

            print(f"✅ Sudoers entry created for '{system_username}' with {len(user.sudo_commands)} whitelisted commands")
            return True

        except Exception as e:
            print(f"❌ Error setting up sudoers entry for '{username}': {e}")
            return False

    def remove_sudoers_entry(self, username: str) -> bool:
        """Remove sudoers entry for a user"""
        try:
            sudoers_file = f"/etc/sudoers.d/a0-{username}"
            if os.path.exists(sudoers_file):
                print(f"Removing sudoers entry: {sudoers_file}")
                subprocess.run(['sudo', 'rm', '-f', sudoers_file], check=True)
                print(f"✅ Sudoers entry removed for user '{username}'")
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
                if os.path.exists(user_data_path):
                    # Set ownership to system user but keep group as a0-users for web app access
                    subprocess.run(['sudo', 'chown', '-R', f'{system_username}:a0-users', user_data_path], check=True)
                    # Set permissions: owner can read/write, group can read/write, others no access
                    subprocess.run(['sudo', 'chmod', '-R', '750', user_data_path], check=True)

            # Set up venv directory permissions if it exists
            venv_path = self.get_user_venv_path(username)
            if os.path.exists(venv_path):
                subprocess.run(['sudo', 'chown', '-R', f'{system_username}:a0-users', venv_path], check=True)
                subprocess.run(['sudo', 'chmod', '-R', '750', venv_path], check=True)

            print(f"✅ Directory permissions set up for system user '{system_username}'")

        except Exception as e:
            print(f"❌ Error setting up directories for system user '{system_username}': {e}")

    def ensure_system_user(self, username: str) -> bool:
        """Ensure system user exists for Agent Zero user"""
        user = self.users.get(username)
        if not user:
            return False

        if user.system_user_created:
            return True  # Already created

        # Create system user
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

    def migrate_venvs_for_existing_users(self) -> None:
        """Create virtual environments for existing users who don't have them"""
        print("🔄 Migrating virtual environments for existing users...")

        migrated_count = 0
        for username, user in self.users.items():
            if not user.venv_created or not user.venv_path or not os.path.exists(user.venv_path):
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

    def ensure_default_admin(self) -> User:
        """Ensure that the default admin user exists"""
        admin_user = self.get_user("admin")
        if not admin_user:
            admin_user = self.create_user("admin", "agent0", True)
        else:
            # Ensure admin directories exist even if user already existed
            self.ensure_user_data_directories("admin")

        # Run one-time migration if needed
        self.migrate_global_to_admin_if_needed()

        # Migrate venvs for all existing users (one-time setup)
        self.migrate_venvs_for_existing_users()

        # Migrate system usernames for existing users (one-time setup)
        self.migrate_system_usernames_for_existing_users()

        # Set up system user infrastructure
        self.setup_system_user_infrastructure()

        return admin_user

    def migrate_existing_data(self, base_dir: str) -> None:
        """Migrate existing data to admin user directory"""
        # This will be used to migrate existing data to the admin user
        # when upgrading from single-user to multi-user system
        self.ensure_default_admin()

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
                        shutil.move(source_path, target_path)
                        migrated_items.append(f"✅ {migration['description']}: {migration['source_pattern']} → {migration['target_pattern']}")
                elif os.path.isdir(source_path):
                    # Move directory (with exclusions)
                    exclude_subdirs = migration.get('exclude_subdirs', [])

                    if not os.path.exists(target_path):
                        # Target doesn't exist, move entire directory
                        shutil.move(source_path, target_path)
                        migrated_items.append(f"✅ {migration['description']}: {migration['source_pattern']} → {migration['target_pattern']}")
                    else:
                        # Target exists, merge contents
                        for item in os.listdir(source_path):
                            if item in exclude_subdirs:
                                continue

                            source_item = os.path.join(source_path, item)
                            target_item = os.path.join(target_path, item)

                            if not os.path.exists(target_item):
                                shutil.move(source_item, target_item)
                                migrated_items.append(f"📁 Moved {item} from {migration['description']}")

        # Create migration marker
        with open(migration_marker, 'w') as f:
            f.write(f"Migration completed at: {os.popen('date').read().strip()}\n")
            f.write("Migrated items:\n")
            f.write("\n".join(migrated_items))

        if migrated_items:
            print(f"✅ Migration completed! Moved {len(migrated_items)} items to admin user.")
        else:
            print("ℹ️  No data to migrate (fresh installation).")


# Global user manager instance
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """Get the global user manager instance"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
        _user_manager.ensure_default_admin()
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
