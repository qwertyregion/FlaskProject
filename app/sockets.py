from collections import defaultdict
from app.models import Room
from flask import request
from flask_login import current_user
from flask_socketio import leave_room, emit, join_room
from sqlalchemy import func
from app.extensions import db
from app.models import Message, User

DEFAULT_ROOM = 'general_chat'

active_users = defaultdict(dict)  # {room: {user_id: username, }, }
active_users[DEFAULT_ROOM] = {}  # Сразу добавляем постоянную комнату

# Храним подключенных пользователей
connected_users = {}  # {user_id: socket_id}
dm_rooms = defaultdict(set)  # {dm_room_id: set(socket_ids)}


def register_socketio_handlers(socketio):
    """Регистрирует все обработчики SocketIO"""

    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            user_id = current_user.id

            # Проверяем, не подключен ли пользователь уже
            if user_id in connected_users:
                old_sid = connected_users[user_id]
                if old_sid != request.sid:
                    # Отключаем старое соединение
                    leave_room(DEFAULT_ROOM, sid=old_sid)
                    # Принудительно закрываем старое соединение
                    socketio.server.disconnect(old_sid)

            connected_users[current_user.id] = request.sid
            join_room('app_aware_clients')
            current_user.online = True
            db.session.commit()
            emit('user_status', {'user_id': current_user.id, 'online': True}, broadcast=True)

            # Автоматически присоединяем к комнате по умолчанию
            join_room(DEFAULT_ROOM)

            # Убедимся, что комната всегда существует в active_users
            if DEFAULT_ROOM not in active_users:
                active_users[DEFAULT_ROOM] = {}

            active_users[DEFAULT_ROOM][current_user.id] = current_user.username

            # Отправляем список пользователей в комнате по умолчанию
            emit('current_users', {
                'users': dict(active_users[DEFAULT_ROOM]),
                'room': DEFAULT_ROOM
            }, room=DEFAULT_ROOM)

            # Отправляем список комнат новому пользователю
            emit('room_list', {'rooms': get_rooms_list()})

    @socketio.on('disconnect')
    def handle_disconnect():
        if not current_user.is_authenticated:
            return

        user_id = current_user.id
        user_was_in_any_room = False

        # Удаляем пользователя из всех комнат, где он был
        for room_name, users in list(active_users.items()):
            if user_id in users:
                user_was_in_any_room = True

                # Удаляем пользователя и уведомляем комнату
                del users[user_id]
                leave_room(room_name)

                emit('user_left', {
                    'user_id': user_id,
                    'username': current_user.username,
                    'room': room_name,
                }, room=room_name)

                # Отправляем обновленный список пользователей
                emit('current_users', {
                    'users': dict(users),
                    'room': room_name
                }, room=room_name)

                # ПРОВЕРЯЕМ И УДАЛЯЕМ ПУСТЫЕ КОМНАТЫ
                cleanup_empty_rooms(room_name)

        # Удаляем из подключенных пользователей только если это текущее соединение
        if user_id in connected_users and connected_users[user_id] == request.sid:
            connected_users.pop(user_id, None)

        # Обновляем статус
        if user_was_in_any_room:
            current_user.online = False
            db.session.commit()
            broadcast_room_list()

    @socketio.on('create_room')
    def handle_create_room(data):
        """Обработчик создания новой комнаты"""
        if not current_user.is_authenticated:
            emit('room_created', {'success': False, 'message': 'Не авторизован'})
            return

        room_name = data.get('room_name', '').strip()

        if not room_name:
            emit('room_created', {'success': False, 'message': 'Введите название комнаты'})
            return

        if len(room_name) > 20:
            emit('room_created', {'success': False, 'message': 'Название слишком длинное (макс. 20 символов)'})
            return

        if len(room_name) < 2:
            emit('room_created', {'success': False, 'message': 'Название слишком короткое (мин. 2 символа)'})
            return

        try:
            # Проверяем, нет ли уже такой комнаты
            existing_room = Room.query.filter_by(name=room_name).first()
            if existing_room:
                emit('room_created', {'success': False, 'message': 'Комната с таким названием уже существует'})
                return

            # Создаем новую комнату
            new_room = Room(
                name=room_name,
                created_by=current_user.id
            )
            db.session.add(new_room)
            db.session.commit()

            # автоматически присоединяем создателя к новой комнате
            join_room(room_name)
            if room_name not in active_users:
                active_users[room_name] = {}
            active_users[room_name][current_user.id] = current_user.username

            # ОТПРАВЛЯЕМ ОБНОВЛЕННЫЙ СПИСОК КОМНАТ ВСЕМ КЛИЕНТАМ
            broadcast_room_list()

            # ОТПРАВЛЯЕМ СОЗДАТЕЛЮ ОТВЕТ С ФЛАГОМ ДЛЯ АВТОПЕРЕХОДА
            emit('room_created', {
                'success': True,
                'room_name': room_name,
                'message': f'Комната "{room_name}" создана!',
                'auto_join': True  # Флаг для автоматического перехода
            }, )

            # ОТПРАВЛЯЕМ ОСТАЛЬНЫМ КЛИЕНТАМ ОБЫЧНОЕ УВЕДОМЛЕНИЕ
            emit('room_created', {
                'success': True,
                'room_name': room_name,
                'message': f'Комната "{room_name}" создана!',
                'auto_join': False  # Без автоперехода
            }, broadcast=True, include_self=False)

        except Exception as e:
            print(f"Ошибка при создании комнаты: {e}")
            emit('room_created', {'success': False, 'message': 'Ошибка при создании комнаты'})
            db.session.rollback()

    @socketio.on('join_room')
    def handle_join_room(data):
        """Позволяет пользователю войти в указанную комнату, выйдя из предыдущей."""

        if not current_user.is_authenticated:
            return

        new_room_name = data.get('room')
        if not new_room_name:
            return

        # Находим или создаем комнату в базе данных
        room = Room.query.filter_by(name=new_room_name).first()
        if not room:
            room = Room(name=new_room_name, created_by=current_user.id)
            db.session.add(room)
            db.session.commit()

        # Если комната не существует в active_users, создаем ее
        if new_room_name not in active_users:
            active_users[new_room_name] = {}

        # Выходим из предыдущих комнат (кроме DM комнат и комнаты по умолчанию)
        for room_name, users in list(active_users.items()):
            if not room_name.startswith('dm_') and current_user.id in users and room_name != new_room_name:
                leave_room(room_name)
                del active_users[room_name][current_user.id]

                emit('user_left', {
                    'user_id': current_user.id,
                    'username': current_user.username,
                    'room': room_name,
                }, room=room_name)

                # Отправляем обновленный список пользователей
                emit('current_users', {
                    'users': dict(active_users[room_name]),
                    'room': room_name
                }, room=room_name)

                # ПРОВЕРЯЕМ И УДАЛЯЕМ ПУСТЫЕ КОМНАТЫ
                cleanup_empty_rooms(room_name)

        # Присоединяемся к новой комнате
        join_room(new_room_name)
        active_users[new_room_name][current_user.id] = current_user.username
        current_user.online = True
        current_user.ping()
        db.session.commit()

        # Отправляем новому пользователю список участников комнаты
        emit('current_users', {
            'users': dict(active_users[new_room_name]),
            'room': new_room_name,
        }, to=request.sid)

        # Оповещаем других о новом участнике
        emit('user_joined', {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': new_room_name
        }, room=new_room_name, include_self=False)

        # Отправляем обновленный список пользователей всем в комнате
        emit('current_users', {
            'users': dict(active_users[new_room_name]),
            'room': new_room_name
        }, room=new_room_name)

        broadcast_room_list()

    @socketio.on('get_current_users')
    def handle_get_current_users(data):
        """Запрос списка пользователей в текущей комнате"""
        if not current_user.is_authenticated:
            return

        room_name = data.get('room', DEFAULT_ROOM)

        if room_name in active_users:
            emit('current_users', {
                'users': dict(active_users[room_name]),
                'room': room_name
            }, to=request.sid)

    @socketio.on('send_message')
    def handle_send_message(data):
        """Обработчик отправки сообщения в комнату"""
        if not current_user.is_authenticated:
            return

        room_name = data.get('room')
        message_content = data.get('message', '').strip()

        if not room_name or not message_content:
            return

        # Сохраняем сообщение в базу данных
        try:
            # Находим или создаем комнату
            room = Room.query.filter_by(name=room_name).first()
            if not room:
                room = Room(name=room_name, created_by=current_user.id)
                db.session.add(room)
                db.session.commit()

            # Создаем сообщение для комнаты
            new_message = Message(
                content=message_content,
                sender_id=current_user.id,
                room_id=room.id,  # Используем room_id вместо room
                is_dm=False  # Указываем, что это не личное сообщение
            )

            db.session.add(new_message)
            db.session.commit()

            # Отправляем сообщение всем в комнате, КРОМЕ отправителя
            emit('new_message', {
                'sender_id': current_user.id,
                'sender_username': current_user.username,
                'content': new_message.content,
                'room': room_name,
                'room_id': room.id,
                'timestamp': new_message.timestamp.isoformat(),
                'created_at': new_message.timestamp.isoformat(),
                'is_dm': False,
            }, room=room_name, include_self=False)  # ИСКЛЮЧАЕМ отправителя

        except Exception as e:
            print(f"Ошибка при сохранении сообщения: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

    @socketio.on('get_message_history')
    def handle_get_message_history(data):
        """Обработчик загрузки истории сообщений комнаты"""
        if not current_user.is_authenticated:
            return

        room_name = data.get('room')
        limit = data.get('limit', 20)  # По умолчанию 20 сообщений

        if not room_name:
            return

        try:
            # Находим комнату
            room = Room.query.filter_by(name=room_name).first()
            if not room:
                return

            # Загружаем сообщения с ограничением
            messages = Message.query.filter_by(
                room_id=room.id,
                is_dm=False
            ).order_by(
                Message.timestamp.desc()
            ).limit(limit).all()

            # Преобразуем в правильный порядок (от старых к новым)
            messages.reverse()

            # Форматируем сообщения для отправки
            messages_data = []
            for message in messages:
                messages_data.append({
                    'id': message.id,
                    'sender_id': message.sender_id,
                    'sender_username': message.sender.username if message.sender else 'Unknown',
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_dm': False,
                    'room': room_name
                })

            # Отправляем историю клиенту
            emit('message_history', {
                'room': room_name,
                'messages': messages_data,
                'has_more': len(messages) == limit  # Есть ли еще сообщения
            })

        except Exception as e:
            print(f"Ошибка при загрузке истории сообщений: {e}")
            emit('message_history_error', {
                'error': 'Не удалось загрузить историю сообщений'
            })

    @socketio.on('start_dm')
    def handle_start_dm(data):
        """Обработчик начала личной переписки - загружает историю сообщений"""
        if not current_user.is_authenticated:
            return

        recipient_id = data.get('recipient_id')
        limit = data.get('limit', 20)  # Добавляем ограничение

        if not recipient_id:
            return

        try:
            # Находим получателя
            recipient = User.query.get(recipient_id)
            if not recipient:
                print(f"Получатель с ID {recipient_id} не найден")
                return

            # Загружаем историю переписки между текущим пользователем и получателем
            messages = Message.query.filter(
                ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
                ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
            ).filter_by(is_dm=True).order_by(
                Message.timestamp.desc()
            ).all()

            # Преобразуем сообщения в правильном порядке
            messages.reverse()

            # Преобразуем сообщения в словари
            messages_data = []
            for message in messages:
                messages_data.append({
                    'sender_id': message.sender_id,
                    'sender_username': message.sender.username if message.sender else 'Unknown',
                    'recipient_id': message.recipient_id,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_dm': True
                })

            # Отправляем историю переписки клиенту
            emit('dm_history', {
                'recipient_id': recipient_id,
                'recipient_name': recipient.username,
                'messages': messages_data
            })
        except Exception as e:
            print(f"Ошибка при загрузке истории ЛС: {e}")

    @socketio.on('send_dm')
    def handle_send_dm(data):
        """Обработчик отправки личного сообщения"""
        if not current_user.is_authenticated:
            return

        recipient_id = data.get('recipient_id')
        message_content = data.get('message', '').strip()

        if not recipient_id or not message_content:
            return

        try:
            # Сохраняем сообщение в базу данных
            new_message = Message(
                content=message_content,
                sender_id=current_user.id,
                recipient_id=recipient_id,
                is_dm=True
            )

            db.session.add(new_message)
            db.session.commit()

            # Формируем данные сообщения
            message_data = {
                'sender_id': current_user.id,
                'sender_username': current_user.username,
                'recipient_id': recipient_id,
                'content': new_message.content,
                'timestamp': new_message.timestamp.isoformat(),
                'is_dm': True
            }

            # Отправляем сообщение получателю
            recipient_sid = connected_users.get(int(recipient_id))
            if recipient_sid:
                emit('new_dm', message_data, room=recipient_sid)

                # ОБНОВЛЯЕМ СПИСОК ДИАЛОГОВ ПОЛУЧАТЕЛЯ
                emit('dm_conversations', {
                    'conversations': get_dm_conversations(int(recipient_id))
                }, room=recipient_sid)

                # ОТПРАВЛЯЕМ СИГНАЛ ДЛЯ ОБНОВЛЕНИЯ ИНДИКАТОРА
                emit('update_unread_indicator', {
                    'sender_id': current_user.id,
                    'username': current_user.username
                }, room=recipient_sid)

            # ТАКЖЕ ОБНОВЛЯЕМ СПИСОК ДИАЛОГОВ ОТПРАВИТЕЛЯ
            emit('dm_conversations', {
                'conversations': get_dm_conversations(current_user.id)
            })
        except Exception as e:
            print(f"Ошибка при отправке ЛС: {e}")
            db.session.rollback()

    @socketio.on('update_unread_indicator')
    def handle_update_unread_indicator(data):
        """Обработчик для обновления индикатора непрочитанных"""
        # Этот обработчик будет вызываться на клиенте
        # Сервер просто пересылает сигнал получателю
        recipient_id = data.get('recipient_id')
        if recipient_id:
            recipient_sid = connected_users.get(int(recipient_id))
            if recipient_sid:
                emit('update_unread_indicator', data, room=recipient_sid)

    @socketio.on('get_dm_conversations')
    def handle_get_dm_conversations():
        """Обработчик запроса списка диалогов"""
        if not current_user.is_authenticated:
            return

        try:
            conversations = get_dm_conversations(current_user.id)
            emit('dm_conversations', {
                'conversations': conversations
            })
        except Exception as e:
            print(f"Ошибка при получении диалогов: {e}")

    @socketio.on('mark_messages_as_read')
    def handle_mark_messages_as_read(data):
        """Помечает сообщения как прочитанные"""
        if not current_user.is_authenticated:
            return

        sender_id = data.get('sender_id')

        try:
            # Помечаем все непрочитанные сообщения от этого пользователя как прочитанные
            unread_messages = Message.query.filter(
                (Message.sender_id == sender_id) &
                (Message.recipient_id == current_user.id) &
                (Message.is_read == False)
            ).all()

            for message in unread_messages:
                message.is_read = True

            db.session.commit()

            # Обновляем список диалогов
            emit('dm_conversations', {
                'conversations': get_dm_conversations(current_user.id)
            })

            # Отправляем подтверждение
            emit('messages_marked_read', {
                'success': True,
                'sender_id': sender_id
            })
        except Exception as e:
            print(f"Ошибка при пометке сообщений как прочитанных: {e}")
            db.session.rollback()


def broadcast_room_list():
    """Рассылает актуальный список комнат всем клиентам."""
    room_list = get_rooms_list()
    emit('room_list', {'rooms': room_list}, broadcast=True)


def get_rooms_list():
    """Возвращает список всех комнат: постоянные + активные с пользователями."""
    # Всегда включаем комнату по умолчанию
    all_rooms = {DEFAULT_ROOM}

    # Добавляем все комнаты из базы данных
    rooms_from_db = Room.query.all()
    for room in rooms_from_db:
        all_rooms.add(room.name)

    # Добавляем все комнаты, где есть пользователи (исключаем DM комнаты)
    for room_name in active_users.keys():
        if not room_name.startswith('dm_'):
            all_rooms.add(room_name)
    return sorted(list(all_rooms))  # Просто список названий комнат


def cleanup_empty_rooms(room_name):
    """Удаляет комнату из базы, если в ней нет пользователей и это не комната по умолчанию"""
    if room_name == DEFAULT_ROOM:
        return  # Не удаляем комнату по умолчанию

    if room_name in active_users and not active_users[room_name]:
        # Комната пустая - удаляем из active_users
        del active_users[room_name]

        # Удаляем из базы данных
        room = Room.query.filter_by(name=room_name).first()
        if room:
            # Сначала удаляем все сообщения этой комнаты
            Message.query.filter_by(room_id=room.id).delete()
            # Затем удаляем саму комнату
            db.session.delete(room)
            db.session.commit()

            # Рассылаем обновленный список комнат
            broadcast_room_list()


def get_dm_conversations(user_id):
    """Возвращает список диалогов для пользователя"""
    conversations = []

    # Находим всех пользователей, с которыми есть переписка
    sent_messages = Message.query.filter_by(sender_id=user_id, is_dm=True).all()
    received_messages = Message.query.filter_by(recipient_id=user_id, is_dm=True).all()

    # Собираем уникальных собеседников
    interlocutors = set()
    for msg in sent_messages:
        interlocutors.add(msg.recipient_id)
    for msg in received_messages:
        interlocutors.add(msg.sender_id)

    # Для каждого собеседника получаем информацию
    for interlocutor_id in interlocutors:
        interlocutor = User.query.get(interlocutor_id)
        if interlocutor:
            # Находим последнее сообщение в диалоге
            last_message = Message.query.filter(
                ((Message.sender_id == user_id) & (Message.recipient_id == interlocutor_id)) |
                ((Message.sender_id == interlocutor_id) & (Message.recipient_id == user_id))
            ).filter_by(is_dm=True).order_by(Message.timestamp.desc()).first()

            # Считаем непрочитанные сообщения (ВАЖНО: только входящие сообщения)
            unread_count = Message.query.filter(
                (Message.sender_id == interlocutor_id) &
                (Message.recipient_id == user_id) &
                (Message.is_read == False)  # Сообщения не прочитаны
            ).count()

            # Преобразуем datetime в строку
            last_message_time = last_message.timestamp.isoformat() if last_message else None

            conversations.append({
                'user_id': interlocutor_id,
                'username': interlocutor.username,
                'last_message_time': last_message_time,
                'unread_count': unread_count,  # Добавляем счетчик непрочитанных
            })

    return conversations



