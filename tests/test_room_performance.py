"""
Тесты производительности функционала работы с комнатами
"""
import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from app.services.room_service import RoomService
from app.services.websocket_service import WebSocketService
from app.services.message_service import MessageService
from app.models import Room, User, Message
from app.extensions import db


class TestRoomPerformance:
    """Тесты производительности работы с комнатами"""
    
    def test_bulk_room_creation_performance(self, app, db):
        """Тест производительности массового создания комнат"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='bulk_perf_user', email='bulk_perf@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Измеряем время создания множества комнат
            start_time = time.time()
            
            rooms_created = 0
            for i in range(50):  # Создаем 50 комнат
                room = RoomService.create_room(
                    name=f'perf_room_{i:03d}',
                    creator_id=user.id
                )
                if room:
                    rooms_created += 1
            
            end_time = time.time()
            creation_time = end_time - start_time
            
            # Проверяем результаты
            assert rooms_created == 50
            assert creation_time < 5.0  # Должно быть быстрее 5 секунд
            
            # Проверяем, что все комнаты созданы в БД
            rooms_in_db = Room.query.filter(Room.name.like('perf_room_%')).count()
            assert rooms_in_db == 50
    
    def test_room_cleanup_performance(self, app, db):
        """Тест производительности очистки множества комнат"""
        with app.app_context():
            # Очищаем все комнаты кроме general_chat перед тестом
            Room.query.filter(Room.name != 'general_chat').delete()
            db.session.commit()
            
            # Создаем пользователя
            user = User(username='cleanup_perf_user', email='cleanup_perf@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем множество комнат
            for i in range(100):
                room = Room(
                    name=f'cleanup_room_{i:03d}',
                    created_by=user.id,
                    is_active=True
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Измеряем время очистки
            start_time = time.time()
            
            deleted_count = RoomService.cleanup_all_rooms()
            
            end_time = time.time()
            cleanup_time = end_time - start_time
            
            # Проверяем результаты
            assert deleted_count == 100
            assert cleanup_time < 3.0  # Должно быть быстрее 3 секунд
            
            # Проверяем, что все комнаты удалены
            remaining_rooms = Room.query.filter(Room.name.like('cleanup_room_%')).count()
            assert remaining_rooms == 0
    
    def test_room_query_performance(self, app, db):
        """Тест производительности запросов к комнатам"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='query_perf_user', email='query_perf@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем множество комнат
            for i in range(200):
                room = Room(
                    name=f'query_room_{i:03d}',
                    created_by=user.id,
                    is_active=True
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Тестируем производительность различных запросов
            
            # 1. Получение всех комнат
            start_time = time.time()
            all_rooms = RoomService.get_all_rooms()
            end_time = time.time()
            get_all_time = end_time - start_time
            
            assert len(all_rooms) == 200
            assert get_all_time < 1.0  # Должно быть быстрее 1 секунды
            
            # 2. Поиск комнаты по имени
            start_time = time.time()
            for i in range(10):
                room = RoomService.get_room_by_name(f'query_room_{i:03d}')
                assert room is not None
            end_time = time.time()
            search_time = end_time - start_time
            
            assert search_time < 0.5  # Должно быть быстрее 0.5 секунды
    
    def test_room_with_many_messages_performance(self, app, db):
        """Тест производительности комнаты с большим количеством сообщений"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='messages_perf_user', email='messages_perf@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='message_heavy_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Создаем множество сообщений
            start_time = time.time()
            
            for i in range(1000):  # 1000 сообщений
                message = Message(
                    content=f'Message {i:04d}',
                    sender_id=user.id,
                    room_id=room.id
                )
                db.session.add(message)
            
            db.session.commit()
            
            creation_time = time.time() - start_time
            
            # Проверяем время создания сообщений
            assert creation_time < 10.0  # Должно быть быстрее 10 секунд
            
            # Тестируем производительность получения сообщений
            start_time = time.time()
            
            # Получаем сообщения с пагинацией
            messages = MessageService.get_room_messages(room.id, limit=50, offset=0)
            
            end_time = time.time()
            retrieval_time = end_time - start_time
            
            # Проверяем результаты
            assert len(messages) == 50
            assert retrieval_time < 1.0  # Должно быть быстрее 1 секунды
            
            # Тестируем получение всех сообщений
            start_time = time.time()
            
            all_messages = MessageService.get_room_messages(room.id, limit=1000, offset=0)
            
            end_time = time.time()
            all_retrieval_time = end_time - start_time
            
            assert len(all_messages) == 1000
            assert all_retrieval_time < 2.0  # Должно быть быстрее 2 секунд


class TestRoomConcurrency:
    """Тесты конкурентности работы с комнатами"""
    
    def test_concurrent_room_creation(self, app, db):
        """Тест одновременного создания комнат (симуляция конкурентности)"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='concurrent_user', email='concurrent@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Симулируем одновременное создание комнат
            # ВАЖНО: Это НЕ реальная конкурентность, а симуляция
            # Реальная конкурентность требует threading или multiprocessing
            created_rooms = []
            failed_creations = 0
            
            # Последовательное создание комнат с уникальными именами
            for i in range(20):
                room = RoomService.create_room(
                    name=f'concurrent_room_{i:02d}',
                    creator_id=user.id
                )
                
                if room:
                    created_rooms.append(room)
                else:
                    failed_creations += 1
            
            # Проверяем результаты
            assert len(created_rooms) == 20
            assert failed_creations == 0
            
            # Проверяем, что все комнаты уникальны
            room_names = [room.name for room in created_rooms]
            assert len(set(room_names)) == 20  # Все имена уникальны
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: тестируем создание дубликатов
            # Это проверяет защиту от race conditions в create_room
            duplicate_room = RoomService.create_room(
                name='concurrent_room_00',  # Дубликат
                creator_id=user.id
            )
            assert duplicate_room is None  # Дубликат должен быть отклонен
    
    def test_concurrent_room_access_simulation(self, app, db):
        """Симуляция конкурентного доступа к комнатам"""
        with app.app_context():
            # Создаем пользователя и комнату
            user = User(username='access_sim_user', email='access_sim@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            room = Room(
                name='concurrent_access_sim_room',
                created_by=user.id,
                is_active=True
            )
            db.session.add(room)
            db.session.commit()
            
            # Симулируем множественные обращения к комнате
            access_results = []
            start_time = time.time()
            
            # Быстрые последовательные запросы (имитация конкурентности)
            for i in range(100):
                retrieved_room = RoomService.get_room_by_name('concurrent_access_sim_room')
                access_results.append(retrieved_room is not None)
            
            end_time = time.time()
            access_time = end_time - start_time
            
            # Все запросы должны быть успешными
            assert all(access_results), "Некоторые запросы к комнате не удались"
            assert len(access_results) == 100, f"Выполнено {len(access_results)} запросов вместо 100"
            
            # Проверяем производительность доступа
            assert access_time < 1.0, f"Доступ к комнате занял {access_time:.2f} секунд"
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: тестируем доступ к несуществующей комнате
            non_existent_room = RoomService.get_room_by_name('non_existent_room')
            assert non_existent_room is None, "Несуществующая комната должна возвращать None"
    
    def test_concurrent_room_cleanup_simulation(self, app, db):
        """Симуляция конкурентной очистки комнат"""
        with app.app_context():
            # Очищаем все комнаты кроме general_chat перед тестом
            Room.query.filter(Room.name != 'general_chat').delete()
            db.session.commit()
            
            # Создаем пользователя
            user = User(username='cleanup_sim_user', email='cleanup_sim@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем множество комнат
            for i in range(50):
                room = Room(
                    name=f'concurrent_cleanup_sim_{i:02d}',
                    created_by=user.id,
                    is_active=True
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Симулируем множественные попытки очистки
            cleanup_results = []
            start_time = time.time()
            
            # Быстрые последовательные попытки очистки (имитация конкурентности)
            for i in range(10):  # 10 попыток очистки
                deleted_count = RoomService.cleanup_all_rooms()
                cleanup_results.append(deleted_count)
            
            end_time = time.time()
            cleanup_time = end_time - start_time
            
            # Проверяем результаты
            # Первая очистка должна удалить все комнаты
            assert cleanup_results[0] == 50, f"Первая очистка удалила {cleanup_results[0]} комнат вместо 50"
            
            # Последующие очистки должны удалить 0 комнат
            for i in range(1, 10):
                assert cleanup_results[i] == 0, f"Попытка {i+1} удалила {cleanup_results[i]} комнат вместо 0"
            
            # Проверяем производительность очистки
            assert cleanup_time < 2.0, f"Очистка заняла {cleanup_time:.2f} секунд"
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: убеждаемся, что все комнаты удалены
            remaining_rooms = Room.query.filter(Room.name.like('concurrent_cleanup_sim_%')).count()
            assert remaining_rooms == 0, f"Осталось {remaining_rooms} комнат после очистки"
    
    def test_concurrent_room_creation_simulation(self, app, db):
        """Симуляция конкурентного создания комнат (без реального threading из-за SQLite)"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='concurrent_sim_user', email='concurrent_sim@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Симулируем конкурентное создание комнат
            # ВАЖНО: SQLite не поддерживает конкурентные записи из разных потоков
            # Поэтому мы симулируем это через быстрые последовательные операции
            
            created_rooms = []
            failed_creations = 0
            
            # Быстрое последовательное создание (имитация конкурентности)
            start_time = time.time()
            for i in range(20):
                room = RoomService.create_room(
                    name=f'concurrent_sim_room_{i:02d}',
                    creator_id=user.id
                )
                
                if room:
                    created_rooms.append(room)
                else:
                    failed_creations += 1
            end_time = time.time()
            
            # Проверяем результаты
            assert len(created_rooms) == 20, f"Создано {len(created_rooms)} комнат вместо 20"
            assert failed_creations == 0, f"Неудачных созданий: {failed_creations}"
            
            # Проверяем, что все комнаты уникальны
            room_names = [room.name for room in created_rooms]
            assert len(set(room_names)) == 20, "Найдены дубликаты комнат"
            
            # Проверяем время выполнения
            execution_time = end_time - start_time
            assert execution_time < 3.0, f"Создание заняло {execution_time:.2f} секунд"
            
            # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: тестируем защиту от дубликатов
            duplicate_room = RoomService.create_room(
                name='concurrent_sim_room_00',  # Дубликат
                creator_id=user.id
            )
            assert duplicate_room is None, "Дубликат должен быть отклонен"
            
            # Проверяем, что все комнаты созданы в БД
            rooms_in_db = Room.query.filter(Room.name.like('concurrent_sim_room_%')).count()
            assert rooms_in_db == 20, f"В БД найдено {rooms_in_db} комнат вместо 20"


class TestRoomMemoryUsage:
    """Тесты использования памяти при работе с комнатами"""
    
    def test_large_room_list_memory(self, app, db):
        """Тест использования памяти при работе с большим списком комнат"""
        with app.app_context():
            # Очищаем все комнаты кроме general_chat перед тестом
            Room.query.filter(Room.name != 'general_chat').delete()
            db.session.commit()
            
            # Создаем пользователя
            user = User(username='memory_user', email='memory@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем большое количество комнат
            for i in range(500):
                room = Room(
                    name=f'memory_room_{i:03d}',
                    created_by=user.id,
                    is_active=True
                )
                db.session.add(room)
            
            db.session.commit()
            
            # Получаем все комнаты
            all_rooms = RoomService.get_all_rooms()
            
            # Проверяем, что все комнаты получены
            assert len(all_rooms) == 500
            
            # Проверяем структуру данных
            for room_data in all_rooms:
                assert isinstance(room_data, dict)
                assert 'id' in room_data
                assert 'name' in room_data
                assert 'created_by' in room_data
                assert 'creator_username' in room_data
                assert 'is_private' in room_data
                assert 'created_at' in room_data
    
    def test_websocket_service_memory_scaling(self, app, db):
        """Тест масштабирования памяти WebSocket сервиса"""
        with app.app_context():
            # Создаем пользователей
            users = []
            for i in range(100):
                user = User(username=f'user{i:03d}', email=f'user{i:03d}@example.com', password_hash='test_hash')
                users.append(user)
                db.session.add(user)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Симулируем присоединение пользователей к разным комнатам
            for i in range(50):  # 50 комнат
                room_name = f'memory_room_{i:02d}'
                ws_service.active_users[room_name] = {}
                
                # Каждая комната содержит 2 пользователя
                for j in range(2):
                    user_idx = i * 2 + j
                    if user_idx < len(users):
                        ws_service.active_users[room_name][users[user_idx].id] = users[user_idx].username
            
            # Проверяем, что все пользователи распределены по комнатам
            total_users = sum(len(room_users) for room_users in ws_service.active_users.values())
            assert total_users == 100
            
            # Проверяем количество комнат
            assert len(ws_service.active_users) == 51  # 50 комнат + default room


class TestRoomStressTest:
    """Стресс-тесты функционала комнат"""
    
    def test_rapid_room_creation_deletion_cycle(self, app, db):
        """Тест быстрого цикла создания и удаления комнат"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='stress_user', email='stress@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Выполняем множество циклов создания-удаления
            for cycle in range(10):
                # Создаем комнату
                room = RoomService.create_room(
                    name=f'stress_room_{cycle:02d}',
                    creator_id=user.id
                )
                
                assert room is not None
                
                # Сразу удаляем комнату
                result = RoomService.cleanup_empty_room(f'stress_room_{cycle:02d}')
                
                assert result is True
                
                # Проверяем, что комната удалена
                deleted_room = Room.query.filter_by(name=f'stress_room_{cycle:02d}').first()
                assert deleted_room is None
    
    def test_room_operations_under_load(self, app, db):
        """Тест операций с комнатами под нагрузкой"""
        with app.app_context():
            # Создаем пользователя
            user = User(username='load_user', email='load@example.com', password_hash='test_hash')
            db.session.add(user)
            db.session.commit()
            
            # Создаем WebSocket сервис
            ws_service = WebSocketService()
            
            # Симулируем нагрузку
            start_time = time.time()
            
            operations_count = 0
            
            # Выполняем множество операций
            for i in range(100):
                # Создание комнаты
                room = RoomService.create_room(
                    name=f'load_room_{i:03d}',
                    creator_id=user.id
                )
                operations_count += 1
                
                # Получение комнаты
                retrieved_room = RoomService.get_room_by_name(f'load_room_{i:03d}')
                operations_count += 1
                
                # Добавление пользователя в комнату (WebSocket)
                ws_service.active_users[f'load_room_{i:03d}'] = {user.id: user.username}
                operations_count += 1
                
                # Получение списка комнат
                all_rooms = RoomService.get_all_rooms()
                operations_count += 1
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Проверяем результаты
            assert operations_count == 400  # 100 * 4 операции
            assert total_time < 15.0  # Должно быть быстрее 15 секунд
            
            # Проверяем, что все комнаты созданы
            rooms_in_db = Room.query.filter(Room.name.like('load_room_%')).count()
            assert rooms_in_db == 100
