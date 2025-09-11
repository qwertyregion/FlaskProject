"""
WebSocket модуль для обработки real-time соединений
"""
from .handlers import register_socketio_handlers
from .events import WebSocketEvents

__all__ = [
    'register_socketio_handlers',
    'WebSocketEvents'
]
