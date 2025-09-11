import os
import uuid
import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("REDIS_URL") is None,
    reason="REDIS_URL не задан, пропускаем Redis-тесты",
)


@pytest.fixture(scope="module")
def redis_client():
    import redis

    url = os.environ.get("REDIS_URL")
    client = redis.from_url(url, decode_responses=True)
    try:
        client.ping()
    except Exception as exc:
        pytest.skip(f"Redis недоступен по {url}: {exc}")
    return client


@pytest.fixture(scope="module")
def flask_app_appctx():
    # Минимальный Flask app context для current_app.logger внутри менеджеров
    from flask import Flask

    app = Flask(__name__)
    with app.app_context():
        yield app


@pytest.fixture(autouse=True)
def wire_extensions_redis(redis_client):
    # Подменяем redis_client в расширениях, чтобы менеджеры использовали реальный Redis
    import app.extensions as ext

    prev = getattr(ext, "redis_client", None)
    ext.redis_client = redis_client
    try:
        yield
    finally:
        ext.redis_client = prev


@pytest.fixture
def clean_redis(redis_client):
    """Очищает Redis перед каждым тестом для изоляции"""
    redis_client.flushdb()
    yield
    redis_client.flushdb()


@pytest.fixture
def unique_user_id():
    """Генерирует уникальный user_id для каждого теста"""
    return int(uuid.uuid4().hex[:8], 16)


@pytest.fixture
def unique_room_name():
    """Генерирует уникальное имя комнаты для каждого теста"""
    return f"test_room_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_socket_id():
    """Генерирует уникальный socket_id для каждого теста"""
    return f"socket_{uuid.uuid4().hex[:8]}"


def test_redis_ping(redis_client):
    assert redis_client.ping() is True


def test_user_state_manager_basic(flask_app_appctx, clean_redis, unique_room_name, unique_user_id):
    from app.state import UserStateManager

    mgr = UserStateManager()
    room = unique_room_name
    user_id = unique_user_id
    username = "tester"

    mgr.ensure_room_exists(room)
    mgr.add_user_to_room(user_id, username, room)

    users = mgr.get_room_users(room)
    assert users.get(user_id) == username

    rooms = mgr.get_user_rooms(user_id)
    assert room in rooms

    mgr.remove_user_from_room(user_id, room)
    users_after = mgr.get_room_users(room)
    assert user_id not in users_after

    # cleanup (room hash удалится в cleanup_empty_room)
    mgr.cleanup_empty_room(room)


def test_connection_manager_basic(flask_app_appctx, clean_redis, unique_user_id, unique_socket_id):
    from app.state import ConnectionManager

    mgr = ConnectionManager()
    user_id = unique_user_id
    socket_id = unique_socket_id

    mgr.register_connection(user_id, socket_id)
    assert mgr.is_user_connected(user_id) is True
    assert mgr.get_user_socket(user_id) == socket_id
    assert mgr.get_socket_user(socket_id) == user_id

    mgr.remove_connection(user_id)
    assert mgr.is_user_connected(user_id) is False
    assert mgr.get_user_socket(user_id) is None


def test_room_manager_basic(flask_app_appctx, clean_redis, unique_room_name, unique_user_id):
    from app.state import RoomManager

    mgr = RoomManager()
    room = unique_room_name
    creator_id = unique_user_id

    mgr.create_room_if_absent(room, creator_id=creator_id)
    info = mgr.get_room_info(room)
    assert info is not None
    assert info.get("name") == room

    rooms = mgr.get_all_rooms()
    assert room in rooms

    mgr.remove_room_meta(room)
    rooms_after = mgr.get_all_rooms()
    assert room not in rooms_after


