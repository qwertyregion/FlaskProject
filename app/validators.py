"""
Валидаторы для WebSocket и общих данных
"""
import re
from typing import Dict, Any, Tuple
from flask import current_app


class WebSocketValidator:
    """Валидатор для WebSocket данных"""
    
    # Максимальные длины
    MAX_MESSAGE_LENGTH = 1000
    MAX_ROOM_NAME_LENGTH = 50
    MAX_USERNAME_LENGTH = 20
    
    # Паттерны для валидации
    ROOM_NAME_PATTERN = re.compile(r'^[a-zA-Zа-яА-Я0-9_\-\s]+$')
    MESSAGE_PATTERN = re.compile(r'^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+$')  # Исключаем управляющие символы
    
    @classmethod
    def validate_message_content(cls, content: str) -> Dict[str, Any]:
        """Валидация содержимого сообщения"""
        if not content:
            return {'valid': False, 'error': 'Сообщение не может быть пустым'}
        
        if len(content) > cls.MAX_MESSAGE_LENGTH:
            return {'valid': False, 'error': f'Сообщение слишком длинное (макс. {cls.MAX_MESSAGE_LENGTH} символов)'}
        
        if not cls.MESSAGE_PATTERN.match(content):
            return {'valid': False, 'error': 'Сообщение содержит недопустимые символы'}
        
        # Проверка на спам (повторяющиеся символы)
        if len(set(content)) < 3 and len(content) > 10:
            return {'valid': False, 'error': 'Сообщение выглядит как спам'}
        
        # Проверка на XSS попытки
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                current_app.logger.warning(f"XSS attempt detected: {content}")
                return {'valid': False, 'error': 'Сообщение содержит недопустимый контент'}
        
        return {'valid': True, 'content': content.strip()}
    
    @classmethod
    def validate_room_name(cls, room_name: str) -> Dict[str, Any]:
        """Валидация названия комнаты"""
        if not room_name:
            return {'valid': False, 'error': 'Название комнаты не может быть пустым'}
        
        room_name = room_name.strip()
        
        if len(room_name) < 2:
            return {'valid': False, 'error': 'Название комнаты слишком короткое (мин. 2 символа)'}
        
        if len(room_name) > cls.MAX_ROOM_NAME_LENGTH:
            return {'valid': False, 'error': f'Название комнаты слишком длинное (макс. {cls.MAX_ROOM_NAME_LENGTH} символов)'}
        
        if not cls.ROOM_NAME_PATTERN.match(room_name):
            return {'valid': False, 'error': 'Название комнаты может содержать только буквы, цифры, пробелы, дефисы и подчеркивания'}
        
        # Запрещенные названия
        forbidden_names = [
            'admin', 'administrator', 'root', 'system', 'api', 'www', 'mail', 'ftp',
            'localhost', 'test', 'null', 'undefined', 'none', 'default'
        ]
        
        if room_name.lower() in forbidden_names:
            return {'valid': False, 'error': 'Это название комнаты зарезервировано'}
        
        return {'valid': True, 'room_name': room_name}
    
    @classmethod
    def validate_user_id(cls, user_id: Any) -> Dict[str, Any]:
        """Валидация ID пользователя"""
        try:
            user_id = int(user_id)
            if user_id <= 0:
                return {'valid': False, 'error': 'Неверный ID пользователя'}
            return {'valid': True, 'user_id': user_id}
        except (ValueError, TypeError):
            return {'valid': False, 'error': 'ID пользователя должен быть числом'}


def validate_websocket_data(data: Dict[str, Any], required_fields: list) -> Dict[str, Any]:
    """Общая валидация WebSocket данных"""
    if not isinstance(data, dict):
        return {'valid': False, 'error': 'Данные должны быть объектом'}
    
    # Проверяем обязательные поля
    for field in required_fields:
        if field not in data:
            return {'valid': False, 'error': f'Отсутствует обязательное поле: {field}'}
    
    # Проверяем размер данных
    data_size = len(str(data))
    if data_size > 10000:  # 10KB максимум
        return {'valid': False, 'error': 'Данные слишком большие'}
    
    return {'valid': True}


def sanitize_input(text: str) -> str:
    """Очистка пользовательского ввода"""
    if not text:
        return ""
    
    # Удаляем управляющие символы
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Ограничиваем длину
    text = text[:1000]
    
    # Удаляем лишние пробелы
    text = ' '.join(text.split())
    
    return text.strip()
