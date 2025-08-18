from collections import defaultdict

from flask import request
from flask_login import current_user
from flask_socketio import leave_room, emit, join_room
from app.extensions import db
from app.models import Message

active_users = defaultdict(dict)  # {user_id: {'username': str, 'room': str}} # {room: {user_id: username}}


def register_socketio_handlers(socketio):
    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            current_user.online = True
            db.session.commit()
            emit('user_status', {'user_id': current_user.id, 'online': True}, broadcast=True)
            print(f"Пользователь {current_user.username} подключился")
        else:
            print("Анонимный пользователь подключился")

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated and current_user.id in active_users:
            if current_user.is_authenticated:
                # Удаляем пользователя из всех комнат
                for room, users in active_users.items():
                    if current_user.id in users:
                        del users[current_user.id]
                        emit('user_left', {
                            'user_id': current_user.id,
                            'username': current_user.username
                        }, room=room)
                current_user.online = False
                db.session.commit()

    @socketio.on('join_chat')
    def handle_join(data):
        if not current_user.is_authenticated:
            return
        room = data.get('room', 'general_chat')
        # Выходим из предыдущих комнат
        for r in list(active_users.keys()):
            if current_user.id in active_users[r]:
                if r != room:
                    leave_room(r)
                    del active_users[r][current_user.id]
                    emit('user_left', {
                        'user_id': current_user.id,
                        'username': current_user.username
                    }, room=r)

        # Присоединяемся к новой комнате
        join_room(room)
        # active_users[current_user.id] = {'username': current_user.username, 'room': room}
        active_users[room][current_user.id] = current_user.username
        current_user.online = True  # Обновляем статус пользователя
        current_user.ping()
        db.session.commit()

        # Логирование для отладки
        print(f"User {current_user.username} joined room {room}")
        print(f"Current room users: {active_users[room]}")

        # Отправляем новому пользователю ВСЕХ участников комнаты (включая себя)
        # room_users = {uid: info['username'] for uid, info in active_users.items() if info['room'] == room}  # and uid != current_user.id
        emit('current_users', {
            'users': dict(active_users[room]),  # Преобразуем в обычный dict
            'room': room
        }, broadcast=False, to=request.sid)  # Используем request.sid вместо current_user.id

        # Оповещаем других о новом участнике
        emit('user_joined', {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': room
        }, room=room, include_self=False)

    @socketio.on('send_message')
    def handle_message(data):
        if not current_user.is_authenticated:
            return

        room = data.get('room', 'general_chat')
        message = Message(
            content=data['message'],
            sender_id=current_user.id,
            recipient_id=None,  # Общий чат (если личные сообщения, то указываем recipient_id)
            room=room
        )
        db.session.add(message)
        db.session.commit()

        emit('new_message', message.to_dict(), room=room)

