import pytest
from flask import Flask

from app.validators import WebSocketValidator


@pytest.fixture(scope='module')
def flask_app():
    app = Flask(__name__)
    with app.app_context():
        yield app


class TestValidateMessageContent:
    def test_empty_message(self):
        result = WebSocketValidator.validate_message_content("")
        assert result["valid"] is False
        assert "не может быть пустым" in result["error"].lower()

    def test_too_long_message(self):
        long_text = "a" * (WebSocketValidator.MAX_MESSAGE_LENGTH + 1)
        result = WebSocketValidator.validate_message_content(long_text)
        assert result["valid"] is False
        assert "слишком длинное" in result["error"].lower()

    def test_control_chars_rejected(self):
        result = WebSocketValidator.validate_message_content("hello\x07world")
        assert result["valid"] is False
        assert "недопустимые символы" in result["error"].lower()

    def test_spam_detected(self):
        # Мало уникальных символов и длина > 10
        spam_text = "aaaaaaaaaaaaa"  # 13 одинаковых символов
        result = WebSocketValidator.validate_message_content(spam_text)
        assert result["valid"] is False
        assert "спам" in result["error"].lower()

    def test_xss_detected(self, flask_app):
        result = WebSocketValidator.validate_message_content("<script>alert(1)</script>")
        assert result["valid"] is False
        assert "недопустимый контент" in result["error"].lower()

    def test_valid_message_trimmed(self):
        result = WebSocketValidator.validate_message_content("  Hello world  ")
        assert result["valid"] is True
        assert result["content"] == "Hello world"


class TestValidateRoomName:
    def test_empty_room_name(self):
        result = WebSocketValidator.validate_room_name("")
        assert result["valid"] is False
        assert "не может быть пустым" in result["error"].lower()

    def test_too_short_room_name(self):
        result = WebSocketValidator.validate_room_name("a")
        assert result["valid"] is False
        assert "слишком короткое" in result["error"].lower()

    def test_too_long_room_name(self):
        name = "a" * (WebSocketValidator.MAX_ROOM_NAME_LENGTH + 1)
        result = WebSocketValidator.validate_room_name(name)
        assert result["valid"] is False
        assert "слишком длинное" in result["error"].lower()

    def test_invalid_chars_in_room_name(self):
        result = WebSocketValidator.validate_room_name("bad!name")
        assert result["valid"] is False
        assert "может содержать только" in result["error"].lower()

    def test_forbidden_room_name(self):
        result = WebSocketValidator.validate_room_name("Admin")
        assert result["valid"] is False
        assert "зарезервировано" in result["error"].lower()

    def test_valid_room_name_with_trim(self):
        result = WebSocketValidator.validate_room_name("  Room_1 - Тест  ")
        assert result["valid"] is True
        assert result["room_name"] == "Room_1 - Тест"


class TestValidateUserId:
    def test_valid_integer_id(self):
        result = WebSocketValidator.validate_user_id(10)
        assert result["valid"] is True
        assert result["user_id"] == 10

    def test_valid_string_id(self):
        result = WebSocketValidator.validate_user_id("5")
        assert result["valid"] is True
        assert result["user_id"] == 5

    def test_zero_id_invalid(self):
        result = WebSocketValidator.validate_user_id(0)
        assert result["valid"] is False
        assert "неверный id" in result["error"].lower()

    def test_negative_id_invalid(self):
        result = WebSocketValidator.validate_user_id(-3)
        assert result["valid"] is False
        assert "неверный id" in result["error"].lower()

    def test_non_numeric_id_invalid(self):
        result = WebSocketValidator.validate_user_id("abc")
        assert result["valid"] is False
        assert "должен быть числом" in result["error"].lower()

    def test_none_id_invalid(self):
        result = WebSocketValidator.validate_user_id(None)
        assert result["valid"] is False
        assert "должен быть числом" in result["error"].lower()


# ========== ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ВАЛИДАЦИИ ==========

