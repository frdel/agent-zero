from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Minion

routes = Blueprint('routes', __name__)

@routes.route('/')
@login_required
def dashboard():
    minions = Minion.query.all()
    return render_template('dashboard.html', minions=minions)

@routes.route('/minion/<uuid>')
@login_required
def minion_detail(uuid):
    m = Minion.query.filter_by(uuid=uuid).first_or_404()
    return render_template('minion_detail.html', minion=m)
