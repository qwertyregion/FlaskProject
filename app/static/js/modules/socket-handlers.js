/**
 * Модуль для обработки Socket.IO событий
 */

class SocketHandlers {
    constructor(socket, chatUI, dmHandler) {
        this.socket = socket;
        this.chatUI = chatUI;
        this.dmHandler = dmHandler;
        this.setupHandlers();
    }

    setupHandlers() {
        // Основные события подключения
        this.socket.on('connect', () => this.handleConnect());
        this.socket.on('disconnect', () => this.handleDisconnect());

        // События комнат
        this.socket.on('room_list', (data) => this.handleRoomList(data));
        this.socket.on('current_users', (data) => this.handleCurrentUsers(data));
        this.socket.on('user_joined', (data) => this.handleUserJoined(data));
        this.socket.on('user_left', (data) => this.handleUserLeft(data));
        this.socket.on('room_created', (data) => this.handleRoomCreated(data));

        // События сообщений
        this.socket.on('new_message', (data) => this.handleNewMessage(data));
        this.socket.on('message_history', (data) => this.handleMessageHistory(data));
        this.socket.on('more_messages_loaded', (data) => this.handleMoreMessagesLoaded(data));
        this.socket.on('load_more_error', (data) => this.handleLoadMoreError(data));

        // События личных сообщений
        this.socket.on('dm_conversations', (data) => this.handleDMConversations(data));
        this.socket.on('new_dm', (data) => this.handleNewDM(data));
        this.socket.on('dm_history', (data) => this.handleDMHistory(data));
        this.socket.on('update_unread_indicator', (data) => this.handleUpdateUnreadIndicator(data));
        this.socket.on('messages_marked_read', (data) => this.handleMessagesMarkedRead(data));
    }

    handleConnect() {
        if (window.isPageUnloading) {
            return;
        }

        console.log('Подключение к серверу установлено');
        console.log('Текущий пользователь:', window.currentUser);
        
        // Инициализируем чат и вкладки
        this.chatUI.initChat();
        this.chatUI.initTabs();

        // Автоматически загружаем диалоги при подключении
        if (this.dmHandler) {
            if (this.dmHandler) {
                this.dmHandler.loadDMConversations();
            }
        }

        // Сервер отправит 'current_users' на connect и на join_room, не дергаем лишний запрос
    }

    handleDisconnect() {
        if (!window.isPageUnloading) {
            console.log('Соединение с сервером потеряно, переподключение...');
            // Переподключение через 1 секунду
            setTimeout(() => {
                if (!this.socket.connected) {
                    this.socket.connect();
                }
            }, 1000);
        }
    }

    handleRoomList(data) {
        console.log('Получен список комнат:', data.rooms);
        if (this.chatUI) {
            this.chatUI.updateRoomList(data.rooms);
        } else {
            console.warn('ChatUI не инициализирован при получении списка комнат');
        }
    }

    handleCurrentUsers(data) {
        console.log('Получен список пользователей:', data.users, 'для комнаты:', data.room);
        console.log('Текущая комната:', this.chatUI.currentRoom, 'Режим ЛС:', this.dmHandler ? this.dmHandler.isInDMMode : 'не инициализирован');
        
        if (data.room !== this.chatUI.currentRoom || (this.dmHandler && this.dmHandler.isInDMMode)) {
            console.log('Пропускаем - не текущая комната или режим ЛС');
            return;
        }

        try {
            this.chatUI.updateUsersList(data.users, data.room);
        } catch (error) {
            console.error('Ошибка обработки current_users:', error);
        }
    }

    handleUserJoined(data) {
        if (data.room === this.chatUI.currentRoom && (!this.dmHandler || !this.dmHandler.isInDMMode)) {
            this.chatUI.addUserToList(data.user_id, data.username);
            this.chatUI.addNotification(`${data.username} присоединился к чату`);

            // Список пользователей придет от сервера автоматически
        }
    }

    handleUserLeft(data) {
        const userElement = document.getElementById(`user-${data.user_id}-${this.chatUI.currentRoom}`);
        if (userElement && (!this.dmHandler || !this.dmHandler.isInDMMode)) {
            userElement.remove();
            this.chatUI.updateOnlineCount();

            // Список пользователей придет от сервера автоматически

            // Показываем уведомление только если событие из текущей комнаты
            if (data.room === this.chatUI.currentRoom) {
                this.chatUI.addNotification(`${data.username} покинул чат`);
            }
        }
    }

    handleRoomCreated(data) {
        console.log('Получено событие room_created:', data);
        
        if (data && data.success) {
            console.log('Комната успешно создана:', data.room_name);
            this.chatUI.addNotification(data.message || `Комната "${data.room_name}" создана!`);

            // Автоматически переходим в новую комнату, если установлен флаг
            if (data.auto_join && data.room_name && data.room_name !== this.chatUI.currentRoom) {
                setTimeout(() => {
                    console.log('Автоматический переход в созданную комнату:', data.room_name);
                    this.chatUI.switchToRoom(data.room_name);
                }, 500);
            }
            // Обновляем список комнат - сервер автоматически отправляет room_list при создании
        } else {
            const errorMessage = (data && data.message) ? data.message : 'Ошибка создания комнаты';
            console.error('Ошибка создания комнаты:', errorMessage);
            this.chatUI.showRoomError(errorMessage);
        }
    }