class TestAdvancedMessageValidation:
    def test_unicode_normalization(self):
        """Тест нормализации юникодных символов"""
        # Комбинирующие диакритики
        result = WebSocketValidator.validate_message_content("café")
        assert result["valid"] is True
        
        # Эмодзи и смешанные языки
        result = WebSocketValidator.validate_message_content("Hello 世界 🌍 Привет")
        assert result["valid"] is True
        
        # Арабские цифры и текст
        result = WebSocketValidator.validate_message_content("Цена: 123₽")
        assert result["valid"] is True

    def test_message_trimming_behavior(self):
        """Тест поведения обрезки пробелов"""
        # Обычные пробелы
        result = WebSocketValidator.validate_message_content("  Hello  ")
        assert result["valid"] is True
        assert result["content"] == "Hello"
        
        # Табуляции и переносы строк (должны быть отклонены)
        result = WebSocketValidator.validate_message_content("\tHello\n")
        # Проверяем, что либо отклонено, либо обрезано до "Hello"
        if result["valid"]:
            assert result["content"] == "Hello", f"Ожидалось 'Hello', получено '{result['content']}'"
        else:
            assert "недопустимые символы" in result["error"].lower()
        
        # Неразрывные пробелы (принимаются, но обрезаются как обычные пробелы)
        result = WebSocketValidator.validate_message_content("\u00A0Hello\u00A0")
        assert result["valid"] is True
        assert result["content"] == "Hello"  # валидатор обрезает все пробелы

    def test_spam_detection_edge_cases(self):
        """Тест граничных случаев детекции спама"""
        # Много повторяющихся символов, но короткая строка
        result = WebSocketValidator.validate_message_content("aaaa")
        assert result["valid"] is True  # короткая, не спам
        
        # Много повторяющихся символов, длинная строка
        result = WebSocketValidator.validate_message_content("a" * 20)
        assert result["valid"] is False  # спам
        
        # Повторяющиеся слова
        result = WebSocketValidator.validate_message_content("hello hello hello hello")
        assert result["valid"] is True  # слова, не символы
        
        # Смешанные повторяющиеся символы (2 символа, но >10 символов = спам)
        result = WebSocketValidator.validate_message_content("abababababababababab")
        assert result["valid"] is False  # два символа, но длинная строка = спам

    def test_xss_variations(self):
        """Тест различных вариантов XSS"""
        xss_attempts = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<iframe src=javascript:alert(1)></iframe>",
            "<svg onload=alert(1)>",
            "data:text/html,<script>alert(1)</script>",
            "<link rel=stylesheet href=javascript:alert(1)>",
        ]
        
        for xss in xss_attempts:
            result = WebSocketValidator.validate_message_content(xss)
            assert result["valid"] is False, f"XSS не обнаружен: {xss}"

    def test_control_characters_comprehensive(self):
        """Тест различных управляющих символов"""
        control_chars = [
            "\x00",  # NULL
            "\x01",  # SOH
            "\x02",  # STX
            "\x03",  # ETX
            "\x04",  # EOT
            "\x05",  # ENQ
            "\x06",  # ACK
            "\x07",  # BEL
            "\x08",  # BS
            "\x0B",  # VT
            "\x0C",  # FF
            "\x0E",  # SO
            "\x0F",  # SI
            "\x10",  # DLE
            "\x11",  # DC1
            "\x12",  # DC2
            "\x13",  # DC3
            "\x14",  # DC4
            "\x15",  # NAK
            "\x16",  # SYN
            "\x17",  # ETB
            "\x18",  # CAN
            "\x19",  # EM
            "\x1A",  # SUB
            "\x1B",  # ESC
            "\x1C",  # FS
            "\x1D",  # GS
            "\x1E",  # RS
            "\x1F",  # US
            "\x7F",  # DEL
        ]
        
        for char in control_chars:
            result = WebSocketValidator.validate_message_content(f"Hello{char}World")
            assert result["valid"] is False, f"Управляющий символ не обнаружен: {repr(char)}"


