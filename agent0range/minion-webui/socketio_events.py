from app import socketio
from flask_socketio import emit
from app.models import Minion
from app import db

@socketio.on('connect')
def on_connect():
    emit('status', {'msg':'connected'})

@socketio.on('heartbeat')
def heartbeat(data):
    m = Minion.query.filter_by(uuid=data['uuid']).first()
    if m:
        m.status='online'; m.last_seen=data['timestamp']
        db.session.commit()
        emit('update', {'uuid':m.uuid,'status':m.status}, broadcast=True)
