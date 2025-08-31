// ------------------------- ИНИЦИАЛИЗАЦИЯ И ПЕРЕМЕННЫЕ ------------------------------


const socket = io();
let currentRoom = 'general_chat';
let currentDMRecipient = null;
let isInDMMode = false; // Флаг для отслеживания режима (общий чат / ЛС)
let isPageUnloading = false;
let reconnectTimer = null;
let messageHistoryLoaded = false;  // Добавим в начало файла переменную для отслеживания истории
let virtualizedChat = null;
let currentMessages = []; // Хранилище всех загруженных сообщений
let currentOffset = 0;
let hasMoreMessages = true;
let unreadMessagesCount = 0;
let newMessagesIndicator = null;

// Обработчик перед закрытием страницы
window.addEventListener('beforeunload', () => {
    isPageUnloading = true;
    if (socket && socket.connected) {
        socket.disconnect();
    }
});

// --------------------------ВИРТУАЛИЗАЦИЯ СООБЩЕНИЙ -------------------------------

class VirtualizedChat {
    constructor(container) {
        this.container = container;
        this.messages = [];
        this.offset = 0;
        this.hasMore = true;
        this.isLoading = false;
        this.currentRoom = currentRoom;

        this.setupScrollHandler();
        this.setupLoadMoreButton();
    }

    setupScrollHandler() {
        this.container.addEventListener('scroll', () => {
            if (this.isNearTop(this.container) && this.hasMore && !this.isLoading) {
                this.loadMoreMessages();
            }
        });
    }

    setupLoadMoreButton() {
        this.loadMoreBtn = document.createElement('button');
        this.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';
        this.loadMoreBtn.className = 'load-more-btn';
        this.loadMoreBtn.style.display = 'none';
        this.loadMoreBtn.onclick = () => this.loadMoreMessages();

        this.container.parentNode.insertBefore(this.loadMoreBtn, this.container);
    }

    isNearTop() {
        return this.container.scrollTop < 100;
    }

    loadMoreMessages() {
        if (this.isLoading || !this.hasMore || this.currentRoom !== currentRoom) return;

        this.isLoading = true;
        this.loadMoreBtn.textContent = 'Загрузка...';
        this.loadMoreBtn.disabled = true;

        socket.emit('load_more_messages', {
            room: currentRoom,
            offset: this.offset,
            limit: 20  // Уменьшим лимит для лучшей производительности
        });
    }

    handleNewMessages(data) {
        // Проверяем, что данные для текущей комнаты
        if (data.room !== currentRoom) return;

        this.isLoading = false;
        this.loadMoreBtn.disabled = false;
        this.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';

        if (data.messages && data.messages.length > 0) {
            const oldScrollHeight = this.container.scrollHeight;
            const oldScrollTop = this.container.scrollTop;

            // Добавляем сообщения в начало
            this.messages = [...data.messages, ...this.messages];
            this.offset = data.offset;
            this.hasMore = data.has_more;

            this.renderVisibleMessages();

            // Восстанавливаем позицию скролла
            const newScrollHeight = this.container.scrollHeight;
            this.container.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
        }

        this.loadMoreBtn.style.display = this.hasMore ? 'block' : 'none';
    }

    renderVisibleMessages() {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const oldScrollHeight = chatBox.scrollHeight;
        const oldScrollTop = chatBox.scrollTop;

        // Очищаем и перерисовываем
        chatBox.innerHTML = '';
        this.messages.forEach(message => {
            this.addMessageToDOM(message);
        });

        const newScrollHeight = chatBox.scrollHeight;
        chatBox.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
    }

    addMessageToDOM(message) {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.setAttribute('data-message-id', message.id);

        const timestamp = message.timestamp ? new Date(message.timestamp).toLocaleTimeString() :
                         new Date().toLocaleTimeString();

        // Определяем, свое ли это сообщение
        const isMyMessage = window.currentUser && message.sender_id == window.currentUser.id;

        if (isMyMessage) {
            messageElement.classList.add('my-message');
            messageElement.innerHTML = `
                <strong>Вы</strong>
                <small>[${timestamp}]</small>:
                <div class="message-content">${message.content}</div>
            `;
        } else {
            messageElement.innerHTML = `
                <strong>${message.sender_username}</strong>
                <small>[${timestamp}]</small>:
                <div class="message-content">${message.content}</div>
            `;
        }

        chatBox.appendChild(messageElement);
    }

