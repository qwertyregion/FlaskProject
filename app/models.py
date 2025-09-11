from datetime import datetime
from typing import Dict, Optional
from app.extensions import db, login_manager
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    online = db.Column(db.Boolean, default=False, nullable=False)  # Добавляем статус "онлайн"
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Время последней активности

    # Связи с каскадным удалением
    sent_messages = db.relationship('Message',
                                    foreign_keys='Message.sender_id',
                                    back_populates='sender',
                                    lazy='dynamic',
                                    cascade='all, delete-orphan')

    received_messages = db.relationship('Message',
                                        foreign_keys='Message.recipient_id',
                                        back_populates='recipient',
                                        lazy='dynamic',
                                        cascade='all, delete-orphan')

    created_rooms = db.relationship('Room',
                                    back_populates='creator_obj',
                                    lazy='dynamic',
                                    cascade='all, delete-orphan')

    unread_messages = db.relationship('UnreadMessage',
                                      back_populates='user',
                                      lazy='dynamic',
                                      cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_user_email', 'email', unique=True),
        db.Index('ix_user_username', 'username', unique=True),
        db.Index('ix_user_online', 'online'),  # Для быстрого поиска онлайн пользователей
        db.Index('ix_user_last_seen', 'last_seen'),  # Для сортировки по активности
    )

    def set_password(self, password: str) -> None:
        """Устанавливает хеш пароля"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Проверяет пароль"""
        return check_password_hash(self.password_hash, password)

    def ping(self) -> None:
        """Обновляет время последней активности"""
        self.last_seen = datetime.utcnow()
        db.session.commit()

    @classmethod
    def get_online_users(cls, room: Optional[str] = None) -> Dict[int, str]:
        """Возвращает словарь {id: username} активных пользователей"""
        # Оптимизированный запрос - выбираем только нужные поля
        query = cls.query.with_entities(cls.id, cls.username).filter_by(online=True)
        if room:
            # Если нужна фильтрация по комнате (для будущего расширения)
            pass
        return dict(query.all())


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Может быть None для комнатных сообщений
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)  # Может быть None для ЛС
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    is_dm = db.Column(db.Boolean, default=False, nullable=False)  # Флаг личного сообщения

    # Связи
    sender = db.relationship('User',
                             foreign_keys=[sender_id],
                             back_populates='sent_messages')

    recipient = db.relationship('User',
                                foreign_keys=[recipient_id],
                                back_populates='received_messages')

    room = db.relationship('Room',
                           back_populates='messages')

    read_statuses = db.relationship('UnreadMessage',
                                    back_populates='message',
                                    lazy='dynamic')

    __table_args__ = (
        # Индексы для часто используемых запросов
        db.Index('ix_message_sender_id', 'sender_id'),
        db.Index('ix_message_recipient_id', 'recipient_id'),
        db.Index('ix_message_room_id', 'room_id'),
        db.Index('ix_message_is_dm', 'is_dm'),
        # Составные индексы для часто используемых запросов
        db.Index('ix_message_room_timestamp', 'room_id', 'timestamp'),
        db.Index('ix_message_dm_timestamp', 'is_dm', 'timestamp'),
        db.Index('ix_message_sender_recipient', 'sender_id', 'recipient_id'),
        db.Index('ix_message_room_dm', 'room_id', 'is_dm'),
    )

    def __repr__(self) -> str:
        return f'<Message {self.id} by {self.sender_id}>'

    def to_dict(self) -> Dict[str, any]:
        """Преобразует сообщение в словарь для отправки через Socket.IO"""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'sender_id': self.sender_id,
            'sender_username': self.sender.username if self.sender else 'Unknown',
            'recipient_id': self.recipient_id,
            'room_id': self.room_id,
            'room_name': self.room.name if self.room else None,  # Используем имя комнаты из модели
            'is_dm': self.is_dm,
            'is_read': self.is_read,
        }


# Модель для хранения непрочитанных сообщений
class UnreadMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'))
    is_read = db.Column(db.Boolean, default=False)

    # Связи
    user = db.relationship('User', back_populates='unread_messages')
    message = db.relationship('Message', back_populates='read_statuses')


class Room(db.Model):
    __tablename__ = 'room'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_private = db.Column(db.Boolean, default=False, nullable=False)

    # Связи
    creator_obj = db.relationship('User', foreign_keys=[created_by])
    messages = db.relationship('Message',
                               back_populates='room',
                               lazy='dynamic',
                               )

    def __repr__(self) -> str:
        return f'<Room {self.name}>'

    def to_dict(self) -> Dict[str, any]:
        """Преобразует комнату в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active
        }


@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    """Загрузка пользователя для Flask-Login"""
    if not user_id or not user_id.isdigit():
        return None
    try:
        return User.query.get(int(user_id))
    except (TypeError, ValueError):
        return None
