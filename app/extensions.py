from flask import session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from flask_socketio import emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
import typing as _t
try:
    import redis as _redis
except Exception:  # redis may not be installed in some envs
    _redis = None  # type: ignore

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # Указываем endpoint для страницы входа
login_manager.login_message = "Пожалуйста, войдите для доступа к этой странице"
login_manager.login_message_category = "info"

# Инициализация rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Инициализация Talisman для безопасности
talisman = Talisman()

# Ограничиваем CORS для WebSocket
socketio = SocketIO(cors_allowed_origins=["http://localhost:5000", "http://127.0.0.1:5000"])

# Redis клиент (инициализируется в create_app)
redis_client: _t.Optional["_redis.Redis"] = None
