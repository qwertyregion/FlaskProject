"""
Интеграционные тесты функционала работы с комнатами
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.room_service import RoomService
from app.services.websocket_service import WebSocketService
from app.services.message_service import MessageService
from app.models import Room, User, Message
from app.extensions import db


class TestRoomUserInteraction:
    """Тесты взаимодействия пользователей с комнатами"""
    
    def test_user_join_leave_room_cycle(self, app, db):
        """Тест полного цикла присоединения и выхода пользователя из комнаты"""
        with app.app_context():
            # Создаем пользователей
            user1 = User(username='user1', email='user1@example.com', password_hash='test_hash')
            user2 = User(username='user2', email='user2@example.com', password_hash='test_hash')
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='test_room',
                created_by=user1.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Пользователь 1 присоединяется к комнате
            ws_service.active_users['test_room'] = {user1.id: user1.username}
            
            # Проверяем, что пользователь в комнате
            assert user1.id in ws_service.active_users['test_room']
            assert ws_service.active_users['test_room'][user1.id] == user1.username
            
            # Пользователь 2 присоединяется к комнате
            ws_service.active_users['test_room'][user2.id] = user2.username
            
            # Проверяем, что оба пользователя в комнате
            assert len(ws_service.active_users['test_room']) == 2
            
            # Пользователь 1 выходит из комнаты
            del ws_service.active_users['test_room'][user1.id]
            
            # Проверяем, что пользователь 1 вышел
            assert user1.id not in ws_service.active_users['test_room']
            assert user2.id in ws_service.active_users['test_room']
            
            # Пользователь 2 выходит из комнаты
            del ws_service.active_users['test_room'][user2.id]
            
            # Комната становится пустой
            assert len(ws_service.active_users['test_room']) == 0
    
    def test_room_cleanup_after_last_user_leaves(self, app, db):
        """Тест автоматической очистки комнаты после выхода последнего пользователя"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='testuser', email='test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='temp_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Пользователь присоединяется к комнате
            ws_service.active_users['temp_room'] = {user.id: user.username}
            
            # Проверяем, что комната существует
            assert Room.query.filter_by(name='temp_room').first() is not None
            
            # Пользователь выходит из комнаты
            del ws_service.active_users['temp_room'][user.id]
            
            # Проверяем и очищаем пустую комнату
            ws_service._check_and_cleanup_empty_room('temp_room')
            
            # Проверяем, что комната удалена
            assert Room.query.filter_by(name='temp_room').first() is None
    
    def test_multiple_users_in_room(self, app, db):
        """Тест работы нескольких пользователей в одной комнате"""
        with app.app_context():
            # Создаем пользователей с уникальными именами
            users = []
            for i in range(5):
                user = User(username=f'multi_user_{i}', email=f'multi_user_{i}@example.com', password_hash='test_hash')
                users.append(user)
                db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='multi_user_room',
                created_by=users[0].id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Все пользователи присоединяются к комнате
            ws_service.active_users['multi_user_room'] = {}
            for user in users:
                ws_service.active_users['multi_user_room'][user.id] = user.username
            
            # Проверяем, что все пользователи в комнате
            assert len(ws_service.active_users['multi_user_room']) == 5
            
            # Пользователи по очереди выходят
            for i, user in enumerate(users[:-1]):  # Все кроме последнего
                del ws_service.active_users['multi_user_room'][user.id]
                assert len(ws_service.active_users['multi_user_room']) == 4 - i
            
            # Последний пользователь выходит
            last_user = users[-1]
            del ws_service.active_users['multi_user_room'][last_user.id]
            
            # Комната становится пустой
            assert len(ws_service.active_users['multi_user_room']) == 0


