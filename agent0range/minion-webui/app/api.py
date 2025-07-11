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
    user = User.query.filter_by(username=data['username']).first()
    if user and check_password_hash(user.password, data['password']):
        token = create_access_token(identity=user.id)
        return jsonify(token=token)
    return jsonify(msg='Bad credentials'), 401

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