    addNewMessage(message) {
        // Добавляем новое сообщение в конец
        this.messages.push(message);
        this.addMessageToDOM(message);

        // Автоматически скроллим к новому сообщению, если пользователь near the bottom
        const chatBox = document.getElementById('chat-box');
        const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 150;

        if (isNearBottom) {
            setTimeout(() => {
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 50);
        }
    }

    resetForNewRoom(roomName) {
        this.messages = [];
        this.offset = 0;
        this.hasMore = true;
        this.isLoading = false;
        this.currentRoom = roomName;
        this.loadMoreBtn.style.display = 'none';
    }
}

// Обновим обработчик скролла для скрытия индикатора
function setupChatScrollHandler() {
    const chatBox = document.getElementById('chat-box');
    if (chatBox) {
        chatBox.addEventListener('scroll', () => {
            const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 50;

            if (isNearBottom && unreadMessagesCount > 0) {
                hideNewMessagesIndicator();
            }
        });
    }
}

// Обновим autoScrollToNewMessage
function autoScrollToNewMessage() {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 150;

    if (isNearBottom) {
        setTimeout(() => {
            chatBox.scrollTop = chatBox.scrollHeight;
        }, 50);
        hideNewMessagesIndicator();
    } else {
        // Показываем индикатор новых сообщений
        unreadMessagesCount++;
        showNewMessagesIndicator(unreadMessagesCount);
    }
}

// Функция для создания индикатора новых сообщений
function createNewMessagesIndicator() {
    if (!newMessagesIndicator) {
        newMessagesIndicator = document.createElement('div');
        newMessagesIndicator.id = 'new-messages-indicator';
        newMessagesIndicator.innerHTML = 'Новые сообщения ↓';
        newMessagesIndicator.style.cssText = `
            position: fixed;
            bottom: 70px;
            right: 20px;
            background: #007bff;
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            cursor: pointer;
            z-index: 1000;
            display: none;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        `;

        newMessagesIndicator.addEventListener('click', () => {
            const chatBox = document.getElementById('chat-box');
            if (chatBox) {
                chatBox.scrollTop = chatBox.scrollHeight;
                hideNewMessagesIndicator();
            }
        });

        document.body.appendChild(newMessagesIndicator);
    }
    return newMessagesIndicator;
}

function showNewMessagesIndicator(count) {
    const indicator = createNewMessagesIndicator();
    indicator.innerHTML = `${count} новых сообщения ↓`;
    indicator.style.display = 'block';
    unreadMessagesCount = count;
}

function hideNewMessagesIndicator() {
    if (newMessagesIndicator) {
        newMessagesIndicator.style.display = 'none';
        unreadMessagesCount = 0;
    }
}

function isNearTop(element, threshold = 100) {
    return element.scrollTop < threshold;
}

function isNearBottom(element, threshold = 100) {
    return element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
}

// -------------------------- ОБРАБОТЧИКИ СОБЫТИЙ SOCKET.IO -----------------------------------

socket.on('connect', () => {
    if (isPageUnloading) {
        return; // Не инициализируем чат, если страница закрывается
    }

    // Явно запрашиваем все необходимые данные
    socket.emit('get_rooms'); // Запрашиваем список комнат у сервера
    initChat();  // Присоединение к комнате по умолчанию
    initTabs();

    // АВТОМАТИЧЕСКИ ЗАГРУЖАЕМ ДИАЛОГИ ПРИ ПОДКЛЮЧЕНИИ
    loadDMConversations();

    // Явно запрашиваем список пользователей после небольшой задержки
    setTimeout(() => {
        if (!isInDMMode) {
            socket.emit('get_current_users', { room: currentRoom });
        }
    }, 500);
});

socket.on('disconnect', () => {
    if (!isPageUnloading) {
        // Переподключение через 1 секунду
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(() => {
            if (!socket.connected) {
                socket.connect();
            }
        }, 1000);
    }
});

socket.on('room_list', (data) => {
    updateRoomList(data.rooms);
});

// Получаем список всех пользователей в комнате
socket.on('current_users', (data) => {
    // проверяем, что данные пришли для текущей комнаты (пользователь мог успеть переключиться, пока шёл запрос)
    if (data.room !== currentRoom || isInDMMode) {
        console.log('Пропускаем - не текущая комната или режим ЛС');
        return;
    }

    try {
        const usersList = document.getElementById('active-users');
        if (!usersList) {
            console.error('Элемент active-users не найден');
            return;
        }

        usersList.innerHTML = '';

        // Проверяем и нормализуем данные
        const users = data.users || {};
        const currentUserId = String(window.currentUser?.id || '');

        Object.entries(users).forEach(([userId, username]) => {
            const userElement = document.createElement('li');
            userElement.id = `user-${userId}-${data.room}`;

            // Делаем элемент кликабельным
            userElement.style.cursor = 'pointer';
            userElement.style.color = '#007bff';
            userElement.style.textDecoration = 'underline';
            userElement.style.padding = '2px 4px';
            userElement.style.margin = '2px 0';

            userElement.textContent = username || 'Неизвестный';

            // Добавляем обработчик клика
            userElement.addEventListener('click', (e) => {
                console.log('Клик по пользователю:', username, 'ID:', userId);
                e.stopPropagation();
                startDMWithUser(userId, username);
            });

            if (String(userId) === currentUserId) {
                userElement.style.fontWeight = 'bold';
                userElement.textContent += ' (Вы)';
                userElement.style.cursor = 'default';
                userElement.style.color = 'inherit';
                userElement.style.textDecoration = 'none';
            }

            usersList.appendChild(userElement);
        });

        updateOnlineCount();
    } catch (error) {
        console.error('Ошибка обработки current_users:', error);
    }
});

// Когда новый пользователь присоединился
socket.on('user_joined', (data) => {
    if (data.room === currentRoom && !isInDMMode) {
        addUserToList(data.user_id, data.username);
        addNotification(`${data.username} присоединился к чату`);

        // Явно запрашиваем обновленный список пользователей
        socket.emit('get_current_users', { room: currentRoom });
    }
});

// Когда пользователь вышел
socket.on('user_left', (data) => {
    // Важно: пользователь мог выйти из другой комнаты.
    // Удаляем его из списка, если он там есть, независимо от комнаты события.
    const userElement = document.getElementById(`user-${data.user_id}-${currentRoom}`);
    if (userElement && !isInDMMode) {
        userElement.remove();
        updateOnlineCount();

        // Явно запрашиваем обновленный список пользователей
        socket.emit('get_current_users', { room: currentRoom });

        // Показываем уведомление только если событие из текущей комнаты
        if (data.room === currentRoom) {
            addNotification(`${data.username} покинул чат`);
        }
    }
});

socket.on('room_created', (data) => {
    if (data && data.success) {

        // Показываем уведомление об успешном создании
        addNotification(data.message || `Комната "${data.room_name}" создана!`);

        // Автоматически переходим в новую комнату, если установлен флаг
        if (data.auto_join && data.room_name && data.room_name !== currentRoom) {
            setTimeout(() => {
                console.log('Автоматический переход в созданную комнату:', data.room_name);
                switchToRoom(data.room_name);
            }, 500);
        }
        // Обновляем список комнат
        socket.emit('get_rooms');
    } else {
        // Исправляем ошибку: проверяем существование data.message
        const errorMessage = (data && data.message) ? data.message : 'Ошибка создания комнаты';
        const roomCreateElement = document.getElementById('room-create');
        if (roomCreateElement && roomCreateElement.classList.contains('active')) {
            showRoomError(errorMessage);
            // Показываем форму снова при ошибке
            roomCreateElement.classList.add('active');
        }
    }
});

// ------------------------ОБРАБОТЧИКИ СООБЩЕНИЙ -------------------------

// Получение сообщений
socket.on('new_message', (data) => {
    // Проверяем, что сообщение из текущей комнаты и не ЛС
    if (data.room === currentRoom && !data.is_dm && !isInDMMode) {
        if (virtualizedChat) {
            virtualizedChat.addNewMessage(data);
        } else {
            addMessageToChat(data);
        }

        // Автоскролл или показ индикатора
        autoScrollToNewMessage();
    }
});

// Обработчик получения истории сообщений
socket.on('message_history', (data) => {
    // Проверяем, что история для текущей комнаты
    if (data.room === currentRoom && !isInDMMode) {
        const chatBox = document.getElementById('chat-box');
        if (virtualizedChat) {
            virtualizedChat.messages = data.messages;
            virtualizedChat.offset = data.messages.length;
            virtualizedChat.hasMore = data.has_more;
            virtualizedChat.renderVisibleMessages();
        }

        messageHistoryLoaded = true;

        // Прокручиваем вниз к последнему сообщению
        chatBox.scrollTop = chatBox.scrollHeight;
    }
});

socket.on('message_history_error', (data) => {
    console.error('Ошибка загрузки истории:', data.error);
    addNotification('Не удалось загрузить историю сообщений');
});

// Обновляем обработчик события
socket.on('more_messages_loaded', (data) => {
    console.log('Получены дополнительные сообщения:', data.messages?.length, 'для комнаты:', data.room);

    if (virtualizedChat && data.room === currentRoom && !isInDMMode) {
        virtualizedChat.handleNewMessages(data);
    }
});

// Добавляем обработчик ошибок
socket.on('load_more_error', (data) => {
    console.error('Ошибка загрузки сообщений:', data.error);
    if (virtualizedChat) {
        virtualizedChat.isLoading = false;
        virtualizedChat.loadMoreBtn.disabled = false;
        virtualizedChat.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';
    }
});

// Функция для автоматической прокрутки к новому сообщению
function autoScrollToNewMessage() {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    // Проверяем, находится ли пользователь near the bottom
    const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 150;

    // Если пользователь near the bottom или просматривает самые свежие сообщения, скроллим
    if (isNearBottom) {
        // Небольшая задержка для гарантии, что сообщение уже добавлено в DOM
        setTimeout(() => {
            chatBox.scrollTop = chatBox.scrollHeight;
        }, 50);
    }
}

// ---------------------------- Обработчики для личных сообщений ----------------------------

// Обработчик для обновления списка диалогов
socket.on('dm_conversations', (data) => {
    // Проверяем, есть ли непрочитанные сообщения
    const hasUnread = data.conversations.some(conv => conv.unread_count > 0);

    renderDMConversations(data.conversations);
});

// Обработчик для принудительного обновления диалогов
socket.on('update_dm_conversations', () => {
    console.log('Принудительное обновление диалогов');
    loadDMConversations();
});

// Обработчик для обновления индикатора непрочитанных
socket.on('update_unread_indicator', (data) => {
    console.log('Обновление индикатора для отправителя:', data.sender_id);
    updateUnreadIndicator(data.sender_id, data.username);
});

// Обработчик подтверждения пометки как прочитанного
socket.on('messages_marked_read', (data) => {
    if (data.success) {
        console.log('Сообщения помечены как прочитанные для отправителя:', data.sender_id);
        // Обновляем список диалогов
        loadDMConversations();
    }
});

socket.on('new_dm', (data) => {
    // Проверяем, что это сообщение для текущего диалога
    const isForCurrentDM = currentDMRecipient &&
        (currentDMRecipient == data.sender_id || currentDMRecipient == data.recipient_id);

    if (isForCurrentDM) {
        addDMMessage(data);

        // Если это текущий диалог, помечаем как прочитанное
        socket.emit('mark_messages_as_read', { sender_id: data.sender_id });
    } else {
        // Показать уведомление о новом сообщении
        showDMNotification(data);
        updateUnreadCount(data.sender_id);

        // АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ СПИСОК ДИАЛОГОВ ПРИ НОВОМ СООБЩЕНИИ
        loadDMConversations();
    }
});

// получение истории личных сообщений
socket.on('dm_history', (data) => {
    clearChatUI();
    currentDMRecipient = data.recipient_id;
    isInDMMode = true;
    document.getElementById('current-room').textContent = `Личные сообщения: ${data.recipient_name}`;

    // Переключаемся на вкладку ЛС
    switchToDMTab();

    data.messages.forEach(message => {
        console.log('Добавление сообщения из истории:', message);
        addDMMessage(message);
    });
});

// Индикатор user_online онлайн статуса
socket.on('user_online', (data) => {
    const indicator = document.querySelector(`.online-indicator[data-user-id="${data.user_id}"]`);
    if (indicator) {
        indicator.style.display = 'block';
    }
});

// Индикатор user_offline онлайн статуса
socket.on('user_offline', (data) => {
    const indicator = document.querySelector(`.online-indicator[data-user-id="${data.user_id}"]`);
    if (indicator) {
        indicator.style.display = 'none';
    }
});

// ---------------------------- ОБРАБОТЧИКИ ПОЛЬЗОВАТЕЛЬСКОГО ВВОДА ------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    console.log('Проверка элементов...');