class TestRoomMessageIntegration:
    """Тесты интеграции комнат с сообщениями"""
    
    def test_room_with_message_history(self, app, db):
        """Тест комнаты с историей сообщений"""
        with app.app_context():
            # Создаем пользователей с обязательными полями
            user1 = User(username='history_sender', email='history_sender@example.com', password_hash='test_hash')
            user2 = User(username='history_receiver', email='history_receiver@example.com', password_hash='test_hash')
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='chat_room',
                created_by=user1.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем сообщения в комнате
            messages_data = [
                ('Hello everyone!', user1.id),
                ('Hi there!', user2.id),
                ('How are you?', user1.id),
                ('I am fine, thanks!', user2.id),
            ]
            
            for content, sender_id in messages_data:
                message = Message(
                    content=content,
                    sender_id=sender_id,
                    room_id=room.id
                )
                db.session.add(message)
            
            db.session.commit()
            
            # Получаем историю сообщений
            messages = MessageService.get_room_messages(room.id, limit=10)
            
            assert len(messages) == 4
            
            # Проверяем структуру сообщений
            for message_data in messages:
                assert 'id' in message_data
                assert 'content' in message_data
                assert 'sender_id' in message_data
                assert 'timestamp' in message_data
                assert 'sender_username' in message_data
    
    def test_room_deletion_with_messages(self, app, db):
        """Тест удаления комнаты с сообщениями"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='deletion_testuser', email='deletion_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='room_with_messages',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем сообщения
            for i in range(5):
                message = Message(
                    content=f'Message {i}',
                    sender_id=user.id,
                    room_id=room.id
                )
                db.session.add(message)
            
            db.session.commit()
            
            # Проверяем, что сообщения созданы
            messages_count = Message.query.filter_by(room_id=room.id).count()
            assert messages_count == 5
            
            # Удаляем комнату (физическое удаление)
            result = RoomService.cleanup_empty_room('room_with_messages')
            
            assert result is True
            
            # Проверяем, что комната и сообщения удалены
            assert Room.query.filter_by(name='room_with_messages').first() is None
            assert Message.query.filter_by(room_id=room.id).count() == 0
    
    def test_message_pagination_in_room(self, app, db):
        """Тест пагинации сообщений в комнате"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='pagination_testuser', email='pagination_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='pagination_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем много сообщений
            for i in range(25):
                message = Message(
                    content=f'Message {i:02d}',
                    sender_id=user.id,
                    room_id=room.id
                )
                db.session.add(message)
            
            db.session.commit()
            
            # Тестируем пагинацию
            # Первая страница (10 сообщений) - после reverse() старые первыми
            page1 = MessageService.get_room_messages(room.id, limit=10, offset=0)
            assert len(page1) == 10
            assert page1[0]['content'] == 'Message 15'  # После reverse() первое сообщение
            
            # Вторая страница (10 сообщений)
            page2 = MessageService.get_room_messages(room.id, limit=10, offset=10)
            assert len(page2) == 10
            assert page2[0]['content'] == 'Message 05'  # После reverse() первое сообщение
            
            # Третья страница (5 сообщений) - самые старые сообщения
            page3 = MessageService.get_room_messages(room.id, limit=10, offset=20)
            assert len(page3) == 5
            assert page3[0]['content'] == 'Message 00'  # Самое старое сообщение


