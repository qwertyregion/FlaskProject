/**
 * Модуль для управления UI чата
 */

class ChatUI {
    constructor() {
        this.currentRoom = 'general_chat';
        this.virtualizedChat = null;
        this.messageHistoryLoaded = false;
        this.unreadMessagesCount = 0;
        this.newMessagesIndicator = null;
        this.resizeTimeout = null;
        
        this.init();
    }

    init() {
        console.log('Инициализация ChatUI');
        this.setupEventListeners();
        this.createNewMessagesIndicator();
        this.setupChatScrollHandler();
        console.log('ChatUI инициализирован');
    }

    setupEventListeners() {
        console.log('Настройка обработчиков событий');
        // Обработчик перед закрытием страницы
        window.addEventListener('beforeunload', () => {
            window.isPageUnloading = true;
            if (window.socket && window.socket.connected) {
                window.socket.disconnect();
            }
        });

        // Обработчик ресайза окна
        window.addEventListener('resize', () => {
            clearTimeout(this.resizeTimeout);
            this.resizeTimeout = setTimeout(() => {
                const chatBox = document.getElementById('chat-box');
                if (chatBox) {
                    const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 200;
                    if (isNearBottom) {
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                }
            }, 250);
        });

        // Обработчик Escape для скрытия форм
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.hideCreateRoomInput();
            }
        });
    }

    setupChatScrollHandler() {
        console.log('Настройка обработчика скролла чата');
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            console.log('Chat box найден для скролла');
            chatBox.addEventListener('scroll', () => {
                const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 50;

                if (isNearBottom && this.unreadMessagesCount > 0) {
                    this.hideNewMessagesIndicator();
                }
            });
        } else {
            console.error('Chat box не найден для скролла');
        }
    }

    createNewMessagesIndicator() {
        console.log('Создание индикатора новых сообщений');
        if (!this.newMessagesIndicator) {
            this.newMessagesIndicator = document.createElement('div');
            this.newMessagesIndicator.id = 'new-messages-indicator';
            this.newMessagesIndicator.innerHTML = 'Новые сообщения ↓';
            this.newMessagesIndicator.style.cssText = `
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

            this.newMessagesIndicator.addEventListener('click', () => {
                const chatBox = document.getElementById('chat-box');
                if (chatBox) {
                    chatBox.scrollTop = chatBox.scrollHeight;
                    this.hideNewMessagesIndicator();
                }
            });

            document.body.appendChild(this.newMessagesIndicator);
            console.log('Индикатор новых сообщений добавлен в DOM');
        }
        return this.newMessagesIndicator;
    }

    showNewMessagesIndicator(count) {
        const indicator = this.createNewMessagesIndicator();
        indicator.innerHTML = `${count} новых сообщения ↓`;
        indicator.style.display = 'block';
        this.unreadMessagesCount = count;
    }

    hideNewMessagesIndicator() {
        if (this.newMessagesIndicator) {
            this.newMessagesIndicator.style.display = 'none';
            this.unreadMessagesCount = 0;
        }
    }

    initChat() {
        console.log('Инициализация чата для комнаты:', this.currentRoom);
        this.clearChatUI();

        if (!window.dmHandler || !window.dmHandler.isInDMMode) {
            const chatBox = document.getElementById('chat-box');
            console.log('Chat box найден:', !!chatBox);

            // Инициализируем или обновляем виртуализатор
            if (!this.virtualizedChat) {
                this.virtualizedChat = new VirtualizedChat(chatBox);
            } else {
                this.virtualizedChat.resetForNewRoom(this.currentRoom);
            }
            
            // Убеждаемся, что кнопка скрыта при инициализации
            if (this.virtualizedChat) {
                this.virtualizedChat.loadMoreBtn.style.display = 'none';
            }

            window.socket.emit('join_room', { room: this.currentRoom });

            // Загружаем историю сообщений
            this.loadMessageHistory(this.currentRoom);
        } else {
            console.log('Пропускаем инициализацию чата - режим ЛС');
        }
    }

    switchToRoom(roomName) {
        if (window.dmHandler) {
            window.dmHandler.isInDMMode = false;
            window.dmHandler.currentDMRecipient = null;
        }
        this.messageHistoryLoaded = false;

        this.currentRoom = roomName;
        document.getElementById('current-room').textContent = roomName;

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

        this.switchToRoomsTab();
        this.initChat();

        // Убеждаемся, что кнопка скрыта при переключении комнаты
        if (this.virtualizedChat) {
            this.virtualizedChat.loadMoreBtn.style.display = 'none';
        }

        // Список пользователей придет от сервера после join_room
    }

    switchToRoomsTab() {
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
        if (window.dmHandler && window.dmHandler.isInDMMode) {
            window.dmHandler.isInDMMode = false;
            window.dmHandler.currentDMRecipient = null;
            this.initChat();
            
            if (this.virtualizedChat) {
                this.virtualizedChat.loadMoreBtn.style.display = 'none';
            }
        }
    }

    clearChatUI() {
        console.log('Очистка UI чата');
        const chatBox = document.getElementById('chat-box');
        if (chatBox) chatBox.innerHTML = '';
        
        if (this.virtualizedChat) {
            this.virtualizedChat.loadMoreBtn.style.display = 'none';
        }
        
        this.updateOnlineCount();
    }

    addMessageToChat(data) {
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

        if (this.virtualizedChat && this.virtualizedChat.messages.length > 0) {
            this.virtualizedChat.loadMoreBtn.style.display = 'block';
        }

        this.autoScrollToNewMessage();
    }

    addUserToList(userId, username) {
        console.log('addUserToList вызвана для:', username, 'ID:', userId, 'в комнате:', this.currentRoom);
        if (window.dmHandler && window.dmHandler.isInDMMode) {
            console.log('Пропускаем - режим ЛС');
            return;
        }

        const usersList = document.getElementById('active-users');
        if (!usersList) {
            console.error('Элемент active-users не найден в addUserToList');
            return;
        }

        if (!document.getElementById(`user-${userId}-${this.currentRoom}`)) {
            const userElement = document.createElement('li');
            userElement.id = `user-${userId}-${this.currentRoom}`;

            userElement.style.cursor = 'pointer';
            userElement.style.color = '#007bff';
            userElement.style.textDecoration = 'underline';
            userElement.style.padding = '2px 4px';
            userElement.style.margin = '2px 0';

            userElement.textContent = username || 'Неизвестный';

            userElement.addEventListener('click', (e) => {
                console.log('Клик по пользователю:', username, 'ID:', userId);
                e.stopPropagation();
                if (window.dmHandler) {
                    window.dmHandler.startDMWithUser(userId, username);
                }
            });

            if (window.currentUser && String(userId) === String(window.currentUser.id)) {
                userElement.style.fontWeight = 'bold';
                userElement.textContent += ' (Вы)';
                userElement.style.cursor = 'default';
                userElement.style.color = 'inherit';
                userElement.style.textDecoration = 'none';
            }

            usersList.appendChild(userElement);
            console.log('Пользователь добавлен в список:', username);
            this.updateOnlineCount();
        } else {
            console.log('Пользователь уже существует в списке:', username);
        }
    }

    updateUsersList(users, room) {
        console.log('Обновляем список пользователей:', users, 'для комнаты:', room);
        const usersList = document.getElementById('active-users');
        if (!usersList) {
            console.error('Элемент active-users не найден');
            return;
        }

        usersList.innerHTML = '';

        const currentUserId = String(window.currentUser?.id || '');
        console.log('Текущий ID пользователя:', currentUserId);
        console.log('Обрабатываем пользователей:', Object.entries(users));

        Object.entries(users).forEach(([userId, username]) => {
            const userElement = document.createElement('li');
            userElement.id = `user-${userId}-${room}`;

            userElement.style.cursor = 'pointer';
            userElement.style.color = '#007bff';
            userElement.style.textDecoration = 'underline';
            userElement.style.padding = '2px 4px';
            userElement.style.margin = '2px 0';

            userElement.textContent = username || 'Неизвестный';

            userElement.addEventListener('click', (e) => {
                console.log('Клик по пользователю:', username, 'ID:', userId);
                e.stopPropagation();
                if (window.dmHandler) {
                    window.dmHandler.startDMWithUser(userId, username);
                }
            });

            console.log('Сравниваем userId:', userId, 'с currentUserId:', currentUserId);
            if (String(userId) === String(currentUserId)) {
                console.log('Найден текущий пользователь:', username);
                userElement.style.fontWeight = 'bold';
                userElement.textContent += ' (Вы)';
                userElement.style.cursor = 'default';
                userElement.style.color = 'inherit';
                userElement.style.textDecoration = 'none';
            }

            usersList.appendChild(userElement);
        });

        this.updateOnlineCount();
    }

    addNotification(text) {
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

    updateOnlineCount() {
        const usersList = document.getElementById('active-users');
        const countElement = document.getElementById('online-count');
        if (usersList && countElement) {
            const count = usersList.children.length;
            console.log('Обновляем счетчик онлайн пользователей:', count);
            countElement.textContent = count;
        }
    }

    autoScrollToNewMessage() {
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) return;

        const isNearBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight <= 150;

        if (isNearBottom) {
            setTimeout(() => {
                chatBox.scrollTop = chatBox.scrollHeight;
            }, 50);
            this.hideNewMessagesIndicator();
        } else {
            this.unreadMessagesCount++;
            this.showNewMessagesIndicator(this.unreadMessagesCount);
        }
    }

    scrollToBottom() {
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }

    loadMessageHistory(roomName) {
        console.log('Загружаем историю сообщений для комнаты:', roomName);
        window.socket.emit('get_message_history', {
            room: roomName,
            limit: 20
        });
    }

    updateRoomList(rooms) {
        console.log('Обновляем список комнат:', rooms);
        const roomListElement = document.getElementById('rooms-list');
        if (!roomListElement) {
            console.error('Элемент rooms-list не найден');
            return;
        }

        roomListElement.innerHTML = '';

        const sortedRooms = [...rooms].sort((a, b) => {
            if (a === 'general_chat') return -1;
            if (b === 'general_chat') return 1;
            return a.localeCompare(b);
        });

        sortedRooms.forEach(roomName => {
            const li = document.createElement('li');
            li.textContent = roomName;
            li.className = 'room-item';

            if (roomName === 'general_chat') {
                li.classList.add('default-room');
            }

            if (roomName === this.currentRoom && (!window.dmHandler || !window.dmHandler.isInDMMode)) {
                li.classList.add('active');
            }

            li.addEventListener('click', () => {
                if (roomName !== this.currentRoom || (window.dmHandler && window.dmHandler.isInDMMode)) {
                    this.switchToRoom(roomName);
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
        
        console.log('Список комнат обновлен, количество комнат:', rooms.length);
    }

    showCreateRoomInput() {
        console.log('Показываем форму создания комнаты');
        const roomCreateElement = document.getElementById('room-create');
        const roomInputElement = document.getElementById('new-room-name');
        console.log('Элемент new-room-name найден:', !!roomInputElement);
        console.log('Элемент room-create найден:', !!roomCreateElement);

        if (!roomCreateElement) {
            console.error('Элемент room-create не найден');
            return;
        }
        
        console.log('Элемент room-create найден');

        const dmModal = document.getElementById('dm-modal');
        if (dmModal) {
            dmModal.style.display = 'none';
            console.log('Скрыли модальное окно ЛС');
        }

        console.log('Добавляем класс active');
        roomCreateElement.classList.add('active');
        roomCreateElement.classList.remove('invalid');
        if (roomInputElement) {
            roomInputElement.value = '';
            roomInputElement.focus();
            console.log('Фокус установлен на поле ввода');
        }

        setTimeout(() => {
            console.log('Добавляем обработчик клика вне формы');
            document.addEventListener('click', this.hideCreateRoomOnClickOutside.bind(this));
        }, 100);
    }

    hideCreateRoomOnClickOutside(e) {
        console.log('Проверяем клик вне формы создания комнаты');
        const roomCreateElement = document.getElementById('room-create');
        const createButton = document.querySelector('#rooms-tab > button');

        if (!roomCreateElement || !createButton) {
            console.log('Элементы не найдены для проверки клика');
            return;
        }

        if (roomCreateElement.classList.contains('active') &&
            !roomCreateElement.contains(e.target) &&
            e.target !== createButton &&
            !createButton.contains(e.target)) {
            console.log('Клик вне формы - скрываем');
            this.hideCreateRoomInput();
        }
    }

    hideCreateRoomInput() {
        console.log('Скрываем форму создания комнаты');
        const roomCreateElement = document.getElementById('room-create');
        if (roomCreateElement) {
            roomCreateElement.classList.remove('active');
            roomCreateElement.classList.remove('invalid');
            roomCreateElement.classList.remove('valid');
            document.removeEventListener('click', this.hideCreateRoomOnClickOutside.bind(this));

            const newRoomInput = document.getElementById('new-room-name');
            if (newRoomInput) {
                newRoomInput.value = '';
            }
        }
    }

    submitCreateRoom() {
        console.log('Отправляем форму создания комнаты');
        const newRoomInput = document.getElementById('new-room-name');
        const roomCreateElement = document.getElementById('room-create');
        const newRoomName = newRoomInput.value.trim();
        
        console.log('Название новой комнаты:', newRoomName);

        if (!newRoomName) {
            this.showRoomError('Введите название комнаты');
            return;
        }

        if (newRoomName.length > 20) {
            this.showRoomError('Название комнаты слишком длинное (макс. 20 символов)');
            return;
        }

        if (newRoomName.length < 2) {
            this.showRoomError('Название комнаты слишком короткое (мин. 2 символа)');
            return;
        }

        roomCreateElement.classList.add('valid');
        roomCreateElement.classList.remove('invalid');

        console.log('Отправляем событие create_room на сервер:', { room_name: newRoomName });
        window.socket.emit('create_room', { room_name: newRoomName });
        this.hideCreateRoomInput();
    }

    showRoomError(message) {
        console.log('Показываем ошибку создания комнаты:', message);
        const roomCreateElement = document.getElementById('room-create');
        const errorElement = roomCreateElement?.querySelector('.error-message');

        if (roomCreateElement) {
            roomCreateElement.classList.add('invalid');
            roomCreateElement.classList.remove('valid');

            if (errorElement) {
                errorElement.textContent = message;
            }

            roomCreateElement.style.animation = 'none';
            setTimeout(() => {
                roomCreateElement.style.animation = 'shake 0.3s ease-in-out';
            }, 10);
        }
    }

    initTabs() {
        console.log('Инициализация вкладок');
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');
        
        console.log('Найдено кнопок вкладок:', tabButtons.length);
        console.log('Найдено содержимого вкладок:', tabContents.length);

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.getAttribute('data-tab');

                tabButtons.forEach(btn => btn.classList.remove('active'));
                tabContents.forEach(content => content.classList.remove('active'));

                button.classList.add('active');
                document.getElementById(`${tabId}-tab`).classList.add('active');

                if (tabId === 'dms') {
                    if (window.dmHandler) {
                        window.dmHandler.loadDMConversations();
                    }
                } else if (tabId === 'rooms') {
                    // Список комнат обновляется автоматически сервером
                }
            });
        });
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatUI;
} else {
    window.ChatUI = ChatUI;
}