class TestAdvancedRoomNameValidation:
    def test_unicode_room_names(self):
        """Тест юникодных названий комнат"""
        # Паттерн ROOM_NAME_PATTERN = r'^[a-zA-Zа-яА-Я0-9_\-\s]+$'
        # Поддерживает только латиницу, кириллицу, цифры, пробелы, дефисы, подчеркивания
        unicode_names = [
            "Комната-1",  # кириллица разрешена
        ]
        
        for name in unicode_names:
            result = WebSocketValidator.validate_room_name(name)
            assert result["valid"] is True, f"Юникодное имя отклонено: {name}"
        
        # Нелатинские/некириллические символы не разрешены
        unsupported_names = [
            "チャットルーム",  # японский не разрешен
            "غرفة_الدردشة",  # арабский не разрешен
            "חדר_צ'אט",  # иврит не разрешен
            "ห้องแชท",  # тайский не разрешен
            "Room_🌍",  # эмодзи не разрешены
        ]
        
        for name in unsupported_names:
            result = WebSocketValidator.validate_room_name(name)
            assert result["valid"] is False, f"Неподдерживаемое имя принято: {name}"

    def test_room_name_edge_lengths(self):
        """Тест граничных длин названий комнат"""
        # Минимальная длина
        result = WebSocketValidator.validate_room_name("ab")
        assert result["valid"] is True
        
        # Максимальная длина
        max_name = "a" * WebSocketValidator.MAX_ROOM_NAME_LENGTH
        result = WebSocketValidator.validate_room_name(max_name)
        assert result["valid"] is True
        
        # Превышение максимальной длины
        too_long = "a" * (WebSocketValidator.MAX_ROOM_NAME_LENGTH + 1)
        result = WebSocketValidator.validate_room_name(too_long)
        assert result["valid"] is False

    def test_forbidden_room_names_case_insensitive(self):
        """Тест зарезервированных имён (регистронезависимо)"""
        forbidden_variations = [
            "admin", "Admin", "ADMIN", "AdMiN",
            "root", "Root", "ROOT", "RoOt",
            "system", "System", "SYSTEM", "SyStEm",
        ]
        
        for name in forbidden_variations:
            result = WebSocketValidator.validate_room_name(name)
            assert result["valid"] is False, f"Зарезервированное имя принято: {name}"

    def test_room_name_special_characters(self):
        """Тест специальных символов в названиях комнат"""
        # Разрешённые символы (только буквы, цифры, пробелы, дефисы, подчеркивания)
        allowed_chars = [
            "Room-1", "Room_1", "Room 1",
            "Room-1_Test", "Room_1-Test", "Room 1 Test",
        ]
        
        for name in allowed_chars:
            result = WebSocketValidator.validate_room_name(name)
            assert result["valid"] is True, f"Разрешённое имя отклонено: {name}"
        
        # Точки не разрешены в названиях комнат
        dot_name = "Room.1"
        result = WebSocketValidator.validate_room_name(dot_name)
        assert result["valid"] is False, f"Точка в названии комнаты должна быть отклонена: {dot_name}"
        
        # Запрещённые символы
        forbidden_chars = [
            "Room!1", "Room@1", "Room#1", "Room$1",
            "Room%1", "Room^1", "Room&1", "Room*1",
            "Room(1", "Room)1", "Room+1", "Room=1",
            "Room[1", "Room]1", "Room{1", "Room}1",
            "Room|1", "Room\\1", "Room:1", "Room;1",
            "Room\"1", "Room'1", "Room<1", "Room>1",
            "Room,1", "Room?1", "Room/1", "Room`1",
            "Room~1",
        ]
        
        for name in forbidden_chars:
            result = WebSocketValidator.validate_room_name(name)
            assert result["valid"] is False, f"Запрещённое имя принято: {name}"


class TestAdvancedUserIdValidation:
    def test_large_user_ids(self):
        """Тест больших user_id"""
        large_ids = [2**31 - 1, 2**32 - 1, 999999999]
        
        for user_id in large_ids:
            result = WebSocketValidator.validate_user_id(user_id)
            assert result["valid"] is True, f"Большой ID отклонён: {user_id}"

    def test_user_id_string_conversion(self):
        """Тест конвертации строковых ID"""
        # Только десятичные числа поддерживаются
        string_ids = ["123"]
        
        for user_id in string_ids:
            result = WebSocketValidator.validate_user_id(user_id)
            assert result["valid"] is True, f"Строковый ID отклонён: {user_id}"
            assert result["user_id"] == 123, f"Неправильная конвертация: {user_id}"
        
        # Шестнадцатеричные, восьмеричные и двоичные числа не поддерживаются
        unsupported_ids = ["0x7B", "0o173", "0b1111011"]
        for user_id in unsupported_ids:
            result = WebSocketValidator.validate_user_id(user_id)
            assert result["valid"] is False, f"Неподдерживаемый формат ID принят: {user_id}"

    def test_user_id_edge_cases(self):
        """Тест граничных случаев user_id"""
        edge_cases = [
            (0, False),  # ноль
            (-1, False),  # отрицательный
            (1, True),   # минимальный положительный
            ("0", False),  # строка ноль
            ("-1", False),  # строка отрицательный
            ("1", True),   # строка положительный
            ("", False),   # пустая строка
            ("abc", False),  # нечисловая строка
            ("12.34", False),  # дробное число
            ("12,34", False),  # дробное с запятой
        ]
        
        for user_id, expected_valid in edge_cases:
            result = WebSocketValidator.validate_user_id(user_id)
            assert result["valid"] is expected_valid, f"ID {user_id}: ожидалось {expected_valid}, получено {result['valid']}"