@pytest.mark.slow
def test_connection_manager_ttl_memory_fallback(flask_app_appctx, unique_user_id, unique_socket_id):
    """Тест TTL в памяти (без Redis)"""
    from app.state import ConnectionManager
    import time

    # Временно отключаем Redis
    import app.extensions as ext
    prev_redis = ext.redis_client
    ext.redis_client = None

    try:
        mgr = ConnectionManager()
        user_id = unique_user_id
        socket_id = unique_socket_id

        print(f"Starting test with user_id: {user_id}")

        # Регистрируем соединение
        mgr.register_connection(user_id, socket_id)
        connected = mgr.is_user_connected(user_id)
        print(f"After registration: connected={connected}")
        assert connected is True

        # Обновляем heartbeat
        ttl = 1.0
        mgr.refresh_heartbeat(user_id, ttl_seconds=ttl)
        
        # Проверяем сразу после обновления
        connected = mgr.is_user_connected(user_id)
        print(f"Immediately after refresh: connected={connected}")
        assert connected is True

        # Ждем немного
        sleep_time_1 = 0.5
        time.sleep(sleep_time_1)
        
        # Проверяем после ожидания
        connected = mgr.is_user_connected(user_id)
        print(f"After {sleep_time_1}s: connected={connected}")
        assert connected is True
        
        # Ждем пока TTL истечет
        sleep_time_2 = 0.6
        time.sleep(sleep_time_2)
        
        # Проверяем после истечения TTL
        connected = mgr.is_user_connected(user_id)
        print(f"After {sleep_time_1 + sleep_time_2}s total: connected={connected}")
        assert connected is False

        print("Test completed successfully")

    finally:
        # Восстанавливаем Redis
        ext.redis_client = prev_redis


@pytest.mark.parametrize("invalid_ttl", [0, -1, -100])
def test_connection_manager_invalid_ttl(flask_app_appctx, clean_redis, unique_user_id, unique_socket_id, invalid_ttl):
    """Тест с недопустимыми значениями TTL"""
    from app.state import ConnectionManager

    mgr = ConnectionManager()
    user_id = unique_user_id
    socket_id = unique_socket_id

    mgr.register_connection(user_id, socket_id)
    assert mgr.is_user_connected(user_id) is True

    # Попытка установить недопустимый TTL должна использовать fallback
    mgr.refresh_heartbeat(user_id, ttl_seconds=invalid_ttl)
    # Соединение должно остаться активным (используется fallback TTL)
    assert mgr.is_user_connected(user_id) is True

    mgr.remove_connection(user_id)


@pytest.mark.parametrize("room_name,expected_valid", [
    ("valid_room", True),
    ("room-123", True),
    ("room_with_underscore", True),
    ("", False),  # пустое имя
    ("a", False),  # слишком короткое
    ("a" * 51, False),  # слишком длинное
])
def test_room_validation_edge_cases(flask_app_appctx, clean_redis, room_name, expected_valid):
    """Тест граничных случаев для имён комнат"""
    from app.state import RoomManager
    from app.validators import WebSocketValidator

    if expected_valid:
        # Для валидных имён тестируем создание комнаты
        mgr = RoomManager()
        result = WebSocketValidator.validate_room_name(room_name)
        assert result["valid"] is True
        
        mgr.create_room_if_absent(room_name, creator_id=1)
        info = mgr.get_room_info(room_name)
        assert info is not None
        assert info.get("name") == room_name
    else:
        # Для невалидных имён тестируем валидацию
        result = WebSocketValidator.validate_room_name(room_name)
        assert result["valid"] is False


# ========== ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ==========

@pytest.mark.slow
def test_connection_manager_concurrent_registration(flask_app_appctx, clean_redis, unique_user_id):
    """Тест конкурентной регистрации соединений одного пользователя"""
    from app.state import ConnectionManager
    import threading
    import time

    mgr = ConnectionManager()
    user_id = unique_user_id
    results = []
    errors = []

    def register_connection(socket_id):
        try:
            mgr.register_connection(user_id, socket_id)
            results.append(socket_id)
        except Exception as e:
            errors.append(e)

    # Создаем несколько потоков для регистрации одного пользователя
    threads = []
    socket_ids = [f"socket_{i}" for i in range(5)]
    
    for socket_id in socket_ids:
        thread = threading.Thread(target=register_connection, args=(socket_id,))
        threads.append(thread)
        thread.start()

    # Ждем завершения всех потоков
    for thread in threads:
        thread.join()

    # Проверяем, что нет ошибок
    assert len(errors) == 0, f"Ошибки при конкурентной регистрации: {errors}"
    
    # Проверяем, что пользователь подключен
    assert mgr.is_user_connected(user_id) is True
    
    # Проверяем, что socket_id соответствует последней регистрации
    current_socket = mgr.get_user_socket(user_id)
    assert current_socket in socket_ids
    
    # Проверяем обратную связь
    assert mgr.get_socket_user(current_socket) == user_id


