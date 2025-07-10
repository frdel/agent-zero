"""
API endpoints for collaborative features
Handles real-time state synchronization, progress streaming, and research collaboration
"""

import json
from typing import Dict, Any, Optional
from flask import request, jsonify
from python.helpers.api import ApiHandler
from python.helpers.collaborative_state import collaborative_state_manager, ProgressStatus
from python.helpers.print_style import PrintStyle


class CollaborativeStateAPI(ApiHandler):
    """
    API handler for collaborative state management
    """

    def __init__(self, app, thread_lock):
        super().__init__(app, thread_lock)
        self.setup_routes()

    @classmethod
    def requires_csrf(cls) -> bool:
        return False  # Allow cross-origin for real-time features

    @classmethod
    def get_methods(cls) -> list[str]:
        return ["GET", "POST", "PUT", "DELETE"]

    def setup_routes(self):
        """Setup collaborative API routes using Flask"""

        # State management routes
        @self.app.route("/api/collaborative_state/<state_id>", methods=["GET"])
        def get_state_route(state_id):
            return self.get_state(state_id)

        @self.app.route("/api/collaborative_state/<state_id>", methods=["PUT"])
        def update_state_route(state_id):
            return self.update_state(state_id)

        # Progress management routes
        @self.app.route("/api/progress", methods=["POST"])
        def create_progress_route():
            return self.create_progress()

        @self.app.route("/api/progress/<progress_id>", methods=["PUT"])
        def update_progress_route(progress_id):
            return self.update_progress(progress_id)

        # Research collaboration routes
        @self.app.route("/api/research_session", methods=["POST"])
        def create_research_session_route():
            return self.create_research_session()

        @self.app.route("/api/research_session/<session_id>/finding", methods=["POST"])
        def add_research_finding_route(session_id):
            return self.add_research_finding(session_id)

        @self.app.route("/api/research_session/<session_id>/join", methods=["POST"])
        def join_research_session_route(session_id):
            return self.join_research_session(session_id)

        # Real-time context routes
        @self.app.route("/api/shared_context", methods=["POST"])
        def create_shared_context_route():
            return self.create_shared_context()

        @self.app.route("/api/shared_context/<context_id>", methods=["PUT"])
        def update_shared_context_route(context_id):
            return self.update_shared_context(context_id)

        # User state routes
        @self.app.route("/api/user/<user_id>/states", methods=["GET"])
        def get_user_states_route(user_id):
            return self.get_user_states(user_id)
    
    def get_state(self, state_id: str):
        """Get current state by ID"""
        try:
            state = collaborative_state_manager.get_state(state_id)
            if not state:
                return jsonify({
                    "success": False,
                    "error": "State not found"
                }), 404

            return jsonify({
                "success": True,
                "state_id": state_id,
                "data": state["data"],
                "type": state["type"].value,
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error getting state: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def update_state(self, state_id: str):
        """Update state (generic endpoint)"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")
            updates = body.get("updates", {})

            # Determine state type and update accordingly
            state = collaborative_state_manager.get_state(state_id)
            if not state:
                return jsonify({
                    "success": False,
                    "error": "State not found"
                }), 404

            state_type = state["type"]

            if state_type.value == "shared_context":
                success = collaborative_state_manager.update_shared_context(
                    state_id=state_id,
                    user_id=user_id,
                    updates=updates
                )
            elif state_type.value == "agent_progress":
                success = collaborative_state_manager.update_progress(
                    state_id=state_id,
                    **updates
                )
            else:
                return jsonify({
                    "success": False,
                    "error": "State type not updatable via this endpoint"
                }), 400

            if not success:
                return jsonify({
                    "success": False,
                    "error": "Update failed (check permissions)"
                }), 403

            return jsonify({
                "success": True,
                "state_id": state_id,
                "message": "State updated successfully",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error updating state: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def create_progress(self):
        """Create new progress indicator"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")
            agent_id = body.get("agent_id", "agent")
            total_steps = body.get("total_steps", 5)
            initial_message = body.get("message", "Starting task...")

            progress_id = collaborative_state_manager.create_progress_state(
                user_id=user_id,
                agent_id=agent_id,
                total_steps=total_steps,
                initial_message=initial_message
            )

            return jsonify({
                "success": True,
                "progress_id": progress_id,
                "message": "Progress indicator created",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error creating progress: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def update_progress(self, progress_id: str):
        """Update progress indicator"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            # Parse status if provided
            status = body.get("status")
            progress_status = None
            if status:
                try:
                    progress_status = ProgressStatus(status)
                except ValueError:
                    pass

            success = collaborative_state_manager.update_progress(
                state_id=progress_id,
                completed_steps=body.get("completed_steps"),
                current_step=body.get("current_step"),
                message=body.get("message"),
                status=progress_status,
                details=body.get("details")
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": "Progress not found"
                }), 404

            return jsonify({
                "success": True,
                "progress_id": progress_id,
                "message": "Progress updated",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error updating progress: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def create_research_session(self):
        """Create new research session"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")
            session_name = body.get("session_name", "Research Session")
            research_topic = body.get("research_topic", "General Research")
            collaboration_mode = body.get("collaboration_mode", "interactive")

            session_id = collaborative_state_manager.create_research_session(
                user_id=user_id,
                session_name=session_name,
                research_topic=research_topic,
                collaboration_mode=collaboration_mode
            )

            return jsonify({
                "success": True,
                "session_id": session_id,
                "message": "Research session created",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error creating research session: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def add_research_finding(self, session_id: str):
        """Add finding to research session"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")
            finding_text = body.get("finding", "")
            source = body.get("source", "manual")
            confidence = body.get("confidence", "medium")

            if not finding_text:
                return jsonify({
                    "success": False,
                    "error": "Finding text is required"
                }), 400

            finding = {
                "text": finding_text,
                "source": source,
                "confidence": confidence,
                "type": "text"
            }

            success = collaborative_state_manager.add_research_finding(
                state_id=session_id,
                user_id=user_id,
                finding=finding
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": "Research session not found or access denied"
                }), 404

            return jsonify({
                "success": True,
                "session_id": session_id,
                "message": "Finding added to research session",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error adding research finding: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def join_research_session(self, session_id: str):
        """Join existing research session"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")

            success = collaborative_state_manager.join_research_session(
                state_id=session_id,
                user_id=user_id
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": "Research session not found"
                }), 404

            return jsonify({
                "success": True,
                "session_id": session_id,
                "message": "Joined research session",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error joining research session: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def create_shared_context(self):
        """Create shared context"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            owner_id = body.get("owner_id", "default_user")
            context_type = body.get("context_type", "general")
            data = body.get("data", {})
            shared_with = body.get("shared_with", [])

            context_id = collaborative_state_manager.create_shared_context(
                owner_id=owner_id,
                context_type=context_type,
                data=data,
                shared_with=shared_with
            )

            return jsonify({
                "success": True,
                "context_id": context_id,
                "message": "Shared context created",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error creating shared context: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def update_shared_context(self, context_id: str):
        """Update shared context"""
        try:
            body = request.get_json()
            if not body:
                return jsonify({
                    "success": False,
                    "error": "JSON body required"
                }), 400

            user_id = body.get("user_id", "default_user")
            updates = body.get("updates", {})

            success = collaborative_state_manager.update_shared_context(
                state_id=context_id,
                user_id=user_id,
                updates=updates
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": "Update failed (check permissions)"
                }), 403

            return jsonify({
                "success": True,
                "context_id": context_id,
                "message": "Shared context updated",
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error updating shared context: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def get_user_states(self, user_id: str):
        """Get all states for a user"""
        try:
            states = collaborative_state_manager.get_user_states(user_id)

            return jsonify({
                "success": True,
                "user_id": user_id,
                "states": states,
                "count": len(states),
                "timestamp": self._get_timestamp()
            })

        except Exception as e:
            PrintStyle(font_color="red").print(f"[Collaborative API] Error getting user states: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    def _get_timestamp(self):
        """Helper method to get current timestamp"""
        import time
        return time.time()
