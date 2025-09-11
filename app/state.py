"""
Менеджеры состояния для WebSocket соединений и комнат
"""
from typing import Dict, Set, Optional, Any
import logging
import time
from flask import current_app
from app import extensions


class UserStateManager:
    """Менеджер состояния пользователей в комнатах"""
    
    def __init__(self):
        # In-memory хранилище для разработки
        # В продакшене должно быть Redis
        self._room_users: Dict[str, Dict[int, str]] = {}
        self._user_rooms: Dict[int, Set[str]] = {}
        # Redis keyspace
        self._room_users_key_tpl = "room:{room}:users"
        self._user_rooms_key_tpl = "user:{user_id}:rooms"
    
    def ensure_room_exists(self, room_name: str) -> None:
        """Убеждается, что комната существует"""
        if extensions.redis_client is not None:
            # В Redis комната появится при первом добавлении пользователя.
            # Здесь no-op, чтобы не плодить пустые ключи.
            return
        if room_name not in self._room_users:
            self._room_users[room_name] = {}
            current_app.logger.debug(f"Создана комната (in-memory): {room_name}")
    
    def add_user_to_room(self, user_id: int, username: str, room_name: str) -> None:
        """Добавляет пользователя в комнату"""
        if extensions.redis_client is not None:
            try:
                room_hash = self._room_users_key_tpl.format(room=room_name)
                user_set = self._user_rooms_key_tpl.format(user_id=user_id)
                extensions.redis_client.hset(room_hash, mapping={str(user_id): username})
                extensions.redis_client.sadd(user_set, room_name)
                current_app.logger.debug(f"[Redis] Пользователь {username} добавлен в комнату {room_name}")
                return
            except Exception as e:
                current_app.logger.warning(f"Redis add_user_to_room failed, fallback to memory: {e}")

        self.ensure_room_exists(room_name)
        self._room_users[room_name][user_id] = username
        if user_id not in self._user_rooms:
            self._user_rooms[user_id] = set()
        self._user_rooms[user_id].add(room_name)
        current_app.logger.debug(f"[Memory] Пользователь {username} добавлен в комнату {room_name}")
    
    def remove_user_from_room(self, user_id: int, room_name: str) -> None:
        """Удаляет пользователя из комнаты"""
        if extensions.redis_client is not None:
            try:
                room_hash = self._room_users_key_tpl.format(room=room_name)
                user_set = self._user_rooms_key_tpl.format(user_id=user_id)
                # Получим имя, чтобы залогировать
                username = extensions.redis_client.hget(room_hash, str(user_id))
                extensions.redis_client.hdel(room_hash, str(user_id))
                extensions.redis_client.srem(user_set, room_name)
                current_app.logger.debug(f"[Redis] Пользователь {username} удален из комнаты {room_name}")
                return
            except Exception as e:
                current_app.logger.warning(f"Redis remove_user_from_room failed, fallback to memory: {e}")

        if room_name in self._room_users and user_id in self._room_users[room_name]:
            username = self._room_users[room_name].pop(user_id)
            if user_id in self._user_rooms:
                self._user_rooms[user_id].discard(room_name)
            current_app.logger.debug(f"[Memory] Пользователь {username} удален из комнаты {room_name}")
    
    def get_room_users(self, room_name: str) -> Dict[int, str]:
        """Возвращает пользователей в комнате"""
        if extensions.redis_client is not None:
            try:
                room_hash = self._room_users_key_tpl.format(room=room_name)
                data = extensions.redis_client.hgetall(room_hash) or {}
                # Ключи в Redis строки, конвертируем user_id в int где возможно
                return {int(uid): uname for uid, uname in data.items() if uid.isdigit()}
            except Exception as e:
                current_app.logger.warning(f"Redis get_room_users failed, fallback to memory: {e}")
        return self._room_users.get(room_name, {}).copy()
    
    def get_user_rooms(self, user_id: int) -> Set[str]:
        """Возвращает комнаты пользователя"""
        if extensions.redis_client is not None:
            try:
                user_set = self._user_rooms_key_tpl.format(user_id=user_id)
                rooms = extensions.redis_client.smembers(user_set) or set()
                return set(rooms)
            except Exception as e:
                current_app.logger.warning(f"Redis get_user_rooms failed, fallback to memory: {e}")
        return self._user_rooms.get(user_id, set()).copy()
    
    def cleanup_empty_room(self, room_name: str) -> None:
        """Удаляет пустую комнату"""
        if extensions.redis_client is not None:
            try:
                room_hash = self._room_users_key_tpl.format(room=room_name)
                if extensions.redis_client.hlen(room_hash) == 0:
                    extensions.redis_client.delete(room_hash)
                    current_app.logger.debug(f"[Redis] Удалена пустая комната: {room_name}")
                    return
            except Exception as e:
                current_app.logger.warning(f"Redis cleanup_empty_room failed, fallback to memory: {e}")
        if room_name in self._room_users and not self._room_users[room_name]:
            del self._room_users[room_name]
            current_app.logger.debug(f"[Memory] Удалена пустая комната: {room_name}")


class ConnectionManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        # In-memory хранилище для разработки
        self._connections: Dict[int, str] = {}  # user_id -> socket_id
        self._socket_to_user: Dict[str, int] = {}  # socket_id -> user_id
        self._heartbeat_expires: Dict[int, float] = {}
        # Redis keyspace
        self._user_to_socket_key = "conn:user_to_socket"
        self._socket_to_user_key = "conn:socket_to_user"
        self._heartbeat_key_tpl = "conn:heartbeat:{user_id}"
    
    def register_connection(self, user_id: int, socket_id: str) -> None:
        """Регистрирует новое соединение"""
        # Пробуем Redis, если доступен
        if extensions.redis_client is not None:
            try:
                # Удалим старую обратную ссылку, если была
                old_socket_id = extensions.redis_client.hget(self._user_to_socket_key, str(user_id))
                if old_socket_id:
                    extensions.redis_client.hdel(self._socket_to_user_key, old_socket_id)
                extensions.redis_client.hset(self._user_to_socket_key, str(user_id), socket_id)
                extensions.redis_client.hset(self._socket_to_user_key, socket_id, str(user_id))
                # начальный heartbeat
                try:
                    ttl = int(current_app.config.get('HEARTBEAT_TTL_SECONDS', 120))
                except RuntimeError:
                    ttl = 120  # fallback если нет контекста приложения
                hb_key = self._heartbeat_key_tpl.format(user_id=user_id)
                extensions.redis_client.set(hb_key, '1', ex=ttl)
                try:
                    current_app.logger.debug(f"[Redis] Зарегистрировано соединение: user_id={user_id}, socket_id={socket_id}")
                except RuntimeError:
                    pass  # fallback если нет контекста приложения
                return
            except Exception as e:
                try:
                    current_app.logger.warning(f"Redis register_connection failed, fallback to memory: {e}")
                except RuntimeError:
                    print(f"DEBUG: Redis register_connection failed: {e}")  # fallback для тестов
                # Продолжаем выполнение для fallback в память

        # Fallback в память (если Redis недоступен или произошла ошибка)
        # Удаляем старое соединение если есть
        if user_id in self._connections:
            old_socket_id = self._connections[user_id]
            if old_socket_id in self._socket_to_user:
                del self._socket_to_user[old_socket_id]
        self._connections[user_id] = socket_id
        self._socket_to_user[socket_id] = user_id
        try:
            ttl = int(current_app.config.get('HEARTBEAT_TTL_SECONDS', 120))
        except RuntimeError:
            ttl = 120  # fallback если нет контекста приложения
        self._heartbeat_expires[user_id] = time.time() + ttl
        try:
            current_app.logger.debug(f"[Memory] Зарегистрировано соединение: user_id={user_id}, socket_id={socket_id}")
        except RuntimeError:
            pass  # fallback если нет контекста приложения
    
    def remove_connection(self, user_id: int) -> None:
        """Удаляет соединение пользователя"""
        if extensions.redis_client is not None:
            try:
                socket_id = extensions.redis_client.hget(self._user_to_socket_key, str(user_id))
                if socket_id:
                    extensions.redis_client.hdel(self._user_to_socket_key, str(user_id))
                    extensions.redis_client.hdel(self._socket_to_user_key, socket_id)
                hb_key = self._heartbeat_key_tpl.format(user_id=user_id)
                extensions.redis_client.delete(hb_key)
                current_app.logger.debug(f"[Redis] Удалено соединение: user_id={user_id}")
                return
            except Exception as e:
                current_app.logger.warning(f"Redis remove_connection failed, fallback to memory: {e}")

        if user_id in self._connections:
            socket_id = self._connections[user_id]
            del self._connections[user_id]
            if socket_id in self._socket_to_user:
                del self._socket_to_user[socket_id]
        self._heartbeat_expires.pop(user_id, None)
        current_app.logger.debug(f"[Memory] Удалено соединение: user_id={user_id}")
    
    def get_user_socket(self, user_id: int) -> Optional[str]:
        """Возвращает socket_id пользователя"""
        if extensions.redis_client is not None:
            try:
                return extensions.redis_client.hget(self._user_to_socket_key, str(user_id))
            except Exception as e:
                current_app.logger.warning(f"Redis get_user_socket failed, fallback to memory: {e}")
        return self._connections.get(user_id)
    
    def get_socket_user(self, socket_id: str) -> Optional[int]:
        """Возвращает user_id по socket_id"""
        if extensions.redis_client is not None:
            try:
                uid = extensions.redis_client.hget(self._socket_to_user_key, socket_id)
                return int(uid) if uid is not None and str(uid).isdigit() else None
            except Exception as e:
                current_app.logger.warning(f"Redis get_socket_user failed, fallback to memory: {e}")
        return self._socket_to_user.get(socket_id)
    
    def is_user_connected(self, user_id: int) -> bool:
        """Проверяет, подключен ли пользователь"""
        if extensions.redis_client is not None:
            try:
                hb_key = self._heartbeat_key_tpl.format(user_id=user_id)
                return extensions.redis_client.exists(hb_key) == 1
            except Exception as e:
                current_app.logger.warning(f"Redis is_user_connected failed, fallback to memory: {e}")
        
        # Fallback to memory logic
        # Check if user has a connection
        if user_id not in self._connections:
            return False
        
        # Check heartbeat expiration if it exists
        exp = self._heartbeat_expires.get(user_id)
        if exp is not None:
            # Считаем соединение активным, пока текущее время строго меньше exp
            if time.time() >= exp:
                # Срок действия heartbeat истёк — очищаем соединение
                self.remove_connection(user_id)
                return False
            return True
        
        # If no heartbeat exists but connection exists, consider connected
        return True

    def refresh_heartbeat(self, user_id: int, ttl_seconds: Optional[int] = None) -> None:
        """Обновляет heartbeat пользователя, продлевая TTL."""
        if ttl_seconds is None:
            try:
                ttl = int(current_app.config.get('HEARTBEAT_TTL_SECONDS', 120))
            except RuntimeError:
                ttl = 120  # fallback если нет контекста приложения
        else:
            ttl = float(ttl_seconds)  # Используем float для точности
        
        # Пробуем Redis, если доступен
        if extensions.redis_client is not None:
            try:
                hb_key = self._heartbeat_key_tpl.format(user_id=user_id)
                # Redis ожидает целочисленный TTL (секунды)
                redis_ttl = int(ttl) if ttl >= 1 else 1
                extensions.redis_client.set(hb_key, '1', ex=redis_ttl)
                return
            except Exception as e:
                try:
                    current_app.logger.warning(f"Redis refresh_heartbeat failed, fallback to memory: {e}")
                except RuntimeError:
                    pass
        
        # Fallback в память
        if user_id not in self._connections:
            self._connections[user_id] = f"fallback_socket_{user_id}"
            self._socket_to_user[f"fallback_socket_{user_id}"] = user_id
        
        # Убедимся, что устанавливаем правильное время
        expiration_time = time.time() + ttl
        self._heartbeat_expires[user_id] = expiration_time
        print(f"DEBUG: Set heartbeat for user {user_id}, expires at {expiration_time}, current time: {time.time()}")