def test_redis_failure_fallback(flask_app_appctx, unique_user_id, unique_socket_id):
    """Тест fallback в память при падении Redis во время операции"""
    from app.state import ConnectionManager
    import app.extensions as ext
    from unittest.mock import Mock

    # Создаем мок Redis клиента, который падает при операциях
    mock_redis = Mock()
    mock_redis.hset.side_effect = Exception("Redis connection lost")
    mock_redis.hget.side_effect = Exception("Redis connection lost")
    mock_redis.exists.side_effect = Exception("Redis connection lost")
    mock_redis.delete.side_effect = Exception("Redis connection lost")
    mock_redis.set.side_effect = Exception("Redis connection lost")

    # Подменяем Redis клиент
    prev_redis = ext.redis_client
    ext.redis_client = mock_redis

    try:
        mgr = ConnectionManager()
        user_id = unique_user_id
        socket_id = unique_socket_id

        # Регистрация должна упасть в память
        mgr.register_connection(user_id, socket_id)
        assert mgr.is_user_connected(user_id) is True
        assert mgr.get_user_socket(user_id) == socket_id
        assert mgr.get_socket_user(socket_id) == user_id

        # Heartbeat должен работать в памяти
        mgr.refresh_heartbeat(user_id, ttl_seconds=1.0)
        assert mgr.is_user_connected(user_id) is True

        # Удаление должно работать в памяти
        mgr.remove_connection(user_id)
        assert mgr.is_user_connected(user_id) is False

    finally:
        ext.redis_client = prev_redis


@pytest.mark.parametrize("ttl, sleep_time, should_be_connected", [
    (1.0, 0.9, True),    # чуть меньше TTL (увеличил запас)
    (1.0, 1.1, False),   # чуть больше TTL
    (0.5, 0.4, True),    # субсекундный TTL
    (0.5, 0.6, False),   # больше субсекундного TTL
])
@pytest.mark.slow
def test_ttl_boundary_conditions(flask_app_appctx, unique_user_id, unique_socket_id, ttl, sleep_time, should_be_connected):
    """Тест граничных условий TTL"""
    from app.state import ConnectionManager
    import time
    import app.extensions as ext

    # Отключаем Redis для точного контроля TTL
    prev_redis = ext.redis_client
    ext.redis_client = None

    try:
        mgr = ConnectionManager()
        user_id = unique_user_id
        socket_id = unique_socket_id

        mgr.register_connection(user_id, socket_id)
        mgr.refresh_heartbeat(user_id, ttl_seconds=ttl)
        
        time.sleep(sleep_time)
        
        connected = mgr.is_user_connected(user_id)
        assert connected is should_be_connected, f"TTL={ttl}, sleep={sleep_time}, expected={should_be_connected}, got={connected}"

    finally:
        ext.redis_client = prev_redis


