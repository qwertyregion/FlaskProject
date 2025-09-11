"""
HTTP контроллер для работы с пользователями
"""
from typing import Dict, Any
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.services import UserService


class UserController:
    """HTTP контроллер для пользователей"""
    
    def __init__(self):
        self.bp = Blueprint('users', __name__, url_prefix='/api/users')
        self._register_routes()
    
    def _register_routes(self):
        """Регистрирует маршруты"""
        
        @self.bp.route('/online', methods=['GET'])
        @login_required
        def get_online_users():
            """Получает список онлайн пользователей"""
            try:
                room = request.args.get('room')
                users = UserService.get_online_users(room)
                
                return jsonify({'users': users})
                
            except Exception as e:
                current_app.logger.error(f"Error getting online users: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/<int:user_id>', methods=['GET'])
        @login_required
        def get_user(user_id: int):
            """Получает информацию о пользователе"""
            try:
                user = UserService.get_user_by_id(user_id)
                if not user:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                return jsonify({
                    'id': user.id,
                    'username': user.username,
                    'online': user.online,
                    'last_seen': user.last_seen.isoformat() if user.last_seen else None
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting user: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/username/<username>', methods=['GET'])
        @login_required
        def get_user_by_username(username: str):
            """Получает информацию о пользователе по имени"""
            try:
                user = UserService.get_user_by_username(username)
                if not user:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                return jsonify({
                    'id': user.id,
                    'username': user.username,
                    'online': user.online,
                    'last_seen': user.last_seen.isoformat() if user.last_seen else None
                })
                
            except Exception as e:
                current_app.logger.error(f"Error getting user by username: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/<int:user_id>/stats', methods=['GET'])
        @login_required
        def get_user_stats(user_id: int):
            """Получает статистику пользователя"""
            try:
                stats = UserService.get_user_stats(user_id)
                if not stats:
                    return jsonify({'error': 'Пользователь не найден'}), 404
                
                return jsonify(stats)
                
            except Exception as e:
                current_app.logger.error(f"Error getting user stats: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
        
        @self.bp.route('/conversations', methods=['GET'])
        @login_required
        def get_dm_conversations():
            """Получает список диалогов пользователя"""
            try:
                conversations = UserService.get_dm_conversations(current_user.id)
                return jsonify({'conversations': conversations})
                
            except Exception as e:
                current_app.logger.error(f"Error getting DM conversations: {e}")
                return jsonify({'error': 'Внутренняя ошибка сервера'}), 500