class RoomManager:
    """Менеджер комнат чата"""
    
    def __init__(self):
        # In-memory хранилище для разработки
        self._rooms: Dict[str, Dict[str, Any]] = {}
        # Redis keyspace
        self._rooms_set_key = "rooms"
        self._room_meta_key_tpl = "room:meta:{room}"
    
    def create_room_if_absent(self, room_name: str, creator_id: int) -> None:
        """Создает комнату если её нет"""
        if extensions.redis_client is not None:
            try:
                meta_key = self._room_meta_key_tpl.format(room=room_name)
                # Добавим в множество комнат и установим базовые метаданные
                extensions.redis_client.sadd(self._rooms_set_key, room_name)
                if not extensions.redis_client.exists(meta_key):
                    extensions.redis_client.hset(meta_key, mapping={
                        'name': room_name,
                        'created_by': str(creator_id),
                        'is_active': '1'
                    })
                current_app.logger.debug(f"[Redis] Создана комната: {room_name}")
                return
            except Exception as e:
                current_app.logger.warning(f"Redis create_room_if_absent failed, fallback to memory: {e}")
        if room_name not in self._rooms:
            self._rooms[room_name] = {
                'name': room_name,
                'created_by': creator_id,
                'created_at': None,  # В реальном приложении должно быть время
                'is_active': True
            }
            current_app.logger.debug(f"[Memory] Создана комната: {room_name}")
    
    def get_room_info(self, room_name: str) -> Optional[Dict[str, Any]]:
        """Возвращает информацию о комнате"""
        if extensions.redis_client is not None:
            try:
                meta_key = self._room_meta_key_tpl.format(room=room_name)
                data = extensions.redis_client.hgetall(meta_key) or None
                if not data:
                    return None
                # Приводим типы частично
                return {
                    'name': data.get('name', room_name),
                    'created_by': int(data['created_by']) if 'created_by' in data and str(data['created_by']).isdigit() else None,
                    'created_at': None,
                    'is_active': data.get('is_active', '1') == '1'
                }
            except Exception as e:
                current_app.logger.warning(f"Redis get_room_info failed, fallback to memory: {e}")
        return self._rooms.get(room_name)
    
    def get_all_rooms(self) -> Set[str]:
        """Возвращает список всех комнат"""
        if extensions.redis_client is not None:
            try:
                rooms = extensions.redis_client.smembers(self._rooms_set_key) or set()
                return set(rooms)
            except Exception as e:
                current_app.logger.warning(f"Redis get_all_rooms failed, fallback to memory: {e}")
        return set(self._rooms.keys())
    
    def remove_room_meta(self, room_name: str) -> None:
        """Удаляет метаданные комнаты"""
        if extensions.redis_client is not None:
            try:
                meta_key = self._room_meta_key_tpl.format(room=room_name)
                extensions.redis_client.srem(self._rooms_set_key, room_name)
                extensions.redis_client.delete(meta_key)
                current_app.logger.debug(f"[Redis] Удалены метаданные комнаты: {room_name}")
                return
            except Exception as e:
                current_app.logger.warning(f"Redis remove_room_meta failed, fallback to memory: {e}")
        if room_name in self._rooms:
            del self._rooms[room_name]
            current_app.logger.debug(f"[Memory] Удалены метаданные комнаты: {room_name}")
    
    def cleanup_empty_room(self, room_name: str) -> None:
        """Очищает пустую комнату"""
        # В Redis логика может быть сложнее; здесь переиспользуем remove_room_meta
        self.remove_room_meta(room_name)


# Глобальные экземпляры менеджеров
user_state = UserStateManager()
conn_mgr = ConnectionManager()
room_mgr = RoomManager()