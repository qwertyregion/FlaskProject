"""
Middleware для дополнительной безопасности
"""
from flask import request, current_app, g
import time
import hashlib


class SecurityMiddleware:
    """Middleware для дополнительной безопасности"""
    
    def __init__(self, app=None):
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Обработка запросов до их выполнения"""
        # Устанавливаем время начала обработки запроса
        g.start_time = time.time()
        
        # Проверяем User-Agent
        user_agent = request.headers.get('User-Agent', '')
        if self.is_suspicious_user_agent(user_agent):
            current_app.logger.warning(f"Suspicious User-Agent from {request.remote_addr}: {user_agent}")
        
        # Проверяем на подозрительные паттерны в URL
        if self.is_suspicious_url(request.path):
            current_app.logger.warning(f"Suspicious URL from {request.remote_addr}: {request.path}")
    
    def after_request(self, response):
        """Обработка ответов после их выполнения"""
        # Добавляем заголовки безопасности
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Логируем время обработки запроса
        if hasattr(g, 'start_time'):
            processing_time = time.time() - g.start_time
            if processing_time > 5.0:  # Логируем медленные запросы
                current_app.logger.warning(f"Slow request: {request.method} {request.path} took {processing_time:.2f}s")
        
        return response
    
    def is_suspicious_user_agent(self, user_agent):
        """Проверяет подозрительные User-Agent"""
        suspicious_patterns = [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'zap', 'burp',
            'scanner', 'bot', 'crawler', 'spider', 'scraper'
        ]
        
        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)
    
    def is_suspicious_url(self, url):
        """Проверяет подозрительные URL"""
        suspicious_patterns = [
            '../', '..\\', 'admin', 'wp-admin', 'phpmyadmin',
            'config', 'backup', 'test', 'debug', 'api/',
            'script', 'javascript:', 'data:'
        ]
        
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in suspicious_patterns)


class RateLimitMiddleware:
    """Middleware для дополнительного rate limiting"""
    
    def __init__(self, app=None):
        self.requests = {}
        self.cleanup_interval = 300  # 5 минут
        self.last_cleanup = time.time()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        app.before_request(self.before_request)
    
    def before_request(self):
        """Проверяет rate limit перед обработкой запроса"""
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Очищаем старые записи
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.cleanup_old_requests(current_time)
            self.last_cleanup = current_time
        
        # Проверяем лимит для IP
        if client_ip in self.requests:
            # Удаляем запросы старше 1 минуты
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if current_time - req_time < 60
            ]
            
            # Проверяем лимит (100 запросов в минуту)
            if len(self.requests[client_ip]) > 100:
                current_app.logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return "Rate limit exceeded", 429
        else:
            self.requests[client_ip] = []
        
        # Добавляем текущий запрос
        self.requests[client_ip].append(current_time)
    
    def cleanup_old_requests(self, current_time):
        """Очищает старые записи о запросах"""
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                req_time for req_time in self.requests[ip] 
                if current_time - req_time < 60
            ]
            if not self.requests[ip]:
                del self.requests[ip]
