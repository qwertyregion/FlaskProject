"""
HTTP контроллер для работы с комнатами
"""
from typing import Dict, Any
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services import RoomService


class RoomController:
    """HTTP контроллер для комнат"""
    
    def __init__(self):
        self.bp = Blueprint('rooms', __name__, url_prefix='/api/rooms')
        self._register_routes()
    
    def _register_routes(self):
        """Регистрирует маршруты"""
        
        @self.bp.route('/', methods=['GET'])
        @login_required
        def get_all_rooms():
            """Получает список всех комнат"""
            try:
                rooms = RoomService.get_all_rooms()
                return jsonify({'rooms': rooms})
                
            except Exception as e:
                current_app.logger.error(f"Error getting all rooms: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/<int:room_id>', methods=['GET'])
        @login_required
        def get_room(room_id: int):
            """Получает информацию о комнате"""
            try:
                room = RoomService.get_room_by_id(room_id)
                if not room:
                    return jsonify({'error': 'Комната не найдена'}), 404
                
                return jsonify({
                    'id': room.id,
                    'name': room.name,
                    'description': room.description,
                    'creator_id': room.creator_id,
                    'creator_username': room.creator.username if room.creator else 'Unknown',
                    'is_private': room.is_private,
                    'created_at': room.created_at.isoformat() if room.created_at else None
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting room: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/name/<room_name>', methods=['GET'])
        @login_required
        def get_room_by_name(room_name: str):
            """Получает информацию о комнате по имени"""
            try:
                room = RoomService.get_room_by_name(room_name)
                if not room:
                    return jsonify({'error': 'Комната не найдена'}), 404
                
                return jsonify({
                    'id': room.id,
                    'name': room.name,
                    'description': room.description,
                    'creator_id': room.creator_id,
                    'creator_username': room.creator.username if room.creator else 'Unknown',
                    'is_private': room.is_private,
                    'created_at': room.created_at.isoformat() if room.created_at else None
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting room by name: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/', methods=['POST'])
        @login_required
        def create_room():
            """Создает новую комнату"""
            try:
                data = request.get_json()
                if not data:
                    return jsonify({'error': 'Данные не предоставлены'}), 400
                
                name = data.get('name', '').strip()
                description = data.get('description', '').strip()
                is_private = data.get('is_private', False)
                
                if not name:
                    return jsonify({'error': 'Название комнаты обязательно'}), 400
                
                # Создаем комнату
                room = RoomService.create_room(
                    name=name,
                    creator_id=current_user.id,
                    description=description,
                    is_private=is_private
                )
                
                if room:
                    return jsonify({
                        'id': room.id,
                        'name': room.name,
                        'description': room.description,
                        'creator_id': room.creator_id,
                        'is_private': room.is_private,
                        'created_at': room.created_at.isoformat() if room.created_at else None
                    }), 201
                else:
                    return jsonify({'error': 'Не удалось создать комнату'}), 400
                    
            except Exception as e:
                current_app.logger.error(f"Error creating room: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/<int:room_id>', methods=['DELETE'])
        @login_required
        def delete_room(room_id: int):
            """Удаляет комнату"""
            try:
                success = RoomService.delete_room(room_id, current_user.id)
                
                if success:
                    return jsonify({'success': True, 'message': 'Комната удалена'})
                else:
                    return jsonify({'error': 'Не удалось удалить комнату'}), 403
                    
            except Exception as e:
                current_app.logger.error(f"Error deleting room: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