class TestRoomWebSocketIntegration:
    """Тесты интеграции комнат с WebSocket"""
    
    def test_room_list_broadcast(self, app, db):
        """Тест рассылки списка комнат"""
        with app.app_context():
            # Очищаем все комнаты перед тестом
            Room.query.delete()
            db.session.commit()
            
            # Создаем пользователя
            user = User(username='broadcast_testuser', email='broadcast_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем несколько комнат
            rooms_data = [
                ('room1', True),
                ('room2', True),
                ('room3', False),  # Неактивная комната
            ]
            
            for name, is_active in rooms_data:
                room = Room(
                    name=name,
                    created_by=user.id,
                    is_active=is_active
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Мокаем emit для проверки рассылки
            with patch('app.services.websocket_service.emit') as mock_emit:
                # Рассылаем список комнат
                ws_service._broadcast_room_list()
                
                # Проверяем, что emit был вызван
                mock_emit.assert_called_once()
                
                # Проверяем данные рассылки
                call_args = mock_emit.call_args
                assert call_args[0][0] == 'room_list'
                
                rooms_list = call_args[0][1]['rooms']
                assert len(rooms_list) == 2  # Только активные комнаты
                
                # rooms_list - это уже список названий комнат (строк)
                assert 'room1' in rooms_list
                assert 'room2' in rooms_list
                assert 'room3' not in rooms_list  # Неактивная комната не включена
    
    def test_room_users_broadcast(self, app, db):
        """Тест рассылки списка пользователей комнаты"""
        with app.app_context():
            # Создаем пользователей
            users = []
            for i in range(3):
                user = User(username=f'broadcast_user_{i}', email=f'broadcast_user_{i}@example.com', password_hash='test_hash')
                users.append(user)
                db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='broadcast_test_room',
                created_by=users[0].id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Пользователи присоединяются к комнате
            ws_service.active_users['broadcast_test_room'] = {}
            for user in users:
                ws_service.active_users['broadcast_test_room'][user.id] = user.username
            
            # Мокаем emit для проверки рассылки
            with patch('app.services.websocket_service.emit') as mock_emit, \
                 patch('app.state.user_state.get_room_users') as mock_get_room_users:
                
                # Мокаем Redis, чтобы он возвращал пользователей из локального кеша
                mock_get_room_users.return_value = ws_service.active_users['broadcast_test_room']
                
                # Рассылаем список пользователей комнаты
                ws_service._send_room_users('broadcast_test_room')
                
                # Проверяем, что emit был вызван
                mock_emit.assert_called_once()
                
                # Проверяем данные рассылки
                call_args = mock_emit.call_args
                assert call_args[0][0] == 'current_users'
                
                users_data = call_args[0][1]
                assert users_data['room'] == 'broadcast_test_room'
                assert len(users_data['users']) == 3
                
                # Проверяем структуру данных пользователей
                # users - это словарь {user_id: username}
                for user_id, username in users_data['users'].items():
                    assert isinstance(user_id, int)
                    assert isinstance(username, str)
    
    def test_room_join_leave_events(self, app, db):
        """Тест событий присоединения и выхода из комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='events_testuser', email='events_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='event_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Мокаем current_user и request.sid для WebSocket операций
            with patch('app.services.websocket_service.current_user') as mock_user, \
                 patch('app.services.websocket_service.request') as mock_request, \
                 patch('app.services.websocket_service.join_room') as mock_join_room, \
                 patch('app.services.websocket_service.leave_room') as mock_leave_room, \
                 patch('app.services.websocket_service.emit') as mock_emit:
                
                # Настраиваем моки
                mock_user.is_authenticated = True
                mock_user.id = user.id
                mock_user.username = user.username
                mock_request.sid = 'test_socket_id'
                
                # Пользователь присоединяется к комнате
                ws_service.handle_join_room({'room': 'event_room'})
                
                # Проверяем, что пользователь добавлен в локальный кеш
                assert 'event_room' in ws_service.active_users
                assert user.id in ws_service.active_users['event_room']
                
                # Пользователь выходит из комнаты
                ws_service.handle_leave_room({'room': 'event_room'})
                
                # Проверяем, что пользователь удален из локального кеша
                assert user.id not in ws_service.active_users['event_room']


class TestRoomErrorHandling:
    """Тесты обработки ошибок в работе с комнатами"""
    
    def test_database_error_during_room_creation(self, app, db):
        """Тест обработки ошибки БД при создании комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='error_testuser', email='error_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Мокаем ошибку БД
            with patch('app.extensions.db.session.commit', side_effect=Exception("Database error")):
                room = RoomService.create_room(
                    name='error_room',
                    creator_id=user.id
                )
                
                assert room is None
                
                # Проверяем, что комната не создана
                assert Room.query.filter_by(name='error_room').first() is None
    
    def test_room_service_with_invalid_user(self, app, db):
        """Тест работы сервиса комнат с несуществующим пользователем"""
        with app.app_context():
            # Пытаемся создать комнату с несуществующим пользователем
            room = RoomService.create_room(
                name='invalid_user_room',
                creator_id=99999  # Несуществующий ID
            )
            
            # Комната должна быть создана (проверка пользователя не выполняется)
            assert room is not None
            assert room.created_by == 99999
    
    def test_room_cleanup_with_database_error(self, app, db):
        """Тест обработки ошибки БД при удалении комнаты"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='cleanup_error_testuser', email='cleanup_error_test@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='error_cleanup_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Мокаем ошибку БД при удалении
            with patch('app.extensions.db.session.commit', side_effect=Exception("Database error")):
                result = RoomService.cleanup_empty_room('error_cleanup_room')
                
                assert result is False
                
                # Проверяем, что комната не удалена
                assert Room.query.filter_by(name='error_cleanup_room').first() is not None
    
    def test_websocket_service_without_authenticated_user(self, app, db):
        """Тест WebSocket сервиса без аутентифицированного пользователя"""
        with app.app_context():
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Мокаем неаутентифицированного пользователя
            with patch('app.services.websocket_service.current_user') as mock_user:
                mock_user.is_authenticated = False
                
                # Мокаем emit
                with patch('app.services.websocket_service.emit') as mock_emit:
                    # Пытаемся создать комнату
                    ws_service.handle_create_room({'room_name': 'unauthorized_room'})
                    
                    # Проверяем, что комната не создана (метод просто возвращается)
                    assert Room.query.filter_by(name='unauthorized_room').first() is None
                    
                    # Проверяем, что emit не был вызван (метод возвращается без emit)
                    mock_emit.assert_not_called()