    const elementsToCheck = [
        { id: 'room-create', name: 'Форма создания комнаты' },
        { id: 'new-room-name', name: 'Поле ввода названия' },
        { id: 'dm-modal', name: 'Модальное окно ЛС' }
    ];

    elementsToCheck.forEach(item => {
        const element = document.getElementById(item.id);
        console.log(`${item.name}:`, element ? '✅ Найден' : '❌ Не найден');
    });

    const messageForm = document.getElementById('message-form');
    initScrollHandler();

    if (messageForm) {
        messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            if (isInDMMode) {
                sendDM();
            } else {
                sendMessage();
            }
        });
    }

    addEnterHandler('message-input', () => {
        if (isInDMMode) {
            sendDM();
        } else {
            sendMessage();
        }
    });

    addEnterHandler('new-room-name', submitCreateRoom);

    // Инициализация табов после загрузки DOM
    initTabs();

    // Инициализируем обработчик скролла чата
    setupChatScrollHandler();

    // Создаем индикатор новых сообщений
    createNewMessagesIndicator();
});

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

// ----------------------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -----------------------------------

// Функция загрузки истории сообщений
function loadMessageHistory(roomName) {
    socket.emit('get_message_history', {
        room: roomName,
        limit: 20
    });
}

// Добавим обработчик для подгрузки истории при прокрутке вверх
function initScrollHandler() {
    const chatBox = document.getElementById('chat-box');
    if (chatBox) {
        chatBox.addEventListener('scroll', () => {
            // Если прокрутили до верха, можно добавить загрузку более старых сообщений
            if (chatBox.scrollTop === 0 && messageHistoryLoaded) {
                console.log('Пользователь прокрутил к началу - можно добавить загрузку более старых сообщений');
                // Здесь можно реализовать пагинацию
            }
        });
    }
}

