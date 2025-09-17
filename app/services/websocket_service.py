"""
Сервис для WebSocket операций
"""
from typing import Dict, List, Optional, Any
from collections import defaultdict
from flask import current_app, request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import db
from app.models import User
from app.state import user_state, conn_mgr, room_mgr
from .message_service import MessageService
from .room_service import RoomService
from .user_service import UserService


class WebSocketService:
    """Сервис для WebSocket операций"""
    
    # Константы
    DEFAULT_ROOM = 'general_chat'
    
    def __init__(self):
        # Локальный in-memory кеш (fallback для dev)
        self.active_users = defaultdict(dict)  # {room: {user_id: username}}
        self.active_users[self.DEFAULT_ROOM] = {}
        self.connected_users = {}  # {user_id: socket_id}
        self.dm_rooms = defaultdict(set)
    
    def handle_connect(self, socketio) -> None:
        """Обрабатывает подключение пользователя"""
        if not current_user.is_authenticated:
            current_app.logger.warning("🔴 [CONNECT DEBUG] Пользователь не аутентифицирован")
            return
        
        user_id = current_user.id
        current_app.logger.info(f"🔵 [CONNECT DEBUG] Подключение пользователя {user_id} ({current_user.username}) с SID {request.sid}")
        
        # Проверяем, не подключен ли пользователь уже
        if user_id in self.connected_users:
            old_sid = self.connected_users[user_id]
            current_app.logger.info(f"🔵 [CONNECT DEBUG] Пользователь {user_id} уже подключен с SID {old_sid}")
            if old_sid != request.sid:
                # Отключаем старое соединение
                current_app.logger.info(f"🔵 [CONNECT DEBUG] Отключаем старое соединение {old_sid}")
                leave_room(self.DEFAULT_ROOM, sid=old_sid)
                socketio.server.disconnect(old_sid)
        
        # Регистрируем новое соединение
        self.connected_users[user_id] = request.sid
        current_app.logger.info(f"✅ [CONNECT DEBUG] Пользователь {user_id} зарегистрирован с SID {request.sid}")
        current_app.logger.info(f"🔵 [CONNECT DEBUG] Все подключенные пользователи: {self.connected_users}")
        
        # Регистрируем соединение в Redis
        try:
            conn_mgr.register_connection(user_id, request.sid)
        except Exception as e:
            current_app.logger.warning(f"Redis conn register failed: {e}")
        
        # Обновляем статус пользователя
        join_room('app_aware_clients')
        UserService.set_user_online(user_id, True)
        emit('user_status', {'user_id': user_id, 'online': True}, broadcast=True)
        
        # Автоматически присоединяем к комнате по умолчанию
        self._join_default_room(user_id)
        
        # Отправляем данные пользователю
        self._send_initial_data(user_id)
    
    def handle_disconnect(self) -> None:
        """Обрабатывает отключение пользователя"""
        if not current_user.is_authenticated:
            return
        
        user_id = current_user.id
        username = current_user.username
        user_was_in_any_room = False
        
        # Удаляем пользователя из всех комнат
        for room_name, users in list(self.active_users.items()):
            if user_id in users:
                user_was_in_any_room = True
                del users[user_id]
                
                # Удаляем из Redis
                try:
                    user_state.remove_user_from_room(user_id, room_name)
                except Exception as e:
                    current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")
                
                # Уведомляем остальных пользователей
                emit('user_left', {
                    'user_id': user_id,
                    'username': current_user.username,
                    'room': room_name
                }, room=room_name, include_self=False)
                
                # Отправляем обновленный список пользователей
                emit('current_users', {
                    'users': dict(users),
                    'room': room_name
                }, room=room_name)
                
                # ПРОВЕРЯЕМ И УДАЛЯЕМ ПУСТЫЕ КОМНАТЫ
                self._check_and_cleanup_empty_room(room_name)
        
        # Удаляем из локального кеша
        if user_id in self.connected_users:
            del self.connected_users[user_id]
        
        # Обновляем статус пользователя
        UserService.set_user_online(user_id, False)
        emit('user_status', {'user_id': user_id, 'online': False}, broadcast=True)
        
        # Удаляем соединение из Redis
        try:
            conn_mgr.remove_connection(user_id)
        except Exception as e:
            current_app.logger.warning(f"Redis remove_connection failed: {e}")
    
    def _check_and_cleanup_empty_room(self, room_name: str) -> None:
        """Проверяет и удаляет одну пустую комнату"""
        try:
            # Проверяем, что комната не является комнатой по умолчанию
            if room_name == self.DEFAULT_ROOM:
                return
            
            # Проверяем локальный кеш
            local_users = self.active_users.get(room_name, {})
            local_user_count = len(local_users)
            
            # Проверяем Redis
            redis_user_count = 0
            try:
                redis_users = user_state.get_room_users(room_name)
                redis_user_count = len(redis_users)
            except Exception as e:
                current_app.logger.warning(f"Redis get_room_users failed: {e}")
            
            # Если комната пустая в обоих местах, удаляем её
            if local_user_count == 0 and redis_user_count == 0:
                # Удаляем из БД через сервис
                success = RoomService.cleanup_empty_room(room_name)
                
                if success:
                    # Удаляем из локального кеша
                    if room_name in self.active_users:
                        del self.active_users[room_name]
                    
                    # Уведомляем всех клиентов об обновлении списка комнат
                    self._broadcast_room_list()
                
        except Exception as e:
            current_app.logger.error(f"Ошибка при проверке комнаты '{room_name}': {e}")
    
    def _check_and_cleanup_empty_rooms(self) -> None:
        """Проверяет и удаляет пустые комнаты"""
        try:
            # Получаем все комнаты кроме комнаты по умолчанию
            rooms = RoomService.get_all_rooms()
            
            for room_data in rooms:
                room_name = room_data['name']
                if room_name == self.DEFAULT_ROOM:
                    continue
                
                # Проверяем, есть ли пользователи в комнате
                has_users = False
                
                # Проверяем локальный кеш
                if room_name in self.active_users and self.active_users[room_name]:
                    has_users = True
                
                # Проверяем Redis
                if not has_users:
                    try:
                        users = user_state.get_room_users(room_name)
                        has_users = len(users) > 0
                    except Exception as e:
                        current_app.logger.warning(f"Redis get_room_users failed: {e}")
                
                # Если комната пустая, удаляем её
                if not has_users:
                    current_app.logger.info(f"Комната {room_name} пустая, удаляем...")
                    RoomService.cleanup_empty_room(room_name)
                    
                    # Удаляем из локального кеша
                    if room_name in self.active_users:
                        del self.active_users[room_name]
                    
                    # Уведомляем всех клиентов об обновлении списка комнат
                    self._broadcast_room_list()
                    
        except Exception as e:
            current_app.logger.error(f"Error checking empty rooms: {e}")
    
    def handle_heartbeat(self, data: Optional[Dict] = None) -> None:
        """Обрабатывает heartbeat от клиента"""
        if not current_user.is_authenticated:
            return
        
        user_id = current_user.id
        
        # Обновляем heartbeat в Redis
        try:
            conn_mgr.refresh_heartbeat(user_id)
        except Exception as e:
            current_app.logger.warning(f"Redis refresh_heartbeat failed: {e}")
        
        # Отправляем подтверждение
        emit('heartbeat_ack', {'timestamp': data.get('timestamp') if data else None})
    
    def handle_create_room(self, data: Dict) -> None:
        """Обрабатывает создание комнаты"""
        if not current_user.is_authenticated:
            return
        
        # ИСПРАВЛЕНО: используем 'room_name' как в sockets_old.py
        room_name = data.get('room_name', '').strip()
        
        if not room_name:
            emit('room_created', {'success': False, 'message': 'Название комнаты не может быть пустым'})
            return
        
        # Создаем комнату через сервис (БЕЗ description)
        room = RoomService.create_room(
            name=room_name,
            creator_id=current_user.id
        )
        
        if room:
            # ИСПРАВЛЕНО: используем формат ответа как в sockets_old.py
            emit('room_created', {
                'success': True,
                'room_name': room.name,
                'message': f'Комната "{room.name}" создана!',
                'auto_join': True  # Флаг для автоматического перехода
            })
            
            # Обновляем список комнат
            self._broadcast_room_list()
        else:
            emit('room_created', {'success': False, 'message': 'Не удалось создать комнату'})
    
    def handle_join_room(self, data: Dict) -> None:
        """Обрабатывает присоединение к комнате"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        if not room_name:
            return
        
        user_id = current_user.id
        username = current_user.username
        
        # Выходим из предыдущих комнат (кроме DM комнат и комнаты по умолчанию)
        for existing_room_name, users in list(self.active_users.items()):
            if not existing_room_name.startswith('dm_') and user_id in users and existing_room_name != room_name:
                leave_room(existing_room_name)
                del self.active_users[existing_room_name][user_id]
                
                # Синхронизируем удаление пользователя из менеджера состояния (Redis/in-memory)
                try:
                    user_state.remove_user_from_room(user_id, existing_room_name)
                except Exception as e:
                    current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")
                
                emit('user_left', {
                    'user_id': user_id,
                    'username': username,
                    'room': existing_room_name,
                }, room=existing_room_name)
                
                # Отправляем обновленный список пользователей
                emit('current_users', {
                    'users': dict(self.active_users[existing_room_name]),
                    'room': existing_room_name
                }, room=existing_room_name)
                
                # ПРОВЕРЯЕМ И УДАЛЯЕМ ПУСТЫЕ КОМНАТЫ
                self._check_and_cleanup_empty_room(existing_room_name)
        
        # Получаем комнату или создаем если не существует
        room = RoomService.get_room_by_name(room_name)
        if not room:
            room = RoomService.create_room(
                name=room_name,
                creator_id=user_id
            )
            if not room:
                emit('room_join_error', {'error': 'Не удалось создать комнату'})
                return
        
        # Присоединяемся к комнате
        join_room(room_name)
        
        # Добавляем в локальный кеш
        if room_name not in self.active_users:
            self.active_users[room_name] = {}
        self.active_users[room_name][user_id] = username
        
        # Добавляем в Redis
        try:
            user_state.ensure_room_exists(room_name)
            user_state.add_user_to_room(user_id, username, room_name)
        except Exception as e:
            current_app.logger.warning(f"Redis add_user_to_room failed: {e}")
        
        # Уведомляем других пользователей
        emit('user_joined', {
            'user_id': user_id,
            'username': username,
            'room': room_name
        }, room=room_name, include_self=False)
        
        # Отправляем список пользователей в комнате
        self._send_room_users(room_name)
        
        # Обновляем список комнат
        self._broadcast_room_list()
        
        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: проверяем все комнаты на пустоту после переключения
        for check_room_name, check_users in list(self.active_users.items()):
            if not check_room_name.startswith('dm_') and check_room_name != self.DEFAULT_ROOM and len(check_users) == 0:
                self._check_and_cleanup_empty_room(check_room_name)
    
    def handle_leave_room(self, data: Dict) -> None:
        """Обрабатывает выход из комнаты"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        if not room_name:
            return
        
        user_id = current_user.id
        username = current_user.username
        
        # Проверяем, что пользователь находится в этой комнате
        if room_name not in self.active_users or user_id not in self.active_users[room_name]:
            return
        
        # Выходим из комнаты
        leave_room(room_name)
        del self.active_users[room_name][user_id]
        
        # Удаляем из Redis
        try:
            user_state.remove_user_from_room(user_id, room_name)
        except Exception as e:
            current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")
        
        # Уведомляем остальных пользователей
        emit('user_left', {
            'user_id': user_id,
            'username': username,
            'room': room_name
        }, room=room_name, include_self=False)
        
        # Отправляем обновленный список пользователей
        emit('current_users', {
            'users': dict(self.active_users[room_name]),
            'room': room_name
        }, room=room_name)
        
        # ПРОВЕРЯЕМ И УДАЛЯЕМ ПУСТЫЕ КОМНАТЫ
        self._check_and_cleanup_empty_room(room_name)
    
    def handle_send_message(self, data: Dict) -> None:
        """Обрабатывает отправку сообщения"""
        if not current_user.is_authenticated:
            return
        
        # ИСПРАВЛЕНО: используем 'message' как в sockets_old.py
        content = data.get('message', '').strip()
        room_name = data.get('room', '').strip()
        
        if not content or not room_name:
            return
        
        # Получаем комнату или создаем если не существует
        room = RoomService.get_room_by_name(room_name)
        if not room:
            # Создаем комнату если не существует (как в sockets_old.py)
            room = RoomService.create_room(
                name=room_name,
                creator_id=current_user.id
            )
            if not room:
                emit('message_error', {'error': 'Не удалось создать комнату'})
                return
        
        # Создаем сообщение через сервис
        message = MessageService.create_message(
            content=content,
            sender_id=current_user.id,
            room_id=room.id
        )
        
        if message:
            # ИСПРАВЛЕНО: используем формат как в sockets_old.py и ИСКЛЮЧАЕМ отправителя
            emit('new_message', {
                'sender_id': message.sender_id,
                'sender_username': current_user.username,
                'content': message.content,
                'room': room_name,
                'room_id': room.id,
                'timestamp': message.timestamp.isoformat(),
                'created_at': message.timestamp.isoformat(),
                'is_dm': False,
            }, room=room_name, include_self=False)  # ИСКЛЮЧАЕМ отправителя
        else:
            emit('message_error', {'error': 'Не удалось отправить сообщение'})
    
    def handle_send_dm(self, data: Dict) -> None:
        """Обрабатывает отправку личного сообщения"""
        current_app.logger.info(f"🔵 [DM DEBUG] handle_send_dm вызван с данными: {data}")
        current_app.logger.info(f"🔵 [DM DEBUG] Текущий пользователь: {current_user.id if current_user.is_authenticated else 'не аутентифицирован'}")
        
        if not current_user.is_authenticated:
            current_app.logger.warning("🔴 [DM DEBUG] Пользователь не аутентифицирован")
            emit('dm_error', {'error': 'Пользователь не аутентифицирован'})
            return
        
        # ИСПРАВЛЕНО: используем 'message' как в sockets_old.py
        content = data.get('message', '').strip()
        recipient_id = data.get('recipient_id')
        
        current_app.logger.info(f"🔵 [DM DEBUG] Отправитель: {current_user.id} ({current_user.username})")
        current_app.logger.info(f"🔵 [DM DEBUG] Получатель ID: {recipient_id}")
        current_app.logger.info(f"🔵 [DM DEBUG] Содержимое: '{content}'")
        current_app.logger.info(f"🔵 [DM DEBUG] Длина содержимого: {len(content)}")
        
        if not content or not recipient_id:
            current_app.logger.warning(f"🔴 [DM DEBUG] Недостаточно данных: content='{content}', recipient_id={recipient_id}")
            emit('dm_error', {'error': 'Недостаточно данных для отправки сообщения'})
            return
        
        # Проверяем, что пользователь не отправляет сообщение самому себе
        if int(recipient_id) == current_user.id:
            current_app.logger.warning(f"🔴 [DM DEBUG] Попытка отправить сообщение самому себе")
            emit('dm_error', {'error': 'Нельзя отправлять сообщения самому себе'})
            return
        
        # Проверяем получателя
        recipient = UserService.get_user_by_id(recipient_id)
        if not recipient:
            current_app.logger.warning(f"🔴 [DM DEBUG] Получатель {recipient_id} не найден")
            emit('dm_error', {'error': 'Получатель не найден'})
            return
        
        current_app.logger.info(f"🔵 [DM DEBUG] Получатель найден: {recipient.username} (ID: {recipient.id})")
        
        # Создаем личное сообщение
        current_app.logger.info(f"🔵 [DM DEBUG] Создаем сообщение в БД...")
        message = MessageService.create_message(
            content=content,
            sender_id=current_user.id,
            recipient_id=recipient_id,
            is_dm=True
        )
        
        current_app.logger.info(f"🔵 [DM DEBUG] Сообщение создано: {message is not None}")
        if message:
            current_app.logger.info(f"🔵 [DM DEBUG] ID сообщения: {message.id}")
            current_app.logger.info(f"🔵 [DM DEBUG] Время создания: {message.timestamp}")
        
        if message:
            # Формируем данные сообщения как в sockets_old.py
            message_data = {
                'sender_id': current_user.id,
                'sender_username': current_user.username,
                'recipient_id': recipient_id,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'is_dm': True
            }
            
            current_app.logger.info(f"🔵 [DM DEBUG] Данные сообщения сформированы: {message_data}")
            
            # ИСПРАВЛЕНО: отправляем получателю через Redis connection manager
            try:
                current_app.logger.info(f"🔵 [DM DEBUG] Ищем SID для получателя {recipient_id}")
                
                # Упрощенная логика - сначала локальный кеш, потом Redis (как в sockets_old.py)
                recipient_sid = self.connected_users.get(int(recipient_id))
                current_app.logger.info(f"🔵 [DM DEBUG] Локальный SID: {recipient_sid}")
                
                if not recipient_sid:
                    # Fallback на Redis
                    recipient_sid = conn_mgr.get_user_socket(int(recipient_id))
                    current_app.logger.info(f"🔵 [DM DEBUG] Redis SID: {recipient_sid}")
                
                current_app.logger.info(f"🔵 [DM DEBUG] Все подключенные пользователи: {self.connected_users}")
                
                if recipient_sid:
                    current_app.logger.info(f"🔵 [DM DEBUG] Отправляем new_dm в room={recipient_sid}")
                    emit('new_dm', message_data, room=recipient_sid)
                    
                    # ИСПРАВЛЕНО: НЕ отправляем dm_conversations - это может вызывать обновление индикаторов
                    # emit('dm_conversations', {
                    #     'conversations': UserService.get_dm_conversations(int(recipient_id))
                    # }, room=recipient_sid)
                    
                    # ИСПРАВЛЕНО: НЕ отправляем update_unread_indicator - это уже делается через new_dm
                    # emit('update_unread_indicator', {
                    #     'sender_id': current_user.id,
                    #     'username': current_user.username
                    # }, room=recipient_sid)
                    
                    current_app.logger.info(f"✅ [DM DEBUG] DM отправлен пользователю {recipient_id} через SID {recipient_sid}")
                    
                    # Отправляем подтверждение отправителю
                    emit('dm_sent', {
                        'success': True,
                        'recipient_id': recipient_id,
                        'recipient_username': recipient.username,
                        'message_id': message.id
                    })
                else:
                    current_app.logger.warning(f"🔴 [DM DEBUG] Получатель {recipient_id} не подключен")
                    # Сообщение сохранено в БД, но получатель не онлайн
                    emit('dm_sent', {
                        'success': True,
                        'recipient_id': recipient_id,
                        'recipient_username': recipient.username,
                        'message_id': message.id,
                        'offline': True
                    })
            except Exception as e:
                current_app.logger.error(f"🔴 [DM DEBUG] Ошибка отправки DM пользователю {recipient_id}: {e}")
                emit('dm_error', {'error': f'Ошибка отправки сообщения: {str(e)}'})
        else:
            current_app.logger.error(f"🔴 [DM DEBUG] Не удалось создать сообщение")
            emit('dm_error', {'error': 'Не удалось создать сообщение'})
        
        # ИСПРАВЛЕНО: НЕ обновляем список диалогов отправителя - это может вызывать обновление индикаторов
        # emit('dm_conversations', {
        #     'conversations': UserService.get_dm_conversations(current_user.id)
        # })
    
    def _join_default_room(self, user_id: int) -> None:
        """Присоединяет пользователя к комнате по умолчанию"""
        username = current_user.username
        
        # Присоединяемся к комнате
        join_room(self.DEFAULT_ROOM)
        
        # Добавляем в локальный кеш
        self.active_users[self.DEFAULT_ROOM][user_id] = username
        
        # Добавляем в Redis
        try:
            user_state.ensure_room_exists(self.DEFAULT_ROOM)
            user_state.add_user_to_room(user_id, username, self.DEFAULT_ROOM)
        except Exception as e:
            current_app.logger.warning(f"Redis add_user_to_room failed: {e}")
    
    def _send_initial_data(self, user_id: int) -> None:
        """Отправляет начальные данные пользователю"""
        # Отправляем список пользователей в комнате по умолчанию
        self._send_room_users(self.DEFAULT_ROOM)
        
        # Отправляем список комнат
        self._broadcast_room_list()
        
        # Отправляем историю сообщений для комнаты по умолчанию
        self.handle_get_message_history({
            'room': self.DEFAULT_ROOM,
            'limit': 20
        })
    
    def _send_room_users(self, room_name: str) -> None:
        """Отправляет список пользователей в комнате"""
        try:
            users = user_state.get_room_users(room_name)
        except Exception:
            users = dict(self.active_users.get(room_name, {}))
        
        emit('current_users', {'users': users, 'room': room_name})
    
    def _broadcast_room_list(self) -> None:
        """Отправляет обновленный список комнат всем клиентам"""
        # ИСПРАВЛЕНО: извлекаем только названия комнат как в sockets_old.py
        rooms_data = RoomService.get_all_rooms()
        rooms_list = [room['name'] for room in rooms_data]
        emit('room_list', {'rooms': rooms_list}, broadcast=True)
    
    def handle_get_current_users(self, data: Dict) -> None:
        """Запрос списка пользователей в текущей комнате"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', self.DEFAULT_ROOM)
        
        # Получаем пользователей из локального кеша
        users = dict(self.active_users.get(room_name, {}))
        
        # Убеждаемся, что текущий пользователь включен в список
        if current_user.id not in users:
            users[current_user.id] = current_user.username
            
        current_app.logger.info(f"Запрос списка пользователей для комнаты {room_name}: {users}")
        emit('current_users', {
            'users': users,
            'room': room_name
        })
    
    def handle_load_more_messages(self, data: Dict) -> None:
        """Загрузка дополнительных сообщений с пагинацией"""
        if not current_user.is_authenticated:
            current_app.logger.warning("LOAD MORE: Пользователь не авторизован")
            return
        
        room_name = data.get('room')
        offset = data.get('offset', 0)
        limit = data.get('limit', 10)
        
        
        try:
            # Проверяем, что комната существует
            room = RoomService.get_room_by_name(room_name)
            if not room:
                current_app.logger.warning(f"LOAD MORE: Комната '{room_name}' не найдена")
                emit('load_more_error', {'error': 'Комната не найдена'})
                return
            
            # Загружаем сообщения через сервис
            messages_data = MessageService.get_room_messages(room.id, limit, offset)
            
            emit('more_messages_loaded', {
                'messages': messages_data,
                'has_more': len(messages_data) == limit,
                'offset': offset + len(messages_data),
                'room': room_name
            })
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при загрузке сообщений: {e}")
            emit('load_more_error', {'error': 'Ошибка загрузки сообщений'})
    
    def handle_get_message_history(self, data: Dict) -> None:
        """Обработчик загрузки истории сообщений комнаты"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room')
        limit = data.get('limit', 20)
        
        if not room_name:
            return
        
        try:
            # Находим комнату
            room = RoomService.get_room_by_name(room_name)
            if not room:
                return
            
            # Загружаем сообщения через сервис
            messages_data = MessageService.get_room_messages(room.id, limit)
            
            # Отправляем историю клиенту
            emit('message_history', {
                'room': room_name,
                'messages': messages_data,
                'has_more': len(messages_data) == limit
            })
            
        except Exception as e:
            current_app.logger.error(f"Ошибка при загрузке истории сообщений: {e}")
            emit('message_history_error', {
                'error': 'Не удалось загрузить историю сообщений'
            })
    
    def handle_start_dm(self, data: Dict) -> None:
        """Обработчик начала личной переписки - загружает историю сообщений"""
        current_app.logger.info(f"🔵 [DM DEBUG] handle_start_dm вызван с данными: {data}")
        
        if not current_user.is_authenticated:
            current_app.logger.warning(f"🔴 [DM DEBUG] start_dm: пользователь не аутентифицирован")
            emit('dm_error', {'error': 'Пользователь не аутентифицирован'})
            return
        
        recipient_id = data.get('recipient_id')
        limit = data.get('limit', 20)
        
        current_app.logger.info(f"🔵 [DM DEBUG] Отправитель: {current_user.id} ({current_user.username})")
        current_app.logger.info(f"🔵 [DM DEBUG] Получатель ID: {recipient_id}")
        current_app.logger.info(f"🔵 [DM DEBUG] Лимит сообщений: {limit}")
        
        if not recipient_id:
            current_app.logger.warning(f"🔴 [DM DEBUG] recipient_id не указан")
            emit('dm_error', {'error': 'ID получателя не указан'})
            return
        
        # Проверяем, что пользователь не пытается начать диалог с самим собой
        if int(recipient_id) == current_user.id:
            current_app.logger.warning(f"🔴 [DM DEBUG] Попытка начать диалог с самим собой")
            emit('dm_error', {'error': 'Нельзя начать диалог с самим собой'})
            return
        
        try:
            # Находим получателя
            current_app.logger.info(f"🔵 [DM DEBUG] Ищем получателя в БД...")
            recipient = UserService.get_user_by_id(recipient_id)
            if not recipient:
                current_app.logger.warning(f"🔴 [DM DEBUG] Получатель с ID {recipient_id} не найден")
                emit('dm_error', {'error': 'Получатель не найден'})
                return
            
            current_app.logger.info(f"🔵 [DM DEBUG] Получатель найден: {recipient.username} (ID: {recipient.id})")
            
            # Загружаем историю переписки через сервис
            current_app.logger.info(f"🔵 [DM DEBUG] Загружаем историю сообщений...")
            messages_data = MessageService.get_dm_messages(current_user.id, recipient_id, limit)
            current_app.logger.info(f"🔵 [DM DEBUG] Загружено сообщений: {len(messages_data)}")
            
            # Логируем первые несколько сообщений для отладки
            if messages_data:
                current_app.logger.info(f"🔵 [DM DEBUG] Первое сообщение: {messages_data[0] if len(messages_data) > 0 else 'нет'}")
                current_app.logger.info(f"🔵 [DM DEBUG] Последнее сообщение: {messages_data[-1] if len(messages_data) > 0 else 'нет'}")
            
            # Отправляем историю переписки клиенту
            history_data = {
                'recipient_id': recipient_id,
                'recipient_name': recipient.username,
                'messages': messages_data
            }
            
            current_app.logger.info(f"🔵 [DM DEBUG] Отправляем dm_history с данными: {history_data}")
            emit('dm_history', history_data)
            
            current_app.logger.info(f"✅ [DM DEBUG] dm_history отправлен с {len(messages_data)} сообщениями")
        except Exception as e:
            current_app.logger.error(f"🔴 [DM DEBUG] Ошибка при загрузке истории ЛС: {e}")
            current_app.logger.error(f"🔴 [DM DEBUG] Тип ошибки: {type(e).__name__}")
            emit('dm_error', {'error': f'Ошибка загрузки истории: {str(e)}'})
    
    def handle_get_dm_conversations(self) -> None:
        """Обработчик запроса списка диалогов"""
        if not current_user.is_authenticated:
            return
        
        try:
            conversations = UserService.get_dm_conversations(current_user.id)
            current_app.logger.info(f"🔵 [DM DEBUG] Отправляем dm_conversations с {len(conversations)} диалогами")
            emit('dm_conversations', {
                'conversations': conversations
            })
            current_app.logger.info(f"✅ [DM DEBUG] dm_conversations отправлен успешно")
        except Exception as e:
            current_app.logger.error(f"🔴 [DM DEBUG] Ошибка при получении диалогов: {e}")
    
    def handle_mark_messages_as_read(self, data: Dict) -> None:
        """Помечает сообщения как прочитанные"""
        current_app.logger.info(f"🔵 [DM DEBUG] handle_mark_messages_as_read вызван с данными: {data}")
        
        if not current_user.is_authenticated:
            current_app.logger.warning("🔴 [DM DEBUG] Пользователь не аутентифицирован")
            return
        
        sender_id = data.get('sender_id')
        current_app.logger.info(f"🔵 [DM DEBUG] Помечаем сообщения как прочитанные: получатель={current_user.id}, отправитель={sender_id}")
        
        try:
            # Помечаем сообщения как прочитанные через сервис
            success = MessageService.mark_messages_as_read(current_user.id, sender_id)
            current_app.logger.info(f"🔵 [DM DEBUG] Результат пометки сообщений: {success}")
            
            if success:
                # ИСПРАВЛЕНО: НЕ обновляем список диалогов автоматически - это может вызывать проблемы
                # emit('dm_conversations', {
                #     'conversations': UserService.get_dm_conversations(current_user.id)
                # })
                
                # Отправляем подтверждение
                emit('messages_marked_read', {
                    'success': True,
                    'sender_id': sender_id
                })
                current_app.logger.info(f"✅ [DM DEBUG] Сообщения помечены как прочитанные для отправителя {sender_id}")
        except Exception as e:
            current_app.logger.error(f"🔴 [DM DEBUG] Ошибка при пометке сообщений как прочитанных: {e}")
    
    def handle_update_unread_indicator(self, data: Dict) -> None:
        """Обработчик для обновления индикатора непрочитанных"""
        # Этот обработчик будет вызываться на клиенте
        # Сервер просто пересылает сигнал получателю
        recipient_id = data.get('recipient_id')
        if recipient_id:
            recipient_sid = self.connected_users.get(int(recipient_id))
            if recipient_sid:
                emit('update_unread_indicator', data, room=recipient_sid)
