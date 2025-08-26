from collections import defaultdict

from flask import request
from flask_login import current_user
from flask_socketio import leave_room, emit, join_room
from app.extensions import db
from app.models import Message


DEFAULT_ROOM = 'general_chat'

active_users = defaultdict(dict)  # {room: {user_id: username, }, }
active_users[DEFAULT_ROOM] = {}  # Сразу добавляем постоянную комнату


def register_socketio_handlers(socketio):
    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            join_room('app_aware_clients')  # <- Добавляем эту строку

            current_user.online = True
            db.session.commit()
            emit('user_status', {'user_id': current_user.id, 'online': True}, broadcast=True)
            print(f"Пользователь {current_user.username} подключился")
        else:
            print("Анонимный пользователь подключился")

    @socketio.on('disconnect')
    def handle_disconnect():
        if not current_user.is_authenticated:
            return

        user_was_in_any_room = False

        # Удаляем пользователя из всех комнат, где он был
        for room, users in list(active_users.items()):
            if current_user.id in users:
                user_was_in_any_room = True

                # Удаляем пользователя и уведомляем комнату
                del users[current_user.id]
                emit('user_left', {
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'room': room,
                }, room=room)

                # Если комната пустая, удаляем ее
                if not users and room != DEFAULT_ROOM:
                    del active_users[room]

        # Обновляем статус только если пользователь был в какой-то комнате
        if user_was_in_any_room:
            current_user.online = False
            db.session.commit()
            print(f"User {current_user.username} disconnected and removed from rooms")

            # оповестить всех о новом списке комнат.
            broadcast_room_list()

    @socketio.on('join_room')  # join_chat
    def handle_join_room(data):
        """Позволяет пользователю войти в указанную комнату, выйдя из предыдущей."""
        if not current_user.is_authenticated:
            return

        new_room = data.get('room')
        if not new_room:
            return

        # Запоминаем комнату, из которой выходим (если она была)
        old_room = None
        for room_name, users in list(active_users.items()):
            if current_user.id in users:
                if room_name != new_room:
                    old_room = room_name  # Запоминаем старую комнату
                    break  # Пользователь может быть только в одной комнате

        # Выходим из предыдущих комнат
        for room_name, users in list(active_users.items()):
            if current_user.id in users:
                if room_name != new_room:
                    leave_room(room_name)
                    del active_users[room_name][current_user.id]
                    emit('user_left', {
                        'user_id': current_user.id,
                        'username': current_user.username,
                        'room': room_name,
                    }, room=room_name)

                    # Очищаем пустые комнаты
                    if not active_users[room_name] and room_name != DEFAULT_ROOM:
                        del active_users[room_name]

        # Присоединяемся к новой комнате
        join_room(new_room)
        active_users.setdefault(new_room, {})[current_user.id] = current_user.username
        current_user.online = True  # Обновляем статус пользователя
        current_user.ping()
        db.session.commit()

        # Логирование для отладки
        print(f"User {current_user.username} joined room {new_room}")
        print(f"Current room users: {active_users[new_room]}")

        # Отправляем новому пользователю список участников НОВОЙ комнаты (включая себя)
        emit('current_users', {
            'users': dict(active_users[new_room]),  # Преобразуем в обычный dict
            'room': new_room
        }, broadcast=False, to=request.sid)  # Используем request.sid вместо current_user.id

        # Оповещаем других о новом участнике
        emit('user_joined', {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': new_room
        }, room=new_room, include_self=False)

        # Рассылаем всем клиентам новый список комнат
        broadcast_room_list()

    @socketio.on('send_message')
    def handle_message(data):
        if not current_user.is_authenticated:
            return

        room = data.get('room')
        message_text = data['message']

        if not room:
            return

        message = Message(
            content=message_text,
            sender_id=current_user.id,
            recipient_id=None,  # Общий чат (если личные сообщения, то указываем recipient_id)
            room=room  # Сохраняем название комнаты в базе
        )
        db.session.add(message)
        db.session.commit()
        emit('new_message', message.to_dict(), room=room)

        # запрос списка доступных комнат
        @socketio.on('get_rooms')
        def handle_get_rooms():
            """Отправляет клиенту список всех комнат."""
            # Можно расширить, чтобы отдавать и предопределённые комнаты из config
            room_list = get_rooms_list()
            emit('room_list', {'rooms': room_list})


def broadcast_room_list():
    """Рассылает актуальный список комнат всем клиентам."""
    room_list = get_rooms_list()  # Используем новую функцию
    emit('room_list', {'rooms': room_list}, broadcast=True, namespace='/')


def get_rooms_list():
    """Возвращает список всех комнат: постоянные + активные с пользователями."""
    # Всегда включаем комнату по умолчанию
    all_rooms = {DEFAULT_ROOM}
    # Добавляем все комнаты, где есть пользователи
    all_rooms.update(active_users.keys())
    return list(all_rooms)

