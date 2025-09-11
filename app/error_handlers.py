"""
Безопасные обработчики ошибок
"""
from flask import render_template, request, current_app
import logging


def register_error_handlers(app):
    """Регистрирует безопасные обработчики ошибок"""
    
    @app.errorhandler(400)
    def bad_request(error):
        current_app.logger.warning(f"Bad request from {request.remote_addr}: {request.url}")
        return render_template('error.html', 
                             error="Неверный запрос",
                             error_code="400"), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        current_app.logger.warning(f"Unauthorized access from {request.remote_addr}: {request.url}")
        return render_template('error.html', 
                             error="Требуется авторизация",
                             error_code="401"), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        current_app.logger.warning(f"Forbidden access from {request.remote_addr}: {request.url}")
        return render_template('error.html', 
                             error="Доступ запрещен",
                             error_code="403"), 403
    
    @app.errorhandler(404)
    def not_found(error):
        current_app.logger.info(f"Page not found from {request.remote_addr}: {request.url}")
        return render_template('error.html', 
                             error="Страница не найдена",
                             error_code="404"), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        current_app.logger.warning(f"Method not allowed from {request.remote_addr}: {request.method} {request.url}")
        return render_template('error.html', 
                             error="Метод не разрешен",
                             error_code="405"), 405
    
    @app.errorhandler(413)
    def payload_too_large(error):
        current_app.logger.warning(f"Payload too large from {request.remote_addr}")
        return render_template('error.html', 
                             error="Файл слишком большой",
                             error_code="413"), 413
    
    @app.errorhandler(429)
    def too_many_requests(error):
        current_app.logger.warning(f"Rate limit exceeded from {request.remote_addr}")
        return render_template('error.html', 
                             error="Слишком много запросов. Попробуйте позже.",
                             error_code="429"), 429
    
    @app.errorhandler(500)
    def internal_error(error):
        current_app.logger.error(f"Internal server error: {str(error)}")
        return render_template('error.html', 
                             error="Внутренняя ошибка сервера",
                             error_code="500"), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        current_app.logger.error(f"Unhandled exception: {str(error)}")
        return render_template('error.html', 
                             error="Произошла неожиданная ошибка",
                             error_code="500"), 500