    handleNewMessage(data) {
        if (data.room === this.chatUI.currentRoom && !data.is_dm && (!this.dmHandler || !this.dmHandler.isInDMMode)) {
            if (this.chatUI.virtualizedChat) {
                this.chatUI.virtualizedChat.addNewMessage(data);
            } else {
                this.chatUI.addMessageToChat(data);
            }

            // Автоскролл с задержкой для длинных сообщений
            setTimeout(() => {
                this.chatUI.autoScrollToNewMessage();
            }, 200);
        }
    }

    handleMessageHistory(data) {
        if (data.room === this.chatUI.currentRoom && (!this.dmHandler || !this.dmHandler.isInDMMode)) {
            if (this.chatUI.virtualizedChat) {
                this.chatUI.virtualizedChat.messages = data.messages;
                this.chatUI.virtualizedChat.offset = data.messages.length;
                this.chatUI.virtualizedChat.hasMore = data.has_more;
                this.chatUI.virtualizedChat.renderVisibleMessages();
                
                // Скрываем кнопку если нет сообщений или нет дополнительных сообщений
                if (data.messages.length === 0 || !data.has_more) {
                    this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
                } else {
                    this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'block';
                }
            }

            this.chatUI.messageHistoryLoaded = true;
            this.chatUI.scrollToBottom();
        }
    }

    handleMoreMessagesLoaded(data) {
        console.log('Получены дополнительные сообщения:', data.messages?.length, 'для комнаты:', data.room);

        if (this.chatUI.virtualizedChat && data.room === this.chatUI.currentRoom && (!this.dmHandler || !this.dmHandler.isInDMMode)) {
            this.chatUI.virtualizedChat.handleNewMessages(data);
        }
    }

    handleLoadMoreError(data) {
        console.error('Ошибка загрузки сообщений:', data.error);
        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.isLoading = false;
            this.chatUI.virtualizedChat.loadMoreBtn.disabled = false;
            this.chatUI.virtualizedChat.loadMoreBtn.textContent = 'Загрузить предыдущие сообщения';
        }
    }

    handleDMConversations(data) {
        if (this.dmHandler) {
            this.dmHandler.renderDMConversations(data.conversations);
        }
    }

    handleNewDM(data) {
        if (this.dmHandler) {
            const isForCurrentDM = this.dmHandler.currentDMRecipient &&
                (this.dmHandler.currentDMRecipient == data.sender_id || this.dmHandler.currentDMRecipient == data.recipient_id);

            if (isForCurrentDM) {
                this.dmHandler.addDMMessage(data);
                this.socket.emit('mark_messages_as_read', { sender_id: data.sender_id });
            } else {
                this.dmHandler.showDMNotification(data);
                this.dmHandler.updateUnreadCount(data.sender_id);
                if (this.dmHandler) {
                this.dmHandler.loadDMConversations();
            }
            }
        }
    }

    handleDMHistory(data) {
        if (!this.dmHandler) return;

        // ВАЖНО: не вызываем startDMWithUser снова, чтобы не триггерить повторный start_dm и зацикливание
        // Просто рендерим полученную историю и переключаемся в режим ЛС
        this.dmHandler.currentDMRecipient = data.recipient_id;
        this.dmHandler.isInDMMode = true;
        this.dmHandler.chatUI?.hideCreateRoomInput();

        const title = document.getElementById('current-room');
        if (title) title.textContent = `Личные сообщения: ${data.recipient_name}`;

        // Подсветка активного диалога
        document.querySelectorAll('.dm-conversation').forEach(conv => conv.classList.remove('active'));
        const currentConversation = document.querySelector(`.dm-conversation[data-user-id="${data.recipient_id}"]`);
        if (currentConversation) {
            currentConversation.classList.add('active');
            currentConversation.classList.remove('has-unread');
            const badge = currentConversation.querySelector('.unread-badge');
            if (badge) badge.remove();
        }

        // Очистка чата и отрисовка истории
        this.chatUI.clearChatUI();
        if (Array.isArray(data.messages)) {
            data.messages.forEach(msg => this.dmHandler.addDMMessage(msg));
        }

        // Переключаемся на вкладку ЛС и фокусируем инпут
        this.dmHandler.switchToDMTab();
        setTimeout(() => {
            const input = document.getElementById('message-input');
            if (input) input.focus();
        }, 50);
    }

    handleUpdateUnreadIndicator(data) {
        console.log('Обновление индикатора для отправителя:', data.sender_id);
        if (this.dmHandler) {
            this.dmHandler.updateUnreadIndicator(data.sender_id, data.username);
        }
    }

    handleMessagesMarkedRead(data) {
        if (data.success) {
            console.log('Сообщения помечены как прочитанные для отправителя:', data.sender_id);
            if (this.dmHandler) {
                this.dmHandler.loadDMConversations();
            }
        }
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SocketHandlers;
} else {
    window.SocketHandlers = SocketHandlers;
}
