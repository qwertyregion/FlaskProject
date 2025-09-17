"""
Сервис для работы с пользователями
"""
from typing import Dict, List, Optional, Any, Set
from flask import current_app
from app.extensions import db
from app.models import User, Message


class UserService:
    """Сервис для работы с пользователями"""
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Получает пользователя по ID"""
        try:
            return User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(f"Failed to get user by ID: {e}")
            return None
    
    @staticmethod
    def get_user_by_username(username: str) -> Optional[User]:
        """Получает пользователя по имени"""
        try:
            return User.query.filter_by(username=username).first()
        except Exception as e:
            current_app.logger.error(f"Failed to get user by username: {e}")
            return None
    
    @staticmethod
    def get_online_users(room: Optional[str] = None) -> Dict[int, str]:
        """Получает словарь онлайн пользователей {id: username}"""
        try:
            # Оптимизированный запрос - выбираем только нужные поля
            query = User.query.with_entities(User.id, User.username).filter_by(online=True)
            if room:
                # Если нужна фильтрация по комнате (для будущего расширения)
                pass
            return dict(query.all())
        except Exception as e:
            current_app.logger.error(f"Failed to get online users: {e}")
            return {}
    
    @staticmethod
    def set_user_online(user_id: int, online: bool = True) -> bool:
        """Устанавливает статус онлайн/оффлайн пользователя"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            user.online = online
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Failed to set user online status: {e}")
            return False
    
    @staticmethod
    def get_dm_conversations(user_id: int) -> List[Dict[str, Any]]:
        """Получает список диалогов для пользователя"""
        try:
            current_app.logger.info(f"🔵 [DM DEBUG] get_dm_conversations вызван для пользователя {user_id}")
            
            conversations = []
            
            # Находим всех пользователей, с которыми есть переписка
            sent_messages = Message.query.filter_by(sender_id=user_id, is_dm=True).all()
            received_messages = Message.query.filter_by(recipient_id=user_id, is_dm=True).all()
            
            current_app.logger.info(f"🔵 [DM DEBUG] Найдено отправленных сообщений: {len(sent_messages)}")
            current_app.logger.info(f"🔵 [DM DEBUG] Найдено полученных сообщений: {len(received_messages)}")
            
            # Собираем уникальных собеседников
            interlocutors: Set[int] = set()
            for msg in sent_messages:
                if msg.recipient_id:
                    interlocutors.add(msg.recipient_id)
            for msg in received_messages:
                interlocutors.add(msg.sender_id)
            
            current_app.logger.info(f"🔵 [DM DEBUG] Найдено собеседников: {len(interlocutors)}")
            
            # Для каждого собеседника получаем информацию
            for interlocutor_id in interlocutors:
                interlocutor = User.query.get(interlocutor_id)
                if not interlocutor:
                    continue
                
                # Находим последнее сообщение в диалоге
                last_message = Message.query.filter(
                    ((Message.sender_id == user_id) & (Message.recipient_id == interlocutor_id)) |
                    ((Message.sender_id == interlocutor_id) & (Message.recipient_id == user_id))
                ).filter_by(is_dm=True).order_by(Message.timestamp.desc()).first()
                
                # Считаем непрочитанные сообщения (только входящие)
                unread_count = Message.query.filter(
                    (Message.sender_id == interlocutor_id) &
                    (Message.recipient_id == user_id) &
                    (Message.is_read == False)
                ).count()
                
                conversations.append({
                    'user_id': interlocutor_id,
                    'username': interlocutor.username,
                    'last_message': last_message.content if last_message else None,
                    'last_message_time': last_message.timestamp.isoformat() if last_message else None,
                    'unread_count': unread_count
                })
            
            # Сортируем по времени последнего сообщения
            conversations.sort(
                key=lambda x: x['last_message_time'] or '1970-01-01T00:00:00',
                reverse=True
            )
            
            current_app.logger.info(f"🔵 [DM DEBUG] Возвращаем {len(conversations)} диалогов")
            return conversations
        except Exception as e:
            current_app.logger.error(f"Failed to get DM conversations: {e}")
            return []
    
    @staticmethod
    def get_user_stats(user_id: int) -> Dict[str, Any]:
        """Получает статистику пользователя"""
        try:
            user = User.query.get(user_id)
            if not user:
                return {}
            
            # Подсчитываем сообщения
            sent_count = Message.query.filter_by(sender_id=user_id).count()
            received_count = Message.query.filter_by(recipient_id=user_id).count()
            
            return {
                'user_id': user_id,
                'username': user.username,
                'online': user.online,
                'last_seen': user.last_seen.isoformat() if user.last_seen else None,
                'sent_messages': sent_count,
                'received_messages': received_count,
                'total_messages': sent_count + received_count
            }
        except Exception as e:
            current_app.logger.error(f"Failed to get user stats: {e}")
            return {}
