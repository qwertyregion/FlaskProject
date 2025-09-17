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
        console.log('🔵 [SOCKET DEBUG] Регистрируем обработчики событий');
        
        // Общий обработчик для всех событий (для отладки)
        this.socket.onAny((eventName, ...args) => {
            console.log(`🔵 [SOCKET DEBUG] Получено событие: ${eventName}`, args);
            console.log(`🔵 [SOCKET DEBUG] Socket ID: ${this.socket.id}`);
            console.log(`🔵 [SOCKET DEBUG] Current User:`, window.currentUser);
        });
        
        // Основные события подключения
        this.socket.on('connect', () => {
            console.log('🔵 [SOCKET DEBUG] Событие connect получено');
            this.handleConnect();
        });
        this.socket.on('disconnect', () => {
            console.log('🔵 [SOCKET DEBUG] Событие disconnect получено');
            this.handleDisconnect();
        });

        // События комнат
        this.socket.on('room_list', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие room_list получено:', data);
            this.handleRoomList(data);
        });
        this.socket.on('current_users', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие current_users получено:', data);
            this.handleCurrentUsers(data);
        });
        this.socket.on('user_joined', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие user_joined получено:', data);
            this.handleUserJoined(data);
        });
        this.socket.on('user_left', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие user_left получено:', data);
            this.handleUserLeft(data);
        });
        this.socket.on('room_created', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие room_created получено:', data);
            this.handleRoomCreated(data);
        });

        // События сообщений
        this.socket.on('new_message', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие new_message получено:', data);
            this.handleNewMessage(data);
        });
        this.socket.on('message_history', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие message_history получено:', data);
            this.handleMessageHistory(data);
        });
        this.socket.on('more_messages_loaded', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие more_messages_loaded получено:', data);
            this.handleMoreMessagesLoaded(data);
        });
        this.socket.on('load_more_error', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие load_more_error получено:', data);
            this.handleLoadMoreError(data);
        });

        // События личных сообщений
        this.socket.on('dm_conversations', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие dm_conversations получено:', data);
            this.handleDMConversations(data);
        });
        this.socket.on('new_dm', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие new_dm получено:', data);
            this.handleNewDM(data);
        });
        this.socket.on('dm_history', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие dm_history получено:', data);
            this.handleDMHistory(data);
        });
        this.socket.on('update_unread_indicator', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие update_unread_indicator получено:', data);
            this.handleUpdateUnreadIndicator(data);
        });
        this.socket.on('messages_marked_read', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие messages_marked_read получено:', data);
            this.handleMessagesMarkedRead(data);
        });
        this.socket.on('dm_sent', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие dm_sent получено:', data);
            this.handleDMSent(data);
        });
        this.socket.on('dm_error', (data) => {
            console.log('🔵 [SOCKET DEBUG] Событие dm_error получено:', data);
            this.handleDMError(data);
        });
        
        console.log('✅ [SOCKET DEBUG] Все обработчики событий зарегистрированы');
    }

    handleConnect() {
        if (window.isPageUnloading) {
            return;
        }

        console.log('🔵 [CLIENT DEBUG] Подключение к серверу установлено');
        console.log('🔵 [CLIENT DEBUG] Socket ID:', this.socket.id);
        console.log('🔵 [CLIENT DEBUG] Current User:', window.currentUser);
        console.log('🔵 [CLIENT DEBUG] Socket connected:', this.socket.connected);
        
        // Инициализируем чат и вкладки (initChat() автоматически присоединится к комнате)
        this.chatUI.initChat();
        this.chatUI.initTabs();

        // Автоматически загружаем диалоги при подключении
        if (this.dmHandler) {
            this.dmHandler.loadDMConversations();
        }
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
        console.log('🔵 [CLIENT DEBUG] handleNewDM вызван с данными:', data);
        
        if (this.dmHandler) {
            console.log('🔵 [CLIENT DEBUG] dmHandler найден');
            console.log('🔵 [CLIENT DEBUG] currentDMRecipient:', this.dmHandler.currentDMRecipient);
            console.log('🔵 [CLIENT DEBUG] data.sender_id:', data.sender_id);
            console.log('🔵 [CLIENT DEBUG] data.recipient_id:', data.recipient_id);
            console.log('🔵 [CLIENT DEBUG] currentUser.id:', window.currentUser?.id);
            
            // ИСПРАВЛЕНО: Проверяем, что получатель - это текущий пользователь
            const isForCurrentUser = data.recipient_id == window.currentUser?.id;
            
            // И проверяем, что пользователь находится в диалоге с отправителем
            const isInActiveDialog = this.dmHandler.isInDMMode && 
                                   this.dmHandler.currentDMRecipient == data.sender_id;
            
            const isForCurrentDM = isForCurrentUser && isInActiveDialog;

            console.log('🔵 [CLIENT DEBUG] isForCurrentUser:', isForCurrentUser);
            console.log('🔵 [CLIENT DEBUG] isInDMMode:', this.dmHandler.isInDMMode);
            console.log('🔵 [CLIENT DEBUG] isInActiveDialog:', isInActiveDialog);
            console.log('🔵 [CLIENT DEBUG] isForCurrentDM:', isForCurrentDM);

            if (isForCurrentDM) {
                console.log('🔵 [CLIENT DEBUG] Сообщение для текущего диалога, добавляем сообщение БЕЗ индикаторов');
                this.dmHandler.addDMMessage(data);
                // ИСПРАВЛЕНО: Помечаем сообщение как прочитанное, так как пользователь его видит
                console.log('🔵 [CLIENT DEBUG] Помечаем сообщение как прочитанное (пользователь в активном диалоге)');
                window.socket.emit('mark_messages_as_read', { sender_id: data.sender_id });
            } else if (isForCurrentUser) {
                console.log('🔵 [CLIENT DEBUG] Сообщение для текущего пользователя, но не в активном диалоге - добавляем индикаторы');
                this.dmHandler.showDMNotification(data);
                this.dmHandler.updateUnreadCount(data.sender_id, data.sender_username);
                // ИСПРАВЛЕНО: НЕ вызываем updateTabIndicatorFromCurrentState - это делается в updateUnreadCount
            } else {
                console.log('🔵 [CLIENT DEBUG] Сообщение не для текущего пользователя');
            }
        } else {
            console.log('🔴 [CLIENT DEBUG] dmHandler не найден!');
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
            
            // Получаем количество непрочитанных сообщений до их удаления
            const badge = currentConversation.querySelector('.unread-badge');
            let unreadCount = 0;
            if (badge) {
                unreadCount = parseInt(badge.textContent) || 0;
                console.log(`🔵 [CLIENT DEBUG] handleDMHistory: было непрочитанных сообщений: ${unreadCount}`);
                badge.remove();
            }
            
            // Удаляем unread-line
            const unreadLine = currentConversation.querySelector('.unread-line');
            if (unreadLine) unreadLine.remove();
            
            // Обновляем общий счетчик и индикатор на вкладке
            if (unreadCount > 0) {
                this.dmHandler.totalUnreadCount = Math.max(0, this.dmHandler.totalUnreadCount - unreadCount);
                console.log(`🔵 [CLIENT DEBUG] handleDMHistory: общий счетчик уменьшен на ${unreadCount}, новый totalUnreadCount: ${this.dmHandler.totalUnreadCount}`);
                this.dmHandler.updateTabIndicatorSimple();
            }
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
        console.log('🔵 [CLIENT DEBUG] handleUpdateUnreadIndicator вызван для:', data.sender_id);
        // ИСПРАВЛЕНО: НЕ вызываем updateUnreadIndicator здесь - это уже делается в handleNewDM
        // this.dmHandler.updateUnreadIndicator(data.sender_id, data.username);
    }

    handleMessagesMarkedRead(data) {
        if (data.success) {
            console.log('Сообщения помечены как прочитанные для отправителя:', data.sender_id);
            // ИСПРАВЛЕНО: не перезагружаем диалоги, только обновляем индикаторы
            if (this.dmHandler) {
                // Обновляем только индикаторы непрочитанных, не перезагружая весь список
                this.dmHandler.updateUnreadIndicatorsOnly(data.sender_id);
            }
        }
    }

    handleDMSent(data) {
        console.log('🔵 [CLIENT DEBUG] handleDMSent вызван с данными:', data);
        
        if (data.success) {
            console.log('✅ [CLIENT DEBUG] Сообщение успешно отправлено');
            console.log('🔵 [CLIENT DEBUG] Получатель:', data.recipient_username);
            console.log('🔵 [CLIENT DEBUG] ID сообщения:', data.message_id);
            
            if (data.offline) {
                console.log('🔵 [CLIENT DEBUG] Получатель не в сети, сообщение сохранено');
                this.chatUI.addNotification(`Сообщение отправлено пользователю ${data.recipient_username} (не в сети)`);
            } else {
                console.log('🔵 [CLIENT DEBUG] Получатель в сети, сообщение доставлено');
                this.chatUI.addNotification(`Сообщение отправлено пользователю ${data.recipient_username}`);
            }
        } else {
            console.error('🔴 [CLIENT DEBUG] Ошибка отправки сообщения');
            this.chatUI.addNotification('Ошибка отправки сообщения', 'error');
        }
    }

    handleDMError(data) {
        console.log('🔵 [CLIENT DEBUG] handleDMError вызван с данными:', data);
        
        const errorMessage = data.error || 'Неизвестная ошибка';
        console.error('🔴 [CLIENT DEBUG] Ошибка DM:', errorMessage);
        
        // Показываем уведомление об ошибке
        this.chatUI.addNotification(`Ошибка: ${errorMessage}`, 'error');
        
        // Если это ошибка валидации, можно добавить специальную обработку
        if (errorMessage.includes('самому себе')) {
            console.log('🔵 [CLIENT DEBUG] Попытка отправить сообщение самому себе');
        } else if (errorMessage.includes('не найден')) {
            console.log('🔵 [CLIENT DEBUG] Получатель не найден');
        } else if (errorMessage.includes('не аутентифицирован')) {
            console.log('🔵 [CLIENT DEBUG] Пользователь не аутентифицирован');
        }
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SocketHandlers;
} else {
    window.SocketHandlers = SocketHandlers;
}
