from flask import session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask_socketio import emit, join_room, leave_room

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Указываем endpoint для страницы входа
login_manager.login_message = "Пожалуйста, войдите для доступа к этой странице"
login_manager.login_message_category = "info"

socketio = SocketIO(cors_allowed_origins="*")
