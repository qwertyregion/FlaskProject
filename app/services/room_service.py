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
        
        # Создаем комнату (БЕЗ description - его нет в модели)
        room = Room(
            name=validation_result['room_name'],
            created_by=creator_id,  # ИСПРАВЛЕНО: используем created_by вместо creator_id
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
                    'created_by': room.created_by,  # ИСПРАВЛЕНО: используем created_by
                    'creator_username': room.creator_obj.username if room.creator_obj else 'Unknown',  # ИСПРАВЛЕНО: используем creator_obj
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
            if room.created_by != user_id:  # ИСПРАВЛЕНО: используем created_by
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
        """Проверяет, пуста ли комната (нет активных пользователей)"""
        try:
            # Получаем комнату по ID
            room = Room.query.filter_by(id=room_id).first()
            if not room:
                return True
            
            # Проверяем активных пользователей через WebSocket сервис
            from app.services.websocket_service import WebSocketService
            ws_service = WebSocketService()
            
            # Проверяем локальный кеш
            local_users = ws_service.active_users.get(room.name, {})
            local_user_count = len(local_users)
            
            # Проверяем Redis
            redis_user_count = 0
            try:
                from app.state import user_state
                redis_users = user_state.get_room_users(room.name)
                redis_user_count = len(redis_users)
            except Exception as e:
                current_app.logger.warning(f"Redis get_room_users failed: {e}")
            
            # Комната пустая если нет пользователей в обоих местах
            return local_user_count == 0 and redis_user_count == 0
        except Exception as e:
            current_app.logger.error(f"Failed to check if room is empty: {e}")
            return False
    
    @staticmethod
    def cleanup_empty_room(room_name: str) -> bool:
        """Удаляет пустую комнату (физическое удаление как в sockets_old.py)"""
        try:
            # Проверяем, что комната не является комнатой по умолчанию
            if room_name == 'general_chat':
                return False
            
            # Находим комнату по имени
            room = Room.query.filter_by(name=room_name).first()
            if not room:
                return False
            
            # Удаляем комнату независимо от количества сообщений
            # В sockets_old.py комната удаляется если нет пользователей, а не сообщений
            
            # ФИЗИЧЕСКОЕ УДАЛЕНИЕ как в sockets_old.py
            # Сначала удаляем все сообщения комнаты
            Message.query.filter_by(room_id=room.id).delete()
            
            # Затем удаляем саму комнату
            db.session.delete(room)
            db.session.commit()
            
            current_app.logger.info(f"Комната '{room_name}' удалена из БД")
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при удалении комнаты '{room_name}': {e}")
            return False
    
    @staticmethod
    def cleanup_all_rooms() -> int:
        """Удаляет все комнаты (кроме комнаты по умолчанию)"""
        try:
            deleted_count = 0
            
            # Получаем все комнаты кроме комнаты по умолчанию
            rooms = Room.query.filter(Room.name != 'general_chat').all()
            
            for room in rooms:
                # Удаляем все комнаты кроме general_chat (независимо от пользователей/сообщений)
                
                # Удаляем все сообщения комнаты
                Message.query.filter_by(room_id=room.id).delete()
                
                # Удаляем саму комнату
                db.session.delete(room)
                deleted_count += 1
            
            if deleted_count > 0:
                db.session.commit()
                current_app.logger.info(f"Удалено {deleted_count} пустых комнат")
            
            return deleted_count
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Ошибка при удалении комнат: {e}")
            return 0
    
    @staticmethod
    def ensure_default_room_exists() -> bool:
        """Убеждается, что комната по умолчанию существует"""
        try:
            default_room = Room.query.filter_by(name='general_chat').first()
            if not default_room:
                # Создаем комнату по умолчанию
                default_room = Room(
                    name='general_chat',
                    created_by=1,  # Системный пользователь или первый пользователь
                    is_active=True
                )
                db.session.add(default_room)
                db.session.commit()
                current_app.logger.info("Создана комната по умолчанию: general_chat")
                return True
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to ensure default room exists: {e}")
            return False