def test_data_cleanup_after_removal(flask_app_appctx, clean_redis, unique_user_id, unique_socket_id, unique_room_name):
    """Тест полной очистки данных после удаления"""
    from app.state import ConnectionManager, UserStateManager, RoomManager
    import app.extensions as ext

    conn_mgr = ConnectionManager()
    user_mgr = UserStateManager()
    room_mgr = RoomManager()
    
    user_id = unique_user_id
    socket_id = unique_socket_id
    room_name = unique_room_name
    username = "test_user"

    # Создаем данные
    conn_mgr.register_connection(user_id, socket_id)
    room_mgr.create_room_if_absent(room_name, creator_id=user_id)
    user_mgr.add_user_to_room(user_id, username, room_name)

    # Проверяем, что данные созданы
    assert conn_mgr.is_user_connected(user_id) is True
    assert room_name in room_mgr.get_all_rooms()
    assert user_id in user_mgr.get_room_users(room_name)

    # Удаляем соединение
    conn_mgr.remove_connection(user_id)
    assert conn_mgr.is_user_connected(user_id) is False
    assert conn_mgr.get_user_socket(user_id) is None

    # Удаляем пользователя из комнаты
    user_mgr.remove_user_from_room(user_id, room_name)
    assert user_id not in user_mgr.get_room_users(room_name)

    # Очищаем пустую комнату
    user_mgr.cleanup_empty_room(room_name)
    room_mgr.remove_room_meta(room_name)
    assert room_name not in room_mgr.get_all_rooms()

    # Проверяем, что в Redis нет "висячих" ключей
    if ext.redis_client is not None:
        # Проверяем отсутствие ключей соединения
        hb_key = f"conn:heartbeat:{user_id}"
        user_socket_key = f"conn:user_to_socket"
        socket_user_key = f"conn:socket_to_user"
        
        assert ext.redis_client.exists(hb_key) == 0
        assert ext.redis_client.hget(user_socket_key, str(user_id)) is None
        assert ext.redis_client.hget(socket_user_key, socket_id) is None
        
        # Проверяем отсутствие ключей комнаты
        room_users_key = f"room:{room_name}:users"
        user_rooms_key = f"user:{user_id}:rooms"
        room_meta_key = f"room:meta:{room_name}"
        
        assert ext.redis_client.exists(room_users_key) == 0
        assert ext.redis_client.exists(user_rooms_key) == 0
        assert ext.redis_client.exists(room_meta_key) == 0


@pytest.mark.parametrize("message, should_be_valid", [
    ("Hello world", True),
    ("Привет мир", True),
    ("Hello 🌍", True),  # эмодзи
    ("Hello\x00world", False),  # null байт (точно блокируется)
    ("  Hello world  ", True),  # пробелы в начале/конце (должны обрезаться)
    ("Hello\u00A0world", True),  # неразрывный пробел
    ("Hello\u2000world", True),  # en quad
    ("Hello\u2001world", True),  # em quad
    ("Hello\u2002world", True),  # en space
    ("Hello\u2003world", True),  # em space
    ("Hello\u2004world", True),  # three-per-em space
    ("Hello\u2005world", True),  # four-per-em space
    ("Hello\u2006world", True),  # six-per-em space
    ("Hello\u2007world", True),  # figure space
    ("Hello\u2008world", True),  # punctuation space
    ("Hello\u2009world", True),  # thin space
    ("Hello\u200Aworld", True),  # hair space
    ("Hello\u202Fworld", True),  # narrow no-break space
    ("Hello\u205Fworld", True),  # medium mathematical space
    ("Hello\u3000world", True),  # ideographic space
])
def test_unicode_message_validation(message, should_be_valid):
    """Тест валидации сообщений с юникодными символами"""
    from app.validators import WebSocketValidator

    result = WebSocketValidator.validate_message_content(message)
    # Некоторые символы могут проходить валидацию, но обрезаться
    if should_be_valid:
        assert result["valid"] is True, f"Message '{message}' validation failed: {result.get('error', 'No error message')}"
    else:
        # Если сообщение не должно быть валидным, проверяем что оно отклонено
        if result["valid"]:
            # Если прошло валидацию, проверяем что содержимое изменилось (обрезалось)
            assert result["content"] != message, f"Message '{message}' should be invalid but passed validation unchanged"
        else:
            assert "недопустимые символы" in result["error"].lower() or "спам" in result["error"].lower()


