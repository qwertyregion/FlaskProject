/**
 * Модуль для обработки личных сообщений (DM)
 */

class DMHandler {
    constructor() {
        this.currentDMRecipient = null;
        this.isInDMMode = false;
        this.pendingUnreadUpdate = null;
        this.totalUnreadCount = 0; // ИСПРАВЛЕНО: Простой счетчик
    }

    loadDMConversations() {
        console.log('🔵 [CLIENT DEBUG] loadDMConversations вызван');
        window.socket.emit('get_dm_conversations');
        console.log('🔵 [CLIENT DEBUG] get_dm_conversations отправлен на сервер');
    }

    renderDMConversations(conversations) {
        console.log('🔵 [CLIENT DEBUG] renderDMConversations вызван с данными:', conversations);
        
        const container = document.getElementById('dm-conversations');
        if (!container) {
            console.error('🔴 [CLIENT DEBUG] Контейнер dm-conversations не найден');
            return;
        }

        console.log('🔵 [CLIENT DEBUG] Контейнер найден, очищаем содержимое');
        container.innerHTML = '';

        if (conversations.length === 0) {
            console.log('🔵 [CLIENT DEBUG] Нет диалогов, показываем сообщение');
            container.innerHTML = '<li class="no-conversations">Нет диалогов</li>';
            return;
        }

        console.log(`🔵 [CLIENT DEBUG] Рендерим ${conversations.length} диалогов`);
        conversations.forEach(conv => {
            const li = document.createElement('li');
            li.className = 'dm-conversation';
            li.setAttribute('data-user-id', conv.user_id);

            if (conv.unread_count > 0) {
                li.classList.add('has-unread');
                li.setAttribute('data-unread', conv.unread_count);
            }

            let lastMessageTime = 'Нет сообщений';
            if (conv.last_message_time) {
                try {
                    const messageDate = new Date(conv.last_message_time);
                    const now = new Date();
                    const diffTime = Math.abs(now - messageDate);
                    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

                    if (diffDays === 0) {
                        lastMessageTime = messageDate.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    } else if (diffDays === 1) {
                        lastMessageTime = 'Вчера';
                    } else if (diffDays < 7) {
                        lastMessageTime = messageDate.toLocaleDateString([], {weekday: 'short'});
                    } else {
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

            li.addEventListener('click', () => {
                console.log('Переход в диалог с:', conv.username, 'ID:', conv.user_id);
                this.startDMWithUser(conv.user_id, conv.username);
            });

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
        
        console.log(`✅ [CLIENT DEBUG] Диалоги отрендерены, добавлено ${conversations.length} элементов в контейнер`);
        
        // ИСПРАВЛЕНО: Если есть отложенное обновление индикаторов, выполняем его
        if (this.pendingUnreadUpdate) {
            console.log('🔵 [CLIENT DEBUG] Выполняем отложенное обновление индикаторов');
            const { senderId, username } = this.pendingUnreadUpdate;
            this.pendingUnreadUpdate = null;
            
            // Теперь диалог должен быть найден, обновляем индикаторы
            this.updateUnreadCount(senderId, username);
        } else {
            // ИСПРАВЛЕНО: Пересчитываем общий счетчик из UI
            this.recalculateTotalUnreadCount();
        }
    }

    startDMWithUser(userId, username) {
        if (window.currentUser && String(userId) === String(window.currentUser.id)) {
            this.chatUI.addNotification('Нельзя отправлять сообщения самому себе');
            return;
        }

        this.chatUI.hideCreateRoomInput();
        const dmModal = document.getElementById('dm-modal');
        if (dmModal) dmModal.style.display = 'none';

        this.currentDMRecipient = userId;
        this.isInDMMode = true;

        document.getElementById('current-room').textContent = `Личные сообщения: ${username}`;

        document.querySelectorAll('.dm-conversation').forEach(conv => {
            conv.classList.remove('active');
        });

        const currentConversation = document.querySelector(`.dm-conversation[data-user-id="${userId}"]`);
        if (currentConversation) {
            currentConversation.classList.add('active');
            currentConversation.classList.remove('has-unread');

            // Получаем количество непрочитанных сообщений до их удаления
            const badge = currentConversation.querySelector('.unread-badge');
            let unreadCount = 0;
            if (badge) {
                unreadCount = parseInt(badge.textContent) || 0;
                console.log(`🔵 [CLIENT DEBUG] startDMWithUser: было непрочитанных сообщений: ${unreadCount}`);
                badge.remove();
            }
            
            // Удаляем unread-line
            const unreadLine = currentConversation.querySelector('.unread-line');
            if (unreadLine) {
                unreadLine.remove();
            }
            
            // Обновляем общий счетчик и индикатор на вкладке
            if (unreadCount > 0) {
                this.totalUnreadCount = Math.max(0, this.totalUnreadCount - unreadCount);
                console.log(`🔵 [CLIENT DEBUG] startDMWithUser: общий счетчик уменьшен на ${unreadCount}, новый totalUnreadCount: ${this.totalUnreadCount}`);
                this.updateTabIndicatorSimple();
            }
        }

        this.chatUI.clearChatUI();

        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }

        window.socket.emit('start_dm', { recipient_id: userId });
        window.socket.emit('mark_messages_as_read', { sender_id: userId });

        this.switchToDMTab();

        setTimeout(() => {
            const messageInput = document.getElementById('message-input');
            if (messageInput) {
                messageInput.focus();
            }
        }, 100);

        console.log('ЛС инициализировано');
    }

    switchToDMTab() {
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
        
        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }
    }

    addDMMessage(message) {
        console.log('🔵 [CLIENT DEBUG] addDMMessage вызван с данными:', message);
        
        const chatBox = document.getElementById('chat-box');
        if (!chatBox) {
            console.error('🔴 [CLIENT DEBUG] Chat box не найден для DM');
            return;
        }

        const messageElement = document.createElement('div');

        const isMyMessage = window.currentUser && message.sender_id == window.currentUser.id;
        console.log('🔵 [CLIENT DEBUG] isMyMessage:', isMyMessage);
        console.log('🔵 [CLIENT DEBUG] currentUser:', window.currentUser);
        console.log('🔵 [CLIENT DEBUG] message.sender_id:', message.sender_id);
        
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
        
        if (this.chatUI.virtualizedChat) {
            this.chatUI.virtualizedChat.loadMoreBtn.style.display = 'none';
        }
        
        console.log('✅ [CLIENT DEBUG] ЛС добавлено в UI');
    }

    sendDM() {
        console.log('🔵 [CLIENT DEBUG] sendDM вызван');
        
        if (!this.currentDMRecipient) {
            console.error('🔴 [CLIENT DEBUG] Нет получателя для ЛС');
            return;
        }

        const messageInput = document.getElementById('message-input');
        const message = messageInput?.value.trim();
        
        console.log('🔵 [CLIENT DEBUG] Получатель:', this.currentDMRecipient);
        console.log('🔵 [CLIENT DEBUG] Сообщение:', message);

        if (message) {
            const dmData = {
                recipient_id: this.currentDMRecipient,
                message: message,
            };
            
            console.log('🔵 [CLIENT DEBUG] Отправляем send_dm с данными:', dmData);
            window.socket.emit('send_dm', dmData);

            this.addDMMessage({
                sender_id: window.currentUser?.id,
                sender_username: window.currentUser?.username || 'Вы',
                content: message,
                timestamp: new Date().toISOString(),
                is_local: true
            });

            messageInput.value = '';
        }
    }

    showDMNotification(message) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(`Новое сообщение от ${message.sender_username}`, {
                body: message.content,
            });
        }

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

    updateUnreadCount(senderId, username) {
        console.log('🔵 [CLIENT DEBUG] updateUnreadCount вызван для:', username, senderId);

        const conversation = document.querySelector(`.dm-conversation[data-user-id="${senderId}"]`);

        if (conversation) {
            conversation.classList.add('has-unread');

            // ИСПРАВЛЕНО: Простая логика обновления
            const badge = conversation.querySelector('.unread-badge');
            if (badge) {
                const currentCount = parseInt(badge.textContent) || 0;
                badge.textContent = currentCount + 1;
                console.log(`🔵 [CLIENT DEBUG] Обновлен badge: ${currentCount} -> ${currentCount + 1}`);
            } else {
                // Создаем новый badge
                const newBadge = document.createElement('span');
                newBadge.className = 'unread-badge';
                newBadge.textContent = '1';
                conversation.appendChild(newBadge);
                console.log('🔵 [CLIENT DEBUG] Создан новый badge: 1');
            }

            // ИСПРАВЛЕНО: Простое обновление счетчика
            this.totalUnreadCount += 1;
            this.updateTabIndicatorSimple();

            this.showDMNotification({
                sender_id: senderId,
                sender_username: username,
                content: 'Новое сообщение'
            });
        } else {
            console.log('🔵 [CLIENT DEBUG] Диалог не найден, загружаем список диалогов');
            this.pendingUnreadUpdate = { senderId, username };
            this.loadDMConversations();
        }
    }

    updateUnreadIndicator(senderId, username) {
        this.updateUnreadCount(senderId, username);
    }

    updateUnreadIndicatorsOnly(senderId) {
        console.log('🔵 [CLIENT DEBUG] Обновляем только индикаторы для отправителя:', senderId);
        
        // Находим диалог с этим пользователем
        const conversation = document.querySelector(`.dm-conversation[data-user-id="${senderId}"]`);
        
        if (conversation) {
            // Получаем количество непрочитанных сообщений до их удаления
            const badge = conversation.querySelector('.unread-badge');
            let unreadCount = 0;
            if (badge) {
                unreadCount = parseInt(badge.textContent) || 0;
                console.log(`🔵 [CLIENT DEBUG] Было непрочитанных сообщений: ${unreadCount}`);
            }
            
            // Убираем индикаторы непрочитанных
            conversation.classList.remove('has-unread');
            
            // Удаляем badge
            if (badge) badge.remove();
            
            // Удаляем unread-line
            const unreadLine = conversation.querySelector('.unread-line');
            if (unreadLine) unreadLine.remove();
            
            console.log('✅ [CLIENT DEBUG] Индикаторы обновлены для диалога с пользователем:', senderId);
            
            // ИСПРАВЛЕНО: Уменьшаем общий счетчик
            this.totalUnreadCount = Math.max(0, this.totalUnreadCount - unreadCount);
            console.log(`🔵 [CLIENT DEBUG] Общий счетчик уменьшен на ${unreadCount}, новый totalUnreadCount: ${this.totalUnreadCount}`);
            this.updateTabIndicatorSimple();
        } else {
            console.log('⚠️ [CLIENT DEBUG] Диалог не найден для пользователя:', senderId);
        }
    }
    
    recalculateTotalUnreadCount() {
        console.log('🔵 [CLIENT DEBUG] Пересчитываем общий счетчик непрочитанных');
        
        const conversations = document.querySelectorAll('.dm-conversation');
        let totalUnread = 0;
        
        conversations.forEach(conv => {
            const badge = conv.querySelector('.unread-badge');
            if (badge) {
                const count = parseInt(badge.textContent) || 0;
                totalUnread += count;
            }
        });
        
        this.totalUnreadCount = totalUnread;
        console.log(`🔵 [CLIENT DEBUG] Общий счетчик пересчитан: ${this.totalUnreadCount}`);
        
        this.updateTabIndicatorSimple();
    }
    
    updateTabIndicatorSimple() {
        console.log('🔵 [CLIENT DEBUG] updateTabIndicatorSimple вызван, totalUnreadCount:', this.totalUnreadCount);
        
        // Находим вкладку ЛС
        const dmTab = document.querySelector('.tab-btn[data-tab="dms"]');
        if (!dmTab) {
            console.warn('🔴 [CLIENT DEBUG] Вкладка ЛС не найдена');
            return;
        }
        
        // Находим или создаем индикатор непрочитанных
        let indicator = dmTab.querySelector('.unread-indicator');
        if (!indicator) {
            indicator = document.createElement('span');
            indicator.className = 'unread-indicator';
            indicator.style.cssText = `
                background: #dc3545;
                color: white;
                border-radius: 50%;
                padding: 2px 6px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 5px;
                min-width: 18px;
                text-align: center;
                display: inline-block;
            `;
            dmTab.appendChild(indicator);
            console.log('🔵 [CLIENT DEBUG] Создан новый индикатор непрочитанных');
        }
        
        // Обновляем содержимое индикатора
        if (this.totalUnreadCount > 0) {
            indicator.textContent = this.totalUnreadCount > 99 ? '99+' : this.totalUnreadCount.toString();
            indicator.style.display = 'inline-block';
            console.log(`🔵 [CLIENT DEBUG] Индикатор обновлен: ${indicator.textContent} (totalUnreadCount: ${this.totalUnreadCount})`);
        } else {
            indicator.style.display = 'none';
            console.log(`🔵 [CLIENT DEBUG] Индикатор скрыт (totalUnreadCount: ${this.totalUnreadCount})`);
        }
        
        // Добавляем визуальный эффект для новых сообщений
        if (this.totalUnreadCount > 0) {
            dmTab.style.position = 'relative';
            dmTab.style.animation = 'pulse 1s ease-in-out';
            
            // Убираем анимацию через 1 секунду
            setTimeout(() => {
                dmTab.style.animation = '';
            }, 1000);
        }
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DMHandler;
} else {
    window.DMHandler = DMHandler;
}