// Функция инициализации, вызывается при загрузке или смене комнаты
function initChat() {
    clearChatUI();

    if (!isInDMMode) {
        const chatBox = document.getElementById('chat-box');

        // Инициализируем или обновляем виртуализатор
        if (!virtualizedChat) {
            virtualizedChat = new VirtualizedChat(chatBox);
        } else {
            virtualizedChat.resetForNewRoom(currentRoom);
        }

        socket.emit('join_room', { room: currentRoom });
        socket.emit('get_current_users', { room: currentRoom });
        socket.emit('get_rooms');

        // Загружаем историю сообщений
        loadMessageHistory(currentRoom);
    }
}

function switchToRoom(roomName) {
    isInDMMode = false;
    currentDMRecipient = null;
    messageHistoryLoaded = false;

    currentRoom = roomName;
    document.getElementById('current-room').textContent = currentRoom;

    // Обновляем выделение активной комнаты
    document.querySelectorAll('.room-item.active').forEach(item => {
        item.classList.remove('active');
    });

    document.querySelectorAll('.room-item').forEach(item => {
        if (item.textContent.includes(roomName)) {
            item.classList.add('active');
            item.classList.add('new-room');
            setTimeout(() => {
                item.classList.remove('new-room');
            }, 2000);
        }
    });

    switchToRoomsTab();
    initChat();

    setTimeout(() => {
        socket.emit('get_rooms');
        socket.emit('get_current_users', { room: currentRoom });
    }, 100);
}

