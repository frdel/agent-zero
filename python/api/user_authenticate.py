from python.helpers.api import ApiHandler, Request, Response
from python.helpers.user_management import get_user_manager, set_current_user
from flask import session


class UserAuthenticate(ApiHandler):

    @classmethod
    def requires_auth(cls) -> bool:
        return False  # This endpoint doesn't require basic auth

    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # Don't require CSRF for initial authentication

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["POST"]

    async def process(self, input: dict, request: Request) -> dict | Response:
        try:
            # Input received

            # Get credentials from input
            username = input.get('username')
            password = input.get('password')
            is_temporary = input.get('temporary', False)

            # Debug removed

            if not username or not password:
                return {"error": "Username and password are required"}

            # Check if user is already authenticated in session
            current_username = session.get('username')
            current_is_admin = session.get('is_admin')

            # If user is already logged in as the same user, just validate and continue
            # (This prevents session corruption from re-authentication)
            if current_username == username and current_username:

                # Still validate the password for security
                user_manager = get_user_manager()
                if user_manager.authenticate(username, password):
                    user = user_manager.get_user(username)
                    if user:
                        # DO NOT change session or user context - keep existing session intact

                        return {
                            'success': True,
                            'message': 'Authentication successful',
                            'user': {
                                'username': user.username,
                                'is_admin': user.is_admin
                            }
                        }

            # For new authentication or different user, proceed with normal flow
            user_manager = get_user_manager()
            if user_manager.authenticate(username, password):
                user = user_manager.get_user(username)
                if user:
                    # Set central username immediately (works outside request contexts)
                    try:
                        user_manager.set_central_current_username(user.username)
                    except Exception:
                        pass
                    # Decide whether to treat this as temporary elevation even without explicit flag
                    current_username = session.get('username')
                    current_is_admin = session.get('is_admin')
                    should_force_temporary = (
                        not is_temporary
                        and bool(current_username)
                        and current_username != username
                        and not bool(current_is_admin)
                        and bool(user.is_admin)
                    )

                    if is_temporary or should_force_temporary:
                        # TEMPORARY AUTHENTICATION - DO NOT CLEAR SESSION

                        # Persist short-lived temporary admin elevation in session
                        try:
                            import time
                            session['temp_admin'] = True
                            session['temp_admin_username'] = user.username
                            session['temp_admin_expires'] = int(time.time()) + 600  # 10 minutes
                            session.modified = True
                        except Exception:
                            pass

                        # Set thread-local context for temporary admin access
                        set_current_user(user)

                        return {
                            'success': True,
                            'message': 'Temporary authentication successful - session preserved',
                            'user': {
                                'username': user.username,
                                'is_admin': user.is_admin
                            },
                            'temporary': True,
                            'session_preserved': True,
                            'implicit_temporary': should_force_temporary
                        }
                    else:
                        # REGULAR AUTHENTICATION - Update session normally
                        # Only clear session if it's a different user or initial login
                        if current_username != username:
                            session.clear()

                        # Set up session
                        session['username'] = user.username
                        session['is_admin'] = user.is_admin
                        session.permanent = True

                        # Set thread-local context for NEW authentication
                        set_current_user(user)

                        return {
                            'success': True,
                            'message': 'Authentication successful',
                            'user': {
                                'username': user.username,
                                'is_admin': user.is_admin
                            }
                        }

            # Clear central username on failure to prevent empty/default usage
            try:
                get_user_manager().set_central_current_username(None)
            except Exception:
                pass
            return {"error": "Invalid credentials"}

        except Exception as e:
            return {"error": f"Authentication failed: {str(e)}"}
