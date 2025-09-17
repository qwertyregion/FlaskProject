/**
 * Модульная версия чата - основной файл
 * Использует модульную архитектуру для лучшей организации кода
 */

console.log('🔵 [CLIENT DEBUG] chat-modular.js загружен');

// Инициализация глобальных переменных
window.isPageUnloading = false;

// ВРЕМЕННО: Включаем логи для отладки DM
window.CHAT_DEBUG = true;
console.log('🔵 [CLIENT DEBUG] CHAT_DEBUG включен');

// Отключаем лишние консольные логи на странице чата, оставляя предупреждения и ошибки
if (!window.CHAT_DEBUG) {
    try {
        console.log = function(){};
        console.info = function(){};
        console.debug = function(){};
    } catch (e) {}
}

// Проверяем, инициализирован ли currentUser модулем user-init.js
if (!window.currentUser) {
    console.warn('🔴 [INIT DEBUG] currentUser не инициализирован модулем user-init.js!');
} else {
    console.log('✅ [INIT DEBUG] currentUser инициализирован:', window.currentUser);
}

// Инициализация Socket.IO
window.socket = io();

// Проверяем состояние Socket.IO
console.log('🔵 [SOCKET DEBUG] Socket.IO инициализирован');
console.log('🔵 [SOCKET DEBUG] Socket состояние:', window.socket.connected ? 'подключен' : 'отключен');
console.log('🔵 [SOCKET DEBUG] Socket ID:', window.socket.id);

// Обработчики состояния Socket.IO
window.socket.on('connect', () => {
    console.log('✅ [SOCKET DEBUG] Socket.IO подключен, ID:', window.socket.id);
});

window.socket.on('disconnect', () => {
    console.log('🔴 [SOCKET DEBUG] Socket.IO отключен');
});

window.socket.on('connect_error', (error) => {
    console.error('🔴 [SOCKET DEBUG] Ошибка подключения Socket.IO:', error);
});

// Инициализация модулей
let chatUI, dmHandler, socketHandlers;

// Безопасная функция для работы с classList
function safeClassList(element, method, className) {
    if (!element || !element.classList) {
        console.warn(`🔴 [SAFE DEBUG] Элемент не найден или не имеет classList:`, element);
        return false;
    }
    try {
        return element.classList[method](className);
    } catch (error) {
        console.error(`🔴 [SAFE DEBUG] Ошибка с classList.${method}:`, error);
        return false;
    }
}

// Обработчик загрузки DOM
document.addEventListener('DOMContentLoaded', function() {
    console.log('Инициализация модульного чата...');
    console.log('window.currentUser при инициализации:', window.currentUser);
    
    // Проверяем наличие необходимых элементов
    const elementsToCheck = [
        { id: 'room-create', name: 'Форма создания комнаты' },
        { id: 'new-room-name', name: 'Поле ввода названия' },
        { id: 'message-form', name: 'Форма сообщений' },
        { id: 'active-users', name: 'Список пользователей' },
        { id: 'rooms-list', name: 'Список комнат' },
        { id: 'chat-box', name: 'Область чата' }
    ];

    elementsToCheck.forEach(item => {
        const element = document.getElementById(item.id);
        console.log(`${item.name}:`, element ? '✅ Найден' : '❌ Не найден');
    });

    // Инициализируем модули
    try {
        // Сначала создаем dmHandler
        dmHandler = new DMHandler();
        console.log('🔵 [CLIENT DEBUG] dmHandler создан:', dmHandler);
        // Делаем обработчик ЛС доступным глобально для кликов из списка пользователей и других модулей
        window.dmHandler = dmHandler;
        console.log('🔵 [CLIENT DEBUG] window.dmHandler установлен:', window.dmHandler);
        
        // Затем создаем chatUI и передаем dmHandler
        chatUI = new ChatUI();
        // Делаем ChatUI глобальным, т.к. VirtualizedChat ссылается на window.chatUI
        window.chatUI = chatUI;
        chatUI.dmHandler = dmHandler;
        
        // Устанавливаем обратную ссылку
        dmHandler.chatUI = chatUI;
        
        // Создаем socketHandlers с уже инициализированными модулями
        socketHandlers = new SocketHandlers(window.socket, chatUI, dmHandler);
        
        // Инициализируем обработчики форм
        initFormHandlers();
        
        console.log('✅ Модульный чат успешно инициализирован');
    } catch (error) {
        console.error('❌ Ошибка инициализации модульного чата:', error);
        showErrorNotification('Ошибка инициализации чата. Перезагрузите страницу.');
    }
});

// Инициализация обработчиков форм
function initFormHandlers() {
    const messageForm = document.getElementById('message-form');
    if (messageForm) {
        messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (dmHandler && dmHandler.isInDMMode) {
                dmHandler.sendDM();
            } else {
                sendMessage();
            }
        });
    }

    // Обработчики Enter для полей ввода
    addEnterHandler('message-input', () => {
        if (dmHandler && dmHandler.isInDMMode) {
            dmHandler.sendDM();
        } else {
            sendMessage();
        }
    });

    addEnterHandler('new-room-name', () => {
        chatUI.submitCreateRoom();
    });
}

// Декоратор для добавления обработки Enter к любому полю ввода
function addEnterHandler(inputId, callback) {
    const input = document.getElementById(inputId);
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                callback();
            }
        });
    }
}

// Функция отправки сообщения
function sendMessage() {
    if (dmHandler && dmHandler.isInDMMode) return;

    const messageInput = document.getElementById('message-input');
    const message = messageInput?.value.trim();

    if (message) {
        // Локальное отображение сообщения сразу
        chatUI.addMessageToChat({
            sender_id: window.currentUser?.id,
            sender_username: window.currentUser?.username || 'Вы',
            content: message,
            timestamp: new Date().toISOString(),
            is_local: true
        });

        // Отправка на сервер
        window.socket.emit('send_message', {
            message: message,
            room: chatUI.currentRoom
        });
        messageInput.value = '';

        // Гарантированный скролл после отправки
        setTimeout(() => {
            chatUI.scrollToBottom();
        }, 100);
    }
}

// Функция показа уведомлений об ошибках
function showErrorNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'error-notification';
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #dc3545;
        color: white;
        padding: 15px 20px;
        border-radius: 5px;
        z-index: 10000;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        max-width: 300px;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Функция для принудительного обновления всех списков
function refreshAllLists() {
    if (!dmHandler || !dmHandler.isInDMMode) {
        window.socket.emit('get_current_users', { room: chatUI.currentRoom });
    }

    if (dmHandler) {
        dmHandler.loadDMConversations();
    }
}

// Добавляем кнопку обновления
document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.createElement('button');
    refreshBtn.textContent = '🔄';
    refreshBtn.style.cssText = `
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: #007bff;
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
        font-size: 16px;
    `;
    refreshBtn.onclick = refreshAllLists;
    refreshBtn.title = 'Обновить списки';
    document.body.appendChild(refreshBtn);
});

// Экспорт функций для глобального использования
window.sendMessage = sendMessage;
window.refreshAllLists = refreshAllLists;
window.showCreateRoomInput = () => chatUI.showCreateRoomInput();
window.submitCreateRoom = () => chatUI.submitCreateRoom();