function switchToDMTab() {
    const dmTab = document.querySelector('.tab-btn[data-tab="dms"]');
    const roomsTab = document.querySelector('.tab-btn[data-tab="rooms"]');
    const dmContent = document.getElementById('dms-tab');
    const roomsContent = document.getElementById('rooms-tab');

    if (dmTab && roomsTab && dmContent && roomsContent) {
        roomsTab.classList.remove('active');
        dmTab.classList.add('active');
        roomsContent.classList.remove('active');
        dmContent.classList.add('active');
    }
}

function switchToRoomsTab() {
    const dmTab = document.querySelector('.tab-btn[data-tab="dms"]');
    const roomsTab = document.querySelector('.tab-btn[data-tab="rooms"]');
    const dmContent = document.getElementById('dms-tab');
    const roomsContent = document.getElementById('rooms-tab');

    if (dmTab && roomsTab && dmContent && roomsContent) {
        dmTab.classList.remove('active');
        roomsTab.classList.add('active');
        dmContent.classList.remove('active');
        roomsContent.classList.add('active');
    }

    // Выходим из режима ЛС при переключении на вкладку комнат
    if (isInDMMode) {
        isInDMMode = false;
        currentDMRecipient = null;
        initChat(); // Переинициализируем чат комнаты
    }
}

function clearChatUI() {
    // Очищаем только чат
    const chatBox = document.getElementById('chat-box');
    if (chatBox) chatBox.innerHTML = '';
    updateOnlineCount(); // Сбросит счетчик на 0
}

function sendMessage() {
    if (isInDMMode) return;

    const messageInput = document.getElementById('message-input');
    const message = messageInput?.value.trim();

    if (message) {
        // Локальное отображение сообщения сразу
        addMessageToChat({
            sender_id: window.currentUser?.id,
            sender_username: window.currentUser?.username || 'Вы',
            content: message,
            timestamp: new Date().toISOString(),
            is_local: true
        });

        // Отправка на сервер
        socket.emit('send_message', {
            message: message,
            room: currentRoom
        });
        messageInput.value = '';
        // Фокус остаётся на поле ввода для быстрого набора следующего сообщения
        messageInput.focus();
    }
}

function addMessageToChat(data) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    // Проверяем дубликаты
    const existingMessage = chatBox.querySelector(`[data-message-id="${data.id}"]`);
    if (existingMessage && !data.is_local) return;

    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    messageElement.setAttribute('data-message-id', data.id);

    const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() :
                     new Date().toLocaleTimeString();

    // Определяем, свое ли это сообщение
    const isMyMessage = data.is_local || (window.currentUser && data.sender_id === window.currentUser.id);

    if (isMyMessage) {
        messageElement.classList.add('my-message');
        messageElement.innerHTML = `
            <strong>Вы</strong>
            <small>[${timestamp}]</small>:
            <div class="message-content">${data.content}</div>
        `;
    } else {
        messageElement.innerHTML = `
            <strong>${data.sender_username}</strong>
            <small>[${timestamp}]</small>:
            <div class="message-content">${data.content}</div>
        `;
    }

    chatBox.appendChild(messageElement);

    // Автоскролл ТОЛЬКО если пользователь near the bottom
    const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 150;
    if (isNearBottom) {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

function addUserToList(userId, username) {
    if (isInDMMode) return;

    const usersList = document.getElementById('active-users');
    if (!usersList) return;

    // Проверяем, нет ли уже этого пользователя в списке
    if (!document.getElementById(`user-${userId}-${currentRoom}`)) {
        const userElement = document.createElement('li');
        userElement.id = `user-${userId}-${currentRoom}`;

        // Делаем элемент кликабельным
        userElement.style.cursor = 'pointer';
        userElement.style.color = '#007bff';
        userElement.style.textDecoration = 'underline';
        userElement.style.padding = '2px 4px';
        userElement.style.margin = '2px 0';

        // Добавляем текст пользователя
        userElement.textContent = username || 'Неизвестный';

        // Добавляем обработчик клика
        userElement.addEventListener('click', (e) => {
            console.log('Клик по пользователю:', username, 'ID:', userId);
            e.stopPropagation();
            startDMWithUser(userId, username);
        });

        if (window.currentUser && String(userId) === String(window.currentUser.id)) {
            userElement.style.fontWeight = 'bold';
            userElement.textContent += ' (Вы)';
            userElement.style.cursor = 'default';
            userElement.style.color = 'inherit';
            userElement.style.textDecoration = 'none';
        }

        usersList.appendChild(userElement);
        updateOnlineCount();
    }
}

function addNotification(text) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) return;

    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.style.color = 'gray';
    notification.style.fontStyle = 'italic';
    notification.textContent = text;
    chatBox.appendChild(notification);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function updateOnlineCount() {
    const usersList = document.getElementById('active-users');
    const countElement = document.getElementById('online-count');
    if (usersList && countElement) {
        countElement.textContent = usersList.children.length;
    }
}

// Функция для принудительного обновления всех списков
function refreshAllLists() {
    socket.emit('get_rooms');

    if (!isInDMMode) {
        socket.emit('get_current_users', { room: currentRoom });
    }

    loadDMConversations();
}

