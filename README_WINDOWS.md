# 🚀 Flask Project - Windows Setup Guide

## ✅ Все критические уязвимости безопасности исправлены!

### 🔧 Быстрый запуск

#### **Способ 1: PowerShell (Рекомендуется)**
```powershell
# Установка зависимостей
pip install -r requirements.txt

# Запуск в режиме разработки
.\start_dev.ps1

# Или вручную:
$env:FLASK_ENV="development"
python run.py
```

#### **Способ 2: Batch файлы**
```cmd
# Двойной клик на файл или в командной строке:
start_dev.bat
```

#### **Способ 3: Ручная установка переменных**
```powershell
# В PowerShell:
$env:FLASK_ENV="development"
$env:SECRET_KEY="dev-secret-key"
python run.py
```

### 🛡️ Режимы работы

#### **Разработка (Development)**
- Debug режим включен
- Подробные логи
- Автоперезагрузка
- Менее строгие настройки безопасности

#### **Продакшен (Production)**
- Debug режим отключен
- Строгие настройки безопасности
- HTTPS обязательно
- Минимальные логи

### 🔒 Безопасность

#### **Исправленные уязвимости:**
- ✅ Валидация паролей (сложность, защита от слабых паролей)
- ✅ Rate Limiting (защита от брутфорса)
- ✅ Безопасная обработка ошибок
- ✅ WebSocket валидация
- ✅ HTTP заголовки безопасности
- ✅ CSRF защита
- ✅ Security logging

#### **Новые возможности:**
- 🔐 Строгие требования к паролям
- 🚫 Защита от XSS атак
- ⏱️ Ограничение частоты запросов
- 📝 Логирование безопасности
- 🛡️ Middleware защиты

### 📁 Структура проекта

```
FlaskProject/
├── app/                    # Основное приложение
│   ├── auth/              # Аутентификация
│   ├── chat/              # Чат функциональность
│   ├── main/              # Главные страницы
│   ├── middleware/        # Middleware безопасности
│   ├── static/            # CSS, JS файлы
│   ├── templates/         # HTML шаблоны
│   ├── validators.py      # Валидаторы
│   └── error_handlers.py  # Обработчики ошибок
├── logs/                  # Логи безопасности
├── migrations/            # Миграции БД
├── start_dev.bat         # Запуск разработки (Windows)
├── start_dev.ps1         # Запуск разработки (PowerShell)
├── start_prod.bat        # Запуск продакшена (Windows)
├── start_prod.ps1        # Запуск продакшена (PowerShell)
├── run.py                # Главный файл запуска
├── config.py             # Конфигурация
└── requirements.txt      # Зависимости
```

### 🚀 Команды для разработки

```powershell
# Активация виртуального окружения
.\flask_venv\Scripts\Activate.ps1

# Установка зависимостей
pip install -r requirements.txt

# Запуск в режиме разработки
.\start_dev.ps1

# Остановка (Ctrl+C)
```

### 🔧 Настройка для продакшена

1. **Создайте файл `.env`:**
```env
FLASK_ENV=production
SECRET_KEY=your-very-secure-secret-key-here
WEATHER_API_KEY=your-weather-api-key
DATABASE_URL=sqlite:///app.db
```

2. **Запустите:**
```powershell
.\start_prod.ps1
```

### 🐛 Устранение проблем

#### **Ошибка "export не распознано"**
- Используйте PowerShell вместо CMD
- Или используйте batch файлы

#### **Ошибка импорта модулей**
```powershell
pip install -r requirements.txt
```

#### **Ошибка порта занят**
```powershell
# Измените порт в run.py или убейте процесс
netstat -ano | findstr :5000
taskkill /PID <PID> /F
```

### 📊 Мониторинг

- **Логи безопасности:** `logs/security.log`
- **Логи приложения:** Консоль
- **Мониторинг:** Подозрительные запросы логируются автоматически

### 🎯 Следующие шаги

1. **Тестирование:** Добавьте unit тесты
2. **CI/CD:** Настройте автоматическое развертывание
3. **Мониторинг:** Настройте алерты
4. **Backup:** Настройте резервное копирование БД

---

**🎉 Поздравляем! Ваш Flask проект теперь безопасен и готов к разработке!**
