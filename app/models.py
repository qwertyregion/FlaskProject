from datetime import datetime
from app.extensions import db, login_manager

from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    online = db.Column(db.Boolean, default=False)  # Добавляем статус "онлайн"
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)  # Время последней активности
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)

    __table_args__ = (
        db.Index('ix_user_email', 'email', unique=True),
        db.Index('ix_user_username', 'username', unique=True)
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def ping(self):
        """Обновляет время последней активности"""
        self.last_seen = datetime.utcnow()
        db.session.commit()

    @classmethod
    def get_online_users(cls, room=None):
        """Возвращает словарь {id: username} активных пользователей"""
        query = cls.query.filter_by(online=True)
        if room:
            # Если нужна фильтрация по комнате (для будущего расширения)
            pass
        return {user.id: user.username for user in query.all()}


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login"""
    if not user_id or not user_id.isdigit():
        return None
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_read = db.Column(db.Boolean, default=False)
    room = db.Column(db.String(50), default="general_chat")  # Добавляем комнату чата

    def to_dict(self):
        """Преобразует сообщение в словарь для отправки через Socket.IO"""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'sender_id': self.sender_id,
            'sender_username': self.sender.username,
            'recipient_id': self.recipient_id,
            'is_read': self.is_read,
            'room': self.room
        }