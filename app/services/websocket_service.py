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
            return
        
        user_id = current_user.id
        
        # Проверяем, не подключен ли пользователь уже
        if user_id in self.connected_users:
            old_sid = self.connected_users[user_id]
            if old_sid != request.sid:
                # Отключаем старое соединение
                leave_room(self.DEFAULT_ROOM, sid=old_sid)
                socketio.server.disconnect(old_sid)
        
        # Регистрируем новое соединение
        self.connected_users[user_id] = request.sid
        
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
        
        room_name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not room_name:
            emit('room_creation_error', {'error': 'Название комнаты не может быть пустым'})
            return
        
        # Создаем комнату через сервис
        room = RoomService.create_room(
            name=room_name,
            creator_id=current_user.id,
            description=description
        )
        
        if room:
            emit('room_created', {
                'id': room.id,
                'name': room.name,
                'description': room.description,
                'creator_id': room.creator_id
            }, broadcast=True)
            
            # Обновляем список комнат
            self._broadcast_room_list()
        else:
            emit('room_creation_error', {'error': 'Не удалось создать комнату'})
    
    def handle_join_room(self, data: Dict) -> None:
        """Обрабатывает присоединение к комнате"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        if not room_name:
            return
        
        user_id = current_user.id
        username = current_user.username
        
        # Получаем комнату
        room = RoomService.get_room_by_name(room_name)
        if not room:
            emit('room_join_error', {'error': 'Комната не найдена'})
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
    
    def handle_send_message(self, data: Dict) -> None:
        """Обрабатывает отправку сообщения"""
        if not current_user.is_authenticated:
            return
        
        content = data.get('content', '').strip()
        room_name = data.get('room', '').strip()
        
        if not content or not room_name:
            return
        
        # Получаем комнату
        room = RoomService.get_room_by_name(room_name)
        if not room:
            emit('message_error', {'error': 'Комната не найдена'})
            return
        
        # Создаем сообщение через сервис
        message = MessageService.create_message(
            content=content,
            sender_id=current_user.id,
            room_id=room.id
        )
        
        if message:
            # Отправляем сообщение всем в комнате
            emit('new_message', {
                'id': message.id,
                'sender_id': message.sender_id,
                'sender_username': current_user.username,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'room': room_name
            }, room=room_name)
        else:
            emit('message_error', {'error': 'Не удалось отправить сообщение'})
    
    def handle_send_dm(self, data: Dict) -> None:
        """Обрабатывает отправку личного сообщения"""
        if not current_user.is_authenticated:
            return
        
        content = data.get('content', '').strip()
        recipient_id = data.get('recipient_id')
        
        if not content or not recipient_id:
            return
        
        # Проверяем получателя
        recipient = UserService.get_user_by_id(recipient_id)
        if not recipient:
            emit('dm_error', {'error': 'Получатель не найден'})
            return
        
        # Создаем личное сообщение
        message = MessageService.create_message(
            content=content,
            sender_id=current_user.id,
            recipient_id=recipient_id,
            is_dm=True
        )
        
        if message:
            # Отправляем сообщение получателю
            emit('new_dm', {
                'sender_id': message.sender_id,
                'sender_username': current_user.username,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'recipient_id': recipient_id
            }, room=f"user_{recipient_id}")
            
            # Отправляем подтверждение отправителю
            emit('dm_sent', {
                'recipient_id': recipient_id,
                'recipient_username': recipient.username,
                'content': message.content,
                'timestamp': message.timestamp.isoformat()
            })
        else:
            emit('dm_error', {'error': 'Не удалось отправить сообщение'})
    
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
    
    def _send_room_users(self, room_name: str) -> None:
        """Отправляет список пользователей в комнате"""
        try:
            users = user_state.get_room_users(room_name)
        except Exception:
            users = dict(self.active_users.get(room_name, {}))
        
        emit('current_users', {'users': users, 'room': room_name})
    
    def _broadcast_room_list(self) -> None:
        """Отправляет обновленный список комнат всем клиентам"""
        rooms_list = RoomService.get_all_rooms()
        emit('room_list', {'rooms': rooms_list}, broadcast=True)