@pytest.mark.parametrize("room_name, should_be_valid", [
    ("Room_1", True),
    ("Комната-1", True),
    ("Room🌍", False),  # эмодзи в названии не разрешены
    ("Room\u200B", False),  # невидимый символ
    ("Room\u00A0", True),  # неразрывный пробел
    ("Room\u2000", True),  # en quad
    ("Room\u2001", True),  # em quad
    ("Room\u2002", True),  # en space
    ("Room\u2003", True),  # em space
    ("Room\u2004", True),  # three-per-em space
    ("Room\u2005", True),  # four-per-em space
    ("Room\u2006", True),  # six-per-em space
    ("Room\u2007", True),  # figure space
    ("Room\u2008", True),  # punctuation space
    ("Room\u2009", True),  # thin space
    ("Room\u200A", True),  # hair space
    ("Room\u202F", True),  # narrow no-break space
    ("Room\u205F", True),  # medium mathematical space
    ("Room\u3000", True),  # ideographic space
    ("  Room  ", True),  # обычные пробелы (должны обрезаться)
])
def test_unicode_room_name_validation(room_name, should_be_valid):
    """Тест валидации названий комнат с юникодными символами"""
    from app.validators import WebSocketValidator

    result = WebSocketValidator.validate_room_name(room_name)
    assert result["valid"] is should_be_valid, f"Room name '{room_name}' validation failed: {result.get('error', 'No error message')}"


def test_heartbeat_config_integration(flask_app_appctx, unique_user_id, unique_socket_id):
    """Тест интеграции с config.HEARTBEAT_TTL_SECONDS"""
    from app.state import ConnectionManager
    from flask import Flask
    import app.extensions as ext

    # Отключаем Redis для тестирования in-memory логики
    prev_redis = ext.redis_client
    ext.redis_client = None

    try:
        # Создаем Flask app с кастомным конфигом
        app = Flask(__name__)
        app.config['HEARTBEAT_TTL_SECONDS'] = 300  # 5 минут

        with app.app_context():
            mgr = ConnectionManager()
            user_id = unique_user_id
            socket_id = unique_socket_id

            # Регистрируем соединение (должно использовать конфиг)
            mgr.register_connection(user_id, socket_id)
            assert mgr.is_user_connected(user_id) is True

            # Обновляем heartbeat без явного TTL (должен использовать конфиг)
            mgr.refresh_heartbeat(user_id)
            assert mgr.is_user_connected(user_id) is True

            # Проверяем, что TTL установлен из конфига
            import time
            current_time = time.time()
            expiration_time = mgr._heartbeat_expires[user_id]
            expected_ttl = 300  # 5 минут из конфига
            actual_ttl = expiration_time - current_time
            
            # Допускаем погрешность в 1 секунду
            assert abs(actual_ttl - expected_ttl) <= 1, f"Expected TTL ~{expected_ttl}, got {actual_ttl}"

    finally:
        ext.redis_client = prev_redis


def test_heartbeat_config_fallback(flask_app_appctx, unique_user_id, unique_socket_id):
    """Тест fallback TTL при отсутствии конфига"""
    from app.state import ConnectionManager
    from flask import Flask
    import app.extensions as ext

    # Отключаем Redis для тестирования in-memory логики
    prev_redis = ext.redis_client
    ext.redis_client = None

    try:
        # Создаем Flask app без HEARTBEAT_TTL_SECONDS
        app = Flask(__name__)
        # Не устанавливаем HEARTBEAT_TTL_SECONDS

        with app.app_context():
            mgr = ConnectionManager()
            user_id = unique_user_id
            socket_id = unique_socket_id

            # Регистрируем соединение (должно использовать fallback)
            mgr.register_connection(user_id, socket_id)
            assert mgr.is_user_connected(user_id) is True

            # Обновляем heartbeat без явного TTL (должен использовать fallback)
            mgr.refresh_heartbeat(user_id)
            assert mgr.is_user_connected(user_id) is True

            # Проверяем, что TTL установлен из fallback (120 секунд)
            import time
            current_time = time.time()
            expiration_time = mgr._heartbeat_expires[user_id]
            expected_ttl = 120  # fallback значение
            actual_ttl = expiration_time - current_time
            
            # Допускаем погрешность в 1 секунду
            assert abs(actual_ttl - expected_ttl) <= 1, f"Expected fallback TTL ~{expected_ttl}, got {actual_ttl}"

    finally:
        ext.redis_client = prev_redis


