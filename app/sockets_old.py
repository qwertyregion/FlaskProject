from collections import defaultdict
from app.models import Room
from flask import request, current_app
from flask_login import current_user
from flask_socketio import leave_room, emit, join_room
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Message, User
from app.validators import WebSocketValidator, validate_websocket_data
from app.state import user_state, conn_mgr, room_mgr
import logging

DEFAULT_ROOM = 'general_chat'

# Локальный in-memory кеш (fallback для dev)
active_users = defaultdict(dict)  # {room: {user_id: username}}
active_users[DEFAULT_ROOM] = {}
connected_users = {}  # {user_id: socket_id}
dm_rooms = defaultdict(set)

# Менеджеры состояния уже импортированы из app.state


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
            # Регистрируем соединение в Redis
            try:
                conn_mgr.register_connection(user_id, request.sid)
            except Exception as e:
                current_app.logger.warning(f"Redis conn register failed: {e}")
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
            current_app.logger.info(f"Добавили пользователя {current_user.username} (ID: {current_user.id}) в active_users для комнаты {DEFAULT_ROOM}")
            current_app.logger.info(f"Текущее состояние active_users: {active_users}")

            # Дублируем состояние в Redis
            try:
                user_state.ensure_room_exists(DEFAULT_ROOM)
                user_state.add_user_to_room(user_id, current_user.username, DEFAULT_ROOM)
            except Exception as e:
                current_app.logger.warning(f"Redis add_user_to_room failed: {e}")

            # Отправляем список пользователей в комнате по умолчанию
            try:
                users = user_state.get_room_users(DEFAULT_ROOM)
            except Exception:
                users = dict(active_users[DEFAULT_ROOM])
            
            # Убеждаемся, что текущий пользователь включен в список
            if user_id not in users:
                users[user_id] = current_user.username
                
            current_app.logger.info(f"Отправляем список пользователей: {users} для комнаты {DEFAULT_ROOM}")
            emit('current_users', {'users': users, 'room': DEFAULT_ROOM}, to=request.sid)

            # Отправляем список комнат новому пользователю
            rooms_list = get_rooms_list()
            current_app.logger.info(f"Отправляем список комнат: {rooms_list}")
            emit('room_list', {'rooms': rooms_list})

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
                # Синхронизируем удаление пользователя из комнаты в менеджере состояния (Redis/in-memory)
                try:
                    user_state.remove_user_from_room(user_id, room_name)
                except Exception as e:
                    current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")
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
        # Удаляем соединение в Redis
        try:
            conn_mgr.remove_connection(user_id)
        except Exception as e:
            current_app.logger.warning(f"Redis remove_connection failed: {e}")

        # Обновляем статус
        if user_was_in_any_room:
            current_user.online = False
            db.session.commit()
            broadcast_room_list()

    @socketio.on('heartbeat')
    def handle_heartbeat(data=None):
        if not current_user.is_authenticated:
            return
        try:
            ttl = None
            if isinstance(data, dict):
                ttl = data.get('ttl')
            conn_mgr.refresh_heartbeat(current_user.id, ttl_seconds=ttl)
        except Exception as e:
            current_app.logger.warning(f"Heartbeat refresh failed: {e}")

    @socketio.on('create_room')
    def handle_create_room(data):
        """Обработчик создания новой комнаты"""
        if not current_user.is_authenticated:
            current_app.logger.warning("Попытка создания комнаты неавторизованным пользователем")
            emit('room_created', {'success': False, 'message': 'Не авторизован'})
            return
            
        current_app.logger.info(f"Запрос создания комнаты от пользователя {current_user.id}: {data}")

        # Валидация входных данных
        validation = validate_websocket_data(data, ['room_name'])
        if not validation['valid']:
            current_app.logger.warning(f"Ошибка валидации данных: {validation['error']}")
            emit('room_created', {'success': False, 'message': validation['error']})
            return

        # Валидация названия комнаты
        room_validation = WebSocketValidator.validate_room_name(data.get('room_name'))
        if not room_validation['valid']:
            current_app.logger.warning(f"Ошибка валидации названия комнаты: {room_validation['error']}")
            emit('room_created', {'success': False, 'message': room_validation['error']})
            return

        room_name = room_validation['room_name']

        try:
            # Проверяем, нет ли уже такой комнаты
            existing_room = Room.query.filter_by(name=room_name).first()
            if existing_room:
                current_app.logger.warning(f"Попытка создать существующую комнату: {room_name}")
                emit('room_created', {'success': False, 'message': 'Комната с таким названием уже существует'})
                return

            # Создаем новую комнату
            current_app.logger.info(f"Создаем новую комнату: {room_name} пользователем {current_user.id}")
            new_room = Room(
                name=room_name,
                created_by=current_user.id
            )
            db.session.add(new_room)
            db.session.commit()
            current_app.logger.info(f"Комната {room_name} успешно создана в БД")

            # Создаем комнату в Redis (best-effort)
            try:
                room_mgr.create_room_if_absent(room_name, current_user.id)
            except Exception as e:
                current_app.logger.warning(f"Redis create_room_if_absent failed: {e}")

            # автоматически присоединяем создателя к новой комнате
            join_room(room_name)
            if room_name not in active_users:
                active_users[room_name] = {}
            active_users[room_name][current_user.id] = current_user.username

            try:
                user_state.add_user_to_room(current_user.id, current_user.username, room_name)
            except Exception as e:
                current_app.logger.warning(f"Redis add_user_to_room failed: {e}")

            # ОТПРАВЛЯЕМ ОБНОВЛЕННЫЙ СПИСОК КОМНАТ ВСЕМ КЛИЕНТАМ
            current_app.logger.info(f"Отправляем обновленный список комнат")
            broadcast_room_list()

            # ОТПРАВЛЯЕМ СОЗДАТЕЛЮ ОТВЕТ С ФЛАГОМ ДЛЯ АВТОПЕРЕХОДА
            current_app.logger.info(f"Отправляем событие room_created создателю")
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
            current_app.logger.error(f"Ошибка при создании комнаты: {e}")
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
                # Синхронизируем удаление пользователя из менеджера состояния (Redis/in-memory)
                try:
                    user_state.remove_user_from_room(current_user.id, room_name)
                except Exception as e:
                    current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")

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

        # Получаем пользователей из локального кеша
        users = dict(active_users.get(room_name, {}))
        
        # Убеждаемся, что текущий пользователь включен в список
        if current_user.id not in users:
            users[current_user.id] = current_user.username
            
        current_app.logger.info(f"Запрос списка пользователей для комнаты {room_name}: {users}")
        emit('current_users', {
            'users': users,
            'room': room_name
        }, to=request.sid)

    @socketio.on('send_message')
    def handle_send_message(data):
        """Обработчик отправки сообщения в комнату"""
        if not current_user.is_authenticated:
            return

        # Валидация входных данных
        validation = validate_websocket_data(data, ['room', 'message'])
        if not validation['valid']:
            emit('message_error', {'error': validation['error']})
            return

        room_name = data.get('room')
        
        # Валидация содержимого сообщения
        message_validation = WebSocketValidator.validate_message_content(data.get('message'))
        if not message_validation['valid']:
            emit('message_error', {'error': message_validation['error']})
            return

        message_content = message_validation['content']

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
            logging.error(f"Ошибка при сохранении сообщения: {e}")
            emit('message_error', {'error': 'Ошибка при отправке сообщения'})
            db.session.rollback()

    # пагинация обработчика истории сообщений
    @socketio.on('load_more_messages')
    def handle_load_more_messages(data):
        """Загрузка дополнительных сообщений с пагинацией"""
        if not current_user.is_authenticated:
            return

        room_name = data.get('room')
        offset = data.get('offset', 0)
        limit = data.get('limit', 10)

        try:
            # Проверяем, что комната существует
            room = Room.query.filter_by(name=room_name).first()
            if not room:
                emit('load_more_error', {'error': 'Комната не найдена'})
                return

            # Загружаем сообщения с предзагрузкой отправителей
            messages = Message.query.options(
                joinedload(Message.sender)
            ).filter_by(
                room_id=room.id,
                is_dm=False
            ).order_by(
                Message.timestamp.desc()
            ).offset(offset).limit(limit).all()

            messages.reverse()  # Меняем порядок на старые → новые

            messages_data = []
            for message in messages:
                messages_data.append({
                    'id': message.id,
                    'sender_id': message.sender_id,
                    'sender_username': message.sender.username,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'is_dm': False,
                    'room': room_name  # Добавляем информацию о комнате
                })

            emit('more_messages_loaded', {
                'messages': messages_data,
                'has_more': len(messages) == limit,
                'offset': offset + len(messages),
                'room': room_name  # Добавляем информацию о комнате
            })

        except Exception as e:
            current_app.logger.error(f"Ошибка при загрузке сообщений: {e}")
            emit('load_more_error', {'error': 'Ошибка загрузки сообщений'})

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

            # Загружаем сообщения с ограничением и предзагружаем отправителей
            messages = Message.query.options(
                joinedload(Message.sender)
            ).filter_by(
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
            current_app.logger.error(f"Ошибка при загрузке истории сообщений: {e}")
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

            # Загружаем историю переписки между текущим пользователем и получателем с предзагрузкой отправителей
            messages = Message.query.options(
                joinedload(Message.sender)
            ).filter(
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
            current_app.logger.error(f"Ошибка при загрузке истории ЛС: {e}")

    @socketio.on('send_dm')
    def handle_send_dm(data):
        """Обработчик отправки личного сообщения"""
        if not current_user.is_authenticated:
            return

        recipient_id = data.get('recipient_id')
        message_content_raw = data.get('message', '')

        if not recipient_id or not message_content_raw:
            return

        try:
            # Валидация содержимого сообщения (аналогично send_message)
            message_validation = WebSocketValidator.validate_message_content(message_content_raw)
            if not message_validation['valid']:
                emit('message_error', {'error': message_validation['error']})
                return
            message_content = message_validation['content']

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
            current_app.logger.error(f"Ошибка при отправке ЛС: {e}")
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
            current_app.logger.error(f"Ошибка при получении диалогов: {e}")

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
            current_app.logger.error(f"Ошибка при пометке сообщений как прочитанных: {e}")
            db.session.rollback()


def broadcast_room_list():
    """Рассылает актуальный список комнат всем клиентам."""
    room_list = get_rooms_list()
    emit('room_list', {'rooms': room_list}, broadcast=True)


def get_rooms_list():
    """Возвращает список всех комнат: DB + активные (Redis + локальный fallback)."""
    all_rooms = {DEFAULT_ROOM}

    # Из БД
    for room in Room.query.all():
        all_rooms.add(room.name)

    # Из локального кеша (fallback)
    for room_name in active_users.keys():
        if not room_name.startswith('dm_'):
            all_rooms.add(room_name)

    # Из Redis (активные комнаты) - используем локальный менеджер
    try:
        redis_rooms = room_mgr.get_all_rooms()
        all_rooms.update(redis_rooms)
    except Exception as e:
        current_app.logger.error(f"Error getting rooms from Redis: {e}")

    return sorted(all_rooms)


def cleanup_empty_rooms(room_name):
    """Удаляет комнату если пустая (Redis + локальный fallback)."""
    current_app.logger.info(f"Проверяем комнату {room_name} на пустоту")
    
    if room_name == DEFAULT_ROOM:
        current_app.logger.info(f"Комната {room_name} - это комната по умолчанию, не удаляем")
        return

    # Проверяем локально
    no_local_users = room_name in active_users and not active_users[room_name]
    current_app.logger.info(f"Локально в комнате {room_name} пользователей: {len(active_users.get(room_name, {}))}, пустая: {no_local_users}")

    # Проверяем Redis - используем локальный менеджер
    no_redis_users = True
    try:
        users = user_state.get_room_users(room_name)
        no_redis_users = len(users) == 0
        current_app.logger.info(f"В Redis в комнате {room_name} пользователей: {len(users)}, пустая: {no_redis_users}")
    except Exception as e:
        current_app.logger.error(f"Error checking Redis for room {room_name}: {e}")

    if no_local_users and no_redis_users:
        current_app.logger.info(f"Комната {room_name} пустая, удаляем...")
        # Удаляем из локального кеша
        if room_name in active_users:
            del active_users[room_name]

        # Удаляем из Redis - используем локальный менеджер
        try:
            room_mgr.cleanup_empty_room(room_name)
            room_mgr.remove_room_meta(room_name)
        except Exception as e:
            current_app.logger.error(f"Error cleaning Redis for room {room_name}: {e}")
        
        # Удаляем из БД
        room = Room.query.filter_by(name=room_name).first()
        if room:
            Message.query.filter_by(room_id=room.id).delete()
            db.session.delete(room)
            db.session.commit()
        
        # Уведомляем всех клиентов об обновлении списка комнат
        current_app.logger.info(f"Комната {room_name} успешно удалена, отправляем обновленный список комнат")
        broadcast_room_list()
    else:
        current_app.logger.info(f"Комната {room_name} не пустая, оставляем")


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

