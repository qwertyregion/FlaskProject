"""
Простые тесты функционала работы с комнатами
"""
import pytest
from app.services.room_service import RoomService
from app.models import Room, User
from app.extensions import db


class TestRoomBasic:
    """Базовые тесты работы с комнатами"""
    
    def test_create_room_basic(self, app, db):
        """Тест создания комнаты"""
        with app.app_context():
            # Создаем пользователя с уникальным email
            user = User(
                username='testuser1', 
                email='test1@example.com', 
                password_hash='test_hash'
            )
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = RoomService.create_room(
                name='test_room_1',
                creator_id=user.id
            )
            
            assert room is not None
            assert room.name == 'test_room_1'
            assert room.created_by == user.id
            assert room.is_active is True
    
    def test_get_room_by_name(self, app, db):
        """Тест получения комнаты по имени"""
        with app.app_context():
            # Создаем пользователя
            user = User(
                username='testuser2', 
                email='test2@example.com', 
                password_hash='test_hash'
            )
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату напрямую
            room = Room(
                name='test_room_2',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Получаем комнату
            retrieved_room = RoomService.get_room_by_name('test_room_2')
            
            assert retrieved_room is not None
            assert retrieved_room.id == room.id
            assert retrieved_room.name == 'test_room_2'
    
    def test_room_cleanup(self, app, db):
        """Тест физического удаления комнаты"""
        with app.app_context():
            # Создаем пользователя
            user = User(
                username='testuser3', 
                email='test3@example.com', 
                password_hash='test_hash'
            )
            db.session.add(user)
            db.session.commit()
            
            # Создаем комнату
            room = Room(
                name='test_room_3',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            room_id = room.id
            
            # Удаляем комнату (физическое удаление)
            result = RoomService.cleanup_empty_room('test_room_3')
            
            assert result is True
            
            # Проверяем, что комната физически удалена из БД
            deleted_room = Room.query.filter_by(name='test_room_3').first()
            assert deleted_room is None
            
            # Проверяем, что комната не может быть найдена по ID
            room_by_id = Room.query.filter_by(id=room_id).first()
            assert room_by_id is None
    
    def test_default_room_creation(self, app, db):
        """Тест создания комнаты по умолчанию"""
        with app.app_context():
            # Удаляем существующую комнату по умолчанию если она есть
            existing_room = Room.query.filter_by(name='general_chat').first()
            if existing_room:
                db.session.delete(existing_room)
                db.session.commit()
            
            # Проверяем, что комната по умолчанию не существует
            default_room = Room.query.filter_by(name='general_chat').first()
            assert default_room is None
            
            # Создаем комнату по умолчанию
            result = RoomService.ensure_default_room_exists()
            
            assert result is True
            
            # Проверяем, что комната создана
            default_room = Room.query.filter_by(name='general_chat').first()
            assert default_room is not None
            assert default_room.name == 'general_chat'
            assert default_room.is_active is True
    
    def test_room_validation(self, app, db):
        """Тест валидации названий комнат"""
        with app.app_context():
            # Создаем пользователя
            user = User(
                username='testuser4', 
                email='test4@example.com', 
                password_hash='test_hash'
            )
            db.session.add(user)
            db.session.commit()
            
            # Тестируем валидные названия
            valid_names = ['room_1', 'room-2', 'room123', 'комната_русская', 'room with spaces']
            for name in valid_names:
                room = RoomService.create_room(name, user.id)
                assert room is not None, f"Room '{name}' should be created"
                # Удаляем комнату для следующего теста
                db.session.delete(room)
                db.session.commit()
            
            # Тестируем невалидные названия
            invalid_names = ['', 'a', 'room@special', 'admin', 'system']
            for name in invalid_names:
                room = RoomService.create_room(name, user.id)
                assert room is None, f"Room '{name}' should not be created"