// Можно добавить кнопку обновления в интерфейс
document.addEventListener('DOMContentLoaded', function() {
    // Добавляем кнопку обновления (опционально)
    const refreshBtn = document.createElement('button');
    refreshBtn.textContent = '🔄';
    refreshBtn.style.position = 'absolute';
    refreshBtn.style.top = '10px';
    refreshBtn.style.right = '10px';
    refreshBtn.style.zIndex = '1000';
    refreshBtn.onclick = refreshAllLists;
    document.body.appendChild(refreshBtn);
});

// ----------------------------------- Функции для работы с DM -------------------------------

// Пользователь ищет или выбирает из списка контактов
function selectUserForDM(userId, username) {
    socket.emit('start_dm', { recipient_id: userId });  // Загружаем историе переписки
}

function loadDMConversations() {
    socket.emit('get_dm_conversations');
}

function renderDMConversations(conversations) {
    const container = document.getElementById('dm-conversations');
    if (!container) return;

    container.innerHTML = '';

    if (conversations.length === 0) {
        container.innerHTML = '<li class="no-conversations">Нет диалогов</li>';
        return;
    }

    conversations.forEach(conv => {
        const li = document.createElement('li');
        li.className = 'dm-conversation';
        li.setAttribute('data-user-id', conv.user_id);

        // Добавляем класс для непрочитанных сообщений
        if (conv.unread_count > 0) {
            li.classList.add('has-unread');
            console.log('Добавляем класс has-unread для', conv.username);

            // Добавляем data-атрибут для количества непрочитанных
            li.setAttribute('data-unread', conv.unread_count);
        }

        // Форматируем время последнего сообщения
        let lastMessageTime = 'Нет сообщений';
        if (conv.last_message_time) {
            try {
                const messageDate = new Date(conv.last_message_time);
                const now = new Date();
                const diffTime = Math.abs(now - messageDate);
                const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

                if (diffDays === 0) {
                    // Сегодня - показываем время
                    lastMessageTime = messageDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                } else if (diffDays === 1) {
                    // Вчера
                    lastMessageTime = 'Вчера';
                } else if (diffDays < 7) {
                    // За последнюю неделю - показываем день недели
                    lastMessageTime = messageDate.toLocaleDateString([], {weekday: 'short'});
                } else {
                    // Больше недели - показываем дату
                    lastMessageTime = messageDate.toLocaleDateString([], {day: 'numeric', month: 'short'});
                }
            } catch (e) {
                console.error('Ошибка форматирования времени:', e);
                lastMessageTime = 'Недавно';
            }
        }

        li.innerHTML = `
            <div class="dm-user-info">
                <div class="dm-user-name">
                    ${conv.unread_count > 0 ? '<span class="unread-line"></span>' : ''}
                    <strong>${conv.username}</strong>
                </div>
                <div class="unread-indicator">
                    ${conv.unread_count > 0 ?
                        `<span class="unread-badge">${conv.unread_count}</span>` : ''}
                </div>
            </div>
            <div class="dm-last-message">
                ${lastMessageTime}
            </div>
        `;

        // Добавляем обработчик клика для перехода в диалог
        li.addEventListener('click', () => {
            console.log('Переход в диалог с:', conv.username, 'ID:', conv.user_id);
            startDMWithUser(conv.user_id, conv.username);
        });

        // Добавляем эффект при наведении
        li.addEventListener('mouseenter', () => {
            if (conv.unread_count > 0) {
                li.style.background = 'linear-gradient(to right, #d1e9ff 0%, #bbdefb 100%)';
            }
        });

        li.addEventListener('mouseleave', () => {
            if (conv.unread_count > 0) {
                li.style.background = 'linear-gradient(to right, #e3f2fd 0%, #d1e9ff 100%)';
            } else {
                li.style.background = '';
            }
        });

        container.appendChild(li);
    });
}

function startDMWithUser(userId, username) {
    if (window.currentUser && String(userId) === String(window.currentUser.id)) {
        addNotification('Нельзя отправлять сообщения самому себе');
        return;
    }

    // Закрываем другие модальные окна
    hideCreateRoomInput();
    const dmModal = document.getElementById('dm-modal');
    if (dmModal) dmModal.style.display = 'none';

    // Устанавливаем получателя
    currentDMRecipient = userId;
    isInDMMode = true;

    // Обновляем заголовок
    document.getElementById('current-room').textContent = `Личные сообщения: ${username}`;

    // Убираем подсветку у всех диалогов
    document.querySelectorAll('.dm-conversation').forEach(conv => {
        conv.classList.remove('active');
    });

    // Добавляем подсветку текущему диалогу
    const currentConversation = document.querySelector(`.dm-conversation[data-user-id="${userId}"]`);
    if (currentConversation) {
        currentConversation.classList.add('active');
        currentConversation.classList.remove('has-unread');

        // Убираем badge непрочитанных
        const badge = currentConversation.querySelector('.unread-badge');
        if (badge) {
            badge.remove();
        }
    }

    // Очищаем чат перед загрузкой новых сообщений
    clearChatUI();

    // Загружаем историю переписки
    socket.emit('start_dm', { recipient_id: userId });

    // маркируем как прочитанные
    socket.emit('mark_messages_as_read', { sender_id: userId });

    // Переключаемся на вкладку ЛС
    switchToDMTab();

    // Фокусируемся на поле ввода
    setTimeout(() => {
        const messageInput = document.getElementById('message-input');
        if (messageInput) {
            messageInput.focus();
        }
    }, 100);

    console.log('ЛС инициализировано');
}

