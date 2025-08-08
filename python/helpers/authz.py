from __future__ import annotations

import time
from flask import session


def is_temp_admin_active() -> bool:
    try:
        temp_admin = session.get('temp_admin')
        temp_admin_username = session.get('temp_admin_username')
        temp_admin_expires = session.get('temp_admin_expires')
        if temp_admin and temp_admin_username and temp_admin_expires:
            return int(time.time()) < int(temp_admin_expires)
        return False
    except Exception:
        return False


def is_threadlocal_admin() -> bool:
    try:
        from python.helpers.user_management import get_current_user
        user = get_current_user()
        return bool(user and user.is_admin)
    except Exception:
        return False


def is_request_admin() -> bool:
    # Prefer temp admin and thread-local elevation for per-request admin
    if is_threadlocal_admin() or is_temp_admin_active():
        return True
    # Fallback to session admin flags
    if session.get('is_admin', False):
        return True
    # Username equals admin as last resort
    if session.get('username') == 'admin':
        return True
    return False


def clear_temp_admin_flags() -> None:
    try:
        session.pop('temp_admin', None)
        session.pop('temp_admin_username', None)
        session.pop('temp_admin_expires', None)
        session.modified = True
    except Exception:
        pass
