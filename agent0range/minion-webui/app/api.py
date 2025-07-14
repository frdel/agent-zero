from flask import Blueprint, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from werkzeug.security import check_password_hash
from app import app, db
from app.models import Minion, User

api = Blueprint('api', __name__)
jwt = JWTManager(app)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify(msg='Missing username or password'), 400
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        token = create_access_token(identity=user.id)
        return jsonify(token=token)
    return jsonify(msg='Bad credentials'), 401

@app.route('/api/superadmin', methods=['GET'])
@jwt_required()
def superadmin_route():
    from flask_jwt_extended import get_jwt_identity
    current_user_id = get_jwt_identity()
    if current_user_id is None:
        return jsonify(msg='Unauthorized'), 401
    user = User.query.get(current_user_id)
    if user and getattr(user, 'role', None) == 'superadmin':
        return jsonify(msg='Welcome, superadmin!')
    return jsonify(msg='Forbidden'), 403

@app.route('/api/minions', methods=['GET','POST'])
@jwt_required()
def minions():
    if request.method=='POST':
        data = request.json
        m = Minion(**data)
        db.session.add(m); db.session.commit()
        return jsonify(msg='created'),201
    all_ = Minion.query.all()
    return jsonify([i.serialize() for i in all_])

# Public health endpoint for Docker healthchecks
@app.route('/health', methods=['GET'])
def health():
    return jsonify(status='ok'), 200
