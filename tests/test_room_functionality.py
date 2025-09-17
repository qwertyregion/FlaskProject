"""
Тесты функционала работы с комнатами
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.room_service import RoomService
from app.services.websocket_service import WebSocketService
from app.services.message_service import MessageService
from app.models import Room, User, Message
from app.extensions import db


class TestRoomCreation:
    """Тесты создания комнат"""
    
    def test_create_room_success(self, app, db):
        """Тест успешного создания комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = RoomService.create_room(
                name='test_room',
                creator_id=user.id,
                is_private=False
            )
            
            assert room is not None
            assert room.name == 'test_room'
            assert room.created_by == user.id
            assert room.is_private is False
            assert room.is_active is True
            
            # Проверяем, что комната сохранилась в БД
            saved_room = Room.query.filter_by(name='test_room').first()
            assert saved_room is not None
            assert saved_room.id == room.id
    
    def test_create_room_invalid_name(self, app, db):
        """Тест создания комнаты с невалидным именем"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Пытаемся создать комнату с пустым именем
            room = RoomService.create_room(
                name='',
                creator_id=user.id
            )
            
            assert room is None
            
            # Пытаемся создать комнату с именем из одного символа
            room = RoomService.create_room(
                name='a',
                creator_id=user.id
            )
            
            assert room is None
    
    def test_create_room_duplicate_name(self, app, db):
        """Тест создания комнаты с дублирующимся именем"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем первую комнату
            room1 = RoomService.create_room(
                name='duplicate_room',
                creator_id=user.id
            )
            
            assert room1 is not None
            
            # Пытаемся создать комнату с тем же именем
            room2 = RoomService.create_room(
                name='duplicate_room',
                creator_id=user.id
            )
            
            assert room2 is None
            
            # Проверяем, что в БД только одна комната
            rooms = Room.query.filter_by(name='duplicate_room').all()
            assert len(rooms) == 1
    
    def test_create_room_special_characters(self, app, db):
        """Тест создания комнаты со специальными символами"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Тестируем различные имена
            test_cases = [
                ('room_with_underscore', True),
                ('room-with-dash', True),
                ('room123', True),
                ('room with spaces', True),   # Пробелы разрешены согласно валидатору
                ('room@special', False),      # Специальные символы
                ('комната_на_русском', True), # Unicode
            ]
            
            for room_name, should_succeed in test_cases:
                room = RoomService.create_room(
                    name=room_name,
                    creator_id=user.id
                )
                
                if should_succeed:
                    assert room is not None, f"Room '{room_name}' should be created"
                    # Удаляем комнату для следующего теста
                    db.session.delete(room)
                    db.session.commit()
                else:
                    assert room is None, f"Room '{room_name}' should not be created"
    
    def test_create_private_room(self, app, db):
        """Тест создания приватной комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем приватную комнату
            room = RoomService.create_room(
                name='private_room',
                creator_id=user.id,
                is_private=True
            )
            
            assert room is not None
            assert room.is_private is True


