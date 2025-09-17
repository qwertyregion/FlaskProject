"""
Сервис для работы с сообщениями
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from flask import current_app
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models import Message, User, Room
from app.validators import WebSocketValidator


class MessageService:
    """Сервис для работы с сообщениями"""
    
    @staticmethod
    def create_message(content: str, sender_id: int, room_id: Optional[int] = None, 
                      recipient_id: Optional[int] = None, is_dm: bool = False) -> Optional[Message]:
        """Создает новое сообщение"""
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] create_message вызван:")
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] content: '{content}'")
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] sender_id: {sender_id}")
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] room_id: {room_id}")
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] recipient_id: {recipient_id}")
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] is_dm: {is_dm}")
        
        # Валидация содержимого
        validation_result = WebSocketValidator.validate_message_content(content)
        if not validation_result['valid']:
            current_app.logger.warning(f"🔴 [MESSAGE DEBUG] Invalid message content: {validation_result['error']}")
            return None
        
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] Валидация пройдена, очищенное содержимое: '{validation_result['content']}'")
        
        # Создаем сообщение
        message = Message(
            content=validation_result['content'],
            sender_id=sender_id,
            room_id=room_id,
            recipient_id=recipient_id,
            is_dm=is_dm,
            timestamp=datetime.utcnow()
        )
        
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] Объект сообщения создан, сохраняем в БД...")
        
        try:
            db.session.add(message)
            db.session.commit()
            current_app.logger.info(f"✅ [MESSAGE DEBUG] Message created: ID={message.id}, sender={sender_id}")
            current_app.logger.info(f"🔵 [MESSAGE DEBUG] Timestamp: {message.timestamp}")
            return message
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"🔴 [MESSAGE DEBUG] Failed to create message: {e}")
            current_app.logger.error(f"🔴 [MESSAGE DEBUG] Exception type: {type(e).__name__}")
            return None
    
    @staticmethod
    def get_room_messages(room_id: int, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Получает сообщения комнаты с пагинацией"""
        try:
            messages = Message.query.options(
                joinedload(Message.sender)
            ).filter_by(
                room_id=room_id,
                is_dm=False
            ).order_by(
                Message.timestamp.desc()
            ).offset(offset).limit(limit).all()
            
            # Преобразуем в правильный порядок (от старых к новым)
            messages.reverse()
            
            return [
                {
                    'id': msg.id,
                    'sender_id': msg.sender_id,
                    'sender_username': msg.sender.username if msg.sender else 'Unknown',
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'is_dm': False,
                    'room_id': room_id
                }
                for msg in messages
            ]
        except Exception as e:
            current_app.logger.error(f"Failed to get room messages: {e}")
            return []
    
    @staticmethod
    def get_dm_messages(user_id: int, recipient_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает сообщения личной переписки"""
        try:
            current_app.logger.info(f"🔵 [DM DEBUG] get_dm_messages: user_id={user_id}, recipient_id={recipient_id}, limit={limit}")
            
            messages = Message.query.options(
                joinedload(Message.sender)
            ).filter(
                ((Message.sender_id == user_id) & (Message.recipient_id == recipient_id)) |
                ((Message.sender_id == recipient_id) & (Message.recipient_id == user_id))
            ).filter_by(is_dm=True).order_by(
                Message.timestamp.desc()
            ).limit(limit).all()
            
            current_app.logger.info(f"🔵 [DM DEBUG] Найдено сообщений в БД: {len(messages)}")
            
            # Преобразуем в правильный порядок
            messages.reverse()
            
            result = [
                {
                    'sender_id': msg.sender_id,
                    'sender_username': msg.sender.username if msg.sender else 'Unknown',
                    'recipient_id': msg.recipient_id,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat(),
                    'is_dm': True
                }
                for msg in messages
            ]
            
            current_app.logger.info(f"🔵 [DM DEBUG] Возвращаем {len(result)} сообщений")
            return result
        except Exception as e:
            current_app.logger.error(f"🔴 [DM DEBUG] Failed to get DM messages: {e}")
            return []
    
    @staticmethod
    def mark_messages_as_read(user_id: int, sender_id: int) -> bool:
        """Отмечает сообщения как прочитанные"""
        current_app.logger.info(f"🔵 [MESSAGE DEBUG] mark_messages_as_read вызван: user_id={user_id}, sender_id={sender_id}")
        
        try:
            # Сначала считаем количество непрочитанных сообщений
            unread_count_before = Message.query.filter(
                (Message.sender_id == sender_id) &
                (Message.recipient_id == user_id) &
                (Message.is_read == False)
            ).count()
            
            current_app.logger.info(f"🔵 [MESSAGE DEBUG] Непрочитанных сообщений до пометки: {unread_count_before}")
            
            # Помечаем сообщения как прочитанные
            updated_count = Message.query.filter_by(
                sender_id=sender_id,
                recipient_id=user_id,
                is_read=False
            ).update({'is_read': True})
            
            current_app.logger.info(f"🔵 [MESSAGE DEBUG] Обновлено сообщений: {updated_count}")
            
            db.session.commit()
            
            # Проверяем результат
            unread_count_after = Message.query.filter(
                (Message.sender_id == sender_id) &
                (Message.recipient_id == user_id) &
                (Message.is_read == False)
            ).count()
            
            current_app.logger.info(f"🔵 [MESSAGE DEBUG] Непрочитанных сообщений после пометки: {unread_count_after}")
            current_app.logger.info(f"✅ [MESSAGE DEBUG] Сообщения успешно помечены как прочитанные")
            
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"🔴 [MESSAGE DEBUG] Failed to mark messages as read: {e}")
            current_app.logger.error(f"🔴 [MESSAGE DEBUG] Exception type: {type(e).__name__}")
            return False
    
    @staticmethod
    def get_unread_count(user_id: int, sender_id: int) -> int:
        """Получает количество непрочитанных сообщений"""
        try:
            return Message.query.filter(
                (Message.sender_id == sender_id) &
                (Message.recipient_id == user_id) &
                (Message.is_read == False)
            ).count()
        except Exception as e:
            current_app.logger.error(f"Failed to get unread count: {e}")
            return 0
    
    @staticmethod
    def delete_room_messages(room_id: int) -> bool:
        """Удаляет все сообщения комнаты"""
        try:
            Message.query.filter_by(room_id=room_id).delete()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to delete room messages: {e}")
            return False