function closeDM() {
    isInDMMode = false;
    currentDMRecipient = null;
    switchToRoomsTab();
    initChat(); // Возвращаемся в текущую комнату
}

// Добавьте кнопку закрытия ЛС в ваш HTML или создайте динамически

function sendDM() {
    if (!currentDMRecipient) {
        console.error('Нет получателя для ЛС');
        return;
    }

    const messageInput = document.getElementById('message-input');
    const message = messageInput?.value.trim();

    if (message) {
        socket.emit('send_dm', {
            recipient_id: currentDMRecipient,
            message: message,
        });

        // Локальное отображение сообщения
        addDMMessage({
            sender_id: window.currentUser?.id,
            sender_username: window.currentUser?.username || 'Вы',
            content: message,
            timestamp: new Date().toISOString(),
            is_local: true
        });

        messageInput.value = '';
    }
}

function addDMMessage(message) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) {
        console.error('Chat box not found for DM');
        return;
    }

    const messageElement = document.createElement('div');

     // Определяем класс в зависимости от отправителя
    const isMyMessage = window.currentUser && message.sender_id == window.currentUser.id;
    messageElement.className = `message ${isMyMessage ? 'my-message' : 'their-message'}`;

    const timestamp = message.timestamp ? new Date(message.timestamp).toLocaleTimeString() :
                     message.created_at ? new Date(message.created_at).toLocaleTimeString() :
                     new Date().toLocaleTimeString();

    messageElement.innerHTML = `
        <strong>${isMyMessage ? 'Вы' : message.sender_username}</strong>
        <small>[${timestamp}]</small>:
        ${message.content}
    `;

    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
    console.log('ЛС добавлено в UI');
}

function showDMNotification(message) {
    // Показать браузерное уведомление
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(`Новое сообщение от ${message.sender_username}`, {
            body: message.content,
        });
    }

    // Показать уведомление в интерфейсе
    const notification = document.createElement('div');
    notification.className = 'dm-notification';
    notification.innerHTML = `
        <strong>${message.sender_username}</strong>: ${message.content}
    `;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 5000);
}

function updateUnreadCount(senderId, username) {
    console.log('Обновление индикатора непрочитанных для:', username, senderId);

    // Находим диалог с этим пользователем
    const conversation = document.querySelector(`.dm-conversation[data-user-id="${senderId}"]`);

    if (conversation) {
        // Добавляем класс непрочитанного
        conversation.classList.add('has-unread');

        // Обновляем счетчик
        const badge = conversation.querySelector('.unread-badge');
        if (badge) {
            const currentCount = parseInt(badge.textContent) || 0;
            badge.textContent = currentCount + 1;
        } else {
            // Создаем badge если его нет
            const unreadIndicator = conversation.querySelector('.unread-indicator');
            if (unreadIndicator) {
                unreadIndicator.innerHTML = `<span class="unread-badge">1</span>`;
            }
        }

        // Показываем уведомление
        showDMNotification({
            sender_id: senderId,
            sender_username: username,
            content: 'Новое сообщение'
        });
    } else {
        console.log('Диалог не найден, загружаем список диалогов');
        // Если диалога нет, обновляем весь список
        loadDMConversations();
    }
}

// Поиск пользователей для DM
function searchUsers(query) {
    if (query.length < 2) {
        document.getElementById('user-search-results').innerHTML = '';
        return;
    }

    fetch(`/api/users/search?q=${encodeURIComponent(query)}`)
        .then(response => {
            if (!response.ok) throw new Error('Search failed');
            return response.json();
        })
        .then(users => {
            renderUserSearchResults(users);
        })
        .catch(error => {
            console.error('Search error:', error);
        });
}

function renderUserSearchResults(users) {
    const resultsContainer = document.getElementById('user-search-results');
    if (!resultsContainer) return;

    resultsContainer.innerHTML = '';

    users.forEach(user => {
        const div = document.createElement('div');
        div.className = 'user-search-result';
        div.textContent = user.username;
        div.addEventListener('click', () => {
            selectUserForDM(user.id, user.username);
            document.getElementById('dm-modal').style.display = 'none';
        });
        resultsContainer.appendChild(div);
    });
}

function openDMModal() {
    const modal = document.getElementById('dm-modal');
    if (modal) {
        modal.style.display = 'block';

        // АВТОМАТИЧЕСКИ ОБНОВЛЯЕМ ДИАЛОГИ ПРИ ОТКРЫТИИ МОДАЛЬНОГО ОКНА
        loadDMConversations();
    }
}

function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');

            // Деактивируем все табы
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Активируем выбранный таб
            button.classList.add('active');
            document.getElementById(`${tabId}-tab`).classList.add('active');

            // Загружаем данные для активного таба
            if (tabId === 'dms') {
                loadDMConversations();
            } else if (tabId === 'rooms') {
                socket.emit('get_rooms');
            }
        });
    });
}

// -------------------------- ФУНКЦИИ ДЛЯ СОЗДАНИЯ КОМНАТЫ ----------------------------------

