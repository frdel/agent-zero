"""
User management system for Agent Zero multitenancy.
Handles user authentication, user context, and user data isolation.
"""

import json
import os
import bcrypt
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from python.helpers import files


# Thread-local storage for current user context
_thread_local = threading.local()


@dataclass
class User:
    """User data model"""
    username: str
    password_hash: str
    is_admin: bool
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary for JSON serialization"""
        return {
            'username': self.username,
            'password_hash': self.password_hash,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create user from dictionary"""
        return cls(
            username=data['username'],
            password_hash=data['password_hash'],
            is_admin=data['is_admin'],
            created_at=datetime.fromisoformat(data['created_at'])
        )


class UserManager:
    """Manages user authentication and user data persistence"""

    def __init__(self, user_file: Optional[str] = None):
        self.user_file = user_file or files.get_abs_path("users.json")
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

        # Create user
        user = User(
            username=username,
            password_hash=password_hash,
            is_admin=is_admin,
            created_at=datetime.now(timezone.utc)
        )

        # Store user
        self.users[username] = user
        self._save_users()

        # Ensure user data directories exist
        self.ensure_user_data_directories(username)

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
        from python.helpers import files

        base_dir = files.get_base_dir()
        migration_marker = os.path.join(base_dir, '.multitenancy_migrated')

        # Skip if already migrated
        if os.path.exists(migration_marker):
            return

        print("🔄 Migrating existing data to admin user...")

        # Ensure admin user data directories exist (but don't call ensure_default_admin to avoid recursion)
        self.ensure_user_data_directories("admin")

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
