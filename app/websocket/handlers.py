"""
Регистрация WebSocket обработчиков
"""
from flask_socketio import SocketIO
from app.services import WebSocketService
from .events import WebSocketEvents


def register_socketio_handlers(socketio: SocketIO) -> None:
    """Регистрирует все обработчики SocketIO"""
    
    # Создаем сервисы
    websocket_service = WebSocketService()
    events = WebSocketEvents(websocket_service)
    
    # Регистрируем обработчики событий
    @socketio.on('connect')
    def handle_connect():
        events.handle_connect(socketio)
    
    @socketio.on('disconnect')
    def handle_disconnect():
        events.handle_disconnect()
    
    @socketio.on('heartbeat')
    def handle_heartbeat(data=None):
        events.handle_heartbeat(data)
    
    @socketio.on('create_room')
    def handle_create_room(data):
        events.handle_create_room(data)
    
    @socketio.on('join_room')
    def handle_join_room(data):
        events.handle_join_room(data)
    
    @socketio.on('leave_room')
    def handle_leave_room(data):
        events.handle_leave_room(data)
    
    @socketio.on('get_current_users')
    def handle_get_current_users(data):
        events.handle_get_current_users(data)
    
    @socketio.on('send_message')
    def handle_send_message(data):
        events.handle_send_message(data)
    
    @socketio.on('load_more_messages')
    def handle_load_more_messages(data):
        events.handle_load_more_messages(data)
    
    @socketio.on('get_message_history')
    def handle_get_message_history(data):
        events.handle_get_message_history(data)
    
    @socketio.on('start_dm')
    def handle_start_dm(data):
        events.handle_start_dm(data)
    
    @socketio.on('send_dm')
    def handle_send_dm(data):
        events.handle_send_dm(data)
    
    @socketio.on('get_dm_history')
    def handle_get_dm_history(data):
        events.handle_get_dm_history(data)
    
    @socketio.on('get_dm_conversations')
    def handle_get_dm_conversations():
        events.handle_get_dm_conversations()
    
    @socketio.on('mark_messages_as_read')
    def handle_mark_messages_as_read(data):
        events.handle_mark_messages_as_read(data)
    
    @socketio.on('update_unread_indicator')
    def handle_update_unread_indicator(data):
        events.handle_update_unread_indicator(data)
