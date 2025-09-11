"""
WebSocket события и их обработчики
"""
from typing import Dict, Optional, Any
from flask import current_app, request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.services import MessageService, RoomService, UserService, WebSocketService


class WebSocketEvents:
    """Класс для обработки WebSocket событий"""
    
    def __init__(self, websocket_service: WebSocketService):
        self.websocket_service = websocket_service
    
    def handle_connect(self, socketio) -> None:
        """Обработчик подключения"""
        self.websocket_service.handle_connect(socketio)
    
    def handle_disconnect(self) -> None:
        """Обработчик отключения"""
        self.websocket_service.handle_disconnect()
    
    def handle_heartbeat(self, data: Optional[Dict] = None) -> None:
        """Обработчик heartbeat"""
        self.websocket_service.handle_heartbeat(data)
    
    def handle_create_room(self, data: Dict) -> None:
        """Обработчик создания комнаты"""
        self.websocket_service.handle_create_room(data)
    
    def handle_join_room(self, data: Dict) -> None:
        """Обработчик присоединения к комнате"""
        self.websocket_service.handle_join_room(data)
    
    def handle_leave_room(self, data: Dict) -> None:
        """Обработчик выхода из комнаты"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        if not room_name:
            return
        
        user_id = current_user.id
        username = current_user.username
        
        # Выходим из комнаты
        leave_room(room_name)
        
        # Удаляем из локального кеша
        if room_name in self.websocket_service.active_users:
            if user_id in self.websocket_service.active_users[room_name]:
                del self.websocket_service.active_users[room_name][user_id]
        
        # Удаляем из Redis
        try:
            from app.state import user_state
            user_state.remove_user_from_room(user_id, room_name)
        except Exception as e:
            current_app.logger.warning(f"Redis remove_user_from_room failed: {e}")
        
        # Уведомляем других пользователей
        emit('user_left', {
            'user_id': user_id,
            'username': username,
            'room': room_name
        }, room=room_name, include_self=False)
    
    def handle_get_current_users(self, data: Dict) -> None:
        """Обработчик получения списка пользователей в комнате"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', self.websocket_service.DEFAULT_ROOM)
        
        try:
            from app.state import user_state
            users = user_state.get_room_users(room_name)
        except Exception:
            users = dict(self.websocket_service.active_users.get(room_name, {}))
        
        emit('current_users', {'users': users, 'room': room_name})
    
    def handle_send_message(self, data: Dict) -> None:
        """Обработчик отправки сообщения"""
        self.websocket_service.handle_send_message(data)
    
    def handle_load_more_messages(self, data: Dict) -> None:
        """Обработчик загрузки дополнительных сообщений"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        offset = data.get('offset', 0)
        limit = data.get('limit', 20)
        
        if not room_name:
            emit('load_more_error', {'error': 'Комната не указана'})
            return
        
        # Получаем комнату
        room = RoomService.get_room_by_name(room_name)
        if not room:
            emit('load_more_error', {'error': 'Комната не найдена'})
            return
        
        # Загружаем сообщения
        messages = MessageService.get_room_messages(room.id, limit, offset)
        
        if messages:
            emit('more_messages', {
                'messages': messages,
                'room': room_name,
                'offset': offset
            })
        else:
            emit('no_more_messages', {'room': room_name})
    
    def handle_get_message_history(self, data: Dict) -> None:
        """Обработчик получения истории сообщений"""
        if not current_user.is_authenticated:
            return
        
        room_name = data.get('room', '').strip()
        limit = data.get('limit', 20)
        
        if not room_name:
            return
        
        # Получаем комнату
        room = RoomService.get_room_by_name(room_name)
        if not room:
            return
        
        # Загружаем сообщения
        messages = MessageService.get_room_messages(room.id, limit)
        
        # Отправляем историю
        emit('message_history', {
            'messages': messages,
            'room': room_name
        })
    
    def handle_start_dm(self, data: Dict) -> None:
        """Обработчик начала личной переписки"""
        if not current_user.is_authenticated:
            return
        
        recipient_id = data.get('recipient_id')
        if not recipient_id:
            return
        
        # Проверяем получателя
        recipient = UserService.get_user_by_id(recipient_id)
        if not recipient:
            emit('dm_error', {'error': 'Получатель не найден'})
            return
        
        # Присоединяемся к комнате для ЛС
        dm_room = f"user_{recipient_id}"
        join_room(dm_room)
        
        # Отправляем подтверждение
        emit('dm_started', {
            'recipient_id': recipient_id,
            'recipient_username': recipient.username
        })
    
    def handle_send_dm(self, data: Dict) -> None:
        """Обработчик отправки личного сообщения"""
        self.websocket_service.handle_send_dm(data)
    
    def handle_get_dm_history(self, data: Dict) -> None:
        """Обработчик получения истории личных сообщений"""
        if not current_user.is_authenticated:
            return
        
        recipient_id = data.get('recipient_id')
        if not recipient_id:
            return
        
        # Проверяем получателя
        recipient = UserService.get_user_by_id(recipient_id)
        if not recipient:
            return
        
        # Загружаем историю переписки
        messages = MessageService.get_dm_messages(current_user.id, recipient_id)
        
        # Отправляем историю
        emit('dm_history', {
            'messages': messages,
            'recipient_id': recipient_id,
            'recipient_username': recipient.username
        })
    
    def handle_get_dm_conversations(self) -> None:
        """Обработчик получения списка диалогов"""
        if not current_user.is_authenticated:
            return
        
        conversations = UserService.get_dm_conversations(current_user.id)
        emit('dm_conversations', {'conversations': conversations})
    
    def handle_mark_messages_as_read(self, data: Dict) -> None:
        """Обработчик отметки сообщений как прочитанных"""
        if not current_user.is_authenticated:
            return
        
        sender_id = data.get('sender_id')
        if not sender_id:
            return
        
        # Отмечаем сообщения как прочитанные
        success = MessageService.mark_messages_as_read(current_user.id, sender_id)
        
        if success:
            # Получаем количество непрочитанных сообщений
            unread_count = MessageService.get_unread_count(current_user.id, sender_id)
            
            emit('messages_marked_read', {
                'sender_id': sender_id,
                'unread_count': unread_count
            })
    
    def handle_update_unread_indicator(self, data: Dict) -> None:
        """Обработчик обновления индикатора непрочитанных сообщений"""
        if not current_user.is_authenticated:
            return
        
        sender_id = data.get('sender_id')
        if not sender_id:
            return
        
        # Получаем количество непрочитанных сообщений
        unread_count = MessageService.get_unread_count(current_user.id, sender_id)
        
        emit('unread_count_update', {
            'sender_id': sender_id,
            'unread_count': unread_count
        })
