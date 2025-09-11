"""
Сервис для работы с комнатами
"""
from typing import Dict, List, Optional, Any
from flask import current_app
from app.extensions import db
from app.models import Room, User, Message
from app.validators import WebSocketValidator


class RoomService:
    """Сервис для работы с комнатами"""
    
    @staticmethod
    def create_room(name: str, creator_id: int, description: str = "", is_private: bool = False) -> Optional[Room]:
        """Создает новую комнату"""
        # Валидация названия комнаты
        validation_result = WebSocketValidator.validate_room_name(name)
        if not validation_result['valid']:
            current_app.logger.warning(f"Invalid room name: {validation_result['error']}")
            return None
        
        # Проверяем, не существует ли уже комната
        existing_room = Room.query.filter_by(name=validation_result['room_name']).first()
        if existing_room:
            current_app.logger.warning(f"Room already exists: {validation_result['room_name']}")
            return None
        
        # Создаем комнату
        room = Room(
            name=validation_result['room_name'],
            description=description,
            creator_id=creator_id,
            is_private=is_private,
            is_active=True
        )
        
        try:
            db.session.add(room)
            db.session.commit()
            current_app.logger.info(f"Room created: {room.name} by user {creator_id}")
            return room
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to create room: {e}")
            return None
    
    @staticmethod
    def get_room_by_name(name: str) -> Optional[Room]:
        """Получает комнату по имени"""
        try:
            return Room.query.filter_by(name=name, is_active=True).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get room by name: {e}")
            return None
    
    @staticmethod
    def get_room_by_id(room_id: int) -> Optional[Room]:
        """Получает комнату по ID"""
        try:
            return Room.query.filter_by(id=room_id, is_active=True).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get room by ID: {e}")
            return None
    
    @staticmethod
    def get_all_rooms() -> List[Dict[str, Any]]:
        """Получает список всех активных комнат"""
        try:
            rooms = Room.query.filter_by(is_active=True).all()
            return [
                {
                    'id': room.id,
                    'name': room.name,
                    'description': room.description,
                    'creator_id': room.creator_id,
                    'creator_username': room.creator.username if room.creator else 'Unknown',
                    'is_private': room.is_private,
                    'created_at': room.created_at.isoformat() if room.created_at else None
                }
                for room in rooms
            ]
        except Exception as e:
            current_app.logger.error(f"Failed to get all rooms: {e}")
            return []
    
    @staticmethod
    def delete_room(room_id: int, user_id: int) -> bool:
        """Удаляет комнату (только создатель может удалить)"""
        try:
            room = Room.query.filter_by(id=room_id, is_active=True).first()
            if not room:
                current_app.logger.warning(f"Room not found: {room_id}")
                return False
            
            # Проверяем права на удаление
            if room.creator_id != user_id:
                current_app.logger.warning(f"User {user_id} cannot delete room {room_id}")
                return False
            
            # Удаляем комнату (мягкое удаление)
            room.is_active = False
            db.session.commit()
            
            current_app.logger.info(f"Room deleted: {room.name}")
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to delete room: {e}")
            return False
    
    @staticmethod
    def is_room_empty(room_id: int) -> bool:
        """Проверяет, пуста ли комната"""
        try:
            # Проверяем количество сообщений в комнате
            message_count = db.session.query(Message).filter_by(room_id=room_id).count()
            return message_count == 0
        except Exception as e:
            current_app.logger.error(f"Failed to check if room is empty: {e}")
            return False
    
    @staticmethod
    def cleanup_empty_room(room_id: int) -> bool:
        """Удаляет пустую комнату"""
        try:
            if not RoomService.is_room_empty(room_id):
                return False
            
            room = Room.query.get(room_id)
            if room:
                room.is_active = False
                db.session.commit()
                current_app.logger.info(f"Empty room cleaned up: {room.name}")
                return True
            return False
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to cleanup empty room: {e}")
            return False
