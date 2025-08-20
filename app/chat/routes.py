from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user
from ..extensions import socketio

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')



