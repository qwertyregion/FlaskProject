"""
HTTP контроллер для работы с сообщениями
"""
from typing import Dict, Any
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services import MessageService, RoomService, UserService


class MessageController:
    """HTTP контроллер для сообщений"""
    
    def __init__(self):
        self.bp = Blueprint('messages', __name__, url_prefix='/api/messages')
        self._register_routes()
    
    def _register_routes(self):
        """Регистрирует маршруты"""
        
        @self.bp.route('/room/<int:room_id>', methods=['GET'])
        @login_required
        def get_room_messages(room_id: int):
            """Получает сообщения комнаты"""
            try:
                # Проверяем существование комнаты
                room = RoomService.get_room_by_id(room_id)
                if not room:
                    return jsonify({'error': 'Комната не найдена'}), 404
                
                # Получаем параметры пагинации
                limit = request.args.get('limit', 20, type=int)
                offset = request.args.get('offset', 0, type=int)
                
                # Валидация параметров
                if limit > 100:
                    limit = 100
                if offset < 0:
                    offset = 0
                
                # Получаем сообщения
                messages = MessageService.get_room_messages(room_id, limit, offset)
                
                return jsonify({
                    'messages': messages,
                    'room_id': room_id,
                    'limit': limit,
                    'offset': offset
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting room messages: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/dm/<int:recipient_id>', methods=['GET'])
        @login_required
        def get_dm_messages(recipient_id: int):
            """Получает личные сообщения с пользователем"""
            try:
                # Проверяем существование получателя
                recipient = UserService.get_user_by_id(recipient_id)
                if not recipient:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                # Получаем параметры
                limit = request.args.get('limit', 50, type=int)
                if limit > 100:
                    limit = 100
                
                # Получаем сообщения
                messages = MessageService.get_dm_messages(
                    current_user.id, 
                    recipient_id, 
                    limit
                )
                
                return jsonify({
                    'messages': messages,
                    'recipient_id': recipient_id,
                    'recipient_username': recipient.username,
                    'limit': limit
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting DM messages: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/mark-read', methods=['POST'])
        @login_required
        def mark_messages_as_read():
            """Отмечает сообщения как прочитанные"""
            try:
                data = request.get_json()
                if not data or 'sender_id' not in data:
                    return jsonify({'error': 'Не указан sender_id'}), 400
                
                sender_id = data['sender_id']
                
                # Проверяем существование отправителя
                sender = UserService.get_user_by_id(sender_id)
                if not sender:
                    return jsonify({'error': 'Отправитель не найден'}), 404
                
                # Отмечаем сообщения как прочитанные
                success = MessageService.mark_messages_as_read(current_user.id, sender_id)
                
                if success:
                    # Получаем количество непрочитанных
                    unread_count = MessageService.get_unread_count(current_user.id, sender_id)
                    
                    return jsonify({
                        'success': True,
                        'sender_id': sender_id,
                        'unread_count': unread_count
                    })
                else:
                    return jsonify({'error': 'Не удалось отметить сообщения как прочитанные'}), 500
                    
            except Exception as e:
                current_app.logger.error(f"Error marking messages as read: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/unread-count/<int:sender_id>', methods=['GET'])
        @login_required
        def get_unread_count(sender_id: int):
            """Получает количество непрочитанных сообщений"""
            try:
                # Проверяем существование отправителя
                sender = UserService.get_user_by_id(sender_id)
                if not sender:
                    return jsonify({'error': 'Отправитель не найден'}), 404
                
                # Получаем количество непрочитанных
                unread_count = MessageService.get_unread_count(current_user.id, sender_id)
                
                return jsonify({
                    'sender_id': sender_id,
                    'unread_count': unread_count
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting unread count: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