class TestRoomRetrieval:
    """Тесты получения комнат"""
    
    def test_get_room_by_name(self, app, db):
        """Тест получения комнаты по имени"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name=f'test_room_{id(self)}',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Получаем комнату
            retrieved_room = RoomService.get_room_by_name(f'test_room_{id(self)}')
            
            assert retrieved_room is not None
            assert retrieved_room.id == room.id
            assert retrieved_room.name == f'test_room_{id(self)}'
    
    def test_get_nonexistent_room(self, app, db):
        """Тест получения несуществующей комнаты"""
        with app.app_context():
            room = RoomService.get_room_by_name('nonexistent_room')
            assert room is None
    
    def test_get_all_rooms(self, app, db):
        """Тест получения всех комнат"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем несколько комнат
            rooms_data = [
                ('room1', True),
                ('room2', False),
                ('room3', True),
            ]
            
            for name, is_active in rooms_data:
                room = Room(
                    name=name,
                    created_by=user.id,
                    is_active=is_active
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Получаем все комнаты
            all_rooms = RoomService.get_all_rooms()
            
            # Может быть больше комнат из-за комнаты по умолчанию
            assert len(all_rooms) >= 3
            
            # Проверяем структуру данных
            for room_data in all_rooms:
                assert 'id' in room_data
                assert 'name' in room_data
                assert 'created_by' in room_data
                assert 'is_private' in room_data
                assert 'created_at' in room_data
                assert 'creator_username' in room_data


class TestRoomDeletion:
    """Тесты удаления комнат"""
    
    def test_cleanup_empty_room_success(self, app, db):
        """Тест успешного удаления пустой комнаты"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='empty_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            room_id = room.id
            
            # Удаляем комнату
            result = RoomService.cleanup_empty_room('empty_room')
            
            assert result is True
            
            # Проверяем, что комната удалена
            deleted_room = Room.query.filter_by(name='empty_room').first()
            assert deleted_room is None
    
    def test_cleanup_room_with_messages(self, app, db):
        """Тест удаления комнаты с сообщениями"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='room_with_messages',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем сообщения в комнате
            for i in range(3):
                message = Message(
                    content=f'Test message {i}',
                    sender_id=user.id,
                    room_id=room.id
                )
                db.session.add(message)
            
            db.session.commit()
            
            # Удаляем комнату
            result = RoomService.cleanup_empty_room('room_with_messages')
            
            assert result is True
            
            # Проверяем, что комната и сообщения удалены
            deleted_room = Room.query.filter_by(name='room_with_messages').first()
            assert deleted_room is None
            
            deleted_messages = Message.query.filter_by(room_id=room.id).all()
            assert len(deleted_messages) == 0
    
    def test_cleanup_default_room_protection(self, app, db):
        """Тест защиты комнаты по умолчанию от удаления"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату по умолчанию
            default_room = Room(
                name='general_chat',
                created_by=user.id,
                is_active=True
            )
            db.session.add(default_room)
            db.session.commit()
            
            # Пытаемся удалить комнату по умолчанию
            result = RoomService.cleanup_empty_room('general_chat')
            
            assert result is False
            
            # Проверяем, что комната не удалена
            protected_room = Room.query.filter_by(name='general_chat').first()
            assert protected_room is not None
    
    def test_cleanup_nonexistent_room(self, app, db):
        """Тест удаления несуществующей комнаты"""
        with app.app_context():
            result = RoomService.cleanup_empty_room('nonexistent_room')
            assert result is False
    
    def test_cleanup_all_empty_rooms(self, app, db):
        """Тест удаления всех комнат кроме комнаты по умолчанию"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Проверяем, существует ли уже комната general_chat
            existing_general_chat = Room.query.filter_by(name='general_chat').first()
            if existing_general_chat:
                db.session.delete(existing_general_chat)
                db.session.commit()
            
            # Создаем несколько комнат
            rooms_data = [
                ('empty_room1', True),
                ('empty_room2', True),
                ('room_with_messages', True),
                ('general_chat', True),  # Комната по умолчанию
            ]
            
            for name, is_active in rooms_data:
                room = Room(
                    name=name,
                    created_by=user.id,
                    is_active=is_active
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Добавляем сообщения в одну комнату
            room_with_messages = Room.query.filter_by(name='room_with_messages').first()
            message = Message(
                content='Test message',
                sender_id=user.id,
                room_id=room_with_messages.id
            )
            db.session.add(message)
            db.session.commit()
            
            # Проверяем, что сообщения созданы
            assert Message.query.filter_by(room_id=room_with_messages.id).count() == 1
            
            # Подсчитываем количество комнат до удаления (кроме general_chat)
            rooms_before = Room.query.filter(Room.name != 'general_chat').count()
            
            # Удаляем все комнаты кроме general_chat
            deleted_count = RoomService.cleanup_all_rooms()
            
            # Проверяем, что удалено правильное количество комнат
            assert deleted_count == rooms_before
            
            # Проверяем, что все комнаты кроме general_chat удалены
            assert Room.query.filter_by(name='empty_room1').first() is None
            assert Room.query.filter_by(name='empty_room2').first() is None
            assert Room.query.filter_by(name='room_with_messages').first() is None
            
            # Проверяем, что комната по умолчанию осталась
            assert Room.query.filter_by(name='general_chat').first() is not None
            
            # Проверяем, что сообщения из удаленной комнаты тоже удалены
            assert Message.query.filter_by(room_id=room_with_messages.id).count() == 0


class TestRoomStateManagement:
    """Тесты управления состоянием комнат"""
    
    def test_is_room_empty(self, app, db):
        """Тест проверки пустоты комнаты"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name=f'test_room_{id(self)}',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Проверяем пустую комнату
            assert RoomService.is_room_empty(room.id) is True
            
            # Добавляем сообщение
            message = Message(
                content='Test message',
                sender_id=user.id,
                room_id=room.id
            )
            db.session.add(message)
            db.session.commit()
            
            # Комната все еще считается пустой (нет активных пользователей)
            assert RoomService.is_room_empty(room.id) is True
    
    def test_ensure_default_room_exists(self, app, db):
        """Тест создания комнаты по умолчанию"""
        with app.app_context():
            # Проверяем, что комната по умолчанию не существует (может уже существовать)
            default_room = Room.query.filter_by(name='general_chat').first()
            # Если комната уже существует, удаляем её для теста
            if default_room:
                db.session.delete(default_room)
                db.session.commit()
            
            # Создаем комнату по умолчанию
            result = RoomService.ensure_default_room_exists()
            
            assert result is True
            
            # Проверяем, что комната создана
            default_room = Room.query.filter_by(name='general_chat').first()
            assert default_room is not None
            assert default_room.name == 'general_chat'
            assert default_room.created_by == 1  # Системный пользователь
    
    def test_ensure_default_room_already_exists(self, app, db):
        """Тест когда комната по умолчанию уже существует"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Проверяем, существует ли уже комната general_chat
            existing_general_chat = Room.query.filter_by(name='general_chat').first()
            if not existing_general_chat:
                # Создаем комнату по умолчанию
                default_room = Room(
                    name='general_chat',
                    created_by=user.id,
                    is_active=True
                )
                db.session.add(default_room)
                db.session.commit()

            # Пытаемся создать комнату по умолчанию снова
            result = RoomService.ensure_default_room_exists()
            
            assert result is True
            
            # Проверяем, что комната не дублировалась
            rooms = Room.query.filter_by(name='general_chat').all()
            assert len(rooms) == 1

class TestWebSocketRoomOperations:
    """Тесты WebSocket операций с комнатами"""
    
    def test_handle_create_room_success(self, app, db):
        """Тест успешного создания комнаты через WebSocket"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Мокаем current_user
            with patch('app.services.websocket_service.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = user.id
                
                # Создаем WebSocket сервис
                ws_service = WebSocketService()
                
                # Мокаем emit
                with patch('app.services.websocket_service.emit') as mock_emit:
                    # Вызываем создание комнаты
                    ws_service.handle_create_room({'room_name': 'websocket_room'})
                    
                    # Проверяем, что комната создана
                    room = Room.query.filter_by(name='websocket_room').first()
                    assert room is not None
                    
                    # Проверяем, что отправлен правильный ответ (может быть вызван несколько раз)
                    assert mock_emit.call_count >= 1
                    # Проверяем первый вызов (создание комнаты)
                    first_call = mock_emit.call_args_list[0]
                    assert first_call[0][0] == 'room_created'
                    assert first_call[0][1]['success'] is True
    
    def test_handle_create_room_invalid_data(self, app, db):
        """Тест создания комнаты с невалидными данными через WebSocket"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Мокаем current_user
            with patch('app.services.websocket_service.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = user.id
                
                # Создаем WebSocket сервис
                ws_service = WebSocketService()
                
                # Мокаем emit
                with patch('app.services.websocket_service.emit') as mock_emit:
                    # Вызываем создание комнаты с пустым именем
                    ws_service.handle_create_room({'room_name': ''})
                    
                    # Проверяем, что комната не создана
                    room = Room.query.filter_by(name='').first()
                    assert room is None
                    
                    # Проверяем, что отправлен правильный ответ об ошибке
                    mock_emit.assert_called_once()
                    call_args = mock_emit.call_args
                    assert call_args[0][0] == 'room_created'
                    assert call_args[0][1]['success'] is False
    
    def test_handle_create_room_duplicate(self, app, db):
        """Тест создания дублирующейся комнаты через WebSocket"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name=f'duplicate_room_{id(self)}',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Мокаем current_user
            with patch('app.services.websocket_service.current_user') as mock_user:
                mock_user.is_authenticated = True
                mock_user.id = user.id
                
                # Создаем WebSocket сервис
                ws_service = WebSocketService()
                
                # Мокаем emit
                with patch('app.services.websocket_service.emit') as mock_emit:
                    # Пытаемся создать комнату с тем же именем
                    ws_service.handle_create_room({'room_name': f'duplicate_room_{id(self)}'})
                    
                    # Проверяем, что отправлен ответ об ошибке
                    mock_emit.assert_called_once()
                    call_args = mock_emit.call_args
                    assert call_args[0][0] == 'room_created'
                    assert call_args[0][1]['success'] is False


class TestRoomEdgeCases:
    """Тесты граничных случаев работы с комнатами"""
    
    def test_room_name_length_limits(self, app, db):
        """Тест ограничений длины имени комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Тестируем различные длины имен
            test_cases = [
                ('a' * 1, False),      # Слишком короткое
                ('a' * 2, True),        # Минимальная длина
                ('a' * 50, True),      # Нормальная длина
                ('a' * 100, False),    # Слишком длинное
            ]
            
            for room_name, should_succeed in test_cases:
                room = RoomService.create_room(
                    name=room_name,
                    creator_id=user.id
                )
                
                if should_succeed:
                    assert room is not None, f"Room '{room_name}' should be created"
                    # Удаляем комнату для следующего теста
                    if room:
                        db.session.delete(room)
                        db.session.commit()
                else:
                    assert room is None, f"Room '{room_name}' should not be created"
    
    def test_room_with_unicode_characters(self, app, db):
        """Тест комнат с Unicode символами"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Тестируем Unicode имена (только те, что проходят валидацию)
            unicode_names = [
                'комната_на_русском',
                'room_русский',
                'room_кириллица',
            ]
            
            for room_name in unicode_names:
                room = RoomService.create_room(
                    name=room_name,
                    creator_id=user.id
                )
                
                assert room is not None, f"Unicode room '{room_name}' should be created"
                
                # Проверяем, что комната сохранилась корректно
                saved_room = Room.query.filter_by(name=room_name).first()
                assert saved_room is not None
                assert saved_room.name == room_name
                
                # Удаляем комнату для следующего теста
                db.session.delete(room)
                db.session.commit()
    
    def test_concurrent_room_creation(self, app, db):
        """Тест одновременного создания комнат"""
        with app.app_context():
            # Создаем пользователя
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Симулируем одновременное создание комнат с одинаковым именем
            room1 = RoomService.create_room('concurrent_room', user.id)
            room2 = RoomService.create_room('concurrent_room', user.id)
            
            # Только одна комната должна быть создана
            assert (room1 is not None and room2 is None) or (room1 is None and room2 is not None)
            
            # Проверяем, что в БД только одна комната
            rooms = Room.query.filter_by(name='concurrent_room').all()
            assert len(rooms) == 1
    
    def test_room_deletion_with_active_users(self, app, db):
        """Тест удаления комнаты с активными пользователями"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username=f'testuser_{id(self)}', email=f'test_{id(self)}@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='active_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Симулируем активных пользователей в комнате через WebSocket сервис
            ws_service = WebSocketService()
            ws_service.active_users['active_room'] = {user.id: user.username}
            
            # Пытаемся удалить комнату
            result = RoomService.cleanup_empty_room('active_room')
            
            # Комната должна быть удалена (логика проверки пользователей в WebSocket сервисе)
            assert result is True
            
            # Проверяем, что комната удалена
            deleted_room = Room.query.filter_by(name='active_room').first()
            assert deleted_room is None