function showCreateRoomInput() {
    const roomCreateElement = document.getElementById('room-create');
    const roomInputElement = document.getElementById('new-room-name');

    if (!roomCreateElement) {
        console.error('Элемент room-create не найден');
        return;
    }

    // Скрываем другие открытые формы
    const dmModal = document.getElementById('dm-modal');
    if (dmModal) {
        dmModal.style.display = 'none';
    }

    // Показываем форму создания комнаты
    console.log('Добавляем класс active');
    roomCreateElement.classList.add('active');
    roomCreateElement.classList.remove('invalid');
     if (roomInputElement) {
        roomInputElement.value = '';
        roomInputElement.focus();
    }

    // Добавляем обработчик для скрытия формы при клике вне её
    setTimeout(() => {
        document.addEventListener('click', hideCreateRoomOnClickOutside);
    }, 100);
}

function hideCreateRoomOnClickOutside(e) {
    const roomCreateElement = document.getElementById('room-create');
    const createButton = document.querySelector('#rooms-tab > button');

    // Проверяем, что элементы существуют
    if (!roomCreateElement || !createButton) {
        return;
    }

    if (roomCreateElement.classList.contains('active') &&
        !roomCreateElement.contains(e.target) &&
        e.target !== createButton &&
        !createButton.contains(e.target)) {
        hideCreateRoomInput();
    }
}

function hideCreateRoomInput() {
    const roomCreateElement = document.getElementById('room-create');
    if (roomCreateElement) {
        roomCreateElement.classList.remove('active');
        roomCreateElement.classList.remove('invalid');
        roomCreateElement.classList.remove('valid');
        document.removeEventListener('click', hideCreateRoomOnClickOutside);

        // Очищаем поле ввода
        const newRoomInput = document.getElementById('new-room-name');
        if (newRoomInput) {
            newRoomInput.value = '';
        }
    }
}

function submitCreateRoom() {
    const newRoomInput = document.getElementById('new-room-name');
    const roomCreateElement = document.getElementById('room-create');
    const newRoomName = newRoomInput.value.trim();

    if (!newRoomName) {
        showRoomError('Введите название комнаты');
        return;
    }

    if (newRoomName.length > 20) {
        showRoomError('Название комнаты слишком длинное (макс. 20 символов)');
        return;
    }

    if (newRoomName.length < 2) {
        showRoomError('Название комнаты слишком короткое (мин. 2 символа)');
        return;
    }

    // Валидация пройдена
    roomCreateElement.classList.add('valid');
    roomCreateElement.classList.remove('invalid');

    // Эмитим событие создания комнаты с обработчиком ответа
    socket.emit('create_room', { room_name: newRoomName });

//    socket.emit('create_room', { room_name: newRoomName }, (response) => {
//        if (response && response.success) {
//            // Анимация успешного создания
//            roomCreateElement.classList.add('room-created');
//
//            // Очищаем поле ввода
//            newRoomInput.value = '';
//
//            // Переключаемся на новую комнату через 1 секунду
//            setTimeout(() => {
//                switchToRoom(newRoomName);
//                hideCreateRoomInput();
//                roomCreateElement.classList.remove('room-created');
//            }, 1000);
//
//            // Показываем уведомление
//            addNotification(response.message || `Комната "${newRoomName}" создана!`);
//        }
//    });

    // Сразу скрываем форму после отправки (опционально)
    hideCreateRoomInput();
}

function showRoomError(message) {
    const roomCreateElement = document.getElementById('room-create');
    const errorElement = roomCreateElement?.querySelector('.error-message');

    if (roomCreateElement) {
        roomCreateElement.classList.add('invalid');
        roomCreateElement.classList.remove('valid');

        if (errorElement) {
            errorElement.textContent = message;
        }

        // Анимация тряски
        roomCreateElement.style.animation = 'none';
        setTimeout(() => {
            roomCreateElement.style.animation = 'shake 0.3s ease-in-out';
        }, 10);
    }
}

function updateRoomList(rooms) {
    const roomListElement = document.getElementById('rooms-list');
    if (!roomListElement) {
        console.error('Элемент rooms-list не найден');
        return;
    }

    roomListElement.innerHTML = '';

    // Сортируем комнаты: сначала general_chat, потом остальные
    const sortedRooms = [...rooms].sort((a, b) => {
        if (a === 'general_chat') return -1;
        if (b === 'general_chat') return 1;
        return a.localeCompare(b);
    });

    sortedRooms.forEach(roomName => {
        const li = document.createElement('li');
        li.textContent = roomName;
        li.className = 'room-item';

        // Визуально выделяем комнату по умолчанию
        if (roomName === 'general_chat') {
            li.classList.add('default-room');
        }

        if (roomName === currentRoom && !isInDMMode) {
            li.classList.add('active');
        }

        li.addEventListener('click', () => {
            if (roomName !== currentRoom || isInDMMode) {
                switchToRoom(roomName);
            }
        });

        roomListElement.appendChild(li);
    });

    if (rooms.length === 0) {
        const li = document.createElement('li');
        li.textContent = "Нет активных комнат. Создайте первую!";
        li.className = 'room-placeholder';
        roomListElement.appendChild(li);
    }
}

// Добавляем обработчик Escape для скрытия формы
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideCreateRoomInput();
    }
});




